"""Mycelium client for processing audio embeddings on GPU workers."""
import gc
import logging
import os
import socket
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty, Full
from typing import Optional, List

import requests

from mycelium.application.embedding.registry import create_embedding_generator as create_from_registry
from mycelium.client_config import MyceliumClientConfig
from mycelium.client_config import get_client_config_file_path
from mycelium.client_status import worker_status
from mycelium.domain.repositories import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class DownloadedJob:
    """Represents a job with downloaded audio file."""
    task_id: str
    track_id: str
    original_job: dict
    audio_file: Optional[Path]


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

        self.job_fetcher_thread: Optional[threading.Thread] = None
        self.download_threads: List[threading.Thread] = []
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
                    json={"worker_id": self.worker_id, "ip_address": self.ip_address},
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
            response = requests.get(
                f"{self.server_url}/workers/get_job",
                params={"worker_id": self.worker_id, "ip_address": self.ip_address},
                timeout=30
            )
            response.raise_for_status()
            if response.status_code == 200 and response.text.strip():
                return response.json()
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error getting job from server: {e}")
            return None

    @staticmethod
    def download_audio_file(download_url: str) -> Optional[Path]:
        """Download audio file from server."""
        try:
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
            return Path(temp_file.name)
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading file from {download_url}: {e}")
            return None

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
                        logging.info(f"Job fetcher: Enqueued held job {held_job['task_id']}")
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
                            logging.info(f"Job fetcher: Got job {job['task_id']}, added to queue.")
                        except Full:
                            held_job = job
                            logging.info(f"Job fetcher: Queue full, holding job {job['task_id']}")
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
                    self.job_queue.task_done()
                    continue

                full_url = f"http://{self.server_host}:{self.server_port}{download_url}"
                logging.info(f"Downloading audio for job {task_id} from {full_url}")
                audio_file = self.download_audio_file(full_url)

                if audio_file:
                    downloaded_job = DownloadedJob(
                        task_id=task_id,
                        track_id=job["track_id"],
                        audio_file=audio_file,
                        original_job=job
                    )
                    self.download_queue.put(downloaded_job)
                    logging.info(f"Queued audio job {task_id} for processing.")
                else:
                    logging.error(f"Failed to download audio for job {task_id}. Job discarded.")

                self.job_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logging.error(f"Download worker error: {e}")

        logging.info("Download worker thread stopped")

    def _start_workers(self):
        """Start job fetcher and download worker threads."""
        self.stop_event.clear()

        self.job_fetcher_thread = threading.Thread(target=self._job_fetcher, daemon=True)
        self.job_fetcher_thread.start()

        for _ in range(self.download_workers):
            thread = threading.Thread(target=self._download_worker, daemon=True)
            thread.start()
            self.download_threads.append(thread)
        logging.info(f"Started 1 job fetcher and {self.download_workers} download workers.")

    def _stop_workers(self):
        """Stop all worker threads."""
        logging.info("Stopping all worker threads...")
        self.stop_event.set()

        if self.job_fetcher_thread:
            self.job_fetcher_thread.join(timeout=5)

        for thread in self.download_threads:
            thread.join(timeout=5)

        while not self.download_queue.empty():
            try:
                job = self.download_queue.get_nowait()
                if job.audio_file:
                    os.unlink(job.audio_file)
            except (Empty, OSError):
                break
        logging.info("All worker threads stopped.")


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
        self._process_audio_batch_gpu(audio_jobs)
    
    def _process_audio_batch_gpu(self, audio_jobs: List[DownloadedJob]) -> None:
        """Process audio jobs using GPU batch processing."""
        # Prepare batch data
        audio_files = []
        job_metadata = []
        
        for job in audio_jobs:
            if job.audio_file and job.audio_file.exists():
                audio_files.append(job.audio_file)
                job_metadata.append(job)
            else:
                # Handle jobs with missing files individually
                self.submit_result(job.task_id, job.track_id, None, "Audio file not available")
        
        if not audio_files:
            return
        
        try:
            # Generate embeddings in batch
            embeddings = self.embedding_generator.generate_embedding_batch(audio_files)
            
            # Submit results
            for job, embedding in zip(job_metadata, embeddings):
                success = self.submit_result(job.task_id, job.track_id, embedding, 
                                           None if embedding else "Failed to compute audio embedding")
                if success:
                    logging.debug(f"Successfully submitted batch job {job.task_id}")
                else:
                    logging.warning(f"Failed to submit batch job {job.task_id}")
                    
        except Exception as e:
            logging.error(f"Batch processing failed: {e}", exc_info=True)
        finally:
            # Clean up audio files
            for job in audio_jobs:
                if job.audio_file:
                    try:
                        os.unlink(job.audio_file)
                    except OSError as e:
                        logging.error(f"Error deleting temp file {job.audio_file}: {e}")
            
            # Force garbage collection after batch processing
            collected = gc.collect()
            if collected > 0:
                logging.debug(f"Post-batch cleanup: collected {collected} objects")
    
    def _process_text_batch(self, text_jobs: List[DownloadedJob]) -> None:
        """Process a batch of text embedding jobs."""
        if not self.embedding_generator.supports_text_search:
            # Model doesn't support text search — reject all jobs
            for job in text_jobs:
                self.submit_result(
                    job.task_id, job.track_id, None,
                    "Current embedding model does not support text search"
                )
            return
        self._process_text_batch_gpu(text_jobs)

    
    def _process_text_batch_gpu(self, text_jobs: List[DownloadedJob]) -> None:
        """Process text jobs using GPU batch processing."""
        # Prepare batch data
        text_queries = []
        job_metadata = []
        
        for job in text_jobs:
            text_query = job.original_job.get("text_query")
            if text_query:
                text_queries.append(text_query)
                job_metadata.append(job)
            else:
                # Handle jobs with missing text individually
                self.submit_result(job.task_id, job.track_id, None, "Missing text query")
        
        if not text_queries:
            return
        
        try:
            # Generate embeddings in batch
            embeddings = self.embedding_generator.generate_text_embedding_batch(text_queries)
            
            # Submit results
            for job, embedding in zip(job_metadata, embeddings):
                success = self.submit_result(job.task_id, job.track_id, embedding,
                                           None if embedding else "Failed to compute text embedding")
                if success:
                    logging.debug(f"Successfully submitted batch text job {job.task_id}")
                else:
                    logging.warning(f"Failed to submit batch text job {job.task_id}")
                    
        except Exception as e:
            logging.error(f"Text batch processing failed: {e}", exc_info=True)

    def run(self):
        """Main worker loop with batch processing for better GPU utilization."""
        logging.info("Starting Mycelium client worker loop...")

        if not self.register_with_server():
            logging.error("Failed to register with server. Exiting.")
            return

        self._start_workers()
        self._log_queue_status("worker started")

        last_status_log = time.time()
        status_log_interval = 30
        gpu_batch_size = self.config.client.gpu_batch_size

        try:
            while True:
                # Collect a batch of jobs for processing.
                # Use a short timeout so partial batches are processed
                # promptly (e.g. a single prioritised task isn't stuck
                # waiting for the batch to fill).
                batch = []
                batch_wait_deadline = time.time() + 2.0  # max 2s to fill
                while len(batch) < gpu_batch_size:
                    remaining = batch_wait_deadline - time.time()
                    if remaining <= 0:
                        break  # Don't wait forever — process what we have
                    try:
                        downloaded_job = self.download_queue.get(
                            timeout=min(remaining, 0.5)
                        )
                        batch.append(downloaded_job)
                    except Empty:
                        if self.stop_event.is_set():
                            break
                        # If we already have items, stop waiting and
                        # process the partial batch immediately.
                        if batch:
                            break
                        continue
                
                # Process the batch if we have any jobs
                if batch:
                    self._process_batch(batch)
                    
                    # Mark all jobs as done
                    for _ in batch:
                        self.download_queue.task_done()
                    
                    if time.time() - last_status_log > status_log_interval:
                        self._log_queue_status("processing")
                        last_status_log = time.time()
                        logging.info(f"Processed batch of {len(batch)} jobs")
                else:
                    # No jobs available
                    if self.stop_event.is_set():
                        break
                    if time.time() - last_status_log > status_log_interval:
                        self._log_queue_status("idle")
                        last_status_log = time.time()
                    self._check_config_reload()

        except KeyboardInterrupt:
            logging.info("\nShutting down worker...")
        finally:
            self._log_queue_status("shutdown")
            self._stop_workers()
            if self.embedding_generator is not None:
                self.embedding_generator.unload_model()
            worker_status.update(is_running=False, is_processing=False)
            logging.info("Worker stopped")


def run_client():
    """Run the Mycelium client."""
    client = MyceliumClient()
    client.run()