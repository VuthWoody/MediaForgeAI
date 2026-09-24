"""Unit tests for core.resource_lock."""

import threading
import time

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, ValidationError
from core.resource_lock import ResourceLock


def test_resource_lock_acquire_and_release() -> None:
    res_lock = ResourceLock()
    assert not res_lock.is_locked("GPU_EXCLUSIVE")

    acquired = res_lock.acquire("GPU_EXCLUSIVE", timeout=1.0)
    assert acquired
    assert res_lock.is_locked("GPU_EXCLUSIVE")

    res_lock.release("GPU_EXCLUSIVE")
    assert not res_lock.is_locked("GPU_EXCLUSIVE")


def test_resource_lock_unknown_name() -> None:
    res_lock = ResourceLock()
    with pytest.raises(ValidationError):
        res_lock.acquire("NON_EXISTENT_LOCK")


def test_resource_lock_context_manager() -> None:
    res_lock = ResourceLock()
    with res_lock.hold("CPU_HEAVY"):
        assert res_lock.is_locked("CPU_HEAVY")
    assert not res_lock.is_locked("CPU_HEAVY")


def test_resource_lock_timeout_blocking() -> None:
    res_lock = ResourceLock()
    assert res_lock.acquire("NETWORK_BULK")

    acquired_in_thread = []

    def second_thread() -> None:
        result = res_lock.acquire("NETWORK_BULK", timeout=0.2)
        acquired_in_thread.append(result)

    t = threading.Thread(target=second_thread)
    t.start()
    t.join(timeout=1.0)

    assert acquired_in_thread == [False]
    res_lock.release("NETWORK_BULK")


def test_resource_lock_cancellation_aware() -> None:
    res_lock = ResourceLock()
    assert res_lock.acquire("GPU_EXCLUSIVE")

    token = CancellationToken()
    exception_caught = []

    def cancelling_thread() -> None:
        try:
            res_lock.acquire("GPU_EXCLUSIVE", timeout=2.0, token=token)
        except CancelledError as e:
            exception_caught.append(e)

    t = threading.Thread(target=cancelling_thread)
    t.start()

    time.sleep(0.15)
    token.cancel()
    t.join(timeout=1.0)

    assert len(exception_caught) == 1
    res_lock.release("GPU_EXCLUSIVE")


def test_hold_context_manager_timeout() -> None:
    res_lock = ResourceLock()
    res_lock.acquire("CPU_HEAVY")

    with pytest.raises(TimeoutError):
        with res_lock.hold("CPU_HEAVY", timeout=0.1):
            pass

    res_lock.release("CPU_HEAVY")
