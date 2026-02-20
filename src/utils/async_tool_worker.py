"""Async Tool Worker - Background execution for non-blocking tool calls.

Architecture:
- Voice agent dispatches tool requests to a queue
- Worker processes tools in background
- Results published via LiveKit data channel
- Agent can continue conversation while tools execute

This eliminates awkward silence during long-running operations like:
- Sending emails (15-30s)
- Database queries (5-10s)
- Google Drive operations (5-15s)
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from livekit import rtc

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolTask:
    """A tool execution task."""
    task_id: str
    tool_name: str
    tool_func: Callable[..., Coroutine[Any, Any, str]]
    kwargs: dict
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[float] = None


class AsyncToolWorker:
    """Background worker for async tool execution.

    Usage:
        worker = AsyncToolWorker(room)
        worker.on_result = my_callback  # Direct callback for results
        await worker.start()

        # Dispatch a tool (returns immediately)
        task_id = await worker.dispatch(
            tool_name="send_email",
            tool_func=send_email_impl,
            kwargs={"to": "user@example.com", "subject": "Hello"}
        )

        # Worker executes in background, calls on_result when done
    """

    def __init__(
        self,
        room: rtc.Room,
        max_concurrent: int = 3,
        result_topic: str = "tool_result",
    ):
        self.room = room
        self.max_concurrent = max_concurrent
        self.result_topic = result_topic

        self._queue: asyncio.Queue[ToolTask] = asyncio.Queue()
        self._tasks: dict[str, ToolTask] = {}
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Direct callback for results (avoids data channel self-publish issue)
        self.on_result: Optional[Callable[[dict], Coroutine[Any, Any, None]]] = None

    async def start(self) -> None:
        """Start the background worker pool."""
        if self._running:
            return

        self._running = True

        # Start worker coroutines
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(
                self._worker_loop(worker_id=i),
                name=f"tool_worker_{i}"
            )
            self._workers.append(worker)

        logger.info(f"AsyncToolWorker started with {self.max_concurrent} workers")

    async def stop(self) -> None:
        """Stop all workers gracefully."""
        self._running = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for cancellation
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("AsyncToolWorker stopped")

    async def dispatch(
        self,
        tool_name: str,
        tool_func: Callable[..., Coroutine[Any, Any, str]],
        kwargs: dict,
    ) -> str:
        """Dispatch a tool for background execution.

        Returns immediately with task_id. Result will be published to room.

        Args:
            tool_name: Human-readable name for logging/announcements
            tool_func: Async function to execute
            kwargs: Arguments for the tool function

        Returns:
            task_id: Unique identifier for tracking
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        task = ToolTask(
            task_id=task_id,
            tool_name=tool_name,
            tool_func=tool_func,
            kwargs=kwargs,
        )

        self._tasks[task_id] = task
        await self._queue.put(task)

        logger.info(f"[TOOL_CALL] Dispatched: {tool_name} task_id={task_id}")

        return task_id

    def get_task_status(self, task_id: str) -> Optional[ToolTask]:
        """Get the current status of a task."""
        return self._tasks.get(task_id)

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop that processes tasks from queue."""
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                # Wait for a task with timeout (allows graceful shutdown)
                try:
                    task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Execute the tool
                await self._execute_task(task, worker_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    async def _execute_task(self, task: ToolTask, worker_id: int) -> None:
        """Execute a single task and publish result."""
        task.status = TaskStatus.RUNNING
        start_time = time.time()

        logger.info(f"[TOOL_CALL] Executing: {task.tool_name} task_id={task.task_id} worker={worker_id}")

        try:
            async with self._semaphore:
                # Execute the actual tool function
                result = await task.tool_func(**task.kwargs)

                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = time.time()

                duration = task.completed_at - start_time
                logger.info(
                    f"[TOOL_CALL] Completed: {task.tool_name} "
                    f"duration={duration:.1f}s result={result[:120]}"
                )

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()

            logger.error(f"[TOOL_CALL] Failed: {task.tool_name} error={e}")

        # Publish result to room
        await self._publish_result(task)

    async def _publish_result(self, task: ToolTask) -> None:
        """Notify result via callback and publish to room data channel."""
        # Build result message
        message = {
            "type": "tool_result",
            "task_id": task.task_id,
            "tool_name": task.tool_name,
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
            "duration_ms": int((task.completed_at - task.created_at) * 1000)
                if task.completed_at else None,
        }

        # Primary notification: Direct callback (avoids data channel self-publish issue)
        if self.on_result:
            try:
                await self.on_result(message)
                logger.debug(f"Callback notified for {task.task_id}")
            except Exception as e:
                logger.error(f"Callback failed for {task.task_id}: {e}")

        # Secondary: Also publish to room for external listeners (UI, etc.)
        try:
            if self.room.local_participant:
                data = json.dumps(message).encode("utf-8")
                await self.room.local_participant.publish_data(
                    data,
                    topic=self.result_topic,
                )
                logger.debug(f"Published result for {task.task_id}")
        except Exception as e:
            logger.error(f"Failed to publish result: {e}")


# Singleton instance (initialized in agent.py)
_worker_instance: Optional[AsyncToolWorker] = None


def get_worker() -> Optional[AsyncToolWorker]:
    """Get the global worker instance."""
    return _worker_instance


def set_worker(worker: AsyncToolWorker) -> None:
    """Set the global worker instance."""
    global _worker_instance
    _worker_instance = worker
