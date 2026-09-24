VoxReel — Full Project Plan
Project: VoxReel — Speaker Diarization & Actor Voice Registry Engine
Version: 1.0 (Planning Document)
Status: Draft for review
Type: Open technical plan — suitable as PLAN.md in a repository

Table of Contents
Executive Summary
Problem Statement
Goals & Success Metrics
Scope
Functional Requirements
Non-Functional Requirements
System Architecture
Technology Stack
Data Model & Database Schema
ML Pipeline Design
API Specification
Development Roadmap
Evaluation & Testing Plan
Privacy, Security & Legal
Risks & Mitigations
Resource & Cost Estimates
Future Enhancements
Appendices
1. Executive Summary
VoxReel is a self-hostable engine that ingests movie/TV audio files and automatically:

Separates and identifies every distinct voice (speaker diarization),
Transcribes speech to text with word-level timestamps,
Matches each detected voice against a persistent Actor Voice Registry (AVR) so the same actor is recognized across every file ever processed,
Exports results as JSON, SRT, VTT, and ELAN formats.
The key differentiator vs. existing tools (pyannote, WhisperX, NeMo) is stateful identity: instead of anonymous SPEAKER_00 labels per file, VoxReel maintains a growing, human-correctable database of voice profiles that improves with every use.

Delivery format: CLI (MVP) → REST API + Web UI (V1) → Face/voice fusion + realtime (V2+).

2. Problem Statement
Problem
Impact
Diarization tools are stateless	Same actor gets a new anonymous label in every file
Movie audio is hostile to ASR/diarization	Music scores, SFX, 5.1 mixes, overlapping dialogue degrade accuracy
No identity layer	Manual relabeling repeated for every file/episode
No human-correction feedback loop	Errors never improve the system

Target users: media archivists, subtitle/localization teams, researchers, content studios, accessibility tool builders.

3. Goals & Success Metrics
3.1 Primary Goals
G1: Process a movie file end-to-end with a single command.
G2: Produce word-level timestamped, speaker-attributed transcripts.
G3: Maintain a persistent actor voice registry with auto-matching.
G4: Human corrections feed back into the registry (learning flywheel).
G5: Movie-grade audio conditioning (dialogue isolation) built in.
3.2 Measurable Success Criteria
Metric
Definition
Target (V1)
DER	Diarization Error Rate on clean dialogue scenes	≤ 12%
WER	Word Error Rate (clean dialogue, English)	≤ 8%
Speaker attribution accuracy	Correct speaker per segment	≥ 90%
Registry match precision (auto-assign ≥ 0.82)	Auto-assigned labels that are correct	≥ 95%
RTF (Real-Time Factor)	processing time ÷ audio duration, on 1× RTX 4090	≤ 0.5
Correction effect	Attribution accuracy after 10 corrected files vs. baseline	+5 pts minimum

4. Scope
4.1 In Scope (V1)
Input formats: MKV, MP4, MOV, WAV, MP3, FLAC, OGG (anything FFmpeg reads)
Audio extraction, center-channel extraction from 5.1/7.1, loudness normalization
Music/SFX suppression via source separation
VAD, diarization (up to 10 speakers/scene), word-level ASR
Actor Voice Registry: create, enroll, match, merge, delete actors
Human correction workflow (API + UI), with registry feedback
Exports: JSON, SRT, VTT, ELAN (.eaf), plain TXT
CLI + REST API + minimal Web UI
Single-node deployment (Docker Compose)
4.2 Out of Scope (V1)
Realtime/streaming diarization (V2)
Face detection / lip-sync based speaker naming (V2)
Song lyrics / sung dialogue transcription
Multi-language registry per-locale GUI (registry is language-keyed, but UI is English)
Distributed multi-node GPU clusters
Emotion tagging (V2)
5. Functional Requirements
FR-1: Ingestion
FR-1.1 Accept media files via CLI path, API upload (≤ 10 GB), or watched folder.
FR-1.2 Auto-detect audio streams; select best dialogue candidate (center channel for 5.1+; stereo→mono downmix otherwise).
FR-1.3 Optional source-separation pre-pass (toggleable, default ON for video files).
FR-1.4 Normalize loudness to EBU R128 (-23 LUFS target) before model inference.
FR-1.5 Support per-language audio tracks (select or process all, keyed by language).
FR-2: Diarization
FR-2.1 Detect speech regions via VAD.
FR-2.2 Segment speech; detect overlapping-speech regions.
FR-2.3 Cluster into N speakers; auto-estimate N with user override option (--speakers 2).
FR-2.4 Minimum cluster size guard: clusters < 3 utterances are flagged low_confidence, not auto-enrolled.
FR-3: Transcription
FR-3.1 Whisper-family ASR with language auto-detect + manual override.
FR-3.2 Word-level timestamps via forced alignment.
FR-3.3 Custom vocabulary / initial-prompt injection from registry aliases (character names).
FR-3.4 Per-segment and per-word confidence scores.
FR-4: Actor Voice Registry
FR-4.1 Create actor records: name, aliases, notes, consent flag, per-language voice profiles.
FR-4.2 Enroll from: (a) uploaded reference clips, (b) any processed session's segments.
FR-4.3 Match each new session's clusters to registry via similarity scoring with thresholds: auto ≥ 0.82, review 0.70–0.82, new < 0.70.
FR-4.4 Support multi-profile actors (e.g., normal voice + character voice) with Hungarian assignment across clusters.
FR-4.5 Registry hygiene: enrollment gated on SNR ≥ threshold and segment duration ≥ 1.5 s; profile = centroid + ≤ 50 diverse reference embeddings; embeddings versioned by model.
FR-4.6 Merge duplicate actor records; full deletion (GDPR-style erasure) removes all vectors.
FR-5: Corrections & Feedback
FR-5.1 User can reassign any segment's speaker, edit text, or confirm/reject auto-matches.
FR-5.2 Confirmed labels with quality gates pass embeddings into the actor's profile (bounded growth: dedupe near-duplicates, cap profile size).
FR-5.3 Correction history is audit-logged (never overwrite silently).
FR-6: Output
FR-6.1 JSON master format (full fidelity), SRT/VTT (subtitle), ELAN .eaf (annotation), TXT (readable).
FR-6.2 Output includes per-segment: start, end, speaker ID, actor (if matched), text, confidence, overlap flag.
6. Non-Functional Requirements
ID
Requirement
Target
NFR-1	Performance	RTF ≤ 0.5 on RTX 4090; RTF ≤ 3 on modern CPU (small model)
NFR-2	Scalability	Batch queue handles ≥ 100 queued jobs; registry to 10,000+ actors
NFR-3	Reliability	Resumable job pipeline (stage checkpoints); crash-safe
NFR-4	Portability	Docker Compose one-command deploy; runs on Linux/macOS/Windows (WSL2)
NFR-5	Extensibility	Model adapters: swap diarization/ASR backends via config
NFR-6	Security	Encrypted vectors at rest; JWT auth on API; role-based access (admin/annotator/viewer)
NFR-7	Privacy	Consent flag required before registry export; deletion endpoint purges vectors
NFR-8	Observability	Structured logs, per-stage timings, Prometheus metrics endpoint

7. System Architecture
7.1 Component Diagram
text

┌──────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                     │
│      CLI (Python)          Web UI (React)        3rd-party (REST)    │
└──────────┬─────────────────────┬──────────────────────┬─────────────┘
           │                     │                      │
           └──────────────┬──────┴──────────────────────┘
                          ▼
              ┌───────────────────────┐
              │   API Gateway (FastAPI)│  auth, rate-limit, validation
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │  Job Queue (Redis +    │  stage-based pipeline
              │  RQ / Celery workers)  │
              └──┬────┬────┬────┬─────┘
                 ▼    ▼    ▼    ▼
        ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
        │ INGEST │ │ DIARIZE│ │ TRANSCR│ │ FUSE+MATCH   │
        │ ffmpeg │ │ VAD    │ │ whisper│ │ align + AVR  │
        │ demucs │ │ segm.  │ │ align  │ │ scoring      │
        │ loudn. │ │ embed  │ │        │ │              │
        └───┬────┘ └───┬────┘ └───┬────┘ └──────┬───────┘
            ▼          ▼          ▼             ▼
        ┌─────────────────────────────────────────────────┐
        │            STORAGE LAYER                        │
        │  PostgreSQL (metadata)   Object/local FS (media)│
        │  Qdrant / pgvector (vectors)   Redis (queue)    │
        └─────────────────────────────────────────────────┘
7.2 Pipeline Stages (checkpointed)
Stage
Input → Output
Checkpoint artifact
S1 Ingest	media file → conditioned WAV (16k mono)	s1_audio.wav
S2 Diarize	WAV → segments + embeddings + clusters	s2_diar.json
S3 Transcribe	WAV → words + timestamps	s3_asr.json
S4 Fuse/Match	S2+S3 → attributed transcript + registry scores	s4_final.json
S5 Export	final JSON → requested formats	user-facing outputs

Each stage stores its artifact; a failed/crashed job resumes from the last completed stage.

8. Technology Stack
Layer
Choice
Rationale / License
Language	Python 3.11+	ML ecosystem
Audio tools	FFmpeg 6+	LGPL/GPL build — distribute as external binary
Source separation	Demucs v4 (htdemucs)	MIT
Loudness	pyloudnorm (EBU R128)	MIT
VAD	Silero VAD	MIT
Diarization	pyannote.audio 3.x (primary) / NVIDIA NeMo TitaNet + MSDD (alt)	MIT (model weights gated — accept HF terms at deploy)
Embeddings	pyannote/wespeaker ECAPA-TDNN or TitaNet-Large	MIT / Apache-2.0
ASR	faster-whisper (CTranslate2), large-v3 / distil-large-v3	MIT
Alignment	WhisperX (wav2vec2 forced alignment)	BSD-4 → verify redistribution; can swap to stable-ts
Inference runtime	ONNX Runtime / CTranslate2; PyTorch where needed	—
API	FastAPI + Uvicorn	MIT
Queue	Redis + RQ (MVP) → Celery (V1)	BSD
Metadata DB	PostgreSQL 16 (+ pgvector) or SQLite (MVP)	—
Vector store	pgvector (V1) → Qdrant (scale)	Apache-2.0
Frontend	React + Vite + Tailwind;wavesurfer.js for audio timeline	MIT
Packaging	Docker + Docker Compose; PyPI package for CLI	—
Auth	JWT (OAuth2 password flow)	—
Metrics	Prometheus + Grafana (optional profile)	—

Hardware requirements (recommended):

GPU: NVIDIA ≥ 8 GB VRAM (RTX 3060+); CPU-only mode supported (slower, smaller models)
RAM: 16 GB min / 32 GB recommended
Disk: ~2× media size for intermediate artifacts (auto-GC after 72 h, configurable)
9. Data Model & Database Schema
9.1 ERD (textual)
text

Actor 1──* VoiceProfile 1──* ReferenceEmbedding
Actor 1──* ClusterMatch *──1 Session
Session 1──* Segment 1──* Word
Session *──1 MediaFile
9.2 SQL Schema (PostgreSQL)
sql

CREATE TABLE media_file (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_name   TEXT NOT NULL,
    stored_path     TEXT NOT NULL,
    container       TEXT,
    duration_sec    NUMERIC(10,3),
    audio_tracks    JSONB,               -- [{stream, lang, channels, layout}]
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_file_id   UUID REFERENCES media_file(id),
    language        TEXT,
    num_speakers    INT,                 -- estimated or forced
    pipeline_ver    TEXT NOT NULL,       -- e.g. "vx-1.2.0"
    embedding_model TEXT NOT NULL,       -- e.g. "ecapa-tdnn-voxceleb-v2"
    status          TEXT CHECK (status IN
                      ('queued','running','done','failed','needs_review')),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE actor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT NOT NULL,
    aliases         TEXT[] DEFAULT '{}',
    notes           TEXT,
    consent_flag    BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ          -- soft delete
);

CREATE TABLE voice_profile (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        UUID REFERENCES actor(id) ON DELETE CASCADE,
    language        TEXT NOT NULL DEFAULT 'en',
    embedding_model TEXT NOT NULL,
    centroid        VECTOR(512),         -- pgvector; dim per model
    ref_count       INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (actor_id, language, embedding_model)
);

CREATE TABLE reference_embedding (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voice_profile_id UUID REFERENCES voice_profile(id) ON DELETE CASCADE,
    vector          VECTOR(512) NOT NULL,
    source          TEXT CHECK (source IN ('enroll_clip','confirmed_segment')),
    session_id      UUID REFERENCES session(id),   -- NULL for manual enroll
    snr_db          NUMERIC(5,1),
    duration_sec    NUMERIC(6,3),
    model_version   TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON reference_embedding USING hnsw (vector VECTOR_COSINE_OPS);

CREATE TABLE segment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES session(id) ON DELETE CASCADE,
    start_sec       NUMERIC(10,3) NOT NULL,
    end_sec         NUMERIC(10,3) NOT NULL,
    cluster_label   TEXT NOT NULL,        -- SPK_A, SPK_B, ...
    actor_id        UUID REFERENCES actor(id),   -- NULL = unknown
    match_score     NUMERIC(4,3),
    match_status    TEXT CHECK (match_status IN
                      ('auto','review','new','manual','rejected')),
    text            TEXT,
    asr_conf        NUMERIC(4,3),
    overlap_flag    BOOLEAN DEFAULT FALSE,
    corrected_by    UUID,                 -- user id, NULL if untouched
    UNIQUE (session_id, start_sec, cluster_label)
);

CREATE TABLE word (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_id      UUID REFERENCES segment(id) ON DELETE CASCADE,
    start_sec       NUMERIC(10,3) NOT NULL,
    end_sec         NUMERIC(10,3) NOT NULL,
    token           TEXT NOT NULL,
    conf            NUMERIC(4,3)
);

CREATE TABLE cluster_match (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES session(id) ON DELETE CASCADE,
    cluster_label   TEXT NOT NULL,
    actor_id        UUID REFERENCES actor(id),
    score           NUMERIC(4,3),
    status          TEXT NOT NULL,        -- auto|confirmed|rejected|new_speaker
    decided_by      UUID,                 -- NULL = machine
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    entity      TEXT NOT NULL,
    entity_id   UUID NOT NULL,
    action      TEXT NOT NULL,            -- update/merge/delete/confirm/...
    payload     JSONB,
    user_id     UUID,
    created_at  TIMESTAMPTZ DEFAULT now()
);
10. ML Pipeline Design
10.1 Stage Parameters (defaults, all config-overridable)
yaml

audio:
  target_sr: 16000
  channels: center_or_mono        # center channel preferred on 5.1+
  loudness_target_lufs: -23
  separation:
    enabled_for_video: true
    model: htdemucs
    stems_to_keep: [vocals]        # treat "vocals" stem as dialog+SFX

vad:
  model: silero-vad-v5
  min_speech_ms: 250
  min_silence_ms: 150

diarization:
  segmentation: pyannote/segmentation-3.0
  embedding: ecapa-tdnn-voxceleb   # 192-d, or titanet-large 512-d
  clustering: agglomerative
  distance_threshold: auto         # Bayesian/percentile auto-tune
  overlap_detection: true
  min_cluster_utterances: 3

asr:
  model: large-v3                  # distil-large-v3 for CPU profile
  compute_type: float16            # int8 on CPU
  beam_size: 5
  word_timestamps: true
  vad_filter: true

registry:
  auto_assign_threshold: 0.82      # cosine similarity
  review_band: [0.70, 0.82)
  new_speaker_threshold: 0.70
  min_enroll_snr_db: 12.0
  min_enroll_duration_s: 1.5
  max_profile_embeddings: 50
  dedupe_cosine: 0.98              # near-identical embeddings dropped
10.2 Matching Algorithm
text

for each cluster C in session:
    centroid_c = mean(top-quality embeddings of C)
    candidates = ANN_search(centroid_c, k=5)          # over all profiles
    scores     = max,mean over profile embeddings     # both computed
    combined   = 0.6 * centroid_sim + 0.4 * mean_sim  # robust to outliers

    apply Hungarian assignment across clusters to prevent
    two clusters claiming the same actor (when #clusters ≤ #candidates)

    if combined ≥ 0.82          → status=auto, actor assigned
    elif combined ≥ 0.70        → status=review, tentative assign
    else                        → status=new, create UNKNOWN_N
10.3 Overlap Handling
Overlapping regions get two segments (one per speaker) sharing the time range with overlap_flag: true.
ASR on overlap zones runs a second pass with speaker-conditioned context (top-k transcript hypotheses; if mismatch, mark overlap: low_conf_text).
10.4 Model Adapter Interface (extensibility, NFR-5)
python

class DiarizerBackend(Protocol):
    def segment(self, wav: Audio) -> list[Segment]: ...
    def embed(self, wav: Audio, segments: list[Segment]) -> np.ndarray: ...

class AsrBackend(Protocol):
    def transcribe(self, wav: Audio, language: str | None) -> AsrResult: ...

# Backends selected via config: backend: pyannote | nemo
11. API Specification
Base URL: /api/v1 · Auth: Authorization: Bearer <JWT>

11.1 Endpoints
Method
Path
Description
POST	/ingest	Upload media file (multipart) → {job_id, session_id}
POST	/sessions	Start job from server-side path (CLI/watcher)
GET	/jobs/{id}	Status + per-stage progress
GET	/sessions/{id}	Full attributed transcript (JSON)
GET	/sessions/{id}/export?format=srt|vtt|json|eaf|txt	Download export
POST	/registry/actors	Create actor
GET	/registry/actors?q=	Search actors
PATCH	/registry/actors/{id}	Update name/aliases/consent
DELETE	/registry/actors/{id}	Erase actor + all vectors (GDPR)
POST	/registry/actors/{id}/enroll	Enroll reference clips (multipart audio)
POST	/registry/actors/{id}/merge	Merge another actor into this one
POST	/sessions/{id}/corrections	Batch corrections (speaker reassign, text edit, confirm/reject)
POST	/sessions/{id}/label	Map cluster → actor and promote to profile
GET	/metrics	Prometheus metrics

11.2 Example: submit correction batch
http

POST /api/v1/sessions/7c9e.../corrections
Content-Type: application/json

{
  "corrections": [
    {"segment_id": "a1...", "action": "reassign_speaker", "actor_id": "42..."},
    {"segment_id": "a2...", "action": "edit_text", "text": "There's always a choice."},
    {"segment_id": "a3...", "action": "confirm_match"},
    {"cluster": "SPK_B", "action": "promote_to_actor",
     "name": "Marcus Chen", "aliases": ["Marc"]}
  ]
}
Response 202 — corrections applied; promote_to_actor creates the actor, enrolls quality-gated embeddings, and rewrites the session's labels.

12. Development Roadmap
Phase 0 — Foundations (Week 1)
 Repo scaffold, Python package layout, ruff/mypy/pytest CI
 Docker Compose skeleton (api, worker, postgres+pgvector, redis)
 FFmpeg audio extraction + center-channel selection utility (+unit tests with synthetic 5.1 files)
 Config system (pydantic-settings, YAML overrides)
Exit criteria: voxreel ingest movie.mkv produces a conditioned 16k mono WAV.

Phase 1 — MVP CLI: Diarize + Transcribe (Weeks 2–3)
 Silero VAD integration
 pyannote 3.x segmentation + ECAPA embeddings + AHC clustering
 faster-whisper integration + word timestamps
 Fusion: temporal-overlap alignment of words ↔ speaker segments
 JSON + SRT output writers
 Checkpointed stage pipeline + --resume
Exit criteria: 2-speaker test scene → correct 2 clusters, word-timestamped SRT with speaker labels; RTF ≤ 1.0 on GPU.

Phase 2 — Actor Voice Registry (Weeks 4–5)
 SQLite (MVP) schema → pgvector migration path
 Enrollment from clips and from sessions (SNR/duration gating)
 Scoring + Hungarian assignment + thresholds
 voxreel enroll, voxreel label --map --promote
 Profile hygiene: dedupe, cap at 50 embeddings, model-version stamping
 Merge & delete actors
Exit criteria: Process ep1 → name two unknowns → process ep2 with same cast → both auto-assigned ≥ 0.82 with ≥ 95% correctness on the test set.

Phase 3 — API + Worker + Review UI (Weeks 6–8)
 FastAPI: all endpoints from §11, JWT auth, roles
 Redis queue, stage-progress reporting, resumable jobs
 React UI: upload, job list, transcript table with inline speaker dropdown, audio timeline (wavesurfer) with speaker-colored segments, confirm/reject/merge flows
 Export endpoints (JSON/SRT/VTT/ELAN/TXT)
 Audit log
Exit criteria: Full workflow completable entirely in browser in < 5 minutes for a 40-min episode; corrections propagate to registry.

Phase 4 — Movie-Grade Hardening (Weeks 9–10)
 Demucs separation pre-pass (toggleable) + A/B evaluation on noisy movie set
 Overlap dual-labeling + second-pass ASR on overlap zones
 Custom vocabulary injection from registry aliases
 Multi-language audio tracks; per-language profiles
 Artifact GC, Prometheus metrics, load test (100-job queue)
Exit criteria: Success-metrics table (§3.2) met on the internal movie benchmark.

Phase 5 — Beta Release (Weeks 11–12)
 Docs: quickstart, API reference (OpenAPI), model-card notes
 One-command install (pipx install voxreel + docker compose up)
 Beta with 3–5 external users; feedback fixes
 v1.0.0 tag
Timeline Overview
text

Week:   1    2    3    4    5    6    7    8    9    10   11   12
P0     ████
P1          ██████████
P2                        ██████████
P3                                     ██████████████████
P4                                                    ██████████
P5                                                              ██████████
(Single experienced developer assumption; ~2 devs halves calendar time for P3.)

13. Evaluation & Testing Plan
13.1 Test Sets
Set
Purpose
Composition
Unit fixtures	CI correctness	Synthetic audio (TTS, tones), tiny clips
Clean-dialogue bench	DER/WER baseline	20 two-person scenes (podcast/interview cuts)
Movie-hard bench	Real-condition target	20 movie excerpts w/ score, SFX, overlap; ground truth from subtitles + manual annotation
Registry bench	Identity matching	Same cast across 10 files; known-cast ground truth
Adversarial registry	False-match resistance	Similar voices (VoxCeleb confusable pairs); must NOT auto-match

13.2 Metrics & Tooling
DER / JER via pyannote.metrics (collar 0.25 s)
WER via jiwer, scored against ground-truth subtitles (normalized)
Speaker attribution accuracy — segment-level exact speaker match
Registry precision/recall at the 0.82 auto-threshold
RTF measured per stage; reported per hardware profile
13.3 Regression Gates (CI, per PR)
Unit + integration tests green
Clean-dialogue bench: DER/WER within ±0.5 pts of main
Registry bench: no precision regression
Nightly full benchmark with published report
13.4 Feedback-Loop Test (validates G4)
Run 10-file sequence with an unenrolled cast. Measure attribution accuracy on file N as corrections accumulate. Pass: monotonic improvement; +5 pts by file 10.

14. Privacy, Security & Legal
Area
Requirement
Implementation
Biometric data	Voice prints are biometric PII (GDPR Art. 9, BIPA, etc.)	Explicit consent flag on actor records; legal notice in docs; deployment is self-hosted (data stays with operator)
Right to erasure	Full deletion	DELETE /registry/actors/{id} cascades to profiles, vectors, and de-links sessions
Data minimization	Store vectors, not raw enrollment audio by default	Raw clips deleted after embedding extraction unless user opts in
Encryption	At rest & in transit	Disk encryption guidance; vectors encrypted via app-layer AES-GCM; TLS on API
Access control	Roles	admin / annotator / viewer; annotators can't export registry
Model licenses	Redistribution compliance	pyannote weights: user accepts HF gated-model terms at setup (never bundle weights in Docker); WhisperX BSD-4 clause — or ship stable-ts alternative
Auditability	Traceability	audit_log for every registry mutation and correction
Content copyright	User responsibility	Tool processes user-supplied media; no media bundled

15. Risks & Mitigations
#
Risk
Likelihood
Impact
Mitigation
R1	High DER on movie audio (score/SFX)	High	High	Demucs pre-pass; center-channel extraction; bench-driven tuning (Phase 4 dedicated)
R2	Registry false matches (wrong actor auto-assigned)	Medium	High	High auto-threshold (0.82); review band; adversarial bench as CI gate; Hungarian assignment
R3	WhisperX BSD-4 license friction	Medium	Medium	Swap-in stable-ts alignment backend via adapter
R4	pyannote HF gated-model access annoys deployers	Medium	Medium	NeMo adapter as alternative backend; docs one-time setup
R5	Profile drift (actor's voice changes: age, emotion, mic)	Medium	Medium	Multi-embedding profiles; confirmed corrections update profiles; separate profiles per language/character
R6	Overlap speech destroys attribution	High	Medium	Dual labels + overlap flags rather than forcing one speaker; human review queue
R7	Scope creep (face fusion, realtime…)	High	Medium	Strict V1 scope (§4.2); backlog for V2
R8	GPU not available for some users	Medium	Low	CPU profile (distil-whisper, int8, smaller embedder) with honest RTF documentation
R9	Vector space mismatch after model upgrade	Certain (eventual)	High	embedding_model stamped everywhere; upgrade job re-embeds reference set; never mix spaces

16. Resource & Cost Estimates
16.1 Team (V1)
Role
Allocation
ML/Backend engineer	1.0 FTE, 12 weeks
Frontend (Phase 3 only)	0.5 FTE, 3 weeks
Annotator (ground truth for benches)	0.25 FTE, spread

Realistic solo scenario: 12 weeks full-time, or ~4 months part-time.

16.2 Infrastructure (development + self-host)
Item
Est. cost
Dev GPU (cloud, e.g., RTX 4090 class)	~$0.50–0.80/hr × ~150 hrs ≈ $75–120
Postgres/Redis (self-host in Compose)	$0
Vector DB (pgvector in Compose)	$0
CI runners	Free tier likely sufficient; ~$20/mo if private heavy
Total V1 cash cost	≈ $150–300 (solo, self-hosted)

All core dependencies are open source; only pyannote weights require a one-time (free) Hugging Face terms acceptance.

17. Future Enhancements
Version
Feature
Notes
V2	Face–voice fusion	Active-speaker detection via lip movement (SyncNet-style) → auto-name from on-screen credits/cast lists
V2	Emotion & prosody tags	Per-segment emotion classification
V2	Streaming mode	Chunked realtime diarization for live captioning
V2	Auto character mapping	Align with existing subtitles → map SPK_X → character names
V3	Plugin SDK	Third-party ASR/diarization/embedding backends
V3	Cross-project search	"Find every line Marcus Chen says in the library"
V3	Dubbing pipeline hooks	Per-actor line export for dub studios

18. Appendices
A. Glossary
DER — Diarization Error Rate: fraction of speech time attributed to the wrong speaker (or missed/false speech).
WER — Word Error Rate.
RTF — Real-Time Factor: processing_time / audio_duration (lower is better).
SNR — Signal-to-Noise Ratio.
ECAPA-TDNN / TitaNet — speaker-embedding neural architectures.
AVR — VoxReel's Actor Voice Registry.
VAD — Voice Activity Detection.
B. CLI Command Reference (MVP target)
bash

voxreel ingest <file> [--lang en] [--speakers N] [--no-separation]
voxreel process <file> --registry ./vault --out srt,json
voxreel enroll "<Actor Name>" --from clip1.wav clip2.wav [--lang en]
voxreel label <session_id> --map SPK_B:"Marcus Chen" --promote
voxreel registry list | search <q> | merge <idA> <idB> | delete <id>
voxreel export <session_id> --format srt,vtt,eaf
C. Example Master JSON Output
json

{
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "pipeline": {"voxreel": "1.0.0", "embedding_model": "ecapa-tdnn-voxceleb-v2"},
  "media": {"name": "scene_04.mkv", "duration_sec": 41.8},
  "language": "en",
  "speakers": [
    {"cluster": "SPK_A", "actor": {"id": "42…", "name": "Ella Reyes"},
     "match_score": 0.93, "match_status": "auto"},
    {"cluster": "SPK_B", "actor": null, "label": "UNKNOWN_1",
     "match_score": 0.61, "match_status": "new"}
  ],
  "segments": [
    {"start": 0.84, "end": 2.31, "speaker": "SPK_A", "actor": "Ella Reyes",
     "text": "You knew about the letter?", "asr_conf": 0.97,
     "overlap": false,
     "words": [
       {"w": "You", "s": 0.84, "e": 0.96, "c": 0.99},
       {"w": "knew", "s": 0.97, "e": 1.22, "c": 0.98}
     ]}
  ]
}
D. Key References
pyannote.audio 3 — speaker diarization pipeline & metrics
WhisperX — word-level forced alignment approach
ECAPA-TDNN (SpeechBrain) / TitaNet (NeMo) — speaker embeddings
Demucs v4 — music source separation
Silero VAD — voice activity detection
pyannote.metrics — DER/JER evaluation
GDPR Art. 9 / BIPA — biometric data considerations