"""Mycelium client for processing audio embeddings on GPU workers."""
import logging
import os
import socket
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, List, Dict

import requests
import torch

from mycelium.client_config import MyceliumClientConfig
from mycelium.client_config import get_client_config_file_path
from mycelium.infrastructure import CLAPEmbeddingGenerator

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

    def __init__(
            self,
            server_host: str = "localhost",
            server_port: int = 8000,
            model_id: str = "laion/larger_clap_music_and_speech",
            poll_interval: int = 5,
            download_queue_size: int = 15,
            download_workers: int = 10
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.server_url = f"http://{server_host}:{server_port}"
        self.model_id = model_id
        self.poll_interval = poll_interval
        self.download_queue_size = download_queue_size
        self.download_workers = download_workers
        self.config = MyceliumClientConfig.load_from_yaml()

        self.config_file_path = get_client_config_file_path()
        self.last_config_mtime = self._get_config_mtime()

        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.ip_address = self._get_local_ip()

        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        self.device = CLAPEmbeddingGenerator.get_best_device()

        self.job_queue: Queue[dict] = Queue(maxsize=download_queue_size * 2)
        self.download_queue: Queue[DownloadedJob] = Queue(maxsize=download_queue_size)

        self.job_fetcher_thread: Optional[threading.Thread] = None
        self.download_threads: List[threading.Thread] = []
        self.stop_event = threading.Event()

        self.clap_embedding_generator = CLAPEmbeddingGenerator(model_id=self.config.clap.model_id,
                                                               target_sr=self.config.clap.target_sr,
                                                               chunk_duration_s=self.config.clap.chunk_duration_s)

        logging.info("Mycelium Client initialized")
        logging.info(f"Worker ID: {self.worker_id}")
        logging.info(f"Server: {self.server_url}")
        logging.info(f"Device: {self.device}")
        logging.info(f"Download queue size: {download_queue_size}")
        logging.info(f"Parallel download workers: {download_workers}")

    def _log_queue_status(self, context: str = ""):
        """Log current queue status with context."""
        job_q_size = self.job_queue.qsize()
        dl_q_size = self.download_queue.qsize()
        dl_q_cap = self.download_queue.maxsize
        dl_q_percent = (dl_q_size / dl_q_cap) * 100 if dl_q_cap > 0 else 0

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

    # TODO: move this to clap adapter and also unload for the server side when app is closed
    def _unload_model(self):
        """Unload model to free GPU memory."""
        if self.clap_embedding_generator.model is not None:
            del self.clap_embedding_generator.model
            del self.clap_embedding_generator.processor
            self.clap_embedding_generator.model = None
            self.clap_embedding_generator.processor = None

            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()

            logging.info("Model unloaded")

    def reload_config(self):
        """Reload configuration and recreate CLAPEmbeddingGenerator."""
        try:
            logging.info("Reloading client configuration...")
            new_config = MyceliumClientConfig.load_from_yaml()

            clap_changed = (
                new_config.clap.model_id != self.config.clap.model_id or
                new_config.clap.target_sr != self.config.clap.target_sr or
                new_config.clap.chunk_duration_s != self.config.clap.chunk_duration_s
            )

            if clap_changed:
                logging.info("CLAP configuration changed, recreating embedding generator...")
                self._unload_model()
                self.clap_embedding_generator = CLAPEmbeddingGenerator(
                    model_id=new_config.clap.model_id,
                    target_sr=new_config.clap.target_sr,
                    chunk_duration_s=new_config.clap.chunk_duration_s
                )
                logging.info("CLAP embedding generator updated.")

            self.config = new_config
            logging.info("Client configuration reloaded successfully")
        except Exception as e:
            logging.error(f"Failed to reload client configuration: {e}", exc_info=True)


    def register_with_server(self) -> bool:
        """Register this worker with the server, retrying on failure."""
        delay_seconds = 3
        attempt = 1
        print("Attempting to register with server...")
        while not self.stop_event.is_set():
            try:
                response = requests.post(
                    f"{self.server_url}/workers/register",
                    json={"worker_id": self.worker_id, "ip_address": self.ip_address},
                    timeout=10
                )
                response.raise_for_status()
                print(f"Successfully registered with server (attempt {attempt})")
                return True
            except requests.exceptions.RequestException as e:
                print(f"Error registering with server (attempt {attempt}): {e}")

            time.sleep(delay_seconds)
            attempt += 1
        return False

    def get_job(self) -> Optional[dict]:
        """Get the next job from the server."""
        try:
            response = requests.get(
                f"{self.server_url}/workers/get_job",
                params={"worker_id": self.worker_id},
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
        """
        A single thread that requests jobs from the server and puts them in the job_queue.
        """
        logging.info("Job fetcher thread started")
        while not self.stop_event.is_set():
            try:
                if not self.job_queue.full():
                    job = self.get_job()
                    if job:
                        logging.info(f"Job fetcher: Got job {job['task_id']}, adding to download queue.")
                        self.job_queue.put(job)
                    else:
                        time.sleep(self.poll_interval)
                else:
                    logging.info("Job fetcher: Job queue is full, pausing.")
                    time.sleep(1)
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
                    logging.warning("Download queue is full. Waiting...")
                    self.job_queue.put(job)
                    time.sleep(1)
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

        for i in range(self.download_workers):
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

    def process_job(self, downloaded_job: DownloadedJob) -> bool:
        """Process a downloaded job."""
        task_id = downloaded_job.task_id
        track_id = downloaded_job.track_id
        original_job = downloaded_job.original_job
        task_type = original_job.get("task_type", "compute_audio_embedding")

        logging.info(f"Processing job {task_id} for track {track_id}, task_type: {task_type}")
        embedding = None
        error_message = None

        try:
            if task_type == "compute_audio_embedding":
                if downloaded_job.audio_file:
                    embedding = self.clap_embedding_generator.generate_embedding(filepath=downloaded_job.audio_file)
                    if not embedding:
                        error_message = "Failed to compute audio embedding"
                else:
                    error_message = "Audio file not available for processing"

            elif task_type == "compute_text_embedding":
                text_query = original_job.get("text_query")
                if text_query:
                    embedding = self.clap_embedding_generator.generate_text_embedding(text_query)
                    if not embedding:
                        error_message = "Failed to compute text embedding"
                else:
                    error_message = "Missing text query for text embedding task"
            else:
                error_message = f"Unknown task type: {task_type}"

            success = self.submit_result(task_id, track_id, embedding, error_message)
            if success:
                logging.info(f"Successfully processed and submitted job {task_id}")
            else:
                logging.warning(f"Failed to submit result for job {task_id}")

            return success

        finally:
            if downloaded_job.audio_file:
                try:
                    os.unlink(downloaded_job.audio_file)
                except OSError as e:
                    logging.error(f"Error deleting temp file {downloaded_job.audio_file}: {e}")

    def run(self):
        """Main worker loop."""
        logging.info("Starting Mycelium client worker loop...")

        if not self.register_with_server():
            logging.error("Failed to register with server. Exiting.")
            return

        self._start_workers()
        self._log_queue_status("worker started")

        last_status_log = time.time()
        status_log_interval = 30

        try:
            while True:
                try:
                    downloaded_job = self.download_queue.get(timeout=1)
                    self.process_job(downloaded_job)
                    self.download_queue.task_done()

                    if time.time() - last_status_log > status_log_interval:
                        self._log_queue_status("processing")
                        last_status_log = time.time()

                except Empty:
                    if self.stop_event.is_set():
                        break
                    if time.time() - last_status_log > status_log_interval:
                        self._log_queue_status("idle")
                        last_status_log = time.time()
                    self._check_config_reload()
                    continue

        except KeyboardInterrupt:
            logging.info("\nShutting down worker...")
        finally:
            self._log_queue_status("shutdown")
            self._stop_workers()
            self._unload_model()
            logging.info("Worker stopped")


def run_client(
        server_host: str = "localhost",
        server_port: int = 8000,
        model_id: str = "laion/larger_clap_music_and_speech",
        download_queue_size: int = 15,
        download_workers: int = 10
):
    """Run the Mycelium client."""
    client = MyceliumClient(
        server_host=server_host,
        server_port=server_port,
        model_id=model_id,
        download_queue_size=download_queue_size,
        download_workers=download_workers
    )
    client.run()