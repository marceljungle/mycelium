"""Mycelium client for processing audio embeddings on GPU workers."""
import base64
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

from mycelium.infrastructure import CLAPEmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class DownloadedJob:
    """Represents a job with downloaded audio file."""
    task_id: str
    track_id: str
    audio_file: Path
    original_job: dict


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
        self.download_workers = download_workers  # Number of parallel download threads

        # Generate unique worker ID
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.ip_address = self._get_local_ip()

        self.device = CLAPEmbeddingGenerator().get_best_device()

        # Download queue management
        self.download_queue: Queue[DownloadedJob] = Queue(maxsize=download_queue_size)
        self.pending_downloads: Dict[str, threading.Event] = {}
        self.download_threads: List[threading.Thread] = []  # Multiple download threads
        self.stop_download_thread = threading.Event()

        self.clap_embedding_generator = CLAPEmbeddingGenerator()

        logging.info(f"Mycelium Client initialized")
        logging.info(f"Worker ID: {self.worker_id}")
        logging.info(f"Server: {self.server_url}")
        logging.info(f"Device: {self.device}")
        logging.info(f"Download queue size: {download_queue_size}")
        logging.info(f"Parallel download workers: {download_workers}")

    def _log_queue_status(self, context: str = ""):
        """Log current queue status with context."""
        queue_size = self.download_queue.qsize()
        queue_capacity = self.download_queue.maxsize
        queue_percent = (queue_size / queue_capacity) * 100 if queue_capacity > 0 else 0

        status_msg = f"Queue status{' (' + context + ')' if context else ''}: {queue_size}/{queue_capacity} jobs ({queue_percent:.1f}% full)"
        logging.info(status_msg)

        # Add visual indicator for queue fullness
        if queue_percent >= 90:
            logging.info("  📦 Queue nearly full - download workers will pause fetching new jobs")
        elif queue_percent >= 70:
            logging.info("  ⚠️  Queue getting full")
        elif queue_percent >= 50:
            logging.info("  🔄 Queue half full")
        elif queue_size > 0:
            logging.info("  📥 Queue has jobs ready for processing")
        else:
            logging.info("  📭 Queue empty - waiting for downloads")

    @staticmethod
    def _get_local_ip() -> str:
        """Get the local IP address."""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

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
                torch.mps.empty_cache()  # Clear MPS cache

            logging.info("Model unloaded")

    def register_with_server(self) -> bool:
        """Register this worker with the server.
        Keeps retrying until successful, with a small delay between attempts.
        Returns False only if interrupted (Ctrl+C).
        """
        delay_seconds = 3
        attempt = 1
        print("Attempting to register with server...")
        while True:
            try:
                response = requests.post(
                    f"{self.server_url}/workers/register",
                    json={
                        "worker_id": self.worker_id,
                        "ip_address": self.ip_address
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    print(f"Successfully registered with server (attempt {attempt})")
                    return True
                else:
                    print(f"Failed to register (attempt {attempt}): {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error registering with server (attempt {attempt}): {e}")

            try:
                time.sleep(delay_seconds)
            except KeyboardInterrupt:
                print("Registration interrupted by user.")
                return False
            attempt += 1
    
    def get_job(self) -> Optional[dict]:
        """Get the next job from the server."""
        try:
            response = requests.get(
                f"{self.server_url}/workers/get_job",
                params={"worker_id": self.worker_id},
                timeout=3600
            )

            if response.status_code == 200:
                if response.text.strip():  # Check if response has content
                    return response.json()
                else:
                    return None  # No job available
            else:
                logging.error(f"Error getting job: {response.status_code}")
                return None

        except Exception as e:
            logging.error(f"Error getting job from server: {e}")
            return None

    def download_audio_file(self, download_url: str) -> Optional[Path]:
        """Download audio file from server."""
        try:
            response = requests.get(download_url, stream=True, timeout=30)
            if response.status_code == 200:
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")

                # Write downloaded content
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)

                temp_file.close()
                return Path(temp_file.name)
            else:
                logging.error(f"Failed to download file: {response.status_code}")
                return None

        except Exception as e:
            logging.error(f"Error downloading file: {e}")
            return None

    def _download_worker(self):
        """Background thread worker for downloading audio files."""
        logging.info("Download worker thread started")

        while not self.stop_download_thread.is_set():
            try:
                # If the processing queue is full, pause fetching new jobs
                if self.download_queue.full():
                    logging.info("Download worker: Queue full, pausing job fetch")
                    self._log_queue_status("queue full - pausing fetch")
                    time.sleep(1)
                    continue

                # Get next job from server
                job = self.get_job()

                if job:
                    task_id = job["task_id"]
                    task_type = job.get("task_type", "compute_embedding")
                    logging.info(f"Download worker: Got job {task_id} with task_type {task_type}")

                    # Handle different task types
                    if task_type == "compute_text_embedding":
                        # Text search task - no download needed
                        downloaded_job = DownloadedJob(
                            task_id=task_id,
                            track_id=job["track_id"],
                            audio_file=None,  # No audio file for text search
                            original_job=job
                        )
                        
                        try:
                            self.download_queue.put(downloaded_job, timeout=5)
                            logging.info(f"Download worker: Queued text search job {task_id} for processing")
                            self._log_queue_status("after queuing text search")
                        except:
                            logging.info(f"Download worker: Queue full, could not enqueue text search job {task_id}")
                            
                    elif task_type == "compute_audio_embedding":
                        # Audio search task - download audio file from server
                        download_url = job.get("download_url")
                        audio_filename = job.get("audio_filename", "search.tmp")
                        
                        if download_url:
                            # Download audio file from server
                            try:
                                audio_response = requests.get(f"{self.server_host}:{self.server_port}{download_url}")
                                if audio_response.status_code == 200:
                                    # Create temporary file for the audio data
                                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
                                    temp_file.write(audio_response.content)
                                    temp_file.close()
                                    
                                    downloaded_job = DownloadedJob(
                                        task_id=task_id,
                                        track_id=job["track_id"],
                                        audio_file=temp_file.name,
                                        original_job=job
                                    )
                                    
                                    try:
                                        self.download_queue.put(downloaded_job, timeout=5)
                                        logging.info(f"Download worker: Downloaded and queued audio search job {task_id} from {download_url}")
                                        self._log_queue_status("after downloading audio search")
                                    except:
                                        logging.info(f"Download worker: Queue full, could not enqueue audio search job {task_id}")
                                        # Clean up temp file if couldn't queue
                                        try:
                                            os.unlink(temp_file.name)
                                        except:
                                            pass
                                else:
                                    logging.error(f"Download worker: Failed to download audio file from {download_url}, status: {audio_response.status_code}")
                            except Exception as e:
                                logging.error(f"Download worker: Error downloading audio file: {e}")
                        else:
                            # Fallback to base64 data (backward compatibility)
                            audio_data = job.get("audio_data")
                            if not audio_data:
                                # Check for base64 encoded data
                                audio_data_base64 = job.get("audio_data_base64")
                                if audio_data_base64:
                                    audio_data = base64.b64decode(audio_data_base64)
                            
                            if audio_data:
                                # Create temporary file for the audio data (backward compatibility)
                                try:
                                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
                                    temp_file.write(audio_data)
                                    temp_file.close()
                                    
                                    downloaded_job = DownloadedJob(
                                        task_id=task_id,
                                        track_id=job["track_id"],
                                        audio_file=temp_file.name,
                                        original_job=job
                                    )
                                    
                                    try:
                                        self.download_queue.put(downloaded_job, timeout=5)
                                        logging.info(f"Download worker: Queued audio search job {task_id} for processing (base64 fallback)")
                                        self._log_queue_status("after queuing audio search")
                                    except:
                                        logging.info(f"Download worker: Queue full, could not enqueue audio search job {task_id}")
                                        try:
                                            os.unlink(temp_file.name)
                                        except:
                                            pass
                                except Exception as e:
                                    logging.error(f"Download worker: Failed to create temp file for audio search job {task_id}: {e}")
                            else:
                                logging.error(f"Download worker: Audio search job {task_id} missing audio data and download URL")
                            
                    else:
                        # Traditional track embedding task - download audio file
                        logging.info(f"Download worker: Downloading audio for job {task_id}")
                        audio_file = self.download_audio_file(job["download_url"])

                        if audio_file:
                            # Create downloaded job object
                            downloaded_job = DownloadedJob(
                                task_id=task_id,
                                track_id=job["track_id"],
                                audio_file=audio_file,
                                original_job=job
                            )

                            try:
                                # Add to queue (this will block if queue is full)
                                self.download_queue.put(downloaded_job, timeout=5)
                                logging.info(f"Download worker: Queued job {task_id} for processing")
                                self._log_queue_status("after queuing")
                            except:
                                # Queue remained full; clean up the downloaded temp file
                                logging.info(
                                    f"Download worker: Queue full, could not enqueue job {task_id} within timeout; cleaning up temp file")
                                try:
                                    os.unlink(audio_file)
                                except:
                                    pass
                        else:
                            logging.info(f"Download worker: Failed to download audio for job {task_id}")
                else:
                    # No job available, wait before polling again
                    time.sleep(self.poll_interval)

            except Exception as e:
                logging.error(f"Download worker error: {e}")
                time.sleep(1)

        logging.info("Download worker thread stopped")

    def _start_download_worker(self):
        """Start the background download worker thread."""
        for i in range(self.download_workers):
            thread = threading.Thread(target=self._download_worker, daemon=True)
            thread.start()
            self.download_threads.append(thread)
            logging.info(f"Started download worker thread {i + 1}/{self.download_workers}")

    def _stop_download_worker(self):
        """Stop the background download worker thread."""
        self.stop_download_thread.set()
        for thread in self.download_threads:
            thread.join(timeout=5)

        # Clean up any remaining files in queue
        while not self.download_queue.empty():
            try:
                downloaded_job = self.download_queue.get_nowait()
                try:
                    os.unlink(downloaded_job.audio_file)
                except:
                    pass
            except Empty:
                break

    def submit_result(self, task_id: str, track_id: str, embedding: Optional[List[float]],
                      error_message: Optional[str] = None, search_results: Optional[List[dict]] = None) -> bool:
        """Submit task result to server."""
        try:
            status = "success" if (embedding is not None or search_results is not None) else "failed"

            response = requests.post(
                f"{self.server_url}/workers/submit_result",
                json={
                    "task_id": task_id,
                    "track_id": track_id,
                    "status": status,
                    "embedding": embedding,
                    "error_message": error_message,
                    "search_results": search_results
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("success", False)
            else:
                logging.warning(f"Failed to submit result: {response.status_code}")
                return False

        except Exception as e:
            logging.error(f"Error submitting result: {e}")
            return False

    def process_job(self, downloaded_job: DownloadedJob) -> bool:
        """Process a downloaded job."""
        task_id = downloaded_job.task_id
        track_id = downloaded_job.track_id
        original_job = downloaded_job.original_job
        task_type = original_job.get("task_type", "compute_embedding")
        
        logging.info(f"Processing job {task_id} for track {track_id}, task_type: {task_type}")

        try:
            if task_type == "compute_embedding":
                # Traditional track embedding computation
                audio_file = downloaded_job.audio_file
                embedding = self.clap_embedding_generator.generate_embedding(filepath=audio_file)
                
                if embedding:
                    success = self.submit_result(task_id, track_id, embedding)
                    if success:
                        logging.info(f"Successfully processed embedding job {task_id}")
                    else:
                        logging.warning(f"Failed to submit embedding result for job {task_id}")
                    return success
                else:
                    self.submit_result(task_id, track_id, None, "Failed to compute embedding")
                    return False
                    
            elif task_type == "compute_text_embedding":
                # Text search embedding computation
                text_query = original_job.get("text_query")
                if not text_query:
                    self.submit_result(task_id, track_id, None, "Missing text query")
                    return False
                    
                logging.info(f"Computing text embedding for query: '{text_query}'")
                text_embedding = self.clap_embedding_generator.generate_text_embedding(text_query)
                
                if text_embedding:
                    success = self.submit_result(task_id, track_id, text_embedding)
                    if success:
                        logging.info(f"Successfully processed text embedding job {task_id}")
                    else:
                        logging.warning(f"Failed to submit text embedding result for job {task_id}")
                    return success
                else:
                    self.submit_result(task_id, track_id, None, "Failed to compute text embedding")
                    return False
                    
            elif task_type == "compute_audio_embedding":
                # Audio search embedding computation
                audio_file = downloaded_job.audio_file
                embedding = self.clap_embedding_generator.generate_embedding(filepath=audio_file)
                
                if embedding:
                    success = self.submit_result(task_id, track_id, embedding)
                    if success:
                        logging.info(f"Successfully processed audio embedding job {task_id}")
                    else:
                        logging.warning(f"Failed to submit audio embedding result for job {task_id}")
                    return success
                else:
                    self.submit_result(task_id, track_id, None, "Failed to compute audio embedding")
                    return False
            else:
                logging.error(f"Unknown task type: {task_type}")
                self.submit_result(task_id, track_id, None, f"Unknown task type: {task_type}", None)
                return False

        finally:
            # Clean up temporary file
            if hasattr(downloaded_job, 'audio_file') and downloaded_job.audio_file:
                try:
                    os.unlink(downloaded_job.audio_file)
                except Exception:
                    pass

    def run(self):
        """Main worker loop."""
        logging.info(f"Starting Mycelium client worker loop...")

        # Register with server
        if not self.register_with_server():
            logging.info("Failed to register with server. Exiting.")
            return

        # Start background download worker
        logging.info("Starting background download worker...")
        self._start_download_worker()

        # Log initial queue status
        self._log_queue_status("worker started")

        logging.info(f"Worker loop started. Processing downloaded audio files...")

        # Add periodic queue status logging
        last_status_log = time.time()
        status_log_interval = 30  # Log queue status every 30 seconds

        try:
            while True:
                try:
                    # Get next downloaded job from queue (with timeout)
                    downloaded_job = self.download_queue.get(timeout=self.poll_interval)

                    logging.info(f"Retrieved job {downloaded_job.task_id} from queue")
                    self._log_queue_status("after retrieval")

                    # Process the job (model is already loaded, audio is already downloaded)
                    self.process_job(downloaded_job)

                    # Log queue status after processing
                    self._log_queue_status("after processing")

                except Empty:
                    # No downloaded job available, continue polling
                    current_time = time.time()
                    if current_time - last_status_log >= status_log_interval:
                        self._log_queue_status("periodic check")
                        last_status_log = current_time
                    continue

        except KeyboardInterrupt:
            logging.info("\nShutting down worker...")
        finally:
            # Log final queue status
            self._log_queue_status("shutdown")

            # Stop download worker
            self._stop_download_worker()

            # Only unload model when shutting down
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
