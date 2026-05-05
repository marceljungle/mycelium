"""Mycelium client for processing audio embeddings on GPU workers."""
import gc
import logging
import os
import platform
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue, Empty, Full
from typing import Optional, List

import numpy as np

import requests

from mycelium.application.embedding.registry import create_embedding_generator as create_from_registry
from mycelium.client_config import MyceliumClientConfig
from mycelium.client_config import get_client_config_file_path
from mycelium.client_status import worker_status
from mycelium.domain.repositories import EmbeddingGenerator

logger = logging.getLogger(__name__)

# Module-level reference so the client API can request a graceful stop.
_active_client: Optional["MyceliumClient"] = None


@dataclass
class DownloadedJob:
    """Represents a job with downloaded audio file."""
    task_id: str
    track_id: str
    original_job: dict
    audio_file: Optional[Path]


@dataclass
class PreprocessedBatch:
    """A batch of jobs with audio already loaded and chunked (ready for GPU).

    This is the output of the preprocessing pipeline — librosa work is done,
    numpy arrays are ready to go straight to the GPU.
    """
    audio_jobs: List[DownloadedJob] = field(default_factory=list)
    text_jobs: List[DownloadedJob] = field(default_factory=list)
    # Preprocessed audio data (from parallel librosa loading)
    all_chunks: List[np.ndarray] = field(default_factory=list)
    file_chunk_counts: List[int] = field(default_factory=list)
    preprocess_errors: dict = field(default_factory=dict)
    # Audio jobs that had valid files (matching order of chunks)
    valid_audio_jobs: List[DownloadedJob] = field(default_factory=list)


class MyceliumClient:
    """Client for processing CLAP embeddings on GPU hardware."""

    def __init__(self):
        # Load configuration
        self.config = MyceliumClientConfig.load_from_yaml()
        
        # Use config values for all settings
        self.server_host = self.config.client.server_host
        self.server_port = self.config.client.server_port
        self.server_url = f"http://{self.server_host}:{self.server_port}"
        self.poll_interval = self.config.client.poll_interval
        self.download_queue_size = self.config.client.download_queue_size
        self.download_workers = self.config.client.download_workers

        self.config_file_path = get_client_config_file_path()
        self.last_config_mtime = self._get_config_mtime()

        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.ip_address = self._get_local_ip()

        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        self.device = EmbeddingGenerator.get_best_device()

        self.job_queue: Queue[dict] = Queue(maxsize=self.config.client.job_queue_size)
        self.download_queue: Queue[DownloadedJob] = Queue(maxsize=self.download_queue_size)
        # GPU-ready queue: holds PreprocessedBatch objects (librosa already done)
        self.gpu_ready_queue: Queue[PreprocessedBatch] = Queue(maxsize=2)

        self.job_fetcher_thread: Optional[threading.Thread] = None
        self.download_threads: List[threading.Thread] = []
        self.preprocessor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Embedding generator is created after registration once the server
        # tells us which model to use.
        self.embedding_generator: Optional[EmbeddingGenerator] = None
        self._server_embedding_config: Optional[dict] = None

        # Publish initial status
        worker_status.update(
            worker_id=self.worker_id,
            server_url=self.server_url,
            is_running=True,
        )

        logging.info("Mycelium Client initialized")
        logging.info(f"Worker ID: {self.worker_id}")
        logging.info(f"Server: {self.server_url}")
        logging.info(f"Device: {self.device}")
        logging.info(f"Download queue size: {self.download_queue_size}")
        logging.info(f"Job queue size: {self.config.client.job_queue_size}")
        logging.info(f"Poll interval: {self.poll_interval}s")
        logging.info(f"Parallel download workers: {self.download_workers}")

        self.gpu_name = self._detect_gpu_name()
        logging.info(f"GPU: {self.gpu_name}")

        # Throughput tracking (rolling window)
        self._throughput_history: list = []  # list of (timestamp, job_count)

    def _compute_jobs_per_minute(self, new_jobs: int) -> float:
        """Compute rolling jobs/minute over the last 60 seconds."""
        now = time.time()
        self._throughput_history.append((now, new_jobs))
        # Prune entries older than 60s
        cutoff = now - 60.0
        self._throughput_history = [
            (t, n) for t, n in self._throughput_history if t >= cutoff
        ]
        total = sum(n for _, n in self._throughput_history)
        window = now - self._throughput_history[0][0] if len(self._throughput_history) > 1 else 60.0
        if window < 1.0:
            window = 60.0
        return round(total * 60.0 / window, 1)

    @staticmethod
    def _detect_gpu_name() -> str:
        """Detect the GPU/accelerator name for this worker."""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.get_device_name(0)
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # Apple Silicon — get chip name from sysctl
                try:
                    chip = subprocess.check_output(
                        ["sysctl", "-n", "machdep.cpu.brand_string"],
                        text=True, timeout=5,
                    ).strip()
                    return chip or "Apple Silicon"
                except Exception:
                    return "Apple Silicon"
        except ImportError:
            pass
        return "CPU"

    def _log_queue_status(self, context: str = ""):
        """Log current queue status with context."""
        job_q_size = self.job_queue.qsize()
        dl_q_size = self.download_queue.qsize()
        dl_q_cap = self.download_queue.maxsize
        dl_q_percent = (dl_q_size / dl_q_cap) * 100 if dl_q_cap > 0 else 0

        # Publish queue sizes to shared status
        worker_status.update(
            jobs_in_download_queue=job_q_size,
            jobs_ready_for_gpu=dl_q_size,
        )

        status_msg = (
            f"Queue status ({context}): "
            f"Jobs to download: {job_q_size}, "
            f"Jobs ready for GPU: {dl_q_size}/{dl_q_cap} ({dl_q_percent:.1f}%)"
        )
        logging.info(status_msg)

    @staticmethod
    def _get_local_ip() -> str:
        """Get the local IP address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _get_config_mtime(self) -> float:
        """Get the modification time of the config file."""
        try:
            if self.config_file_path.exists():
                return self.config_file_path.stat().st_mtime
        except Exception:
            pass
        return 0.0

    def _check_config_reload(self) -> None:
        """Check if config file has been modified and reload if necessary."""
        try:
            current_mtime = self._get_config_mtime()
            if current_mtime > self.last_config_mtime:
                logging.info("Config file modification detected, reloading...")
                self.reload_config()
                self.last_config_mtime = current_mtime
        except Exception as e:
            logging.error(f"Error checking config reload: {e}")

    def reload_config(self):
        """Reload configuration and apply changes that can be hot-reloaded."""
        try:
            logging.info("Reloading client configuration...")
            new_config = MyceliumClientConfig.load_from_yaml()

            # Apply server connection changes (hot-reloadable)
            if (new_config.client.server_host != self.config.client.server_host or
                    new_config.client.server_port != self.config.client.server_port):
                old_url = self.server_url
                self.server_host = new_config.client.server_host
                self.server_port = new_config.client.server_port
                self.server_url = f"http://{self.server_host}:{self.server_port}"
                logging.info(f"Server URL updated: {old_url} -> {self.server_url}")
                worker_status.update(server_url=self.server_url)

            # Log changes that still require restart
            if new_config.client.download_workers != self.config.client.download_workers:
                logging.warning(f"Download workers changed: {self.config.client.download_workers} -> {new_config.client.download_workers} (requires restart)")
            if new_config.client.download_queue_size != self.config.client.download_queue_size:
                logging.warning(f"Download queue size changed: {self.config.client.download_queue_size} -> {new_config.client.download_queue_size} (requires restart)")
            if new_config.client.job_queue_size != self.config.client.job_queue_size:
                logging.warning(f"Job queue size changed: {self.config.client.job_queue_size} -> {new_config.client.job_queue_size} (requires restart)")

            # Apply hot-reloadable changes
            self.poll_interval = new_config.client.poll_interval
            if new_config.client.poll_interval != self.config.client.poll_interval:
                logging.info(f"Poll interval updated: {self.config.client.poll_interval}s -> {new_config.client.poll_interval}s")
            
            # GPU batch settings can be hot-reloaded
            if new_config.client.gpu_batch_size != self.config.client.gpu_batch_size:
                logging.info(f"GPU batch size updated: {self.config.client.gpu_batch_size} -> {new_config.client.gpu_batch_size}")

            self.config = new_config
            logging.info("Client configuration reloaded successfully")
        except Exception as e:
            logging.error(f"Failed to reload client configuration: {e}", exc_info=True)


    def register_with_server(self) -> bool:
        """Register this worker with the server, retrying on failure.

        On success the server returns the embedding model configuration which
        is used to create (or recreate) the local embedding generator so the
        client always uses the same model as the server.
        """
        delay_seconds = 3
        attempt = 1
        print("Attempting to register with server...")
        while not self.stop_event.is_set():
            # Pick up config changes (e.g. new server host) between retries
            self._check_config_reload()

            try:
                response = requests.post(
                    f"{self.server_url}/workers/register",
                    json={
                        "worker_id": self.worker_id,
                        "ip_address": self.ip_address,
                        "gpu_name": self.gpu_name,
                    },
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

                # Apply the server-provided embedding config
                embedding_cfg = data.get("embedding_config", {})
                self._apply_server_embedding_config(embedding_cfg)

                print(f"Successfully registered with server at {self.server_url} (attempt {attempt})")
                return True
            except requests.exceptions.RequestException as e:
                print(f"Error registering with server at {self.server_url} (attempt {attempt}): {e}")

            time.sleep(delay_seconds)
            attempt += 1
        return False

    def _apply_server_embedding_config(self, embedding_cfg: dict) -> None:
        """Create or recreate the embedding generator from server-provided config."""
        model_type = embedding_cfg.pop("type", None)
        if not model_type:
            logging.error("Server registration response missing embedding model type")
            return

        # Only recreate if the config actually changed
        if embedding_cfg == self._server_embedding_config and self.embedding_generator is not None:
            logging.info("Server embedding config unchanged, keeping current generator.")
            return

        logging.info(
            f"Server assigned model: type={model_type}, config={embedding_cfg}"
        )

        if self.embedding_generator is not None:
            self.embedding_generator.unload_model()

        # Client-local micro_batch_size overrides the server value
        client_micro_batch = self.config.client.micro_batch_size
        embedding_cfg["micro_batch_size"] = client_micro_batch

        self.embedding_generator = create_from_registry(
            model_type=model_type,
            config_overrides=embedding_cfg,
        )
        self._server_embedding_config = embedding_cfg

        worker_status.update(
            model_type=model_type,
            model_id=embedding_cfg.get("model_id", ""),
            micro_batch_size=embedding_cfg.get("micro_batch_size"),
        )

    def get_job(self) -> Optional[dict]:
        """Get the next job from the server."""
        try:
            params = {"worker_id": self.worker_id, "ip_address": self.ip_address}
            if self.gpu_name:
                params["gpu_name"] = self.gpu_name
            response = requests.get(
                f"{self.server_url}/workers/get_job",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            if response.status_code == 200 and response.text.strip():
                return response.json()
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error getting job from server: {e}")
            return None

    MAX_DOWNLOAD_SIZE_MB = 500  # Skip files larger than this

    @staticmethod
    def download_audio_file(download_url: str) -> tuple[Optional[Path], Optional[str]]:
        """Download audio file from server.

        Returns:
            Tuple of (file_path, error_message). On success error_message
            is ``None``; on failure file_path is ``None``.
        """
        try:
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            # Check Content-Length before downloading
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > MyceliumClient.MAX_DOWNLOAD_SIZE_MB:
                    response.close()
                    msg = f"File too large ({size_mb:.0f}MB > {MyceliumClient.MAX_DOWNLOAD_SIZE_MB}MB limit), skipping"
                    logging.warning(f"Skipping download {download_url}: {msg}")
                    return None, msg

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
            bytes_written = 0
            max_bytes = MyceliumClient.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
            for chunk in response.iter_content(chunk_size=8192):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    temp_file.close()
                    os.unlink(temp_file.name)
                    msg = f"File exceeded {MyceliumClient.MAX_DOWNLOAD_SIZE_MB}MB during download, skipping"
                    logging.warning(f"Aborted download {download_url}: {msg}")
                    return None, msg
                temp_file.write(chunk)
            temp_file.close()
            return Path(temp_file.name), None
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            detail = ""
            if e.response is not None:
                try:
                    detail = e.response.json().get("detail", "")
                except Exception:
                    detail = e.response.text[:200] if e.response.text else ""
            msg = f"HTTP {status}: {detail}" if detail else f"HTTP {status}"
            logging.error(f"Download failed for {download_url}: {msg}")
            return None, msg
        except requests.exceptions.Timeout:
            logging.error(f"Timeout downloading {download_url}")
            return None, "Download timeout"
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error downloading {download_url}: {e}")
            return None, "Connection error"
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading file from {download_url}: {e}")
            return None, f"Download error: {e}"
        except OSError as e:
            # Clean up partial temp file on disk errors (ENOSPC, quota, etc.)
            try:
                if 'temp_file' in locals():
                    temp_file.close()
                    os.unlink(temp_file.name)
            except Exception:
                pass
            raise  # Let caller handle retry logic

    def _job_fetcher(self):
        """Thread that requests jobs from the server and puts them in the job_queue.

        Every call to ``get_job()`` also acts as a heartbeat — the server
        marks the worker as active on each request.  If this thread stops
        calling ``get_job()`` the server will eventually expire the worker,
        so we must *always* call it, even when the local queue is full.
        """
        logging.info("Job fetcher thread started")
        held_job: Optional[dict] = None  # Job waiting for queue space
        while not self.stop_event.is_set():
            try:
                # Pick up config changes (e.g. new server host) promptly
                self._check_config_reload()

                # If we're holding a job from a previous iteration, try
                # to enqueue it before requesting more work.
                if held_job is not None:
                    try:
                        self.job_queue.put(held_job, block=False)
                        logging.debug(f"Job fetcher: Enqueued held job {held_job['task_id']}")
                        held_job = None
                    except Full:
                        pass  # Still full — will heartbeat below and retry next loop

                # Always call get_job so the server receives a heartbeat.
                # Only request new work if we have capacity.
                if held_job is None:
                    job = self.get_job()
                    if job:
                        try:
                            self.job_queue.put_nowait(job)
                            logging.debug(f"Job fetcher: Got job {job['task_id']}, added to queue.")
                        except Full:
                            held_job = job
                            logging.debug(f"Job fetcher: Queue full, holding job {job['task_id']}")
                    else:
                        time.sleep(self.poll_interval)
                else:
                    # We're holding a job and can't take more. Still
                    # heartbeat the server by calling get_job, but
                    # discard the result (the server will re-queue it).
                    self.get_job()
                    time.sleep(min(self.poll_interval, 3))
            except Exception as e:
                logging.error(f"Job fetcher error: {e}")
                time.sleep(self.poll_interval)
        logging.info("Job fetcher thread stopped")

    def _download_worker(self):
        """
        Takes jobs from the job_queue, downloads the audio, and puts them in the download_queue.
        """
        logging.info("Download worker thread started")
        while not self.stop_event.is_set():
            try:
                job = self.job_queue.get(timeout=1)

                if self.download_queue.full():
                    self.job_queue.put(job)
                    time.sleep(5)
                    continue

                task_id = job["task_id"]
                task_type = job.get("task_type", "compute_audio_embedding")

                if task_type == "compute_text_embedding":
                    downloaded_job = DownloadedJob(
                        task_id=task_id,
                        track_id=job["track_id"],
                        audio_file=None,
                        original_job=job
                    )
                    self.download_queue.put(downloaded_job)
                    logging.info(f"Queued text search job {task_id} for processing.")
                    self.job_queue.task_done()
                    continue

                download_url = job.get("download_url")
                if not download_url:
                    logging.error(f"Job {task_id} is missing download_url.")
                    self.submit_result(task_id, job.get("track_id", ""), None, "Job missing download URL")
                    self.job_queue.task_done()
                    continue

                full_url = f"http://{self.server_host}:{self.server_port}{download_url}"
                logging.debug(f"Downloading audio for job {task_id} from {full_url}")
                worker_status.update(active_downloads=worker_status.active_downloads + 1)
                audio_file, dl_error = self.download_audio_file(full_url)
                worker_status.update(active_downloads=max(0, worker_status.active_downloads - 1))

                if audio_file:
                    downloaded_job = DownloadedJob(
                        task_id=task_id,
                        track_id=job["track_id"],
                        audio_file=audio_file,
                        original_job=job
                    )
                    self.download_queue.put(downloaded_job)
                    logging.debug(f"Queued audio job {task_id} for processing.")
                else:
                    logging.error(f"Failed to download audio for job {task_id}: {dl_error}")
                    self.submit_result(task_id, job.get("track_id", ""), None, dl_error or "Failed to download audio file")

                self.job_queue.task_done()

            except Empty:
                continue
            except OSError as e:
                import errno as errno_mod
                if e.errno in (errno_mod.ENOSPC, 122):  # Disk full / quota exceeded
                    logging.warning(f"Download worker: disk full (errno {e.errno}), re-queuing job and waiting for space...")
                    try:
                        self.job_queue.put(job)
                    except Exception:
                        pass
                    # Back off — GPU is processing and deleting files, space will free up
                    for _ in range(30):  # wait up to 30s, checking stop_event
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                else:
                    logging.error(f"Download worker OS error: {e}")
            except Exception as e:
                logging.error(f"Download worker error: {e}")

        logging.info("Download worker thread stopped")

    def _start_workers(self):
        """Start job fetcher, download workers, and preprocessor thread."""
        self.stop_event.clear()

        self.job_fetcher_thread = threading.Thread(target=self._job_fetcher, daemon=True)
        self.job_fetcher_thread.start()

        for _ in range(self.download_workers):
            thread = threading.Thread(target=self._download_worker, daemon=True)
            thread.start()
            self.download_threads.append(thread)

        self.preprocessor_thread = threading.Thread(
            target=self._preprocessor_worker, daemon=True
        )
        self.preprocessor_thread.start()
        logging.info(
            f"Started 1 job fetcher, {self.download_workers} download workers, "
            f"1 preprocessor thread."
        )

    def _stop_workers(self):
        """Stop all worker threads."""
        logging.info("Stopping all worker threads...")
        self.stop_event.set()

        if self.job_fetcher_thread:
            self.job_fetcher_thread.join(timeout=5)

        for thread in self.download_threads:
            thread.join(timeout=5)

        if self.preprocessor_thread:
            self.preprocessor_thread.join(timeout=10)

        while not self.download_queue.empty():
            try:
                job = self.download_queue.get_nowait()
                if job.audio_file:
                    os.unlink(job.audio_file)
            except (Empty, OSError):
                break
        logging.info("All worker threads stopped.")

    def request_graceful_stop(self) -> None:
        """Signal the worker to stop after finishing its current queue.

        The job fetcher stops requesting new work immediately.
        The main loop drains remaining items from the download queue,
        processes them, and then exits.
        """
        if self.stop_event.is_set():
            logging.info("Graceful stop already requested.")
            return
        logging.info("Graceful stop requested — finishing queued work…")
        self.stop_event.set()
        worker_status.update(is_stopping=True)

    def submit_result(self, task_id: str, track_id: str, embedding: Optional[List[float]],
                      error_message: Optional[str] = None) -> bool:
        """Submit task result to server."""
        try:
            status = "success" if (embedding is not None) else "failed"
            response = requests.post(
                f"{self.server_url}/workers/submit_result",
                json={
                    "task_id": task_id,
                    "track_id": track_id,
                    "status": status,
                    "embedding": embedding,
                    "error_message": error_message
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("success", False)
        except requests.exceptions.RequestException as e:
            logging.error(f"Error submitting result for task {task_id}: {e}")
            return False

    def _preprocessor_worker(self):
        """Background thread: collects batches from download_queue, runs parallel
        librosa loading, and puts PreprocessedBatch on gpu_ready_queue.

        This ensures the GPU never waits for CPU-bound audio decoding/resampling.
        Uses a short initial wait then drains immediately — starts librosa ASAP
        rather than waiting for a full batch, since parallel librosa is fast enough
        that partial batches still keep the GPU fed.
        """
        gpu_batch_size = self.config.client.gpu_batch_size
        logging.info("Preprocessor worker started")

        while not self.stop_event.is_set() or not self.download_queue.empty():
            # Collect a batch — short initial wait, then drain what's available
            batch: List[DownloadedJob] = []

            # Wait for at least 1 item (or stop signal)
            try:
                first = self.download_queue.get(timeout=1.0)
                batch.append(first)
            except Empty:
                if self.stop_event.is_set():
                    break
                continue

            # Drain up to gpu_batch_size without blocking (grab what's ready NOW)
            while len(batch) < gpu_batch_size:
                try:
                    batch.append(self.download_queue.get_nowait())
                except Empty:
                    break

            try:
                self._preprocess_batch(batch, gpu_batch_size)
            except Exception as e:
                logging.error(f"Preprocessor: batch failed, discarding {len(batch)} jobs: {e}", exc_info=True)
                # Clean up temp files and report errors
                for job in batch:
                    if job.audio_file:
                        try:
                            os.unlink(job.audio_file)
                        except OSError:
                            pass
                    self.submit_result(job.task_id, job.track_id, None, f"Preprocessor error: {e}")
                # Small backoff to avoid tight error loops
                time.sleep(2.0)
            finally:
                for _ in batch:
                    self.download_queue.task_done()

        logging.info("Preprocessor worker stopped")

    def _preprocess_batch(self, batch: List[DownloadedJob], gpu_batch_size: int) -> None:
        """Process a single batch in the preprocessor thread."""
        logging.info(
            f"Preprocessor: collected {len(batch)} jobs "
            f"(download_queue remaining: ~{self.download_queue.qsize()})"
        )

        # Separate audio from text jobs
        audio_jobs: List[DownloadedJob] = []
        text_jobs: List[DownloadedJob] = []
        for job in batch:
            task_type = job.original_job.get("task_type", "compute_audio_embedding")
            if task_type == "compute_audio_embedding":
                audio_jobs.append(job)
            elif task_type == "compute_text_embedding":
                text_jobs.append(job)

        preprocessed = PreprocessedBatch(
            audio_jobs=audio_jobs,
            text_jobs=text_jobs,
        )

        # Pre-load and chunk audio files in parallel (the expensive part)
        if audio_jobs and self.embedding_generator is not None:
            valid_jobs: List[DownloadedJob] = []
            filepaths: List[Path] = []
            for job in audio_jobs:
                if job.audio_file and job.audio_file.exists():
                    filepaths.append(job.audio_file)
                    valid_jobs.append(job)
                else:
                    self.submit_result(
                        job.task_id, job.track_id, None,
                        "Audio file not available"
                    )

            if filepaths:
                preprocess_start = time.time()
                worker_status.update(
                    is_preprocessing=True,
                    preprocessing_files=len(filepaths),
                )
                all_chunks, file_chunk_counts, errors = (
                    self.embedding_generator.preprocess_files(
                        filepaths,
                        max_workers=self.config.client.preprocessing_workers,
                    )
                )
                preprocess_elapsed = time.time() - preprocess_start
                worker_status.update(
                    is_preprocessing=False,
                    preprocessing_files=0,
                    last_preprocess_duration=round(preprocess_elapsed, 2),
                )
                logging.info(
                    f"Preprocessor: librosa done for {len(filepaths)} files "
                    f"({len(all_chunks)} chunks) in {preprocess_elapsed:.2f}s"
                )
                preprocessed.all_chunks = all_chunks
                preprocessed.file_chunk_counts = file_chunk_counts
                preprocessed.preprocess_errors = errors
                preprocessed.valid_audio_jobs = valid_jobs

        # Put on GPU-ready queue (blocks if GPU is busy with previous batch)
        while not self.stop_event.is_set():
            try:
                self.gpu_ready_queue.put(preprocessed, timeout=1.0)
                break
            except Full:
                continue

    def _process_batch(self, batch: List[DownloadedJob]) -> None:
        """Process a batch of jobs to improve GPU utilization."""
        if not batch:
            return

        worker_status.update(is_processing=True, current_batch_size=len(batch))
        logging.info(f"Processing batch of {len(batch)} jobs")
        
        # Separate jobs by type for more efficient batching
        audio_jobs = []
        text_jobs = []
        
        for job in batch:
            task_type = job.original_job.get("task_type", "compute_audio_embedding")
            if task_type == "compute_audio_embedding":
                audio_jobs.append(job)
            elif task_type == "compute_text_embedding":
                text_jobs.append(job)
        
        # Process audio jobs in batch
        if audio_jobs:
            self._process_audio_batch(audio_jobs)
        
        # Process text jobs in batch  
        if text_jobs:
            self._process_text_batch(text_jobs)

        worker_status.update(
            is_processing=False,
            current_batch_size=0,
            total_jobs_processed=worker_status.total_jobs_processed + len(batch),
            last_job_completed_at=time.time(),
        )
    
    def _process_audio_batch(self, audio_jobs: List[DownloadedJob]) -> None:
        """Process a batch of audio embedding jobs."""
        # Prepare: filter valid jobs, extract file paths
        inputs = []
        valid_jobs = []
        for job in audio_jobs:
            if job.audio_file and job.audio_file.exists():
                inputs.append(job.audio_file)
                valid_jobs.append(job)
            else:
                self.submit_result(job.task_id, job.track_id, None, "Audio file not available")

        if not inputs:
            return

        self._generate_and_submit(
            inputs,
            valid_jobs,
            self.embedding_generator.generate_embedding_batch,
            batch_type="audio",
        )

        # Clean up downloaded audio files
        for job in audio_jobs:
            if job.audio_file:
                try:
                    os.unlink(job.audio_file)
                except OSError as e:
                    logging.error(f"Error deleting temp file {job.audio_file}: {e}")

        collected = gc.collect()
        if collected > 0:
            logging.debug(f"Post-batch cleanup: collected {collected} objects")
    
    def _process_text_batch(self, text_jobs: List[DownloadedJob]) -> None:
        """Process a batch of text embedding jobs."""
        if not self.embedding_generator.supports_text_search:
            for job in text_jobs:
                self.submit_result(
                    job.task_id, job.track_id, None,
                    "Current embedding model does not support text search"
                )
            return

        inputs = []
        valid_jobs = []
        for job in text_jobs:
            text_query = job.original_job.get("text_query")
            if text_query:
                inputs.append(text_query)
                valid_jobs.append(job)
            else:
                self.submit_result(job.task_id, job.track_id, None, "Missing text query")

        if not inputs:
            return

        self._generate_and_submit(
            inputs,
            valid_jobs,
            self.embedding_generator.generate_text_embedding_batch,
            batch_type="text",
        )

    def _generate_and_submit(
        self,
        inputs: list,
        jobs: List[DownloadedJob],
        generate_fn,
        batch_type: str,
    ) -> None:
        """Generate embeddings in batch and submit each result to the server."""
        try:
            embeddings = generate_fn(inputs)
            # Retrieve per-file error reasons if available
            batch_errors: dict[int, str] = {}
            if hasattr(self.embedding_generator, "last_batch_errors"):
                batch_errors = self.embedding_generator.last_batch_errors

            for idx, (job, embedding) in enumerate(zip(jobs, embeddings)):
                if embedding:
                    msg = None
                else:
                    msg = batch_errors.get(idx, f"Failed to compute {batch_type} embedding")
                success = self.submit_result(job.task_id, job.track_id, embedding, msg)
                if success:
                    logging.debug(f"Submitted {batch_type} job {job.task_id}")
                else:
                    logging.warning(f"Failed to submit {batch_type} job {job.task_id}")
        except Exception as e:
            logging.error(f"{batch_type.title()} batch processing failed: {e}", exc_info=True)
            for job in jobs:
                self.submit_result(job.task_id, job.track_id, None, f"{batch_type.title()} batch failed: {e}")

    def _process_preprocessed_batch(self, preprocessed: PreprocessedBatch) -> None:
        """Process a PreprocessedBatch — audio chunks are already loaded, just run GPU.

        This is the fast path: no librosa work here, only GPU inference + submit.
        """
        total_jobs = len(preprocessed.audio_jobs) + len(preprocessed.text_jobs)
        worker_status.update(is_processing=True, current_batch_size=total_jobs)

        # --- Audio: chunks are pre-loaded, run GPU inference directly ---
        if preprocessed.all_chunks and preprocessed.valid_audio_jobs:
            try:
                self.embedding_generator._load_model_if_needed()
                self.embedding_generator._smoke_test_dtype()

                # Micro-batched forward passes (GPU only)
                import torch
                gpu_start = time.time()
                worker_status.update(
                    is_gpu_busy=True,
                    gpu_batch_chunks=len(preprocessed.all_chunks),
                )
                embeddings_list: list = []
                micro_bs = self.embedding_generator.micro_batch_size
                for i in range(0, len(preprocessed.all_chunks), micro_bs):
                    batch_chunks = preprocessed.all_chunks[i : i + micro_bs]
                    embeddings_list.append(
                        self.embedding_generator._forward_chunks(batch_chunks)
                    )
                    self.embedding_generator._clear_device_cache()

                chunk_embeddings = torch.cat(embeddings_list, dim=0)

                # Aggregate per file
                idx = 0
                for file_idx, count in enumerate(preprocessed.file_chunk_counts):
                    job = preprocessed.valid_audio_jobs[file_idx]
                    if count == 0:
                        error_msg = preprocessed.preprocess_errors.get(
                            file_idx,
                            "Failed to compute audio embedding"
                        )
                        self.submit_result(job.task_id, job.track_id, None, error_msg)
                    else:
                        mean = chunk_embeddings[idx : idx + count].mean(dim=0)
                        normed = torch.nn.functional.normalize(mean, p=2, dim=0)
                        embedding = normed.numpy().tolist()
                        self.submit_result(job.task_id, job.track_id, embedding)
                        idx += count

                logging.info(
                    f"GPU processed {len(preprocessed.valid_audio_jobs)} audio files "
                    f"({len(preprocessed.all_chunks)} chunks) in {time.time() - gpu_start:.2f}s"
                )
                worker_status.update(
                    is_gpu_busy=False,
                    gpu_batch_chunks=0,
                    last_gpu_duration=round(time.time() - gpu_start, 2),
                )
            except Exception as e:
                logging.error(f"Audio batch GPU processing failed: {e}", exc_info=True)
                for job in preprocessed.valid_audio_jobs:
                    self.submit_result(
                        job.task_id, job.track_id, None,
                        f"Audio batch failed: {e}"
                    )
        elif preprocessed.audio_jobs and not preprocessed.all_chunks:
            # All audio jobs had preprocess errors — already submitted in preprocessor
            # Handle jobs with file_chunk_counts==0 from preprocess_errors
            for file_idx, job in enumerate(preprocessed.valid_audio_jobs):
                if preprocessed.file_chunk_counts[file_idx] == 0:
                    error_msg = preprocessed.preprocess_errors.get(
                        file_idx, "Failed to load audio"
                    )
                    self.submit_result(job.task_id, job.track_id, None, error_msg)

        # --- Text jobs: no preprocessing needed, process normally ---
        if preprocessed.text_jobs:
            self._process_text_batch(preprocessed.text_jobs)

        # --- Cleanup audio files ---
        for job in preprocessed.audio_jobs:
            if job.audio_file:
                try:
                    os.unlink(job.audio_file)
                except OSError:
                    pass

        collected = gc.collect()
        if collected > 0:
            logging.debug(f"Post-batch cleanup: collected {collected} objects")

        worker_status.update(
            is_processing=False,
            current_batch_size=0,
            total_jobs_processed=worker_status.total_jobs_processed + total_jobs,
            last_job_completed_at=time.time(),
            jobs_per_minute=self._compute_jobs_per_minute(total_jobs),
        )

    def run(self):
        """Main worker loop — consumes preprocessed batches from gpu_ready_queue.

        The pipeline is:
          download_queue -> [preprocessor thread: parallel librosa] -> gpu_ready_queue -> [this loop: GPU]

        This double-buffering ensures the GPU never idles waiting for CPU work.
        """
        logging.info("Starting Mycelium client worker loop...")

        if not self.register_with_server():
            logging.error("Failed to register with server. Exiting.")
            return

        self._start_workers()
        worker_status.update(pipeline_started_at=time.time())
        self._log_queue_status("worker started")

        last_status_log = time.time()
        status_log_interval = 30

        try:
            while True:
                # Consume preprocessed batches from the GPU-ready queue.
                # The preprocessor thread handles batch assembly + librosa in parallel.
                try:
                    preprocessed = self.gpu_ready_queue.get(timeout=1.0)
                except Empty:
                    if self.stop_event.is_set() and self.gpu_ready_queue.empty():
                        break
                    if time.time() - last_status_log > status_log_interval:
                        self._log_queue_status("idle")
                        last_status_log = time.time()
                    self._check_config_reload()
                    continue

                # GPU inference (fast — audio is already decoded/chunked)
                self._process_preprocessed_batch(preprocessed)

                if time.time() - last_status_log > status_log_interval:
                    self._log_queue_status("processing")
                    last_status_log = time.time()

        except KeyboardInterrupt:
            logging.info("\nShutting down worker...")
        finally:
            self._log_queue_status("shutdown")
            self._stop_workers()
            if self.embedding_generator is not None:
                self.embedding_generator.unload_model()
            worker_status.update(is_running=False, is_processing=False, is_stopping=False)
            logging.info("Worker stopped")


def stop_client() -> bool:
    """Request a graceful stop of the active client (if any).

    Returns True if a running client was told to stop.
    """
    if _active_client is not None:
        _active_client.request_graceful_stop()
        return True
    return False


def run_client():
    """Run the Mycelium client."""
    global _active_client
    client = MyceliumClient()
    _active_client = client
    try:
        client.run()
    finally:
        _active_client = None