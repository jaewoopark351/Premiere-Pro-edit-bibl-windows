from __future__ import annotations

from ..timeline.models import TranscriptSegment, TranscriptWord


def validate_words(words: list[TranscriptWord], duration: float | None = None) -> list[str]:
    issues: list[str] = []
    seen: set[tuple[float, float, str]] = set()
    previous_start = -1.0
    for idx, word in enumerate(words):
        if not word.text.strip():
            issues.append(f"word[{idx}] has empty text")
        if word.start is None or word.end is None:
            issues.append(f"word[{idx}] has empty timestamp")
            continue
        if word.start < 0 or word.end < 0:
            issues.append(f"word[{idx}] has negative timestamp")
        if word.end <= word.start:
            issues.append(f"word[{idx}] has reversed timestamp {word.start}->{word.end}")
        if word.start < previous_start:
            issues.append(f"word[{idx}] timestamp order reversed")
        if duration is not None and word.end > duration + 0.25:
            issues.append(f"word[{idx}] exceeds audio duration")
        key = (round(word.start, 3), round(word.end, 3), word.text)
        if key in seen:
            issues.append(f"word[{idx}] duplicates timestamp/text {key}")
        seen.add(key)
        previous_start = word.start
    return issues


def validate_segments(segments: list[TranscriptSegment], duration: float | None = None) -> list[str]:
    issues: list[str] = []
    previous_start = -1.0
    for idx, segment in enumerate(segments):
        if segment.end <= segment.start:
            issues.append(f"segment[{idx}] has reversed timestamp {segment.start}->{segment.end}")
        if segment.start < previous_start:
            issues.append(f"segment[{idx}] timestamp order reversed")
        if duration is not None and segment.end > duration + 0.25:
            issues.append(f"segment[{idx}] exceeds audio duration")
        previous_start = segment.start
    return issues

