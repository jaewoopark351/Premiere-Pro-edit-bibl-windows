from __future__ import annotations

from pathlib import Path

from .features import AudioFeatureSummary, read_wav_segment, segment_features
from ..timeline.models import TimeRange, TranscriptWord


def detect_breath_ranges(
    wav_path: Path,
    words: list[TranscriptWord],
    noise: AudioFeatureSummary,
    total_duration: float,
    max_ranges: int = 120,
) -> list[TimeRange]:
    ranges: list[TimeRange] = []
    for gap in speech_gaps(words, total_duration, min_gap=0.18, max_gap=1.1):
        samples, sample_rate = read_wav_segment(wav_path, gap.start, gap.end)
        features = segment_features(samples, sample_rate)
        if (
            features.rms_db > noise.noise_floor_db + 5.0
            and features.rms_db < -18.0
            and features.zero_crossing_rate > 0.04
            and features.spectral_flatness > 0.12
        ):
            ranges.append(gap)
            if len(ranges) >= max_ranges:
                break
    return ranges


def speech_gaps(words: list[TranscriptWord], total_duration: float, min_gap: float, max_gap: float) -> list[TimeRange]:
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w.start, w.end))
    gaps: list[TimeRange] = []
    cursor = max(0.0, ordered[0].end)
    for word in ordered[1:]:
        gap = word.start - cursor
        if min_gap <= gap <= max_gap:
            gaps.append(TimeRange(cursor, min(total_duration, word.start)))
        cursor = max(cursor, word.end)
    return gaps
