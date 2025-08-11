"""Mycelium client for processing audio embeddings on GPU workers."""

import time
import uuid
import socket
import requests
from pathlib import Path
from typing import Optional, List, Dict
import tempfile
import os
import threading
from queue import Queue, Empty
from dataclasses import dataclass

import torch
from transformers import ClapModel, ClapProcessor
import librosa


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
        download_queue_size: int = 5
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.server_url = f"http://{server_host}:{server_port}"
        self.model_id = model_id
        self.poll_interval = poll_interval
        self.download_queue_size = download_queue_size
        
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
        self.download_thread = None
        self.stop_download_thread = threading.Event()

        print(f"Mycelium Client initialized")
        print(f"Worker ID: {self.worker_id}")
        print(f"Server: {self.server_url}")
        print(f"Device: {self.device}")
        print(f"Download queue size: {download_queue_size}")
        
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
                        except:
                            # Queue is full, clean up the file
                            print(f"Download worker: Queue full, discarding job {task_id}")
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
        if self.download_thread is None or not self.download_thread.is_alive():
            self.stop_download_thread.clear()
            self.download_thread = threading.Thread(target=self._download_worker, daemon=True)
            self.download_thread.start()

    def _stop_download_worker(self):
        """Stop the background download worker thread."""
        if self.download_thread and self.download_thread.is_alive():
            self.stop_download_thread.set()
            self.download_thread.join(timeout=5)
            
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

    def compute_embedding(self, audio_file: Path) -> Optional[List[float]]:
        """Compute CLAP embedding for an audio file."""
        try:
            # Ensure model is loaded (only loads if not already loaded)
            self._load_model()
            
            # Load and process audio
            target_sr = 48000
            chunk_duration_s = 10
            
            waveform, sr = librosa.load(str(audio_file), sr=target_sr, mono=True)
            
            # Split into chunks
            chunk_len = chunk_duration_s * sr
            chunks = [waveform[i:i + chunk_len] for i in range(0, len(waveform), chunk_len)]
            
            # Ensure last chunk is not too short
            if len(chunks) > 1 and len(chunks[-1]) < sr:  # Less than 1 second
                chunks.pop(-1)
            if not chunks:
                return None
            
            # Process chunks
            inputs = self.processor(
                audios=chunks,
                sampling_rate=target_sr,
                return_tensors="pt",
                padding=True
            )
            
            # Move to device with device-specific optimizations
            use_half = self._can_use_half_precision()
            if use_half and (self.device == "cuda" or self.device == "mps"):
                inputs = {k: v.to(self.device).half() for k, v in inputs.items()}
            else:
                # For CPU or devices without half precision support, use float32
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                # Get embeddings for all chunks
                audio_features = self.model.get_audio_features(**inputs)
                
                # Average embeddings of chunks and normalize
                mean_embedding = torch.mean(audio_features, dim=0)
                normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)
            
            return normalized_embedding.cpu().numpy().tolist()
            
        except Exception as e:
            print(f"Error computing embedding: {e}")
            return None
    
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
            embedding = self.compute_embedding(audio_file)
            
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
        
        print(f"Worker loop started. Processing downloaded audio files...")
        
        try:
            while True:
                try:
                    # Get next downloaded job from queue (with timeout)
                    downloaded_job = self.download_queue.get(timeout=self.poll_interval)
                    
                    # Process the job (model is already loaded, audio is already downloaded)
                    self.process_job(downloaded_job)
                    
                except Empty:
                    # No downloaded job available, continue polling
                    continue
                    
        except KeyboardInterrupt:
            print("\nShutting down worker...")
        finally:
            # Stop download worker
            self._stop_download_worker()
            
            # Only unload model when shutting down
            self._unload_model()
            print("Worker stopped")


def run_client(
    server_host: str = "localhost",
    server_port: int = 8000,
    model_id: str = "laion/clap-htsat-unfused",
    download_queue_size: int = 5
):
    """Run the Mycelium client."""
    client = MyceliumClient(
        server_host=server_host,
        server_port=server_port,
        model_id=model_id,
        download_queue_size=download_queue_size
    )
    client.run()