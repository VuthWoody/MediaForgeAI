"""Unit tests for KhmerDialogueLocalizer."""

from __future__ import annotations

from modules.ai.khmer_localizer import KhmerDialogueLocalizer


def test_detect_gender() -> None:
    assert KhmerDialogueLocalizer.detect_gender("Speaker 1 (Mature Female)") == "female"
    assert KhmerDialogueLocalizer.detect_gender("Emma") == "female"
    assert KhmerDialogueLocalizer.detect_gender("Speaker 2 (Male Lead)") == "male"
    assert KhmerDialogueLocalizer.detect_gender("James") == "male"
    assert KhmerDialogueLocalizer.detect_gender(None) == "neutral"
    assert KhmerDialogueLocalizer.detect_gender("Narrator") == "neutral"


def test_naturalize_greetings_and_catchup() -> None:
    # "Hey James, how are you?"
    raw = "ហេ James, សុខសប្បាយជាទេ?"
    res = KhmerDialogueLocalizer.naturalize(raw, speaker_gender="female")
    assert "សួស្តី James!" in res
    assert "សុខសប្បាយអត់" in res

    # "Oh my god, Emma, I am good. How are you?"
    raw_omg = "ឱព្រះជាម្ចាស់អើយ អិមម៉ា ខ្ញុំល្អណាស់។ សុខសប្បាយជាទេ?"
    res_omg = KhmerDialogueLocalizer.naturalize(raw_omg, speaker_gender="male")
    assert "អូព្រះអើយ!" in res_omg
    assert "ខ្ញុំសុខសប្បាយធម្មតាទេ" in res_omg

    # "I am amazing."
    raw_amz = "ខ្ញុំអស្ចារ្យណាស់។"
    res_amz = KhmerDialogueLocalizer.naturalize(raw_amz, speaker_gender="female")
    assert "សប្បាយចិត្តខ្លាំងណាស់!" in res_amz


def test_naturalize_seating_and_long_time_no_see() -> None:
    # "Great. Take the seat. This seat is empty."
    raw_seat = "អស្ចារ្យ។ យកកន្លែងអង្គុយ។ កៅអីនេះគឺទទេ។"
    res_seat = KhmerDialogueLocalizer.naturalize(raw_seat, speaker_gender="male")
    assert "អង្គុយទីនេះមក" in res_seat
    assert "កៅអីនេះទំនេរតើ!" in res_seat

    # "Long time. Now see?"
    raw_ltns = "យូរ។ ឥឡូវឃើញទេ?"
    res_ltns = KhmerDialogueLocalizer.naturalize(raw_ltns, speaker_gender="female")
    assert "ខានជួបគ្នាយូរណាស់ហើយ" in res_ltns


def test_gender_specific_particles() -> None:
    # Female saying 'បាទ' should be corrected to 'ចាស'
    raw_female = "បាទ ខ្ញុំដឹង។"
    res_female = KhmerDialogueLocalizer.naturalize(raw_female, speaker_gender="female")
    assert "ចាស" in res_female
    assert "បាទ" not in res_female

    # Male saying 'ចាស' should be corrected to 'បាទ'
    raw_male = "ចាស ខ្ញុំដឹង។"
    res_male = KhmerDialogueLocalizer.naturalize(raw_male, speaker_gender="male")
    assert "បាទ" in res_male
    assert "ចាស" not in res_male


def test_conversational_pronouns() -> None:
    # "What about you?" -> "ចុះឯងវិញ?"
    raw_way = "បាទរវល់ជាមួយមហាវិទ្យាល័យ។ ចុះអ្នកវិញ?"
    res_way = KhmerDialogueLocalizer.naturalize(raw_way, speaker_gender="male")
    assert "ចុះឯងវិញ?" in res_way
    assert "រវល់រឿងរៀនសូត្រនៅមហាវិទ្យាល័យ" in res_way


def test_non_khmer_passthrough() -> None:
    english = "Hello world! This is a test."
    assert KhmerDialogueLocalizer.naturalize(english) == english
    assert KhmerDialogueLocalizer.naturalize("") == ""
