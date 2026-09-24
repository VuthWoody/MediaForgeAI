"""Unit tests for VoxCPM2 Voice Cloning & Actor Registry TTS Provider."""

import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from modules.ai.providers.voxcpm_tts import (
    VOXCPM_ACTORS,
    VoxCPMProvider,
    analyze_reference_audio,
)
from modules.ai.voice_generator import VoiceGenerator


def _create_sine_wav(path: Path, freq: float, duration: float = 1.0, sr: int = 16000) -> None:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def test_voxcpm_actors_catalog() -> None:
    assert len(VOXCPM_ACTORS) >= 5
    actor_ids = [a["id"] for a in VOXCPM_ACTORS]
    assert "khmer_piseth_actor" in actor_ids
    assert "khmer_sreymom_actor" in actor_ids


def test_analyze_reference_audio_female(tmp_path: Path) -> None:
    wav_path = tmp_path / "female_220hz.wav"
    _create_sine_wav(wav_path, freq=220.0, duration=1.0)

    analysis = analyze_reference_audio(wav_path)
    assert analysis["gender"] == "female"
    assert abs(analysis["pitch_hz"] - 220.0) < 15.0


def test_analyze_reference_audio_male(tmp_path: Path) -> None:
    wav_path = tmp_path / "male_130hz.wav"
    _create_sine_wav(wav_path, freq=130.0, duration=1.0)

    analysis = analyze_reference_audio(wav_path)
    assert analysis["gender"] == "male"
    assert abs(analysis["pitch_hz"] - 130.0) < 15.0


def test_voxcpm_provider_probe() -> None:
    provider = VoxCPMProvider()
    avail = provider.probe()
    assert avail.status == "ready"


def test_voxcpm_zero_shot_synthesis(tmp_path: Path) -> None:
    provider = VoxCPMProvider()
    ref_wav = tmp_path / "ref_actor.wav"
    out_wav = tmp_path / "out_speech.wav"
    _create_sine_wav(ref_wav, freq=210.0, duration=1.0)

    fake_meta = MagicMock()
    fake_meta.duration = 1.2
    fake_meta.file_path = str(out_wav)

    def fake_subprocess_run(cmd, *args, **kwargs):
        _create_sine_wav(out_wav, freq=210.0, duration=1.2)
        return MagicMock(returncode=0)

    with (
        patch("asyncio.run"),
        patch("subprocess.run", side_effect=fake_subprocess_run),
        patch("modules.media.inspector.MediaInspector.probe", return_value=fake_meta),
    ):
        res = provider.generate_speech(
            text="ជំរាបសួរ",
            voice_id="km-KH-SreymomNeural",
            output_wav=out_wav,
            reference_audio=ref_wav,
            target_lang="km",
        )
        assert res.audio_path == out_wav
        assert "voxcpm" in res.provider


def test_voice_generator_voxcpm_routing(tmp_path: Path) -> None:
    vg = VoiceGenerator(cache_dir=tmp_path)
    assert "voxcpm" in vg.providers

    ref_wav = tmp_path / "ref_actor.wav"
    out_wav = tmp_path / "tts_out.wav"
    _create_sine_wav(ref_wav, freq=140.0, duration=1.0)

    def fake_generate_speech(*args, **kwargs):
        _create_sine_wav(out_wav, freq=140.0, duration=1.5)
        from modules.ai.providers.base import TTSResult
        return TTSResult(
            audio_path=out_wav,
            duration_sec=1.5,
            provider="voxcpm",
            voice_id="km-KH-PisethNeural",
        )

    with patch.object(vg.providers["voxcpm"], "generate_speech", side_effect=fake_generate_speech):
        res = vg.generate_speech(
            text="សួស្តីបងប្អូន",
            target_lang="km",
            speaker="Speaker 1 (Male Lead)",
            output_wav=out_wav,
            reference_audio=ref_wav,
            preferred_provider="voxcpm",
        )
        assert res.provider == "voxcpm"
