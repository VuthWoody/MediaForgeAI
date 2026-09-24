"""Unit tests for DirectorManager tag DSL and VoiceGenerator TTS routing."""

from __future__ import annotations

from pathlib import Path

from modules.ai.director import DirectorManager, route_translate
from modules.ai.voice_generator import VoiceGenerator, route_tts


def test_director_tag_extraction_and_stripping() -> None:
    """Verify DirectorManager parses and strips locked {tag} syntax."""
    text = "{whisper} Be very quiet, {laugh} someone might hear us! {shout:angry}"
    tags = DirectorManager.extract_tags(text)
    assert "whisper" in tags
    assert "laugh" in tags
    assert "shout:angry" in tags

    stripped = DirectorManager.strip_tags(text)
    assert stripped == "Be very quiet,  someone might hear us!"
    assert "{" not in stripped


def test_timing_max_chars_calculation() -> None:
    """Verify lip-sync character limits per language."""
    # 2.0 seconds in English -> ~30 chars
    en_chars = DirectorManager.calculate_max_chars(2.0, "en")
    assert en_chars == 30

    # 2.0 seconds in Chinese -> ~8 chars
    zh_chars = DirectorManager.calculate_max_chars(2.0, "zh")
    assert zh_chars == 8


def test_locked_routing_tables() -> None:
    """Verify Section 3 locked routing specifications."""
    # Translation routing
    assert route_translate() == ["gemini", "deepseek", "qwen", "libre"]

    # TTS routing
    assert route_tts("km") == ["edge", "qwen"]
    assert route_tts("zh") == ["qwen", "edge", "gemini"]
    assert route_tts("en") == ["gemini", "qwen", "edge"]


def test_voice_generator_speaker_presets(tmp_path: Path) -> None:
    """Verify speaker voice ID resolution."""
    vg = VoiceGenerator(cache_dir=tmp_path)
    km_v1 = vg.get_voice_for_speaker("Speaker 1", "km")
    km_v2 = vg.get_voice_for_speaker("Speaker 2", "km")
    assert km_v1 != km_v2
    assert "km-KH" in km_v1
    assert "km-KH" in km_v2

    zh_v1 = vg.get_voice_for_speaker("Speaker 1", "zh")
    assert "zh-CN" in zh_v1


def test_voice_generator_ten_distinct_speakers_khmer(tmp_path: Path) -> None:
    """Verify that 10 distinct speakers in Khmer have differentiated voice models, pitch, or rates."""
    vg = VoiceGenerator(cache_dir=tmp_path)
    speaker_settings: list[tuple[str, float, float]] = []

    for i in range(1, 11):
        spk_tag = f"Speaker {i}"
        settings = vg.resolve_speaker_voice_settings(spk_tag, "km")
        speaker_settings.append(settings)

    # Verify that consecutive speakers do not have identical (voice, pitch, rate) triples
    for i in range(len(speaker_settings) - 1):
        assert speaker_settings[i] != speaker_settings[i + 1], f"Speaker {i+1} and {i+2} are identical!"

    # Child voice (Speaker 7) has distinct high pitch
    s7_voice, s7_pitch, s7_rate = vg.resolve_speaker_voice_settings("Speaker 7 (Child)", "km")
    assert s7_pitch > 1.5
    assert s7_rate > 1.0

    # Deep Male (Speaker 3) has low pitch
    s3_voice, s3_pitch, s3_rate = vg.resolve_speaker_voice_settings("Speaker 3 (Deep Male)", "km")
    assert s3_pitch < 0.0


def test_voice_generator_smart_role_resolution(tmp_path: Path) -> None:
    """Verify keyword resolution for child, elderly, and named character roles in Chinese and English."""
    vg = VoiceGenerator(cache_dir=tmp_path)

    # Chinese child voice
    zh_child_v, _, _ = vg.resolve_speaker_voice_settings("Speaker 3: 童童 (Child)", "zh")
    assert "Xiaoshuang" in zh_child_v

    # Chinese elderly voice
    zh_old_v, old_pitch, _ = vg.resolve_speaker_voice_settings("Speaker 4: 老太太 (Elderly)", "zh")
    assert "Xiaohan" in zh_old_v
    assert old_pitch < 0.0

    # English child voice
    en_child_v, _, _ = vg.resolve_speaker_voice_settings("Kid Boy (Child)", "en")
    assert "Ana" in en_child_v
