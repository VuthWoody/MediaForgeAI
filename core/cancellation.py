"""Hierarchical, thread-safe cancellation token mechanism."""

from __future__ import annotations

import threading
from collections.abc import Callable
from weakref import WeakSet

from core.exceptions import CancelledError


class CancellationToken:
    """Hierarchical, thread-safe cancellation token.

    A cancelled parent cancels all registered child tokens.
    Child cancellation does not propagate upward to parents.
    """

    def __init__(self, parent: CancellationToken | None = None) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._children: WeakSet[CancellationToken] = WeakSet()
        self._callbacks: list[Callable[[], None]] = []
        self._parent = parent

        if parent is not None:
            with parent._lock:
                if parent.is_cancelled:
                    self.cancel()
                else:
                    parent._children.add(self)

    def cancel(self) -> None:
        """Cancel this token and all descendant tokens."""
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            callbacks_to_run = list(self._callbacks)
            children_to_cancel = list(self._children)

        # Notify children outside our lock to prevent deadlock
        for child in children_to_cancel:
            child.cancel()

        # Execute registered cancellation callbacks
        for callback in callbacks_to_run:
            try:
                callback()
            except Exception:
                # Callbacks should not raise during cancellation cleanup
                pass

    @property
    def is_cancelled(self) -> bool:
        """Return True if this token or its parent has been cancelled."""
        if self._event.is_set():
            return True
        if self._parent is not None and self._parent.is_cancelled:
            # Propagate cancellation if parent was cancelled
            self.cancel()
            return True
        return False

    def throw_if_cancelled(self, message: str = "Operation was cancelled") -> None:
        """Raise CancelledError if cancellation has been requested."""
        if self.is_cancelled:
            raise CancelledError(message)

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when cancellation occurs."""
        with self._lock:
            if self._event.is_set():
                callback_now = True
            else:
                self._callbacks.append(callback)
                callback_now = False

        if callback_now:
            try:
                callback()
            except Exception:
                pass

    def create_child(self) -> CancellationToken:
        """Create a child token that will be cancelled if this token is cancelled."""
        return CancellationToken(parent=self)
