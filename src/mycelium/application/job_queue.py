"""Job queue and worker management service."""

import uuid
from datetime import datetime, timedelta
from threading import Lock
from typing import List, Optional, Dict

from ..domain.worker import Worker, Task, TaskResult, TaskType, TaskStatus


class JobQueueService:
    """Service for managing job queue and worker coordination."""

    def __init__(self):
        self._workers: Dict[str, Worker] = {}
        self._tasks: Dict[str, Task] = {}
        self._pending_tasks: List[str] = []
        self._lock = Lock()

    def register_worker(self, worker_id: str, ip_address: str) -> Worker:
        """Register a new worker or update existing one."""
        with self._lock:
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

    def get_active_workers(self) -> List[Worker]:
        """Get list of active workers."""
        with self._lock:
            # Clean up inactive workers (no heartbeat for more than 5 minutes)
            cutoff_time = datetime.now() - timedelta(minutes=5)
            for worker in self._workers.values():
                if worker.last_heartbeat < cutoff_time:
                    worker.is_active = False
            
            return [w for w in self._workers.values() if w.is_active]

    def create_task(self, track_id: str, download_url: str, prioritize: bool) -> Task:
        """Create a new task and add it to the queue."""
        with self._lock:
            task_id = str(uuid.uuid4())
            task = Task(
                task_id=task_id,
                task_type=TaskType.COMPUTE_EMBEDDING,
                track_id=track_id,
                download_url=download_url
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

    def create_audio_search_task(self, audio_data: bytes, audio_filename: str, n_results: int = 10, prioritize: bool = True) -> Task:
        """Create a new audio search task and add it to the queue."""
        with self._lock:
            task_id = str(uuid.uuid4())
            task = Task(
                task_id=task_id,
                task_type=TaskType.COMPUTE_AUDIO_EMBEDDING,
                track_id="",  # Not needed for audio search
                download_url="",  # Not needed for audio search
                audio_data=audio_data,
                audio_filename=audio_filename,
                n_results=n_results
            )
            self._tasks[task_id] = task
            if prioritize:
                self._pending_tasks.insert(0, task_id)
            else:
                self._pending_tasks.append(task_id)
            return task

    def get_next_job(self, worker_id: str) -> Optional[Task]:
        """Get the next job for a worker."""
        with self._lock:
            # Update worker heartbeat
            if worker_id in self._workers:
                self._workers[worker_id].last_heartbeat = datetime.now()
            
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
        """Check if there are any tasks currently being processed or pending."""
        with self._lock:
            # Clean up stale in-progress tasks from inactive workers first
            self._cleanup_stale_tasks()
            
            return len(self._pending_tasks) > 0 or any(
                t.status == TaskStatus.IN_PROGRESS for t in self._tasks.values()
            )