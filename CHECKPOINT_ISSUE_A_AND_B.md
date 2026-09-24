# MediaForge AI — Issue Checkpoint Report

**Date:** 2026-09-24  
**Project:** MediaForge AI  
**Reference Video:** `English Conversation Practice Between Two Friends ｜ English Listening Practice ｜ English Speaking.mp4`

---

## 1. Checkpoint: Issue A (Khmer Translation Truncation) — [FIXED & LOCKED]

### Root Cause
In [`modules/ai/providers/libre_translate.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/modules/ai/providers/libre_translate.py), an arbitrary character length cap was slicing translated sentences mid-word before return, resulting in incomplete Khmer sentences like *"ការសន្ទនាភាសាអង់គ្លេសរវាង..."* (cut off).

### Resolution
- Removed string-slicing restrictions in LibreTranslate provider.
- Verified 100% complete Khmer sentences preserved with punctuation:
  - **Segment 01:** *"English Conversation Between Two Friends"* $\rightarrow$ `ការសន្ទនាភាសាអង់គ្លេសរវាងមិត្តពីរនាក់`
  - **Segment 49:** *"Yeah, I'll see you soon. You take care too. Bye."* $\rightarrow$ `បាទ ខ្ញុំនឹងជួបអ្នកឆាប់ៗនេះ។ អ្នកក៏ថែរក្សាដែរ លាហើយ`
- Status: **Saved as verified checkpoint.**

---

## 2. Checkpoint: Issue B (Single Speaker Dubbing & Multi-Actor Cloning) — [FIXED & VERIFIED]

### Root Causes
1. **Average-Linkage Diarization Chaining:**
   The deterministic agglomerative clustering in [`modules/ai/diarizer.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/modules/ai/diarizer.py) on unstandardized positive feature vectors caused agglomerative chaining, placing 49 segments in Cluster 0 and isolating only 1 segment (Segment 50) in Cluster 1.
2. **Tenor Male Frequency Threshold:**
   James speaks at an average pitch of $F_0 \approx 178\text{ Hz}$. A rigid female threshold of $\ge 175\text{ Hz}$ in `_classify_voice_profile` previously misclassified tenor male voices as `Mature Female`.
3. **Stale TTS Cache Reuse:**
   When re-running on an existing work directory, old single-speaker clips (`tts_*.wav`) were reused without checking whether speaker assignments had changed.

### Resolutions
1. **Upgraded Diarization to K-Means++ Clustering ([`modules/ai/diarizer.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/modules/ai/diarizer.py)):**
   - Replaced chaining-prone agglomerative clustering with robust K-Means with K-Means++ initialization and multiple restarts on standardized acoustic feature vectors.
   - Result: Perfectly balanced and accurate separation:
     - **Speaker 1 (Mature Female / Emma):** 27 segments
     - **Speaker 2 (Male Lead / James):** 23 segments
     - Alternating dialogue: Seg 1 (Emma), Seg 2 (Emma), Seg 3 (James), Seg 4 (Emma), Seg 5 (James)...
2. **Integrated OpenBMB VoxCPM2 Voice Cloning Engine ([`modules/ai/providers/voxcpm_tts.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/modules/ai/providers/voxcpm_tts.py)):**
   - Automatic reference audio extraction per actor from separated vocal stems:
     - `ref_Speaker_1__Mature_Female_.wav` (Emma's acoustic timbre & pitch)
     - `ref_Speaker_2__Male_Lead_.wav` (James's acoustic timbre & pitch)
   - Zero-shot pitch & rate modulation tailoring synthesis to each actor's unique vocal profile.
   - Acoustic inspection of synthesized speech clips confirms distinct pitches:
     - **Emma (Female Clone):** $F_0 = 229.0\text{ Hz} - 240.1\text{ Hz}$
     - **James (Male Clone):** $F_0 = 165.2\text{ Hz} - 182.5\text{ Hz}$
3. **Pipeline Invalidation & FFmpeg Unicode Path Sanitization ([`modules/processing/pipeline.py`](file:///c:/Users/sakpo/OneDrive/Desktop/Tool/MediaForgeAI/modules/processing/pipeline.py)):**
   - Implemented `.speakers_manifest.json` in `tts_clips/` to automatically invalidate stale single-speaker clips when diarization changes.
   - Sanitized `workdir` path removing full-width unicode characters (`｜` $\rightarrow$ `_`), eliminating MinGW FFmpeg error code 4294967294.

---

## 3. Test Suite & Verification Summary
- **Unit Tests:** `142 passed, 1 warning` (`pytest tests/unit/ -v` 100% green)
- **Linter:** `All checks passed!` (`ruff check`)
- **Rendered Output:**
  - File: `English Conversation Practice Between Two Friends ｜ English Listening Practice ｜ English Speaking_dubbed_km.mp4`
  - Duration: 272.94s (4m 33s)
  - Video Codec: AV1 1920x1080
  - Audio: AAC 44.1 kHz multi-speaker dubbed dialogue with ducked original BGM
