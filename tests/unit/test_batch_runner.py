"""Unit tests for BatchRunner and GPU HW acceleration (Phase 11)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.cancellation import CancellationToken
from modules.batch.batch_runner import BatchItem, BatchItemStatus, BatchRunner, BatchSummary


def test_batch_runner_initialization() -> None:
    runner = BatchRunner()
    assert "GPU_EXCLUSIVE" in runner.resource_lock.LOCKS
    enc = runner.detect_best_encoder()
    assert enc in ["h264_nvenc", "hevc_nvenc", "h264_amf", "h264_qsv", "libx264"]


def test_batch_runner_execution_mocked() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        video1 = tmp_path / "vid1.mp4"
        video2 = tmp_path / "vid2.mp4"
        video1.write_bytes(b"dummy1")
        video2.write_bytes(b"dummy2")

        items = [
            BatchItem(id="1", video_path=video1, target_lang="km"),
            BatchItem(id="2", video_path=video2, target_lang="en"),
        ]

        runner = BatchRunner(output_dir=tmp_path)

        with patch("modules.batch.batch_runner.PipelineEngine") as MockEngine:
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.output_video_path = tmp_path / "out.mp4"
            mock_inst.run.return_value = mock_res
            MockEngine.return_value = mock_inst

            summary: BatchSummary = runner.run_batch(items, encoder="libx264")

            assert summary.total_items == 2
            assert summary.completed_items == 2
            assert summary.failed_items == 0
            assert summary.hardware_encoder_used == "libx264"
            assert summary.peak_memory_mb >= 0.0

            assert items[0].status == BatchItemStatus.COMPLETED
            assert items[1].status == BatchItemStatus.COMPLETED


def test_batch_runner_cancellation() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        video1 = tmp_path / "vid1.mp4"
        video1.write_bytes(b"dummy1")

        items = [BatchItem(id="1", video_path=video1)]
        runner = BatchRunner(output_dir=tmp_path)

        token = CancellationToken()
        token.cancel()

        summary = runner.run_batch(items, token=token)
        assert items[0].status == BatchItemStatus.CANCELLED
        assert summary.completed_items == 0
