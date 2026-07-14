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


def polish_cues(
    cues: list[tuple[float, float, str]],
    max_chars: int = 35,
    fill_gap_seconds: float = 0.35,
) -> list[tuple[float, float, str]]:
    split = split_long_cues(cues, max_chars=max_chars)
    return fill_small_gaps(split, max_gap=fill_gap_seconds)


def split_long_cues(cues: list[tuple[float, float, str]], max_chars: int = 35) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for start, end, text in cues:
        parts = split_text(text, max_chars=max_chars)
        if len(parts) <= 1:
            out.append((start, end, text.strip()))
            continue
        duration = max(0.4, end - start)
        step = duration / len(parts)
        for idx, part in enumerate(parts):
            part_start = start + step * idx
            part_end = end if idx == len(parts) - 1 else start + step * (idx + 1)
            out.append((round(part_start, 3), round(max(part_start + 0.25, part_end), 3), part))
    return out


def split_text(text: str, max_chars: int = 35) -> list[str]:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return [cleaned] if cleaned else []
    words = cleaned.split(" ")
    parts: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word]).strip()
        if current and len(candidate) > max_chars:
            parts.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        parts.append(" ".join(current))
    return parts or [cleaned]


def fill_small_gaps(cues: list[tuple[float, float, str]], max_gap: float = 0.35) -> list[tuple[float, float, str]]:
    if not cues:
        return []
    out = list(cues)
    for idx in range(len(out) - 1):
        start, end, text = out[idx]
        next_start, _next_end, _next_text = out[idx + 1]
        gap = next_start - end
        if 0 < gap <= max_gap:
            out[idx] = (start, round(next_start, 3), text)
    return out
