"""Named mutex system for shared hardware and network resources."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import ClassVar

from core.cancellation import CancellationToken
from core.exceptions import ValidationError


class ResourceLock:
    """Named mutex for shared resources with cancellation-aware acquisition."""

    LOCKS: ClassVar[tuple[str, ...]] = ("GPU_EXCLUSIVE", "CPU_HEAVY", "NETWORK_BULK")

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {name: threading.Lock() for name in self.LOCKS}
        self._meta_lock = threading.Lock()

    def _get_lock(self, name: str) -> threading.Lock:
        with self._meta_lock:
            if name not in self._locks:
                if name not in self.LOCKS:
                    raise ValidationError(f"Unknown resource lock: '{name}'. Must be one of {self.LOCKS}")
                self._locks[name] = threading.Lock()
            return self._locks[name]

    def is_locked(self, name: str) -> bool:
        """Check whether the named resource is currently locked."""
        lock = self._get_lock(name)
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
            return False
        return True

    def acquire(
        self,
        name: str,
        timeout: float | None = None,
        token: CancellationToken | None = None,
    ) -> bool:
        """Acquire a named lock, polling cancellation token every 100 ms.

        Args:
            name: Resource lock name (e.g. 'GPU_EXCLUSIVE', 'CPU_HEAVY', 'NETWORK_BULK').
            timeout: Maximum seconds to wait. None means wait indefinitely.
            token: Optional cancellation token. If cancelled, raises CancelledError.

        Returns:
            True if acquired, False if timed out without acquisition.
        """
        lock = self._get_lock(name)
        start_time = time.monotonic()
        poll_interval = 0.1  # 100 ms

        while True:
            if token is not None:
                token.throw_if_cancelled()

            # Determine slice timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    return False
                wait_time = min(poll_interval, remaining)
            else:
                wait_time = poll_interval

            # Try to acquire lock with short slice
            acquired = lock.acquire(blocking=True, timeout=wait_time)
            if acquired:
                return True

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

    def release(self, name: str) -> None:
        """Release the named lock."""
        lock = self._get_lock(name)
        try:
            lock.release()
        except RuntimeError:
            # Lock was not held by the current thread or already released
            pass

    @contextmanager
    def hold(
        self,
        name: str,
        timeout: float | None = None,
        token: CancellationToken | None = None,
    ) -> Generator[None, None, None]:
        """Context manager to acquire and release a resource lock."""
        acquired = self.acquire(name=name, timeout=timeout, token=token)
        if not acquired:
            raise TimeoutError(f"Failed to acquire resource lock '{name}' within timeout of {timeout}s")
        try:
            yield
        finally:
            self.release(name)
