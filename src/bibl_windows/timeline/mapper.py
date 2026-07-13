from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .models import CutCandidate, TimeRange, TranscriptWord


def align_time(t: float, fps: float) -> float:
    if fps <= 0:
        return max(0.0, t)
    return max(0.0, round(t * fps) / fps)


def merge_ranges(ranges: list[TimeRange], total: float | None = None, fps: float | None = None) -> list[TimeRange]:
    cleaned: list[TimeRange] = []
    for r in ranges:
        start = r.start
        end = r.end
        if total is not None:
            start = max(0.0, min(total, start))
            end = max(0.0, min(total, end))
        if fps:
            start = align_time(start, fps)
            end = align_time(end, fps)
        if end > start:
            cleaned.append(TimeRange(start, end))
    cleaned.sort(key=lambda r: (r.start, r.end))
    merged: list[TimeRange] = []
    for r in cleaned:
        if merged and merged[-1].touches_or_overlaps(r):
            merged[-1] = TimeRange(merged[-1].start, max(merged[-1].end, r.end))
        else:
            merged.append(r)
    return merged


def candidate_delete_ranges(candidates: list[CutCandidate], total: float, fps: float) -> list[TimeRange]:
    ranges = [c.range() for c in candidates if c.auto_delete and not c.requires_review]
    return merge_ranges(ranges, total=total, fps=fps)


def keep_ranges_from_deletions(deletions: list[TimeRange], total: float, fps: float) -> list[TimeRange]:
    deletions = merge_ranges(deletions, total=total, fps=fps)
    keeps: list[TimeRange] = []
    cursor = 0.0
    for deletion in deletions:
        if deletion.start > cursor:
            keeps.append(TimeRange(align_time(cursor, fps), align_time(deletion.start, fps)))
        cursor = max(cursor, deletion.end)
    if cursor < total:
        keeps.append(TimeRange(align_time(cursor, fps), align_time(total, fps)))
    return [r for r in keeps if r.duration > 0]


@dataclass(frozen=True)
class TimelineMapper:
    total_duration: float
    fps: float
    deletions: list[TimeRange]

    def __post_init__(self) -> None:
        object.__setattr__(self, "deletions", merge_ranges(self.deletions, self.total_duration, self.fps))
        keeps = keep_ranges_from_deletions(self.deletions, self.total_duration, self.fps)
        object.__setattr__(self, "keeps", keeps)
        starts = [k.start for k in keeps]
        object.__setattr__(self, "_starts", starts)
        offsets = []
        acc = 0.0
        for keep in keeps:
            offsets.append(acc)
            acc += keep.duration
        object.__setattr__(self, "_offsets", offsets)
        object.__setattr__(self, "edited_duration", acc)

    def source_to_edit(self, t: float) -> float | None:
        if t < 0 or t > self.total_duration:
            return None
        idx = bisect_right(self._starts, t) - 1
        if idx < 0:
            return None
        keep = self.keeps[idx]
        if keep.start <= t <= keep.end:
            return self._offsets[idx] + (t - keep.start)
        return None

    def map_word(self, word: TranscriptWord) -> TranscriptWord | None:
        midpoint = (word.start + word.end) / 2.0
        mapped_mid = self.source_to_edit(midpoint)
        if mapped_mid is None:
            return None
        mapped_start = self.source_to_edit(word.start)
        mapped_end = self.source_to_edit(word.end)
        duration = max(0.05, word.end - word.start)
        if mapped_start is None:
            mapped_start = mapped_mid
        if mapped_end is None or mapped_end <= mapped_start:
            mapped_end = mapped_start + duration
        return TranscriptWord(
            start=round(align_time(mapped_start, self.fps), 3),
            end=round(align_time(mapped_end, self.fps), 3),
            text=word.text,
            confidence=word.confidence,
        )

    def remap_words(self, words: list[TranscriptWord]) -> list[TranscriptWord]:
        mapped = [w for w in (self.map_word(word) for word in words) if w is not None]
        mapped.sort(key=lambda w: (w.start, w.end))
        return mapped

