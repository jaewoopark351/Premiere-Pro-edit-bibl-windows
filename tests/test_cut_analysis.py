from bibl_windows.analysis.cuts import false_start_candidates, repeated_speech_candidates, silence_candidates
from bibl_windows.timeline.models import TimeRange, TranscriptWord


def test_silence_candidate_start_wait():
    candidates = silence_candidates([TimeRange(0, 2)], total=10, long_silence=3, start_wait=1, end_silence=2, pad_before=0.1, pad_after=0.1)
    assert candidates[0].reason == "start_wait"
    assert candidates[0].auto_delete is True


def test_repeated_speech_candidate():
    words = [TranscriptWord(1, 1.2, "안녕"), TranscriptWord(1.3, 1.5, "안녕")]
    candidates = repeated_speech_candidates(words, max_gap=0.5, pad=0.01)
    assert len(candidates) == 1
    assert candidates[0].reason == "repeated_word"


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
