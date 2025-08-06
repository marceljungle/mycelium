"""Mycelium client for processing audio embeddings on GPU workers."""

import time
import uuid
import socket
import requests
from pathlib import Path
from typing import Optional, List
import tempfile
import os

import torch
from transformers import ClapModel, ClapProcessor
import librosa


class MyceliumClient:
    """Client for processing CLAP embeddings on GPU hardware."""
    
    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 8000,
        model_id: str = "laion/clap-htsat-unfused",
        poll_interval: int = 5
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.server_url = f"http://{server_host}:{server_port}"
        self.model_id = model_id
        self.poll_interval = poll_interval
        
        # Generate unique worker ID
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.ip_address = self._get_local_ip()
        
        # Initialize model (will be loaded when first needed)
        self.model = None
        self.processor = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"Mycelium Client initialized")
        print(f"Worker ID: {self.worker_id}")
        print(f"Server: {self.server_url}")
        print(f"Device: {self.device}")
        
    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    def _load_model(self):
        """Load the CLAP model and processor."""
        if self.model is None:
            print(f"Loading CLAP model: {self.model_id}")
            self.model = ClapModel.from_pretrained(self.model_id).to(self.device)
            self.processor = ClapProcessor.from_pretrained(self.model_id)
            self.model.eval()
            
            if self.device == "cuda":
                self.model.half()  # Use FP16 for faster GPU processing
            
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
                timeout=10
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
    
    def compute_embedding(self, audio_file: Path) -> Optional[List[float]]:
        """Compute CLAP embedding for an audio file."""
        try:
            # Load model if not already loaded
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
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            if self.device == "cuda":
                inputs = {k: v.half() for k, v in inputs.items()}
            
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
    
    def process_job(self, job: dict) -> bool:
        """Process a single job."""
        task_id = job["task_id"]
        track_id = job["track_id"]
        download_url = job["download_url"]
        
        print(f"Processing job {task_id} for track {track_id}")
        
        # Download audio file
        audio_file = self.download_audio_file(download_url)
        if audio_file is None:
            self.submit_result(task_id, track_id, None, "Failed to download audio file")
            return False
        
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
        
        print(f"Worker loop started. Polling every {self.poll_interval} seconds...")
        
        try:
            while True:
                # Get next job
                job = self.get_job()
                
                if job:
                    # Process the job
                    self.process_job(job)
                    
                    # Unload model to free GPU memory between jobs
                    self._unload_model()
                else:
                    # No job available, wait before polling again
                    time.sleep(self.poll_interval)
                    
        except KeyboardInterrupt:
            print("\nShutting down worker...")
        finally:
            self._unload_model()
            print("Worker stopped")


def run_client(
    server_host: str = "localhost",
    server_port: int = 8000,
    model_id: str = "laion/clap-htsat-unfused"
):
    """Run the Mycelium client."""
    client = MyceliumClient(
        server_host=server_host,
        server_port=server_port,
        model_id=model_id
    )
    client.run()