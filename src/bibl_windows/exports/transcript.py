from __future__ import annotations

import csv
from pathlib import Path

from ..timeline.models import TranscriptWord


def timestamp(seconds: float) -> str:
    total = int(max(0.0, seconds))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def paragraphs(words: list[TranscriptWord], max_gap: float = 1.2, max_chars: int = 280) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    current: list[TranscriptWord] = []

    def flush() -> None:
        if not current:
            return
        out.append((current[0].start, current[-1].end, " ".join(w.text for w in current).strip()))
        current.clear()

    for word in words:
        candidate = " ".join(w.text for w in current + [word]).strip()
        if current and (word.start - current[-1].end > max_gap or len(candidate) > max_chars):
            flush()
        current.append(word)
    flush()
    return out


def write_transcript_markdown(words: list[TranscriptWord], path: Path, title: str) -> None:
    lines = [f"# {title}", ""]
    for start, end, text in paragraphs(words):
        lines.append(f"## {timestamp(start)} - {timestamp(end)}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_transcript_text(words: list[TranscriptWord], path: Path) -> None:
    lines = [f"[{timestamp(start)} - {timestamp(end)}] {text}" for start, end, text in paragraphs(words)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")


def write_transcript_csv(words: list[TranscriptWord], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["start", "end", "text", "confidence"])
        for word in words:
            writer.writerow([f"{word.start:.3f}", f"{word.end:.3f}", word.text, "" if word.confidence is None else word.confidence])
