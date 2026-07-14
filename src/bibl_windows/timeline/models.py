from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, order=True)
class TimeRange:
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"negative start time: {self.start}")
        if self.end < self.start:
            raise ValueError(f"end before start: {self.start} > {self.end}")

    @property
    def duration(self) -> float:
        return self.end - self.start

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end

    def touches_or_overlaps(self, other: "TimeRange", eps: float = 1e-9) -> bool:
        return self.start <= other.end + eps and other.start <= self.end + eps

    def clamp(self, total: float) -> "TimeRange":
        return TimeRange(max(0.0, self.start), min(total, self.end))


@dataclass(frozen=True)
class TranscriptWord:
    start: float
    end: float
    text: str
    confidence: float | None = None

    def range(self) -> TimeRange:
        return TimeRange(self.start, self.end)


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[TranscriptWord] = field(default_factory=list)


@dataclass(frozen=True)
class CutCandidate:
    start: float
    end: float
    reason: str
    confidence: float
    auto_delete: bool
    requires_review: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def range(self) -> TimeRange:
        return TimeRange(self.start, self.end)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "reason": self.reason,
            "confidence": self.confidence,
            "auto_delete": self.auto_delete,
            "requires_review": self.requires_review,
            "metadata": self.metadata,
        }

