from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..timeline.models import TranscriptSegment, TranscriptWord


@dataclass
class TranscriptResult:
    source_audio: str
    backend: str
    model: str
    language: str
    device: str
    text: str
    segments: list[TranscriptSegment]
    words: list[TranscriptWord]
    warnings: list[str] = field(default_factory=list)
    validation_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_audio": self.source_audio,
            "backend": self.backend,
            "model": self.model,
            "language": self.language,
            "device": self.device,
            "text": self.text,
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [w.__dict__ for w in s.words],
                }
                for s in self.segments
            ],
            "words": [w.__dict__ for w in self.words],
            "warnings": self.warnings,
            "validation_issues": self.validation_issues,
        }


class SttBackend(Protocol):
    def transcribe(self, audio_path: Path, language: str, allow_cpu_fallback: bool) -> TranscriptResult:
        ...

