from bibl_windows.timeline.mapper import TimelineMapper, candidate_delete_ranges, keep_ranges_from_deletions, merge_ranges
from bibl_windows.timeline.models import CutCandidate, TimeRange, TranscriptWord


def test_merge_overlapping_ranges():
    merged = merge_ranges([TimeRange(1, 2), TimeRange(1.5, 3), TimeRange(4, 5)], total=10, fps=30)
    assert merged == [TimeRange(1, 3), TimeRange(4, 5)]


def test_keep_ranges_from_deletions():
    keeps = keep_ranges_from_deletions([TimeRange(2, 4), TimeRange(6, 7)], total=10, fps=30)
    assert keeps == [TimeRange(0, 2), TimeRange(4, 6), TimeRange(7, 10)]


def test_source_to_edit_mapping():
    mapper = TimelineMapper(total_duration=10, fps=30, deletions=[TimeRange(2, 4), TimeRange(6, 7)])
    assert mapper.source_to_edit(1) == 1
    assert mapper.source_to_edit(3) is None
    assert mapper.source_to_edit(5) == 3
    assert mapper.source_to_edit(8) == 5


def test_word_in_deleted_range_is_removed():
    mapper = TimelineMapper(total_duration=10, fps=30, deletions=[TimeRange(2, 4)])
    words = [TranscriptWord(1, 1.2, "keep"), TranscriptWord(2.2, 2.4, "drop"), TranscriptWord(5, 5.2, "after")]
    mapped = mapper.remap_words(words)
    assert [w.text for w in mapped] == ["keep", "after"]
    assert mapped[1].start == 3


def test_candidate_delete_ranges_only_auto_and_no_review():
    candidates = [
        CutCandidate(1, 2, "auto", 0.9, True, False),
        CutCandidate(3, 4, "review", 0.7, False, True),
    ]
    assert candidate_delete_ranges(candidates, total=5, fps=30) == [TimeRange(1, 2)]

