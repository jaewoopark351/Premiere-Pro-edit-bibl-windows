from __future__ import annotations

from .mapper import merge_ranges
from .models import CutCandidate, TimeRange, TranscriptWord


SILENCE_REASONS = {"start_wait", "end_long_silence", "long_silence"}


def protected_candidate_delete_ranges(
    candidates: list[CutCandidate],
    words: list[TranscriptWord],
    total: float,
    fps: float,
    margin: float = 0.08,
) -> list[TimeRange]:
    ranges: list[TimeRange] = []
    speech = [word.range() for word in words if word.text.strip()]
    for candidate in candidates:
        if not candidate.auto_delete or candidate.requires_review:
            continue
        pieces = [candidate.range()]
        if candidate.reason in SILENCE_REASONS:
            for word_range in speech:
                if not any(piece.overlaps(word_range) for piece in pieces):
                    continue
                protected = TimeRange(max(0.0, word_range.start - margin), min(total, word_range.end + margin))
                pieces = subtract_range_list(pieces, protected)
                if not pieces:
                    break
        ranges.extend(pieces)
    return merge_ranges(ranges, total=total, fps=fps)


def subtract_range_list(ranges: list[TimeRange], blocked: TimeRange) -> list[TimeRange]:
    out: list[TimeRange] = []
    for item in ranges:
        if not item.overlaps(blocked):
            out.append(item)
            continue
        if blocked.start > item.start:
            out.append(TimeRange(item.start, min(item.end, blocked.start)))
        if blocked.end < item.end:
            out.append(TimeRange(max(item.start, blocked.end), item.end))
    return [r for r in out if r.end > r.start]
