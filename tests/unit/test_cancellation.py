"""Unit tests for core.cancellation."""

import threading
import time

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, MediaForgeError


def test_token_initially_not_cancelled() -> None:
    token = CancellationToken()
    assert not token.is_cancelled
    # Should not raise
    token.throw_if_cancelled()


def test_token_cancellation() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled

    with pytest.raises(CancelledError) as exc_info:
        token.throw_if_cancelled("Custom cancel message")
    assert "Custom cancel message" in str(exc_info.value)
    assert isinstance(exc_info.value, MediaForgeError)


def test_repeated_cancel_is_idempotent() -> None:
    token = CancellationToken()
    token.cancel()
    token.cancel()
    assert token.is_cancelled


def test_hierarchical_cancellation_parent_to_child() -> None:
    parent = CancellationToken()
    child1 = parent.create_child()
    child2 = CancellationToken(parent=parent)
    grandchild = child1.create_child()

    assert not child1.is_cancelled
    assert not child2.is_cancelled
    assert not grandchild.is_cancelled

    parent.cancel()

    assert parent.is_cancelled
    assert child1.is_cancelled
    assert child2.is_cancelled
    assert grandchild.is_cancelled


def test_hierarchical_cancellation_child_does_not_cancel_parent() -> None:
    parent = CancellationToken()
    child = parent.create_child()

    child.cancel()

    assert child.is_cancelled
    assert not parent.is_cancelled


def test_child_created_from_already_cancelled_parent() -> None:
    parent = CancellationToken()
    parent.cancel()

    child = parent.create_child()
    assert child.is_cancelled


def test_cancellation_callbacks() -> None:
    token = CancellationToken()
    called = []

    def cb1() -> None:
        called.append("cb1")

    def cb2() -> None:
        raise RuntimeError("Callback failure should be caught")

    def cb3() -> None:
        called.append("cb3")

    token.register_callback(cb1)
    token.register_callback(cb2)
    token.register_callback(cb3)

    token.cancel()
    assert called == ["cb1", "cb3"]


def test_callback_registered_after_cancellation() -> None:
    token = CancellationToken()
    token.cancel()

    called = []
    token.register_callback(lambda: called.append("late"))
    assert called == ["late"]


def test_multithreaded_cancellation() -> None:
    token = CancellationToken()
    thread_caught = threading.Event()

    def worker() -> None:
        try:
            while True:
                token.throw_if_cancelled()
                time.sleep(0.01)
        except CancelledError:
            thread_caught.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    time.sleep(0.05)
    token.cancel()
    t.join(timeout=1.0)

    assert thread_caught.is_set()
