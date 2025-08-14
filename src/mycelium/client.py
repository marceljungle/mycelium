"""Mycelium client for processing audio embeddings on GPU workers."""

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
from transformers import ClapModel, ClapProcessor

from mycelium.infrastructure import CLAPEmbeddingGenerator


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
        model_id: str = "laion/clap-htsat-unfused",
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
        
        # Initialize model (will be loaded when first needed)
        self.model = None
        self.processor = None
        self.device = self._get_best_device()

        # Download queue management
        self.download_queue: Queue[DownloadedJob] = Queue(maxsize=download_queue_size)
        self.pending_downloads: Dict[str, threading.Event] = {}
        self.download_threads: List[threading.Thread] = []  # Multiple download threads
        self.stop_download_thread = threading.Event()

        self.clap_embedding_generator = CLAPEmbeddingGenerator()

        print(f"Mycelium Client initialized")
        print(f"Worker ID: {self.worker_id}")
        print(f"Server: {self.server_url}")
        print(f"Device: {self.device}")
        print(f"Download queue size: {download_queue_size}")
        print(f"Parallel download workers: {download_workers}")

    def _log_queue_status(self, context: str = ""):
        """Log current queue status with context."""
        queue_size = self.download_queue.qsize()
        queue_capacity = self.download_queue.maxsize
        queue_percent = (queue_size / queue_capacity) * 100 if queue_capacity > 0 else 0

        status_msg = f"Queue status{' (' + context + ')' if context else ''}: {queue_size}/{queue_capacity} jobs ({queue_percent:.1f}% full)"
        print(status_msg)

        # Add visual indicator for queue fullness
        if queue_percent >= 90:
            print("  📦 Queue nearly full - download workers will pause fetching new jobs")
        elif queue_percent >= 70:
            print("  ⚠️  Queue getting full")
        elif queue_percent >= 50:
            print("  🔄 Queue half full")
        elif queue_size > 0:
            print("  📥 Queue has jobs ready for processing")
        else:
            print("  📭 Queue empty - waiting for downloads")

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    def _get_best_device(self) -> str:
        """Get the best available device for computation."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def _load_model(self):
        """Load the CLAP model and processor."""
        if self.model is None:
            print(f"Loading CLAP model: {self.model_id}")
            self.model = ClapModel.from_pretrained(self.model_id).to(self.device)
            self.processor = ClapProcessor.from_pretrained(self.model_id)
            self.model.eval()
            
            # Apply device-specific optimizations
            if self.device == "cuda":
                self.model.half()
            elif self.device == "mps":
                try:
                    self.model.half()
                    torch.backends.mps.enabled = True
                    print("MPS half precision enabled for optimal performance")
                except RuntimeError as e:
                    print(f"MPS half precision not supported, using FP32: {e}")

            print("Model loaded successfully")
    
    def _unload_model(self):
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()  # Clear MPS cache

            print("Model unloaded")
    
    def register_with_server(self) -> bool:
        """Register this worker with the server."""
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
                print("Successfully registered with server")
                return True
            else:
                print(f"Failed to register: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error registering with server: {e}")
            return False
    
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
                print(f"Error getting job: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting job from server: {e}")
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
                print(f"Failed to download file: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error downloading file: {e}")
            return None

    def _download_worker(self):
        """Background thread worker for downloading audio files."""
        print("Download worker thread started")
        
        while not self.stop_download_thread.is_set():
            try:
                # If the processing queue is full, pause fetching new jobs
                if self.download_queue.full():
                    print("Download worker: Queue full, pausing job fetch")
                    self._log_queue_status("queue full - pausing fetch")
                    time.sleep(1)
                    continue

                # Get next job from server
                job = self.get_job()
                
                if job:
                    task_id = job["task_id"]
                    print(f"Download worker: Downloading audio for job {task_id}")
                    
                    # Download audio file
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
                            print(f"Download worker: Queued job {task_id} for processing")
                            self._log_queue_status("after queuing")
                        except:
                            # Queue remained full; clean up the downloaded temp file
                            print(f"Download worker: Queue full, could not enqueue job {task_id} within timeout; cleaning up temp file")
                            try:
                                os.unlink(audio_file)
                            except:
                                pass
                    else:
                        print(f"Download worker: Failed to download audio for job {task_id}")
                else:
                    # No job available, wait before polling again
                    time.sleep(self.poll_interval)
                    
            except Exception as e:
                print(f"Download worker error: {e}")
                time.sleep(1)
        
        print("Download worker thread stopped")

    def _start_download_worker(self):
        """Start the background download worker thread."""
        for i in range(self.download_workers):
            thread = threading.Thread(target=self._download_worker, daemon=True)
            thread.start()
            self.download_threads.append(thread)
            print(f"Started download worker thread {i+1}/{self.download_workers}")

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

    def _can_use_half_precision(self) -> bool:
        """Check if the current device supports half precision."""
        if self.device == "cuda":
            return True
        elif self.device == "mps":
            # Test if MPS supports half precision on this device
            try:
                test_tensor = torch.rand(1, device=self.device, dtype=torch.half)
                return True
            except RuntimeError:
                return False
        return False
    
    def submit_result(self, task_id: str, track_id: str, embedding: Optional[List[float]], error_message: Optional[str] = None) -> bool:
        """Submit task result to server."""
        try:
            status = "success" if embedding is not None else "failed"
            
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
            
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False)
            else:
                print(f"Failed to submit result: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Error submitting result: {e}")
            return False
    
    def process_job(self, downloaded_job: DownloadedJob) -> bool:
        """Process a downloaded job."""
        task_id = downloaded_job.task_id
        track_id = downloaded_job.track_id
        audio_file = downloaded_job.audio_file
        
        print(f"Processing job {task_id} for track {track_id}")
        
        try:
            # Compute embedding
            self._load_model()
            embedding = self.clap_embedding_generator.generate_embedding(filepath=audio_file)
            
            # Submit result
            if embedding:
                success = self.submit_result(task_id, track_id, embedding)
                if success:
                    print(f"Successfully processed job {task_id}")
                else:
                    print(f"Failed to submit result for job {task_id}")
                return success
            else:
                self.submit_result(task_id, track_id, None, "Failed to compute embedding")
                return False
                
        finally:
            # Clean up temporary file
            try:
                os.unlink(audio_file)
            except Exception:
                pass
    
    def run(self):
        """Main worker loop."""
        print(f"Starting Mycelium client worker loop...")
        
        # Register with server
        if not self.register_with_server():
            print("Failed to register with server. Exiting.")
            return
        
        # Pre-load model at start of session for efficiency
        print("Loading CLAP model for the session...")
        self._load_model()
        
        # Start background download worker
        print("Starting background download worker...")
        self._start_download_worker()
        
        # Log initial queue status
        self._log_queue_status("worker started")

        print(f"Worker loop started. Processing downloaded audio files...")
        
        # Add periodic queue status logging
        last_status_log = time.time()
        status_log_interval = 30  # Log queue status every 30 seconds

        try:
            while True:
                try:
                    # Get next downloaded job from queue (with timeout)
                    downloaded_job = self.download_queue.get(timeout=self.poll_interval)
                    
                    print(f"Retrieved job {downloaded_job.task_id} from queue")
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
            print("\nShutting down worker...")
        finally:
            # Log final queue status
            self._log_queue_status("shutdown")

            # Stop download worker
            self._stop_download_worker()
            
            # Only unload model when shutting down
            self._unload_model()
            print("Worker stopped")


def run_client(
    server_host: str = "localhost",
    server_port: int = 8000,
    model_id: str = "laion/clap-htsat-unfused",
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