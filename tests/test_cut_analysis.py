from pathlib import Path

from bibl_windows.analysis.cuts import (
    apply_preset_policy,
    false_start_candidates,
    hesitation_candidates,
    looks_like_music_source,
    repeated_speech_candidates,
    short_meaningless_candidates,
    silence_candidates,
    source_repetition_profile,
)
from bibl_windows.presets import load_preset
from bibl_windows.timeline.mapper import candidate_delete_ranges
from bibl_windows.timeline.models import CutCandidate, TimeRange, TranscriptWord


def test_silence_candidate_start_wait():
    candidates = silence_candidates([TimeRange(0, 2)], total=10, long_silence=3, start_wait=1, end_silence=2, pad_before=0.1, pad_after=0.1)
    assert candidates[0].reason == "start_wait"
    assert candidates[0].auto_delete is False
    assert candidates[0].requires_review is True


def test_standard_policy_promotes_silence_candidate_from_config():
    candidates = silence_candidates([TimeRange(0, 2)], total=10, long_silence=3, start_wait=1, end_silence=2, pad_before=0.1, pad_after=0.1)

    standard = apply_preset_policy(candidates, "standard", load_preset(Path("config/standard.json")))

    assert standard[0].reason == "start_wait"
    assert standard[0].auto_delete is True
    assert standard[0].requires_review is False


def test_repeated_speech_candidate():
    words = [TranscriptWord(1, 1.2, "안녕"), TranscriptWord(1.3, 1.5, "안녕")]
    candidates = repeated_speech_candidates(words, max_gap=0.5, pad=0.01)
    assert len(candidates) == 1
    assert candidates[0].reason == "repeated_word"
    assert candidates[0].auto_delete is False
    assert candidates[0].requires_review is True


def test_standard_policy_promotes_repeated_speech_from_config():
    words = [TranscriptWord(1, 1.2, "안녕"), TranscriptWord(1.3, 1.5, "안녕")]
    candidates = repeated_speech_candidates(words, max_gap=0.5, pad=0.01)

    standard = apply_preset_policy(candidates, "standard", load_preset(Path("config/standard.json")))

    assert standard[0].reason == "repeated_word"
    assert standard[0].auto_delete is True
    assert standard[0].requires_review is False


def test_repeated_phrase_candidate():
    words = [
        TranscriptWord(1.0, 1.2, "hello"),
        TranscriptWord(1.25, 1.5, "world"),
        TranscriptWord(1.65, 1.85, "hello"),
        TranscriptWord(1.9, 2.1, "world"),
    ]

    candidates = repeated_speech_candidates(words, max_gap=0.5, pad=0.01)

    assert any(candidate.reason == "repeated_phrase" for candidate in candidates)


def test_false_start_prefix_candidate_requires_review():
    words = [
        TranscriptWord(1.0, 1.15, "record"),
        TranscriptWord(1.2, 1.55, "recording"),
    ]

    candidates = false_start_candidates(words, max_gap=0.5, pad=0.01, ratio=0.75)

    assert len(candidates) == 1
    assert candidates[0].reason == "false_start_prefix"
    assert candidates[0].requires_review is True


def test_aggressive_policy_turns_false_start_into_auto_delete():
    words = [
        TranscriptWord(1.0, 1.15, "record"),
        TranscriptWord(1.2, 1.55, "recording"),
    ]
    candidates = false_start_candidates(words, max_gap=0.5, pad=0.01, ratio=0.75)

    aggressive = apply_preset_policy(candidates, "aggressive", {"policy": {"auto_delete_reasons": []}})

    assert aggressive[0].reason == "false_start_prefix"
    assert aggressive[0].auto_delete is True
    assert aggressive[0].requires_review is False


def test_aggressive_policy_turns_text_filler_into_auto_delete():
    words = [TranscriptWord(1.0, 1.12, "어")]
    candidates = short_meaningless_candidates(words, max_duration=0.45, pad=0.01)

    aggressive = apply_preset_policy(candidates, "aggressive", {"policy": {"auto_delete_reasons": []}})

    assert aggressive[0].reason == "short_meaningless_utterance"
    assert aggressive[0].auto_delete is True
    assert aggressive[0].requires_review is False


def test_conservative_and_aggressive_produce_different_delete_ranges():
    words = [
        TranscriptWord(1.0, 1.15, "record"),
        TranscriptWord(1.2, 1.55, "recording"),
    ]
    candidates = false_start_candidates(words, max_gap=0.5, pad=0.01, ratio=0.75)

    conservative = apply_preset_policy(candidates, "conservative", {"policy": {"auto_delete_reasons": []}})
    aggressive = apply_preset_policy(candidates, "aggressive", {"policy": {"auto_delete_reasons": []}})

    assert candidate_delete_ranges(conservative, total=5.0, fps=30.0) == []
    assert candidate_delete_ranges(aggressive, total=5.0, fps=30.0) == [TimeRange(1.0, 1.1666666666666667)]


def test_policy_demotes_existing_auto_delete_when_reason_is_not_allowed():
    candidates = [
        CutCandidate(
            start=1.0,
            end=1.5,
            reason="repeated_word",
            confidence=0.9,
            auto_delete=True,
            requires_review=False,
            metadata={},
        )
    ]

    conservative = apply_preset_policy(candidates, "conservative", {"policy": {"auto_delete_reasons": []}})

    assert conservative[0].auto_delete is False
    assert conservative[0].requires_review is True


def test_contextual_jom_is_not_auto_deleted_by_aggressive_policy():
    words = [
        TranscriptWord(1.0, 1.12, "좀"),
        TranscriptWord(1.15, 1.35, "더"),
    ]
    candidates = short_meaningless_candidates(words, max_duration=0.45, pad=0.01)

    aggressive = apply_preset_policy(candidates, "aggressive", {"policy": {"auto_delete_reasons": []}})

    assert aggressive[0].metadata["protected_context"] is True
    assert aggressive[0].requires_review is True


def test_hesitation_candidate_uses_silence_between_words():
    words = [
        TranscriptWord(1.0, 1.2, "a"),
        TranscriptWord(2.0, 2.2, "b"),
    ]
    candidates = hesitation_candidates([TimeRange(1.2, 2.0)], words, min_duration=0.5, pad=0.05)

    assert len(candidates) == 1
    assert candidates[0].reason == "hesitation_silence"


def test_music_like_repetition_gate_keeps_repeated_candidates_review_only():
    words = [TranscriptWord(idx * 0.8, idx * 0.8 + 0.2, "음") for idx in range(40)]
    assert looks_like_music_source(words, duration=60.0)
    profile = source_repetition_profile(words, duration=60.0)
    candidates = repeated_speech_candidates(words, max_gap=1.0, pad=0.01, protect_auto_delete=profile["music_like"])

    standard = apply_preset_policy(candidates, "standard", load_preset(Path("config/standard.json")))

    assert candidates
    assert all(candidate.metadata.get("source_type_gate") == "music_like_repetition" for candidate in standard)
    assert all(candidate.auto_delete is False for candidate in standard)
    assert all(candidate.requires_review is True for candidate in standard)


def test_dense_varied_speech_is_not_music_like_source():
    words = [TranscriptWord(idx * 0.2, idx * 0.2 + 0.1, f"word{idx}") for idx in range(30)]

    profile = source_repetition_profile(words, duration=6.0)

    assert profile["music_like"] is False
    assert profile["word_density"] > 1.7


def test_preset_policy_configs_match_original_editing_roles():
    standard = load_preset(Path("config/standard.json"))
    conservative = load_preset(Path("config/conservative.json"))
    aggressive = load_preset(Path("config/aggressive.json"))

    assert set(standard["policy"]["auto_delete_reasons"]) >= {
        "start_wait",
        "end_long_silence",
        "long_silence",
        "repeated_word",
        "repeated_phrase",
    }
    assert conservative["policy"]["auto_delete_reasons"] == []
    assert set(aggressive["policy"]["auto_delete_reasons"]) >= {
        "start_wait",
        "end_long_silence",
        "long_silence",
        "repeated_word",
        "repeated_phrase",
        "short_meaningless_utterance",
        "hesitation_silence",
        "acoustic_filler",
        "false_start_prefix",
        "false_start_repeat",
    }
    assert aggressive["policy"]["remove_fillers"] is True
    assert aggressive["policy"]["remove_hesitation"] is True
    assert aggressive["policy"]["acoustic_filler"] is True
