from bibl_windows.subtitles.srt import group_words, srt_time
from bibl_windows.timeline.models import TranscriptWord


def test_srt_time_rounding():
    assert srt_time(1.2344) == "00:00:01,234"
    assert srt_time(-1) == "00:00:00,000"


def test_group_words_by_length():
    words = [
        TranscriptWord(0, 0.2, "hello"),
        TranscriptWord(0.3, 0.5, "world"),
        TranscriptWord(1.5, 1.7, "again"),
    ]
    cues = group_words(words, max_gap=0.8)
    assert len(cues) == 2

