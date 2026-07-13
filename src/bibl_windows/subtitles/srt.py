from __future__ import annotations

from pathlib import Path

from ..timeline.models import TranscriptWord


def srt_time(seconds: float) -> str:
    t = max(0.0, seconds)
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    t -= m * 60
    s = int(t)
    ms = int(round((t - s) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def group_words(words: list[TranscriptWord], max_chars: int = 35, max_gap: float = 0.8) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    current: list[TranscriptWord] = []

    def flush() -> None:
        if not current:
            return
        cues.append((current[0].start, max(current[-1].end, current[0].start + 0.4), " ".join(w.text for w in current).strip()))
        current.clear()

    for word in words:
        text = " ".join(w.text for w in current + [word]).strip()
        if current and (len(text) > max_chars or word.start - current[-1].end > max_gap):
            flush()
        current.append(word)
        if word.text.endswith((".", "?", "!")):
            flush()
    flush()
    return cues


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for idx, (start, end, text) in enumerate(cues, 1):
            fh.write(f"{idx}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n\n")

