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


def transcript_result_from_dict(data: dict) -> TranscriptResult:
    segments = [
        TranscriptSegment(
            start=float(segment["start"]),
            end=float(segment["end"]),
            text=str(segment.get("text", "")),
            words=[
                TranscriptWord(
                    start=float(word["start"]),
                    end=float(word["end"]),
                    text=str(word.get("text", "")),
                    confidence=word.get("confidence"),
                )
                for word in segment.get("words", [])
            ],
        )
        for segment in data.get("segments", [])
    ]
    words = [
        TranscriptWord(
            start=float(word["start"]),
            end=float(word["end"]),
            text=str(word.get("text", "")),
            confidence=word.get("confidence"),
        )
        for word in data.get("words", [])
    ]
    return TranscriptResult(
        source_audio=str(data.get("source_audio", "")),
        backend=str(data.get("backend", "unknown")),
        model=str(data.get("model", "")),
        language=str(data.get("language", "")),
        device=str(data.get("device", "unknown")),
        text=str(data.get("text", "")),
        segments=segments,
        words=words,
        warnings=[str(item) for item in data.get("warnings", [])],
        validation_issues=[str(item) for item in data.get("validation_issues", [])],
    )


class SttBackend(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        language: str,
        allow_cpu_fallback: bool,
        batch_size: int = 1,
        chunk_length_s: float = 25.0,
        initial_prompt: str | None = None,
        condition_on_previous_text: bool = True,
    ) -> TranscriptResult:
        ...
