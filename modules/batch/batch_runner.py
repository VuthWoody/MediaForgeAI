"""Batch runner with GPU hardware acceleration, ResourceLock gating, and memory leak tracking (Phase 11)."""

from __future__ import annotations

import logging
import subprocess
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.cancellation import CancellationToken
from core.resource_lock import ResourceLock
from modules.processing.pipeline import PipelineConfig, PipelineEngine, PipelineResult

logger = logging.getLogger("mediaforge.batch")


class BatchItemStatus(StrEnum):
    """Execution status of an item in the batch queue."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchItem:
    """Represents a single media task in a batch execution."""

    id: str
    video_path: Path
    target_lang: str = "km"
    translation_provider: str = "libre"
    status: BatchItemStatus = BatchItemStatus.QUEUED
    progress: float = 0.0
    status_message: str = "Queued"
    output_path: Path | None = None
    error_message: str | None = None
    elapsed_sec: float = 0.0


@dataclass
class BatchSummary:
    """Summary metrics of a completed batch execution."""

    total_items: int
    completed_items: int
    failed_items: int
    total_elapsed_sec: float
    peak_memory_mb: float
    hardware_encoder_used: str


class BatchRunner:
    """Runs a sequential batch of Auto-Process pipelines bounded by GPU ResourceLock."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = (
            Path(output_dir).resolve()
            if output_dir
            else Path.home() / "AppData" / "Local" / "MediaForgeAI" / "batch_exports"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.resource_lock = ResourceLock()
        self._detected_encoder: str | None = None

    def detect_best_encoder(self) -> str:
        """Probe available FFmpeg hardware encoders with a quick trial encode."""
        if self._detected_encoder:
            return self._detected_encoder

        candidates = [
            "h264_nvenc",
            "hevc_nvenc",
            "av1_nvenc",
            "h264_amf",
            "h264_qsv",
            "libx264",
        ]

        for enc in candidates:
            if enc == "libx264":
                self._detected_encoder = "libx264"
                return "libx264"

            cmd = [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "nullsrc=s=128x128:d=0.2",
                "-c:v",
                enc,
                "-f",
                "null",
                "-",
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=5)
                if res.returncode == 0:
                    logger.info("BatchRunner: Hardware encoder confirmed: %s", enc)
                    self._detected_encoder = enc
                    return enc
            except Exception:
                continue

        self._detected_encoder = "libx264"
        return "libx264"

    def run_batch(
        self,
        items: list[BatchItem],
        encoder: str = "auto",
        token: CancellationToken | None = None,
        item_callback: Callable[[BatchItem], None] | None = None,
        total_progress: Callable[[float, str], None] | None = None,
    ) -> BatchSummary:
        """Process all queued batch items sequentially without GPU OOM or memory leaks."""
        token = token or CancellationToken()
        chosen_encoder = self.detect_best_encoder() if encoder == "auto" else encoder

        tracemalloc.start()
        start_time = time.time()
        completed = 0
        failed = 0
        total = len(items)

        logger.info("Starting batch of %d items using encoder %s", total, chosen_encoder)

        for idx, item in enumerate(items):
            if token.is_cancelled:
                item.status = BatchItemStatus.CANCELLED
                item.status_message = "Cancelled"
                if item_callback:
                    item_callback(item)
                continue

            item.status = BatchItemStatus.PROCESSING
            item.status_message = "Starting..."
            if item_callback:
                item_callback(item)

            if total_progress:
                total_progress(idx / total, f"Processing item {idx + 1}/{total}: {item.video_path.name}")

            item_start = time.time()

            # Acquire GPU exclusive lock to avoid concurrent model thrashing
            with self.resource_lock.hold("GPU_EXCLUSIVE", token=token):
                try:
                    pipeline = PipelineEngine()
                    config = PipelineConfig(
                        video_path=item.video_path,
                        output_dir=self.output_dir,
                        target_lang=item.target_lang,
                        translation_provider=item.translation_provider,
                        encoder=chosen_encoder,
                    )

                    current_item = item

                    def sub_prog(prog: float, msg: str, target: BatchItem = current_item) -> None:
                        target.progress = prog
                        target.status_message = msg
                        if item_callback:
                            item_callback(target)

                    res: PipelineResult = pipeline.run(config, token=token, progress=sub_prog)

                    item.status = BatchItemStatus.COMPLETED
                    item.output_path = res.output_video_path
                    item.status_message = "Completed"
                    item.progress = 1.0
                    item.elapsed_sec = time.time() - item_start
                    completed += 1
                except Exception as e:
                    logger.exception("Batch item %s failed: %s", item.id, e)
                    item.status = BatchItemStatus.FAILED
                    item.error_message = str(e)
                    item.status_message = f"Error: {e}"
                    item.elapsed_sec = time.time() - item_start
                    failed += 1

            if item_callback:
                item_callback(item)

        total_elapsed = time.time() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak_mem / (1024 * 1024)

        if total_progress:
            total_progress(1.0, f"Batch complete: {completed} succeeded, {failed} failed.")

        return BatchSummary(
            total_items=total,
            completed_items=completed,
            failed_items=failed,
            total_elapsed_sec=total_elapsed,
            peak_memory_mb=round(peak_mb, 2),
            hardware_encoder_used=chosen_encoder,
        )
