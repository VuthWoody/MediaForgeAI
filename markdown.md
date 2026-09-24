MEDIAFORGE AI — ANTIGRAVITY BUILD PROMPT
Version 1.0 — Free Stack Edition
Target: Windows 10/11 x64
Stack: Python 3.11+, PySide6, FFmpeg, faster-whisper, MDX-Net ONNX, SQLite, Playwright
APIs: Gemini, DeepSeek, Qwen (all free tier)
Constraint: Zero recurring cost. Free-tier or open-source only.

================================================================================
SECTION 0 — OPERATING RULES FOR THE AGENT
================================================================================

1. Never skip phases. Each phase ends with a runnable demo and a hard gate.
2. Never introduce a paid dependency. If a package requires a paid license or
   subscription, stop and ask.
3. Never bundle AI models in the installer. Models download on first use with a
   progress UI.
4. Never block the UI thread. All work runs in QThread, QProcess, or a worker
   subprocess.
5. Every engine is cancellable. Cancellation tokens are passed to every
   long-running function.
6. Every external provider is behind an adapter. Core code never imports
   google.generativeai, openai, or edge_tts directly.
7. Every phase produces a test. Pytest coverage for each engine's contract.
8. Log everything to %LOCALAPPDATA%/MediaForgeAI/logs/. Rotating, redacted,
   10 MB × 5 files.
9. Never commit secrets. Use keyring for API keys; .env files are forbidden.
10. Ask before making a schema-breaking change. Project files are versioned;
    migrations must be written.

================================================================================
SECTION 1 — PROJECT IDENTITY
================================================================================

Name                : MediaForge AI
Version             : 1.0.0-dev
License             : MIT (app); FFmpeg LGPL build; Noto fonts OFL
Target              : Windows 10/11 x64
Python              : 3.11+
UI Framework        : PySide6 6.7+
Installer Size      : < 200 MB
Recurring Cost      : $0 (free-tier APIs + local models)

================================================================================
SECTION 2 — DESIGN PRINCIPLES (NON-NEGOTIABLE)
================================================================================

P1 — Cancellable:
     Every long-running engine accepts a CancellationToken.

P2 — Adapter-based:
     Gemini, DeepSeek, Qwen, Edge-TTS sit behind modules/ai/providers/.
     Core code never imports provider SDKs directly.

P3 — Playback-decoupled:
     The player reads files from disk. It does not know pipeline state.

P4 — GPU-serialized:
     All GPU-heavy jobs acquire ResourceLock("GPU_EXCLUSIVE").

P5 — Versioned projects:
     .mfproj files carry schema_version. Migrations live in core/migrations/.

P6 — Models downloaded, not bundled:
     core/model_registry.py orchestrates first-run pulls with progress UI.

P7 — Vertical slices:
     Each phase delivers a demoable artifact end-to-end. No horizontal
     infrastructure-only phases after Phase 0.

================================================================================
SECTION 3 — FREE STACK (LOCKED DECISIONS)
================================================================================

COMPONENT           PRIMARY                     FALLBACK                    NOTES
------------------  --------------------------  --------------------------  ------------------------------------
Transcription       faster-whisper small        faster-whisper large-v3-    CPU-friendly, 4-5x faster than
                                                turbo (opt-in)              reference Whisper
Diarization         Voice-embedding clustering  pyannote (opt-in, HF token) Fully offline after model download
Stem Separation     MDX-Net ONNX                htdemucs_ft (GPU only)      Demucs on CPU disabled in UI
                    UVR-MDX-NET-Inst_HQ_3
Translation         Gemini 2.0 Flash            DeepSeek -> Qwen ->         Provider adapter pattern
                                                LibreTranslate
TTS (general)       Gemini 2.5 Flash TTS        Qwen3-TTS-Flash ->          Gemini free tier: 10 req/day
                                                Edge-TTS
TTS (Khmer)         Edge-TTS Khmer neural       Qwen LiveTranslate          Piper excluded - no Khmer voice
TTS (Chinese)       Qwen3-TTS-Flash             Edge-TTS                    1M free chars (90 days)
Player              QMediaPlayer + FrameCache   libmpv (future, optional)   No libmpv bundling in v1.0
Job Persistence     SQLite (WAL mode)           -                           stdlib, no dependency
Secrets             keyring -> Windows          -                           Never write API keys to disk
                    Credential Locker
Installer           PyInstaller + Inno Setup    -                           Single-click 64-bit installer

3.1 TTS ROUTING TABLE (LOCKED)

    def route_tts(target_lang):
        if target_lang == "km":
            return ["edge", "qwen"]
        if target_lang == "zh":
            return ["qwen", "edge", "gemini"]
        return ["gemini", "qwen", "edge"]

3.2 TRANSLATION ROUTING TABLE (LOCKED)

    def route_translate():
        return ["gemini", "deepseek", "qwen", "libre"]

================================================================================
SECTION 4 — DIRECTORY STRUCTURE
================================================================================

Create exactly this layout. Do not deviate.

MediaForgeAI/
├── app.py
├── requirements.txt
├── pyproject.toml
├── README.md
├── .gitignore
├── config/
│   ├── settings.json
│   └── constants.py
├── core/
│   ├── __init__.py
│   ├── event_bus.py
│   ├── hardware.py
│   ├── project_manager.py
│   ├── storage.py
│   ├── resource_lock.py
│   ├── cancellation.py
│   ├── job_queue.py
│   ├── config_store.py
│   ├── logging_config.py
│   ├── exceptions.py
│   ├── model_registry.py
│   ├── updater.py
│   └── migrations/
│       ├── __init__.py
│       └── v1_to_v2.py
├── modules/
│   ├── __init__.py
│   ├── downloader/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── scraper.py
│   │   ├── queue_manager.py
│   │   └── organizer.py
│   ├── media/
│   │   ├── __init__.py
│   │   ├── player_controller.py
│   │   ├── frame_cache.py
│   │   ├── inspector.py
│   │   └── waveform.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── separator.py
│   │   ├── transcriber.py
│   │   ├── diarizer.py
│   │   ├── director.py
│   │   ├── voice_generator.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── gemini_tts.py
│   │       ├── qwen_tts.py
│   │       ├── edge_tts.py
│   │       ├── gemini_translate.py
│   │       ├── deepseek_translate.py
│   │       ├── qwen_translate.py
│   │       └── libre_translate.py
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── aligner.py
│   │   ├── mixer.py
│   │   ├── subtitle.py
│   │   └── pipeline.py
│   └── batch/
│       ├── __init__.py
│       └── batch_runner.py
├── ui/
│   ├── __init__.py
│   ├── styles/
│   │   └── theme.qss
│   ├── components/
│   │   ├── __init__.py
│   │   ├── sidebar.py
│   │   ├── resource_bar.py
│   │   ├── timeline.py
│   │   ├── video_player.py
│   │   └── toast.py
│   └── views/
│       ├── __init__.py
│       ├── dashboard_view.py
│       ├── downloader_view.py
│       ├── library_view.py
│       ├── studio_view.py
│       ├── batch_view.py
│       └── settings_view.py
├── tests/
│   ├── unit/
│   └── integration/
├── scripts/
│   ├── phase0_demo.py
│   ├── ci.sh
│   └── build_installer.py
└── resources/
    ├── fonts/
    │   ├── NotoSans-Regular.ttf
    │   ├── NotoSans-Bold.ttf
    │   └── NotoSansKhmer-Regular.ttf
    ├── models/
    │   └── manifest.json
    └── ffmpeg/
        ├── ffmpeg.exe
        └── ffprobe.exe

================================================================================
SECTION 5 — CROSS-CUTTING SUBSYSTEMS (BUILD FIRST, PHASE 0)
================================================================================

5.1 core/cancellation.py

    class CancellationToken:
        # Hierarchical cancellation.
        # A cancelled parent cancels all children.
        def __init__(self, parent=None): ...
        def cancel(self): ...
        @property
        def is_cancelled(self): ...
        def throw_if_cancelled(self):
            # Raises CancelledError if cancelled. Call at chunk boundaries.

    REQUIREMENTS:
    - Parent -> child propagation is one-directional.
    - Thread-safe (uses threading.Event internally).
    - CancelledError subclasses MediaForgeError.

5.2 core/resource_lock.py

    class ResourceLock:
        # Named mutex for shared resources. Cancellation-aware acquisition.
        LOCKS = ("GPU_EXCLUSIVE", "CPU_HEAVY", "NETWORK_BULK")
        def acquire(self, name, timeout, token): ...
        def release(self, name): ...
        @contextmanager
        def hold(self, name, timeout, token): ...

    REQUIREMENTS:
    - Blocks with timeout; polls the token every 100 ms.
    - Prevents Demucs + Whisper concurrent VRAM exhaustion.
    - Prevents download workers saturating network during model pulls.

5.3 core/job_queue.py

    Backed by SQLite (jobs.db), WAL mode enabled.

    @dataclass
    class Job:
        id: str
        kind: Literal["download", "transcribe", "separate", "translate",
                      "tts", "align", "mix", "render"]
        payload: dict
        status: Literal["queued", "running", "completed", "failed",
                        "cancelled"]
        progress: float
        created_at: datetime
        updated_at: datetime
        error: str | None = None

    EMITS VIA EVENTBUS:
    - job.queued, job.started, job.progress, job.completed,
      job.failed, job.cancelled

    REQUIREMENTS:
    - Survives crashes: on launch, mark orphaned "running" jobs as "failed".
    - Progress updates at most 4 Hz (throttled) to avoid SQLite write pressure.

5.4 core/event_bus.py

    Singleton pub/sub over Qt signals.

    class EventBus(QObject):
        job_queued      = Signal(str)
        job_started     = Signal(str)
        job_progress    = Signal(str, float, str)
        job_completed   = Signal(str, dict)
        job_failed      = Signal(str, str)
        job_cancelled   = Signal(str)
        hardware_update = Signal(dict)
        toast           = Signal(str, str)   # (level, message)

5.5 core/config_store.py

    - Secrets  -> keyring.set_password("mediaforge", "gemini_api_key", value)
    - Non-secrets -> config/settings.json with schema_version
    - Loader exposes get(key, default=None) and set(key, value, secret=False)

5.6 core/logging_config.py

    - Rotating file handler at
      %LOCALAPPDATA%/MediaForgeAI/logs/mediaforge.log
    - 10 MB x 5 files.
    - Redaction filter strips anything matching:
      (AIza|sk-|hf_)[A-Za-z0-9_\-]{20,}
    - Console handler active only when MEDIAFORGE_DEV=1.

5.7 core/exceptions.py

    class MediaForgeError(Exception): ...
    class CancelledError(MediaForgeError): ...
    class EngineUnavailableError(MediaForgeError): ...
    class ProviderError(MediaForgeError): ...
    class NetworkError(MediaForgeError): ...
    class ValidationError(MediaForgeError): ...

5.8 core/model_registry.py

    Declarative manifest of downloadable models.

    MODELS = {
        "whisper-small":          ModelSpec(url=..., sha256=..., size_mb=460,
                                            dest="models/whisper/small"),
        "whisper-large-v3-turbo": ModelSpec(..., size_mb=1600),
        "mdx-inst-hq3":           ModelSpec(..., size_mb=120,
                                            dest="models/mdx/UVR-MDX-NET-Inst_HQ_3.onnx"),
        "demucs-htdemucs-ft":     ModelSpec(..., size_mb=320,
                                            dest="models/demucs/htdemucs_ft"),
        "embedding-clustering":   ModelSpec(..., size_mb=90),
    }

    FIRST-RUN BEHAVIOR:
    ensure(model_id, progress_cb) - idempotent, checksum-verified, resumable
    via HTTP Range.

================================================================================
SECTION 6 — ENGINE CONTRACT
================================================================================

Every AI/processing module conforms to this shape.

    class Engine(Protocol):
        name: str
        required_locks: list[str]

        def probe(self) -> Availability:
            # Cheap. Never raises.
            # Returns ready/degraded/unavailable + reason string.

        def run(
            self,
            inputs: EngineInput,
            workdir: Path,
            token: CancellationToken,
            progress: Callable[[float, str], None],
        ) -> EngineOutput:
            # Writes only into workdir.
            # Emits progress via callback.
            # Returns typed result. Never touches UI.

================================================================================
SECTION 7 — PHASE PLAN
================================================================================

You may not begin Phase N+1 until Phase N's gate passes.
Report to me after each gate. Wait for explicit confirmation.

--------------------------------------------------------------------------------
PHASE 0 — FOUNDATIONS
--------------------------------------------------------------------------------

OBJECTIVE:
Cross-cutting infrastructure only. No user-visible features.

DELIVERABLES:
- core/cancellation.py
- core/resource_lock.py
- core/job_queue.py + SQLite schema + migrations table
- core/event_bus.py
- core/config_store.py (keyring-backed)
- core/logging_config.py
- core/exceptions.py
- core/model_registry.py (manifest only, no downloads yet)
- tests/unit/test_cancellation.py
- tests/unit/test_resource_lock.py
- tests/unit/test_job_queue.py
- pyproject.toml with ruff + mypy + pytest config
- .gitignore (excludes models/, logs/, *.mfproj, .venv/, __pycache__/)

ACCEPTANCE CRITERIA:
- pytest tests/unit/ passes with >= 90% coverage on the four subsystems.
- scripts/phase0_demo.py queues 3 dummy jobs, cancels the middle one,
  prints the SQLite trace, exits 0.
- mypy --strict core/ passes with zero errors.

GATE:
Report demo output and test results. Wait for "CONFIRM PHASE 0".

--------------------------------------------------------------------------------
PHASE 1 — APP SHELL, HARDWARE PROBE, PROJECT MANAGER
--------------------------------------------------------------------------------

OBJECTIVE:
Navigable UI, live telemetry, persistent projects.

DELIVERABLES:
- app.py - PySide6 bootstrap, splash, single-instance guard (QSharedMemory)
- ui/components/sidebar.py - collapsible nav
  (Dashboard, Downloader, Library, Studio, Batch, Settings)
- ui/components/resource_bar.py - CPU/GPU/RAM meters
- ui/views/dashboard_view.py - quick actions + recent projects
- ui/styles/theme.qss - dark mode
- core/hardware.py - psutil + pynvml + WMI (AMD fallback)
- core/project_manager.py - atomic write, schema_version, .mfproj format
- core/migrations/v1_to_v2.py - stub for future

HARDWARE PROBE RULES:
- Runs as a 1 Hz QTimer on the MAIN THREAD, not a QThread.
- Uses psutil (CPU/RAM/disk), pynvml (NVIDIA), WMI (AMD fallback).
- Emits EventBus.hardware_update(dict).
- Never raises; missing metrics report as None.

PROJECT MANAGER RULES:
- Atomic write: write tmp -> fsync -> os.replace.
- Backup rotation: keep last 3 .mfproj.bak files.
- On load: run migrations if schema_version < CURRENT.
- Auto-save every 30 s and on window close.

NEW PROJECT DIRECTORY LAYOUT:
    <project_root>/
    ├── index.mfproj
    ├── audio/
    ├── stems/
    ├── subtitles/
    ├── exports/
    └── cache/

ACCEPTANCE CRITERIA:
- Switching nav items has no perceptible delay.
- Resource bar updates once per second without blocking the UI.
- Killing the app mid-session and relaunching restores the last project.
- pytest tests/unit/test_project_manager.py passes, including a
  corrupt-file recovery test.

GATE:
Screen recording of demo, test output. Wait for "CONFIRM PHASE 1".

--------------------------------------------------------------------------------
PHASE 2 — DOWNLOADER & MEDIA LIBRARY
--------------------------------------------------------------------------------

OBJECTIVE:
Acquire media from YouTube, TikTok, Douyin, Hongguo, and 20+ platforms.

DELIVERABLES:
- modules/downloader/engine.py - yt-dlp wrapper
- modules/downloader/scraper.py - Playwright stream sniffer, runs in
  a SEPARATE SUBPROCESS
- modules/downloader/queue_manager.py - adapter over core.job_queue
- modules/downloader/organizer.py - sorts by platform/creator/date
- core/updater.py - yt-dlp auto-update on launch
- ui/views/downloader_view.py
- ui/views/library_view.py

RULES:
- yt-dlp auto-update checks nightly PyPI build on launch.
  If offline, uses cached version and shows a warning toast.
- Playwright runs headless Chromium with a mobile User-Agent.
  Intercepts .m3u8 and .mp4 URLs.
- Downloads are jobs on the unified queue, not a bespoke thread pool.
- Thread slider is bounded by ResourceLock("NETWORK_BULK") availability.
- Auto-shutdown requires a 60-second countdown dialog with NO pre-selected.

ACCEPTANCE CRITERIA:
- YouTube URL downloads successfully with best video + best audio merged.
- Douyin mobile-share URL sniffed and downloaded via Playwright.
- Pause, resume, cancel work correctly on the queue.
- Library auto-sorts by platform/creator/date.
- "Send to Studio" loads into the active project.

GATE:
Download logs for one YouTube + one Douyin URL. Wait for "CONFIRM PHASE 2".

--------------------------------------------------------------------------------
PHASE 3 — INSPECTOR, PLAYER, FRAME STEPPING
--------------------------------------------------------------------------------

OBJECTIVE:
Frame-accurate preview with subtitle overlay.

DELIVERABLES:
- modules/media/inspector.py - FFprobe wrapper
- modules/media/frame_cache.py - +/- 30-frame LRU around playhead
- modules/media/player_controller.py - QMediaPlayer + FrameCache hybrid
- modules/media/waveform.py - peaks for timeline
- ui/components/video_player.py - viewport + subtitle overlay

RULES:
- Frame stepping: step_forward()/step_back() decode EXACTLY ONE FRAME
  via FFmpeg subprocess.
- Subtitle overlay is a QWidget painted on top of the video widget,
  NOT a QLabel.
- FrameCache evicts LRU when > 60 frames buffered.
- Inspector results cached in project; re-probe on file mtime change.

ACCEPTANCE CRITERIA:
- 1080p H.264 file: step forward 5 frames, step back 5 frames,
  verify exact frames.
- Scrub bar updates within 50 ms.
- SRT overlay tracks playback within +/- 1 frame.
- Overlay scales correctly on window resize.

GATE:
Screen recording of stepping + overlay. Wait for "CONFIRM PHASE 3".

--------------------------------------------------------------------------------
PHASE 4 — TRANSCRIPTION & STEM SEPARATION
--------------------------------------------------------------------------------

OBJECTIVE:
Diarized transcript from mixed audio, with optional stem separation.

DELIVERABLES:
- modules/ai/transcriber.py - faster-whisper wrapper
- modules/ai/diarizer.py - voice-embedding clustering (default) +
  pyannote (opt-in)
- modules/ai/separator.py - MDX-Net ONNX (CPU) + htdemucs_ft (GPU)

RULES:
- Whisper runs on MIXED AUDIO FIRST. It is robust to BGM and produces
  a draft in minutes on CPU.
- Demucs runs ONLY when needed: segments with Whisper confidence <
  threshold, or full track if "high-fidelity dubbing mode" is enabled.
- Diarization default: faster-whisper word timestamps +
  pyannote/embedding + sklearn.AgglomerativeClustering.
  Fully offline after model download.
- htdemucs on CPU is DISABLED IN THE UI with an explanatory tooltip.
  CPU uses MDX-Net ONNX.
- Whisper model default = small. large-v3-turbo is opt-in via Settings.

TRANSCRIPT SCHEMA:
    {
      "id": 1,
      "start": 1.250,
      "end": 3.800,
      "speaker": "Speaker 1",
      "source_text": "...",
      "target_text": "",
      "voice_id": "",
      "audio_path": "",
      "confidence": 0.92
    }

ACCEPTANCE CRITERIA:
- 10-minute episode transcribed on laptop CPU in <= 5 minutes with
  small model.
- Diarization produces correct speaker labels on a 2-speaker test clip.
- MDX-Net separation runs on CPU within 3x realtime.
- No audible dialogue bleed in no_vocals.wav.

GATE:
Transcript JSON + separation stem samples. Wait for "CONFIRM PHASE 4".

--------------------------------------------------------------------------------
PHASE 5 — SUBTITLE SYSTEM
--------------------------------------------------------------------------------

OBJECTIVE:
Export SRT/VTT/ASS with styler + burn-in.

DELIVERABLES:
- modules/processing/subtitle.py - exporters + burner
- ui/components/subtitle_styler.py - font, size, color, outline,
  shadow, alignment
- resources/fonts/ - Noto Sans Regular/Bold, Noto Sans Khmer Regular

RULES:
- SRT/VTT export via pysubs2.
- ASS export with libass-compatible style header.
- Burn-in uses bundled FFmpeg with:
    -vf subtitles=...:force_style=...
- Soft-mux is the DEFAULT for archival exports; burn-in is opt-in.
- Khmer rendering validated against ligature test corpus.

ACCEPTANCE CRITERIA:
- All four outputs (.srt, .vtt, .ass, burn-in .mp4) generated from the
  Phase 4 transcript.
- Burn-in renders Khmer and Chinese glyphs without square boxes.
- SRT passes pysubs2 validator.

GATE:
Sample files. Wait for "CONFIRM PHASE 5".

--------------------------------------------------------------------------------
PHASE 6 — TRANSLATION & DIRECTOR TAGGING
--------------------------------------------------------------------------------

OBJECTIVE:
Translated transcript with normalized expressive tags.

DELIVERABLES:
- modules/ai/director.py - LLM prompt engineering + tag DSL parser
- modules/ai/providers/gemini_translate.py
- modules/ai/providers/deepseek_translate.py
- modules/ai/providers/qwen_translate.py
- modules/ai/providers/libre_translate.py

INTERNAL DSL (LOCKED):
    {whisper}  {laugh}  {sob}  {shout:angry}  {sigh}  {gasp}  {cry}

RULES:
- Providers receive PROVIDER-SPECIFIC RENDERINGS, not raw brackets:
    - Gemini -> natural language instruction in prompt
    - Qwen -> Chinese-language instruction
    - DeepSeek -> structured JSON mode
    - LibreTranslate -> plain text (tags stripped, logged)
- LLM prompt includes max_chars hint:
    int(dt_orig * chars_per_sec[target_lang])
- Target languages: English, Khmer, Chinese, Japanese, Korean.
- Manual edits in TranscriptEditorWidget round-trip through the DSL.

ACCEPTANCE CRITERIA:
- 20-line transcript translated into English and Khmer with tags preserved.
- No hallucinated dialogue (verified against source length ratio).
- Manual edits survive re-translation.

GATE:
Sample translations. Wait for "CONFIRM PHASE 6".

--------------------------------------------------------------------------------
PHASE 7 — TTS DUBBING
--------------------------------------------------------------------------------

OBJECTIVE:
Per-speaker expressive audio.

DELIVERABLES:
- modules/ai/voice_generator.py - dispatcher
- modules/ai/providers/gemini_tts.py
- modules/ai/providers/qwen_tts.py
- modules/ai/providers/edge_tts.py
- ui/views/studio_view.py - Speaker Assignment Panel

ROUTING (LOCKED):
    if target_lang == "km": return ["edge", "qwen"]
    if target_lang == "zh": return ["qwen", "edge", "gemini"]
    return ["gemini", "qwen", "edge"]

RULES:
- Gemini: prompt-based emotion ("Say in a whisper: ...").
- Qwen: Qwen3-TTS-Flash with free-style instruction following.
- Edge-TTS: SSML <mstts:express-as> where the locale supports it.
- Segment audio cached with hash key (text, voice_id, provider, params).
- Speaker panel maps Speaker N -> voice_id, pitch, rate, gender.

ACCEPTANCE CRITERIA:
- 20-line scene with 2 speakers produces correct per-speaker audio.
- A/B original vs. dubbed in the player.
- Cache hit on re-run produces identical bytes.
- Graceful fallback when Gemini quota exceeded.

GATE:
Sample audio + A/B recording. Wait for "CONFIRM PHASE 7".

--------------------------------------------------------------------------------
PHASE 8 — ALIGNMENT & MIXING
--------------------------------------------------------------------------------

OBJECTIVE:
Fit dubbed audio to original timeline; mix with BGM.

DELIVERABLES:
- modules/processing/aligner.py
- modules/processing/mixer.py

ALIGNER RULES:
- Compute dt_orig = end - start, dt_tts = clip duration.
- If dt_tts > dt_orig: apply atempo CAP CAPPED AT 1.15x.
  Overflow beyond 1.15x triggers a "shorten translation" flag on the
  segment (resolved on next translation pass).
- If dt_tts < dt_orig: pad with silence.
- Prefer rubberband filter when the FFmpeg build supports it.

MIXER RULES:
- Empty timeline matching video length.
- Place aligned TTS at designated timestamps.
- Duck BGM via sidechaincompress, not manual automation.
- Intermediate output: dubbed_dialogue.wav for inspection.

ACCEPTANCE CRITERIA:
- Dubbed dialogue locks to mouth movement within +/- 80 ms.
- BGM audibly ducks under speech and restores in gaps.
- No overlapping dialogue lines.

GATE:
Sample mixed audio. Wait for "CONFIRM PHASE 8".

--------------------------------------------------------------------------------
PHASE 9 — MULTI-TRACK TIMELINE
--------------------------------------------------------------------------------

OBJECTIVE:
Visual, read-only composite view.

DELIVERABLES:
- ui/components/timeline.py

RULES:
- Tracks: Video, Original Audio, BGM/SFX, Dubbed Dialogue, Subtitles.
- READ-ONLY in v1.0. Drag-to-nudge is deferred.
- Mute/solo per track ships.
- Clicking a clip seeks the player.
- Editing happens in the transcript panel, not the timeline.

ACCEPTANCE CRITERIA:
- All five tracks visible and synced to playback.
- Mute/solo works without UI lag.
- Click-to-seek is frame-accurate.

GATE:
Screen recording. Wait for "CONFIRM PHASE 9".

--------------------------------------------------------------------------------
PHASE 10 — UNIFIED AUTO-PROCESS PIPELINE
--------------------------------------------------------------------------------

OBJECTIVE:
One button runs the whole chain.

DELIVERABLES:
- modules/processing/pipeline.py - DAG executor
- Pipeline UI in studio_view.py with per-stage status and master progress bar

RULES:
- DAG:
    Download/Import -> Extract Audio -> Whisper -> Demucs (conditional)
    -> Translate -> TTS -> Align -> Mix -> Burn Subtitles -> Export
- Outputs are CONTENT-ADDRESSED; re-running reuses unchanged ancestors.
- Cancellation at any node cancels descendants but preserves committed
  artifacts.
- Each node is inspectable, cancellable, and re-runnable independently.

ACCEPTANCE CRITERIA:
- Click Auto-Process on an imported video -> finished dubbed + subtitled MP4.
- Modifying a text line updates the timeline clip and subtitle track in
  real time.
- Cancelling mid-pipeline leaves the project in a consistent state.

GATE:
End-to-end video. Wait for "CONFIRM PHASE 10".

--------------------------------------------------------------------------------
PHASE 11 — BATCH & GPU ACCELERATION
--------------------------------------------------------------------------------

OBJECTIVE:
High-throughput batch rendering with HW encoding.

DELIVERABLES:
- modules/batch/batch_runner.py
- ui/views/batch_view.py
- Encoder detection in core/hardware.py

RULES:
- Probe h264_nvenc, hevc_nvenc, av1_nvenc, h264_amf, h264_qsv with a
  1-second trial encode.
- Fall back to libx264 if none available.
- Batch concurrency governed by ResourceLock, not a raw slider.
- Power management: sleep/shutdown ONLY after a 60-second confirmation
  countdown with NO pre-selected.

ACCEPTANCE CRITERIA:
- 10-link batch processes sequentially with no memory growth (verify
  via tracemalloc).
- On NVIDIA system, h264_nvenc engaged -> > 60% render time reduction
  vs. libx264.
- No GPU OOM across the batch.

GATE:
Batch metrics report. Wait for "CONFIRM PHASE 11".

--------------------------------------------------------------------------------
PHASE 12 — HARDENING, DIAGNOSTICS, PACKAGING
--------------------------------------------------------------------------------

OBJECTIVE:
Ship.

DELIVERABLES:
- ui/views/settings_view.py - keyring integration, output directory,
  cache cleaner
- Crash reporter -> %LOCALAPPDATA%/MediaForgeAI/logs/crash-<ts>.zip
  (redacted)
- Custom frameless title bar (Windows only)
- PyInstaller spec + Inno Setup script
- Bundled static FFmpeg (LGPL build with rubberband + libass)
- Bundled Noto Sans + Noto Sans Khmer

RULES:
- Installer verifies VC++ redistributable presence.
- Total installer size target: < 200 MB.
- Crash reporting is OPT-IN, OFF BY DEFAULT.
- No telemetry, no analytics, no usage tracking.

ACCEPTANCE CRITERIA:
- App launches on clean Windows 10/11 with no Python installed.
- Invalid URLs, network disconnects, empty audio streams produce
  informative UI dialogs, not tracebacks.
- Crash zip generated on simulated failure; redaction verified.
- Installer size < 200 MB.

GATE:
Installer + smoke-test report. Wait for "CONFIRM PHASE 12 COMPLETE".

================================================================================
SECTION 8 — NON-GOALS FOR v1.0
================================================================================

Do not build these. If asked, refuse and reference this section.

- Timeline drag-editing (requires undo/redo, snapping, multi-select)
- Custom frameless chrome on non-Windows
- Realtime voice cloning (preset voices only)
- Cloud render offload (local only)
- macOS / Linux packaging (Windows-first)
- Live stream recording (VOD only)
- Multi-user / team features
- Bundled libmpv (deferred to post-1.0)
- Piper TTS (no Khmer voice)

================================================================================
SECTION 9 — RISK REGISTER
================================================================================

RISK                              PHASE   MITIGATION
--------------------------------  ------  --------------------------------------------
yt-dlp breaks on target site      2       Auto-update on launch; user-visible
                                          extractor version
QMediaPlayer insufficient for     3       FrameCache fallback
stepping
Demucs too slow on CPU            4       MDX-Net default on CPU; htdemucs disabled
pyannote gated model              4       Clustering diarizer default
Gemini TTS tag drift              6, 7    Provider adapter isolates DSL
Edge-TTS rate-limited             7       Gemini/Qwen primary
atempo artifacts                  6, 8    Cap 1.15x; translation-side shortening
GPU OOM during batch              0, 11   ResourceLock; VRAM-bound concurrency
Project file corruption           1       Atomic write + backup rotation
Subtitle font missing glyphs      5       Bundle Noto Sans + Khmer; CI check

================================================================================
SECTION 10 — TESTING REQUIREMENTS
================================================================================

- UNIT: Every engine has a contract test using a synthetic fixture.
- INTEGRATION: Each phase adds one integration test that runs the phase's demo.
- COVERAGE FLOOR: 80% for core/, 70% for modules/.
- CI SCRIPT: scripts/ci.sh runs ruff check, mypy --strict core/, pytest.
- NO NETWORK IN UNIT TESTS. Mock providers.

================================================================================
SECTION 11 — INTERACTION PROTOCOL
================================================================================

After each phase:

1. REPORT: Phase number, deliverables, test output, demo artifact path.
2. WAIT: Do not proceed until I reply with "CONFIRM PHASE N" or corrections.
3. ON CORRECTION: Fix, re-run gate, re-report.
4. ON AMBIGUITY: Stop and ask. Do not guess.

================================================================================
SECTION 12 — FIRST ACTION
================================================================================

Begin Phase 0.

1. Create the repository layout exactly as specified in Section 4.
2. Write pyproject.toml, requirements.txt, .gitignore.
3. Implement:
   - core/cancellation.py
   - core/resource_lock.py
   - core/job_queue.py
   - core/event_bus.py
   - core/config_store.py
   - core/logging_config.py
   - core/exceptions.py
   - core/model_registry.py
4. Write unit tests for each.
5. Write scripts/phase0_demo.py.
6. Run pytest tests/unit/ and mypy --strict core/.
7. Report results.
8. WAIT for "CONFIRM PHASE 0" before proceeding to Phase 1.

================================================================================
END OF PROMPT — VERSION 1.0
Do not modify without explicit instruction.
================================================================================

INSTRUCTIONS FOR USE:

1. Copy everything between the opening header and the "END OF PROMPT" line
   into a plain text file named:
   MediaForgeAI-antigravity-prompt.txt

2. If your agent platform supports it, also save a short companion file
   named:
   .antigravity/rules.md
   containing just Sections 0, 2, and 11. This ensures the agent re-reads
   the operating rules at every session start.

3. Attach the full .txt to a new Antigravity agent session as the primary
   instruction document.

4. Optionally split Section 7 into per-phase files (phase0.txt, phase1.txt,
   ...) if you want tighter scoping per session. Feed one file at a time.

5. The agent will stop at each GATE and wait for "CONFIRM PHASE N".
   This is intentional. It prevents regressions and keeps you in control.

6. If the agent proposes a paid dependency, refuse and point it to
   Section 3 (Free Stack, Locked Decisions).

END.