from bibl_windows.timeline.models import CutCandidate, TranscriptWord
from bibl_windows.timeline.protection import protected_candidate_delete_ranges


def test_silence_deletion_protects_word_endings():
    candidates = [CutCandidate(1.0, 2.0, "long_silence", 0.8, True, False)]
    words = [TranscriptWord(0.8, 1.2, "끝")]
    ranges = protected_candidate_delete_ranges(candidates, words, total=5, fps=30, margin=0.1)
    assert ranges[0].start >= 1.3


def test_repeated_word_deletion_is_not_speech_protected():
    candidates = [CutCandidate(1.0, 1.2, "repeated_word", 0.8, True, False)]
    words = [TranscriptWord(1.0, 1.2, "안녕")]
    ranges = protected_candidate_delete_ranges(candidates, words, total=5, fps=30, margin=0.1)
    assert ranges
    assert ranges[0].start == 1.0
