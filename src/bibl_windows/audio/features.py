from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AudioFeatureSummary:
    sample_rate: int
    channels: int
    duration: float
    noise_floor_db: float
    rms_db: float
    peak_db: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SegmentFeatures:
    rms_db: float
    peak_db: float
    zero_crossing_rate: float
    spectral_centroid_hz: float
    spectral_flatness: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def measure_noise_floor(wav_path: Path, frame_seconds: float = 0.05) -> AudioFeatureSummary:
    with wave.open(str(wav_path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        total_frames = wav.getnframes()
        frame_count = max(1, int(sample_rate * frame_seconds))
        rms_values: list[float] = []
        peak = 0.0
        sum_squares = 0.0
        samples_seen = 0
        while True:
            raw = wav.readframes(frame_count)
            if not raw:
                break
            samples = pcm_to_float(raw, sample_width, channels)
            if samples.size == 0:
                continue
            peak = max(peak, float(np.max(np.abs(samples))))
            sum_squares += float(np.sum(samples * samples))
            samples_seen += int(samples.size)
            rms_values.append(float(np.sqrt(np.mean(samples * samples))))
    if not rms_values:
        return AudioFeatureSummary(sample_rate=0, channels=0, duration=0.0, noise_floor_db=-90.0, rms_db=-90.0, peak_db=-90.0)
    floor_rms = float(np.percentile(np.array(rms_values), 10))
    total_rms = math.sqrt(sum_squares / max(1, samples_seen))
    duration = total_frames / sample_rate if sample_rate else 0.0
    return AudioFeatureSummary(
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        noise_floor_db=amplitude_to_db(floor_rms),
        rms_db=amplitude_to_db(total_rms),
        peak_db=amplitude_to_db(peak),
    )


def read_wav_segment(wav_path: Path, start: float, end: float) -> tuple[np.ndarray, int]:
    if end <= start:
        return np.array([], dtype=np.float32), 0
    with wave.open(str(wav_path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        start_frame = max(0, int(start * sample_rate))
        end_frame = min(wav.getnframes(), int(end * sample_rate))
        if end_frame <= start_frame:
            return np.array([], dtype=np.float32), sample_rate
        wav.setpos(start_frame)
        raw = wav.readframes(end_frame - start_frame)
    return pcm_to_float(raw, sample_width, channels), sample_rate


def pcm_to_float(raw: bytes, sample_width: int, channels: int) -> np.ndarray:
    if sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        return np.array([], dtype=np.float32)
    if channels > 1 and data.size >= channels:
        data = data.reshape(-1, channels).mean(axis=1)
    return data


def segment_features(samples: np.ndarray, sample_rate: int) -> SegmentFeatures:
    if samples.size == 0 or sample_rate <= 0:
        return SegmentFeatures(-90.0, -90.0, 0.0, 0.0, 1.0)
    samples = samples.astype(np.float32, copy=False)
    abs_samples = np.abs(samples)
    rms = float(np.sqrt(np.mean(samples * samples)))
    peak = float(np.max(abs_samples))
    signs = np.signbit(samples)
    zcr = float(np.count_nonzero(signs[1:] != signs[:-1]) / max(1, samples.size - 1))
    window = np.hanning(samples.size).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(samples * window)) + 1e-12
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    centroid = float(np.sum(freqs * spectrum) / np.sum(spectrum))
    flatness = float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum))
    return SegmentFeatures(
        rms_db=amplitude_to_db(rms),
        peak_db=amplitude_to_db(peak),
        zero_crossing_rate=zcr,
        spectral_centroid_hz=centroid,
        spectral_flatness=flatness,
    )


def amplitude_to_db(value: float) -> float:
    return 20.0 * math.log10(max(float(value), 1e-9))
