"""Job queue and worker management service."""
import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Callable, List, Optional, Dict, Tuple

from ...domain.worker import Worker, Task, TaskResult, TaskType, TaskStatus, ContextType

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

    def _register_worker_internal(
        self, worker_id: str, ip_address: str, gpu_name: Optional[str] = None,
    ) -> Worker:
        """Internal worker registration without lock (assumes lock is already held)."""
        now = datetime.now()
        if worker_id in self._workers:
            # Update existing worker
            worker = self._workers[worker_id]
            worker.last_heartbeat = now
            worker.is_active = True
            if gpu_name is not None:
                worker.gpu_name = gpu_name
        else:
            # Deactivate any previous workers from the same IP
            for existing in self._workers.values():
                if existing.ip_address == ip_address and existing.is_active:
                    logger.info(
                        f"Deactivating old worker {existing.id} "
                        f"(same IP {ip_address}, replaced by {worker_id})"
                    )
                    existing.is_active = False

            # Create new worker
            worker = Worker(
                id=worker_id,
                ip_address=ip_address,
                registration_time=now,
                last_heartbeat=now,
                is_active=True,
                gpu_name=gpu_name,
            )
            self._workers[worker_id] = worker

        return worker

    def register_worker(
        self, worker_id: str, ip_address: str, gpu_name: Optional[str] = None,
    ) -> Worker:
        """Register a new worker or update existing one."""
        with self._lock:
            return self._register_worker_internal(worker_id, ip_address, gpu_name)

    def get_active_workers(self) -> List[Worker]:
        """Get list of active workers."""
        with self._lock:
            # Clean up inactive workers
            cutoff_time = datetime.now() - timedelta(seconds=60)
            for worker in self._workers.values():
                if worker.last_heartbeat < cutoff_time:
                    worker.is_active = False

            return [w for w in self._workers.values() if w.is_active]

    def create_task(self, track_id: str = "", download_url: str = "",
                    audio_data: bytes = None, audio_filename: str = "",
                    text_query: str = "",
                    n_results: int = 10, prioritize: bool = True,
                    context_type: ContextType = None,
                    track_artist: str = "",
                    track_title: str = "",
                    track_album: str = "") -> Task:
        """Create a new task and add it to the queue.
        
        Handles all task variants:
        - Audio embedding task: provide track_id and download_url
        - Audio search task: provide audio_data and audio_filename
        - Text search task: provide text_query
        """
        with self._lock:
            task_id = str(uuid.uuid4())

            if text_query:
                # Text search task
                task = Task(
                    task_id=task_id,
                    task_type=TaskType.COMPUTE_TEXT_EMBEDDING,
                    context_type=context_type or ContextType.TEXT_SEARCH,
                    track_id="",
                    download_url="",
                    text_query=text_query,
                    n_results=n_results,
                    track_artist=track_artist or None,
                    track_title=track_title or None,
                    track_album=track_album or None,
                )
            elif audio_data is not None:
                # Audio search task - create temporary file and internal URL
                temp_file = self._temp_dir / f"audio_task_{task_id}.tmp"
                temp_file.write_bytes(audio_data)
                self._temp_files[task_id] = temp_file

                task = Task(
                    task_id=task_id,
                    task_type=TaskType.COMPUTE_AUDIO_EMBEDDING,
                    context_type=context_type,
                    track_id="",
                    download_url=f"/download_audio/{task_id}",
                    audio_filename=audio_filename,
                    n_results=n_results,
                    track_artist=track_artist or None,
                    track_title=track_title or None,
                    track_album=track_album or None,
                )
            else:
                # Traditional embedding task
                task = Task(
                    task_id=task_id,
                    task_type=TaskType.COMPUTE_AUDIO_EMBEDDING,
                    context_type=context_type,
                    track_id=track_id,
                    download_url=download_url,
                    n_results=n_results,
                    track_artist=track_artist or None,
                    track_title=track_title or None,
                    track_album=track_album or None,
                )

            self._tasks[task_id] = task
            if prioritize:
                self._pending_tasks.insert(0, task_id)
            else:
                self._pending_tasks.append(task_id)
            return task

    def find_active_task_for_track(self, track_id: str) -> Optional[Task]:
        """Return an existing PENDING or IN_PROGRESS task for *track_id*, if any.

        Useful to avoid creating duplicate tasks when the user requests
        processing for a track that is already queued (e.g. via bulk
        processing).
        """
        with self._lock:
            for task in self._tasks.values():
                if (
                    task.track_id == track_id
                    and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
                ):
                    return task
            return None

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

            # Update the worker heartbeat so result submissions also
            # keep the worker alive (not only get_job calls).
            if task.assigned_worker_id and task.assigned_worker_id in self._workers:
                self._workers[task.assigned_worker_id].last_heartbeat = datetime.now()
            task.completed_at = datetime.now()

            if result.error_message:
                task.error_message = result.error_message

            # Store search results for search tasks
            if result.search_results:
                task.search_results = result.search_results

            return True

    def complete_task_with_search(
        self,
        task_id: str,
        embedding: list,
        search_fn: Callable[[list, int], list],
        map_fn: Callable,
    ) -> None:
        """Run a similarity search using *embedding* and store results on the task.

        This is the single place where post-embed search logic lives.
        Called from the API layer after save_embedding, it keeps lock
        management inside the queue and removes the need for external
        code to touch ``_lock`` directly.

        Args:
            task_id: The task whose results we want to update.
            embedding: The embedding vector to search with.
            search_fn: ``(embedding, n_results) -> List[SearchResult]``.
            map_fn: Converts a single SearchResult → serialisable dict.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            n_results = task.n_results or 10

        # Run the (potentially slow) search outside the lock.
        try:
            search_results = search_fn(embedding, n_results)
            results_dicts = [map_fn(r) for r in search_results]

            with self._lock:
                task.search_results = results_dicts
                if task.status != TaskStatus.SUCCESS:
                    task.status = TaskStatus.SUCCESS
                    task.completed_at = datetime.now()

            logger.info(
                f"Post-embed search completed for task {task_id}, "
                f"found {len(results_dicts)} results"
            )
        except Exception as e:
            logger.error(
                f"Post-embed search failed for task {task_id}: {e}",
                exc_info=True,
            )
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now()

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Safely update a task's status from outside the queue."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.status = status
            if error_message:
                task.error_message = error_message
            task.completed_at = datetime.now()

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
            in_progress_cleaned = self._cleanup_tasks(lambda t: t.status == TaskStatus.IN_PROGRESS,
                                                      "Processing stopped by user request")

            return cleared_count + in_progress_cleaned

    def _cleanup_tasks(self, predicate: Callable[[Task], bool], error_message: str) -> int:
        """Mark tasks matching *predicate* as FAILED. Returns count of cleaned tasks.

        Must be called while ``_lock`` is held.
        """
        cleaned_count = 0
        for task in self._tasks.values():
            if predicate(task):
                task.status = TaskStatus.FAILED
                task.error_message = error_message
                task.completed_at = datetime.now()
                cleaned_count += 1
        return cleaned_count

    def cleanup_stale_tasks(self) -> int:
        """Public method to clean up stale tasks. Returns number of tasks cleaned up."""
        with self._lock:
            active_worker_ids = {w.id for w in self._workers.values() if w.is_active}
            return self._cleanup_tasks(
                lambda t: (
                    t.status == TaskStatus.IN_PROGRESS
                    and t.assigned_worker_id is not None
                    and t.assigned_worker_id not in active_worker_ids
                ),
                "Worker became inactive during processing",
            )

    def has_active_processing(self) -> bool:
        """Check if there are any library processing tasks currently being processed or pending.
        
        Note: This excludes search tasks (text/audio search) which have their own loading states.
        Only counts tasks with AUDIO_PROCESSING context for library processing status.
        """
        with self._lock:
            # Clean up stale in-progress tasks from inactive workers first
            active_worker_ids = {w.id for w in self._workers.values() if w.is_active}
            self._cleanup_tasks(
                lambda t: (
                    t.status == TaskStatus.IN_PROGRESS
                    and t.assigned_worker_id is not None
                    and t.assigned_worker_id not in active_worker_ids
                ),
                "Worker became inactive during processing",
            )

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

    # ------------------------------------------------------------------
    # Queue browsing & management (for the Processing Queue dashboard)
    # ------------------------------------------------------------------

    def get_tasks_by_status(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
        worker_id: Optional[str] = None,
    ) -> Tuple[List[Task], int]:
        """Return tasks filtered by *status* and/or *worker_id*, newest-first.

        Args:
            status: Filter to a single status, or ``None`` for all.
            limit: Maximum tasks to return.
            offset: Number of tasks to skip (for pagination).
            worker_id: Filter to tasks assigned to this worker, or ``None`` for all.

        Returns:
            ``(tasks, total_count)`` where *total_count* is the full
            number of matching tasks (before limit/offset).
        """
        with self._lock:
            if status is not None:
                matching = [
                    t for t in self._tasks.values() if t.status == status
                ]
            else:
                matching = list(self._tasks.values())

            if worker_id is not None:
                matching = [
                    t for t in matching if t.assigned_worker_id == worker_id
                ]

            # Sort newest-first by created_at
            matching.sort(key=lambda t: t.created_at or datetime.min, reverse=True)
            total = len(matching)
            page = matching[offset : offset + limit]
            return page, total

    def get_workers_with_current_task(self) -> List[Tuple[Worker, Optional[Task]]]:
        """Return active workers paired with their current in-progress task.

        Workers whose heartbeat is older than 60 seconds are marked
        inactive and excluded from the result.
        """
        with self._lock:
            # Mark stale workers as inactive
            cutoff_time = datetime.now() - timedelta(seconds=60)
            for worker in self._workers.values():
                if worker.last_heartbeat < cutoff_time:
                    worker.is_active = False

            # Build a map: worker_id → in-progress task (if any)
            worker_task_map: Dict[str, Task] = {}
            for task in self._tasks.values():
                if (
                    task.status == TaskStatus.IN_PROGRESS
                    and task.assigned_worker_id
                ):
                    worker_task_map[task.assigned_worker_id] = task

            return [
                (worker, worker_task_map.get(worker.id))
                for worker in self._workers.values()
                if worker.is_active
            ]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a PENDING task.

        Only tasks that have not been picked up by a worker can be
        cancelled.  The task is marked as FAILED with a user-friendly
        error message.

        Returns:
            ``True`` if the task was cancelled, ``False`` otherwise.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != TaskStatus.PENDING:
                return False

            task.status = TaskStatus.FAILED
            task.error_message = "Cancelled by user"
            task.completed_at = datetime.now()

            # Remove from the pending list
            try:
                self._pending_tasks.remove(task_id)
            except ValueError:
                pass  # Already removed

            return True

    def _cleanup_orphan_files(self):
        """ Clean up any orphaned temporary files in the temp directory on startup. """
        try:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir)
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Temp dir recreated in: {self._temp_dir}")
        except Exception as e:
            logging.error(f"Failed to clean up temp dir {self._temp_dir}: {e}")
