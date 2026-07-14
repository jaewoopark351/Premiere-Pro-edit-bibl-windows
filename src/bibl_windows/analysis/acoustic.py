from __future__ import annotations

from pathlib import Path

from ..audio.breath import speech_gaps
from ..audio.features import AudioFeatureSummary, read_wav_segment, segment_features
from ..timeline.models import CutCandidate, TranscriptWord


def acoustic_filler_candidates(
    wav_path: Path,
    words: list[TranscriptWord],
    noise: AudioFeatureSummary,
    total_duration: float,
    pad: float = 0.03,
    max_candidates: int = 100,
) -> list[CutCandidate]:
    out: list[CutCandidate] = []
    for gap in speech_gaps(words, total_duration, min_gap=0.25, max_gap=1.25):
        samples, sample_rate = read_wav_segment(wav_path, gap.start, gap.end)
        features = segment_features(samples, sample_rate)
        sustained_voice = (
            features.rms_db > noise.noise_floor_db + 8.0
            and features.rms_db < -12.0
            and features.zero_crossing_rate < 0.12
            and features.spectral_centroid_hz < 2200.0
            and features.spectral_flatness < 0.35
        )
        if not sustained_voice:
            continue
        out.append(
            CutCandidate(
                start=max(0.0, gap.start - pad),
                end=min(total_duration, gap.end + pad),
                reason="acoustic_filler",
                confidence=0.55,
                auto_delete=False,
                requires_review=True,
                metadata={"source": "audio_features", "features": features.to_dict()},
            )
        )
        if len(out) >= max_candidates:
            break
    return out
