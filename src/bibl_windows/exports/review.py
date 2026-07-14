from __future__ import annotations

from collections import Counter
from typing import Any

from ..timeline.models import CutCandidate, TimeRange


def summarize_cut_review(
    candidates: list[CutCandidate],
    deletions: list[TimeRange],
    keeps: list[TimeRange],
    timeline_duration: float,
) -> dict[str, Any]:
    reasons = Counter(candidate.reason for candidate in candidates)
    review_candidates = [candidate for candidate in candidates if candidate.requires_review]
    return {
        "timeline_duration": timeline_duration,
        "deleted_duration": sum(item.duration for item in deletions),
        "kept_duration": sum(item.duration for item in keeps),
        "candidate_count": len(candidates),
        "auto_delete_candidate_count": sum(1 for item in candidates if item.auto_delete and not item.requires_review),
        "review_candidate_count": len(review_candidates),
        "reason_counts": dict(sorted(reasons.items())),
        "rejected_ranges": [range_to_dict(item) for item in deletions],
        "keep_ranges": [range_to_dict(item) for item in keeps],
        "choppy_sections": [range_to_dict(item) for item in detect_choppy_sections(deletions, timeline_duration)],
        "review_candidates": [candidate.to_dict() for candidate in review_candidates],
    }


def detect_choppy_sections(
    deletions: list[TimeRange],
    timeline_duration: float,
    window_seconds: float = 10.0,
    min_deletions: int = 3,
) -> list[TimeRange]:
    if not deletions:
        return []
    ordered = sorted(deletions, key=lambda item: (item.start, item.end))
    out: list[TimeRange] = []
    left = 0
    for right, deletion in enumerate(ordered):
        while deletion.start - ordered[left].start > window_seconds:
            left += 1
        if right - left + 1 >= min_deletions:
            out.append(TimeRange(ordered[left].start, min(timeline_duration, deletion.end)))
    return merge_touching(out)


def merge_touching(ranges: list[TimeRange]) -> list[TimeRange]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda item: (item.start, item.end))
    merged = [ordered[0]]
    for item in ordered[1:]:
        prev = merged[-1]
        if prev.touches_or_overlaps(item, eps=0.5):
            merged[-1] = TimeRange(prev.start, max(prev.end, item.end))
        else:
            merged.append(item)
    return merged


def range_to_dict(item: TimeRange) -> dict[str, float]:
    return {"start": item.start, "end": item.end, "duration": item.duration}
