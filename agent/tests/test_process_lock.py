"""Tests for ProcessLock single-instance enforcement."""

from pathlib import Path

import pytest

from poscenter_loyalty_agent.process_lock import AgentAlreadyRunningError, ProcessLock


def test_process_lock_acquire_and_release(tmp_path: Path) -> None:
    lock_file = tmp_path / "test_agent.lock"
    lock = ProcessLock(lock_file)

    assert not lock.is_acquired
    lock.acquire()
    assert lock.is_acquired
    assert lock_file.exists()

    lock.release()
    assert not lock.is_acquired


def test_process_lock_mutual_exclusion(tmp_path: Path) -> None:
    lock_file = tmp_path / "test_agent.lock"
    lock1 = ProcessLock(lock_file)
    lock2 = ProcessLock(lock_file)

    lock1.acquire()

    # Second instance attempting to acquire must fail
    with pytest.raises(AgentAlreadyRunningError, match="AGENT_ALREADY_RUNNING"):
        lock2.acquire()

    # Release first, now second can acquire
    lock1.release()
    lock2.acquire()
    assert lock2.is_acquired
    lock2.release()


def test_process_lock_context_manager(tmp_path: Path) -> None:
    lock_file = tmp_path / "test_agent.lock"

    with ProcessLock(lock_file) as lock:
        assert lock.is_acquired

    # Released after block
    assert not lock.is_acquired
