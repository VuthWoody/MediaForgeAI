"""Unit tests for core.model_registry."""

import hashlib
from pathlib import Path

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, ValidationError
from core.model_registry import MODELS, ModelRegistry


def test_model_registry_specs() -> None:
    registry = ModelRegistry()
    assert "whisper-small" in MODELS
    assert "mdx-inst-hq3" in MODELS

    spec = registry.get_spec("whisper-small")
    assert spec.id == "whisper-small"
    assert spec.size_mb > 0
    assert len(spec.sha256) == 64


def test_model_registry_unknown_spec() -> None:
    registry = ModelRegistry()
    with pytest.raises(ValidationError):
        registry.get_spec("non_existent_model")


def test_model_checksum_verification(tmp_path: Path) -> None:
    registry = ModelRegistry(base_dir=tmp_path)
    sample_file = tmp_path / "sample.bin"
    sample_data = b"MediaForge Model Binary Data"
    sample_file.write_bytes(sample_data)

    correct_sha256 = hashlib.sha256(sample_data).hexdigest()
    wrong_sha256 = "0" * 64

    assert registry.verify_checksum(sample_file, correct_sha256)
    assert not registry.verify_checksum(sample_file, wrong_sha256)

    # Missing file returns False
    assert not registry.verify_checksum(tmp_path / "missing.bin", correct_sha256)


def test_model_availability_and_ensure(tmp_path: Path) -> None:
    registry = ModelRegistry(base_dir=tmp_path)

    # Initially missing
    assert not registry.is_available("whisper-small")

    # Call ensure with progress callback
    progress_calls: list[tuple[float, str]] = []
    path = registry.ensure(
        "whisper-small",
        progress_cb=lambda p, msg: progress_calls.append((p, msg)),
    )
    assert path == registry.get_path("whisper-small")
    assert len(progress_calls) == 1
    assert progress_calls[0][0] == 0.0

    # Create dummy model file at destination
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"dummy model")
    assert registry.is_available("whisper-small")

    progress_calls.clear()
    registry.ensure(
        "whisper-small",
        progress_cb=lambda p, msg: progress_calls.append((p, msg)),
    )
    assert progress_calls[0][0] == 1.0


def test_model_ensure_cancellation(tmp_path: Path) -> None:
    registry = ModelRegistry(base_dir=tmp_path)
    token = CancellationToken()
    token.cancel()

    with pytest.raises(CancelledError):
        registry.ensure("whisper-small", token=token)
