"""Job queue and worker management service."""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from threading import Lock

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

    def create_task(self, track_id: str, download_url: str) -> Task:
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