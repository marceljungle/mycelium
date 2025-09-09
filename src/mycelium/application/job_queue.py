"""Job queue and worker management service."""
import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import List, Optional, Dict

from ..domain.worker import Worker, Task, TaskResult, TaskType, TaskStatus, ContextType

logger = logging.getLogger(__name__)


class JobQueueService:
    """Service for managing job queue and worker coordination."""

    def __init__(self):
        self._workers: Dict[str, Worker] = {}
        self._tasks: Dict[str, Task] = {}
        self._pending_tasks: List[str] = []
        self._lock = Lock()
        # Temporary directory for audio files to avoid base64 encoding large files
        self._temp_dir = Path(tempfile.mkdtemp(prefix="mycelium_audio_"))
        self._cleanup_orphan_files()
        self._temp_files: Dict[str, Path] = {}  # task_id -> temp_file_path

    def _register_worker_internal(self, worker_id: str, ip_address: str) -> Worker:
        """Internal worker registration without lock (assumes lock is already held)."""
        now = datetime.now()
        if worker_id in self._workers:
            # Update existing worker
            worker = self._workers[worker_id]
            worker.last_heartbeat = now
            worker.is_active = True
        else:
            # Create new worker
            worker = Worker(
                id=worker_id,
                ip_address=ip_address,
                registration_time=now,
                last_heartbeat=now,
                is_active=True
            )
            self._workers[worker_id] = worker

        return worker

    def register_worker(self, worker_id: str, ip_address: str) -> Worker:
        """Register a new worker or update existing one."""
        with self._lock:
            return self._register_worker_internal(worker_id, ip_address)

    def get_active_workers(self) -> List[Worker]:
        """Get list of active workers."""
        with self._lock:
            # Clean up inactive workers
            cutoff_time = datetime.now() - timedelta(seconds=10)
            for worker in self._workers.values():
                if worker.last_heartbeat < cutoff_time:
                    worker.is_active = False

            return [w for w in self._workers.values() if w.is_active]

    def create_task(self, track_id: str = "", download_url: str = "",
                    audio_data: bytes = None, audio_filename: str = "",
                    n_results: int = 10, prioritize: bool = True,
                    context_type: ContextType = None) -> Task:
        """Create a new task and add it to the queue.
        
        Can create either:
        - Traditional embedding task: provide track_id and download_url
        - Audio search task: provide audio_data and audio_filename
        """
        with self._lock:
            task_id = str(uuid.uuid4())

            # Determine task type based on provided parameters
            if audio_data is not None:
                # Audio search task - create temporary file and internal URL
                task_type = TaskType.COMPUTE_AUDIO_EMBEDDING

                # Create temporary file for audio data to avoid base64 encoding overhead
                temp_file = self._temp_dir / f"audio_task_{task_id}.tmp"
                temp_file.write_bytes(audio_data)
                self._temp_files[task_id] = temp_file

                # Create download URL for the worker (internal URL)
                download_url = f"/download_audio/{task_id}"
                track_id = ""  # Not needed for audio search

                task = Task(
                    task_id=task_id,
                    task_type=task_type,
                    track_id=track_id,
                    download_url=download_url,
                    audio_filename=audio_filename,
                    n_results=n_results,
                    context_type=context_type
                )
            else:
                # Traditional embedding task
                task_type = TaskType.COMPUTE_AUDIO_EMBEDDING

                task = Task(
                    task_id=task_id,
                    task_type=task_type,
                    track_id=track_id,
                    download_url=download_url,
                    context_type=context_type
                )

            self._tasks[task_id] = task
            if prioritize:
                self._pending_tasks.insert(0, task_id)
            else:
                self._pending_tasks.append(task_id)
            return task

    def create_text_search_task(self, text_query: str, n_results: int = 10, prioritize: bool = True) -> Task:
        """Create a new text search task and add it to the queue."""
        with self._lock:
            task_id = str(uuid.uuid4())
            task = Task(
                task_id=task_id,
                task_type=TaskType.COMPUTE_TEXT_EMBEDDING,
                context_type=ContextType.TEXT_SEARCH,
                track_id="",  # Not needed for text search
                download_url="",  # Not needed for text search
                text_query=text_query,
                n_results=n_results
            )
            self._tasks[task_id] = task
            if prioritize:
                self._pending_tasks.insert(0, task_id)
            else:
                self._pending_tasks.append(task_id)
            return task

    def get_next_job(self, worker_id: str, ip_address: str) -> Optional[Task]:
        """Get the next job for a worker."""
        with self._lock:
            # Update worker heartbeat
            if worker_id in self._workers:
                self._workers[worker_id].last_heartbeat = datetime.now()
            else:
                logger.warning(f"Received heartbeat from unknown worker, registering {worker_id}...")
                self._register_worker_internal(worker_id=worker_id, ip_address=ip_address)

            # Get next pending task
            if not self._pending_tasks:
                return None

            task_id = self._pending_tasks.pop(0)
            task = self._tasks[task_id]
            task.status = TaskStatus.IN_PROGRESS
            task.assigned_worker_id = worker_id
            task.started_at = datetime.now()

            return task

    def submit_result(self, result: TaskResult) -> bool:
        """Submit the result of a completed task."""
        with self._lock:
            if result.task_id not in self._tasks:
                return False

            task = self._tasks[result.task_id]
            task.status = result.status
            task.completed_at = datetime.now()

            if result.error_message:
                task.error_message = result.error_message

            # Store search results for search tasks
            if result.search_results:
                task.search_results = result.search_results

            return True

    def get_task_status(self, task_id: str) -> Optional[Task]:
        """Get the status of a specific task."""
        with self._lock:
            return self._tasks.get(task_id)

    def wait_for_task_completion(self, task_id: str, timeout_seconds: int = 300) -> Optional[Task]:
        """Wait for a task to complete with timeout."""
        import time

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            task = self.get_task_status(task_id)
            if task and task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED]:
                return task
            time.sleep(1)  # Poll every second

        return None

    def get_queue_stats(self) -> Dict:
        """Get statistics about the job queue."""
        with self._lock:
            active_workers = len([w for w in self._workers.values() if w.is_active])
            pending_tasks = len(self._pending_tasks)
            in_progress_tasks = len([t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS])
            completed_tasks = len([t for t in self._tasks.values() if t.status == TaskStatus.SUCCESS])
            failed_tasks = len([t for t in self._tasks.values() if t.status == TaskStatus.FAILED])

            return {
                "active_workers": active_workers,
                "pending_tasks": pending_tasks,
                "in_progress_tasks": in_progress_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "total_tasks": len(self._tasks)
            }

    def clear_pending_tasks(self) -> int:
        """Clear all pending tasks from the queue. Returns number of tasks cleared."""
        with self._lock:
            cleared_count = len(self._pending_tasks)

            # Mark all pending tasks as cancelled
            for task_id in self._pending_tasks:
                if task_id in self._tasks:
                    self._tasks[task_id].status = TaskStatus.FAILED
                    self._tasks[task_id].error_message = "Processing stopped by user"
                    self._tasks[task_id].completed_at = datetime.now()

            # Clear the pending tasks list
            self._pending_tasks.clear()

            # When stopping, clean up ALL in-progress tasks, not just from inactive workers
            # This ensures processing state is properly cleared even if workers are still active
            in_progress_cleaned = self._cleanup_all_in_progress_tasks()

            return cleared_count + in_progress_cleaned

    def _cleanup_stale_tasks(self) -> int:
        """Clean up tasks assigned to inactive workers. Returns number of tasks cleaned up."""
        active_worker_ids = {w.id for w in self._workers.values() if w.is_active}
        cleaned_count = 0

        for task in self._tasks.values():
            # Mark IN_PROGRESS tasks from inactive workers as failed
            if (task.status == TaskStatus.IN_PROGRESS and
                    task.assigned_worker_id and
                    task.assigned_worker_id not in active_worker_ids):
                task.status = TaskStatus.FAILED
                task.error_message = "Worker became inactive during processing"
                task.completed_at = datetime.now()
                cleaned_count += 1

        return cleaned_count

    def _cleanup_all_in_progress_tasks(self) -> int:
        """Clean up ALL in-progress tasks when stopping processing. Returns number of tasks cleaned up."""
        cleaned_count = 0

        for task in self._tasks.values():
            # Mark ALL IN_PROGRESS tasks as failed when explicitly stopping
            if task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.FAILED
                task.error_message = "Processing stopped by user request"
                task.completed_at = datetime.now()
                cleaned_count += 1

        return cleaned_count

    def cleanup_stale_tasks(self) -> int:
        """Public method to clean up stale tasks. Returns number of tasks cleaned up."""
        with self._lock:
            return self._cleanup_stale_tasks()

    def has_active_processing(self) -> bool:
        """Check if there are any library processing tasks currently being processed or pending.
        
        Note: This excludes search tasks (text/audio search) which have their own loading states.
        Only counts tasks with AUDIO_PROCESSING context for library processing status.
        """
        with self._lock:
            # Clean up stale in-progress tasks from inactive workers first
            self._cleanup_stale_tasks()

            # Only count library processing tasks, not search tasks
            library_pending_tasks = [
                task_id for task_id in self._pending_tasks
                if self._tasks.get(task_id) and self._tasks[task_id].context_type == ContextType.AUDIO_PROCESSING
            ]

            library_in_progress_tasks = [
                t for t in self._tasks.values()
                if t.status == TaskStatus.IN_PROGRESS and t.context_type == ContextType.AUDIO_PROCESSING
            ]

            return len(library_pending_tasks) > 0 or len(library_in_progress_tasks) > 0

    def get_audio_task_file(self, task_id: str) -> Optional[Path]:
        """Get the temporary file path for an audio task."""
        with self._lock:
            return self._temp_files.get(task_id)

    def cleanup_task_files(self, task_id: str) -> None:
        """Clean up temporary files for a completed task."""
        with self._lock:
            if task_id in self._temp_files:
                temp_file = self._temp_files[task_id]
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except OSError:
                    pass  # Ignore cleanup errors
                del self._temp_files[task_id]

    def _cleanup_orphan_files(self):
        """ Clean up any orphaned temporary files in the temp directory on startup. """
        try:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir)
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Temp dir recreated in: {self._temp_dir}")
        except Exception as e:
            logging.error(f"Failed to clean up temp dir {self._temp_dir}: {e}")
