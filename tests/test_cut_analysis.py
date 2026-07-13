from bibl_windows.analysis.cuts import repeated_speech_candidates, silence_candidates
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

