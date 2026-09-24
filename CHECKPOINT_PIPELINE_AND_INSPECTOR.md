# MediaForge AI — Checkpoint Report: Pipeline & Inspector Synchronization

**Date:** 2026-09-24  
**Project:** MediaForge AI  
**Scope:** Pipeline Recompute Flow, Text-Aware TTS Invalidation, Timeline & Script Inspector Synchronization  

---

## 1. Issue: Pipeline Jumping to 76% (Skipping Translation / Dubbing) — [RESOLVED & LOCKED]

### Root Cause
1. In `modules/processing/pipeline.py`, Stages 1 through 7 (Inspect, Audio Extraction, Whisper STT, Diarization, Stem Separation, Translation, and TTS) checked for existing output files on disk.
2. When all files from a previous run existed, Stages 1–7 completed in under 15ms.
3. Stage 8 (Audio Alignment) begins at progress 0.76 (76%). Consequently, clicking "Run Full Pipeline" appeared to skip straight to 76%, ignoring any user desire to re-translate or re-dub.
4. Furthermore, Stage 7 checked only `if not out_clip.exists()`, failing to verify whether the translation text (`seg.target_text`) had been modified in Inspector mode. Hence, edited translations were never re-synthesized into audio.

### Resolutions
1. **Added `🔄 Fresh Dubbing (0%)` Mode (`ui/views/studio_view.py`):**
   - Added `self.chk_fresh = QCheckBox("🔄 Fresh Dubbing (0%)")` directly in the AI Studio Auto-Process control strip.
   - When checked, `PipelineConfig.force_recompute = True` is passed to `PipelineEngine.run()`, forcing the entire pipeline to re-transcribe, re-translate, and re-synthesize all dialogue from 0% from scratch.
2. **Text-Aware TTS Manifest Invalidation (`modules/processing/pipeline.py`):**
   - Implemented `.clips_text_manifest.json` in `tts_clips/` to store the exact text, speaker, and emotion for every generated clip:
     ```json
     {
       "1": {
         "text": "ការសន្ទនាភាសាអង់គ្លេសរវាងមិត្តពីរនាក់",
         "speaker": "Speaker 1 (Mature Female)",
         "emotion": "normal"
       }
     }
     ```
   - When Stage 7 iterates over segments, if `text_to_speak`, `speaker`, or `emotion` differs from the manifest, the pipeline **automatically deletes the stale audio clip and synthesizes fresh audio** with VoxCPM2 / Neural TTS.
   - Stage 6 respects `force_recompute` by re-translating cleanly through the configured provider (`libre`, `gemini`, `deepseek`, or `qwen`).

---

## 2. Feature: Inspector Mode Video Editor Actions & Replacement — [COMPLETED & VERIFIED]

### Architecture & UI Implementations
In [`ui/views/script_inspector.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/ui/views/script_inspector.py) and [`ui/views/studio_view.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/ui/views/studio_view.py):

1. **Per-Sentence `📥 Replace` Action Column:**
   - Added an **`📥 Editor`** column (Column 7) to `ScriptInspectorWidget.table`.
   - Each row features an **`📥 Replace`** button with interactive hover and visual confirmation states.
   - Clicking `📥 Replace`:
     - Reads the current edited translation from Column 5 (`🌐 Translation`), speaker from Column 2 (`🗣️ Speaker`), and timestamp from Column 1 (`⏱️ Timestamp`).
     - Parses timestamp strings flexibly via `_parse_timestamp_range` (supports `MM:SS.cc → MM:SS.cc`, `5.5 -> 9.2`, etc.).
     - Emits `segment_replaced = Signal(object)` to `StudioView`.
     - Updates the **Dubbed Dialogue** track and **Subtitles** track in `MultiTrackTimelineWidget` in real time.
     - Updates `video_player.controller.subtitles` and seeks the player to `start_ms` so the new translation immediately overlays the video canvas.
     - Automatically deletes the corresponding `tts_*.wav` file in `tts_clips/` so the next dubbing run synthesizes the new line.
     - Provides instant button visual feedback: transitions to `✅ Replaced!` with green styling for 1.5 seconds.

2. **`📥 Replace All in Editor` Toolbar Button:**
   - Added `self.replace_all_btn = QPushButton("📥 Replace All in Editor")` in the Inspector top toolbar.
   - Clicking `📥 Replace All in Editor`:
     - Iterates through all rows, updating all segments' translations, speakers, and timestamps.
     - Saves the full transcript back to `translated_*.json`.
     - Invalidates old TTS clips for modified lines.
     - Emits `replace_all_requested = Signal(object)` and `transcript_updated = Signal(object)`.
     - Replaces all timeline clips and rebuilds `controller.subtitles` for the entire video.
     - Displays confirmation: button transforms to `✅ All Replaced!` and stats badge updates to `✅ Synced to Video Editor`.

3. **Editable Timestamps in Inspector:**
   - Made Column 1 (`⏱️ Timestamp`) editable in place (`Qt.ItemFlag.ItemIsEditable`).
   - Double-clicking timestamp cells enables direct typing without accidentally triggering player seeking.

4. **Timeline Subtitle Track Enhancement ([`ui/components/timeline.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/ui/components/timeline.py)):**
   - Subtitle track clips now display `target_text or text` so translated dialogue renders visually on the timeline blocks.
   - Added `update_segment_clip(seg_id, label, start_ms, end_ms, speaker)` to `TimelineCanvas` and `MultiTrackTimelineWidget`.

---

## 3. Unit Test Verification & Code Quality

- **Unit Test Suite:**
  - `pytest tests/unit/ -v`: **145 passed (100% green)**
  - `tests/unit/test_script_inspector.py`: Validated single-sentence replace, replace-all, clip invalidation, and timestamp parsing.
  - `tests/unit/test_timeline.py`: Validated `update_segment_clip` on dialogue and subtitle tracks.
  - `tests/unit/test_pipeline.py`: Validated `.clips_text_manifest.json` invalidation and `force_recompute`.
- **Linter & Formatting:**
  - `ruff check`: **All checks passed!** Zero errors or warnings.

---

## 4. Summary of Saved State for Tomorrow
- **Workspace:** `c:\Users\sakpo\OneDrive\Desktop\Tool\MediaForgeAI`
- **All Previous Issues (A, B, C):** Resolved, tested, and locked in this checkpoint.
- **Ready for Next Session:** The pipeline cleanly supports both fast incremental runs and 0% fresh re-runs, and Inspector Mode seamlessly synchronizes with the video editor timeline and subtitle overlay with one-click per sentence or batch replacement.
