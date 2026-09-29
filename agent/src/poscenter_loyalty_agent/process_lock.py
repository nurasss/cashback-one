"""Process singleton lock to prevent multiple agent instances from running concurrently."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentAlreadyRunningError(RuntimeError):
    """Raised when another agent instance holds the process lock."""

    def __init__(self, message: str = "AGENT_ALREADY_RUNNING: Another agent instance is already active.") -> None:
        super().__init__(message)
        self.code = "AGENT_ALREADY_RUNNING"


class ProcessLock:
    """Manages an exclusive lock file to guarantee single-instance execution.

    Supports POSIX (fcntl.flock) and Windows (msvcrt.locking).
    """

    def __init__(self, lock_file_path: Path) -> None:
        self.lock_file_path = lock_file_path
        self._file_handle: Any = None
        self._acquired = False

    @property
    def is_acquired(self) -> bool:
        return self._acquired

    def acquire(self) -> None:
        """Acquire exclusive lock on lock_file_path or raise AgentAlreadyRunningError."""
        if self._acquired:
            return

        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Open for reading and writing, create if not exists
            self._file_handle = open(self.lock_file_path, "a+b")
        except OSError as exc:
            raise AgentAlreadyRunningError(f"AGENT_ALREADY_RUNNING: Could not open lock file: {exc}") from exc

        if sys.platform == "win32":
            import msvcrt

            try:
                # Seek to start
                self._file_handle.seek(0)
                # Try locking 1 byte non-blocking
                msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                self._close_handle()
                raise AgentAlreadyRunningError(
                    f"AGENT_ALREADY_RUNNING: Windows lock file {self.lock_file_path} is held by another process: {exc}"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as exc:
                self._close_handle()
                raise AgentAlreadyRunningError(
                    f"AGENT_ALREADY_RUNNING: Unix lock file {self.lock_file_path} is held by another process: {exc}"
                ) from exc

        # Write current PID
        try:
            self._file_handle.seek(0)
            self._file_handle.truncate(0)
            self._file_handle.write(f"{os.getpid()}\n".encode())
            self._file_handle.flush()
        except OSError:
            pass

        self._acquired = True
        logger.debug("Acquired process lock on %s (PID=%s)", self.lock_file_path, os.getpid())

    def release(self) -> None:
        """Release the lock and close handle."""
        if not self._acquired or not self._file_handle:
            return

        try:
            if sys.platform == "win32":
                import msvcrt

                try:
                    self._file_handle.seek(0)
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                try:
                    fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            self._close_handle()
            self._acquired = False
            logger.debug("Released process lock on %s", self.lock_file_path)

    def _close_handle(self) -> None:
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:
                pass
            self._file_handle = None

    def __enter__(self) -> ProcessLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()
