from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from ..ffmpeg_tools import media_input_arg


def extract_envelope(ffmpeg: Path, media_path: Path, sample_rate: int = 8000, env_rate: int = 100) -> np.ndarray:
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostats",
            "-i",
            media_input_arg(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"failed to extract audio envelope: {stderr}")
    samples = np.frombuffer(completed.stdout, dtype="<i2").astype(np.float32) / 32768.0
    if samples.size == 0:
        return np.array([], dtype=np.float32)
    hop = max(1, sample_rate // env_rate)
    usable = samples[: samples.size - (samples.size % hop)]
    if usable.size == 0:
        return np.array([], dtype=np.float32)
    env = np.sqrt(np.mean(usable.reshape(-1, hop) ** 2, axis=1))
    env -= float(np.mean(env))
    std = float(np.std(env))
    if std > 0:
        env /= std
    return env.astype(np.float32)


def best_lag_seconds(a: np.ndarray, b: np.ndarray, env_rate: int = 100, max_lag_seconds: float = 300.0) -> dict:
    if a.size == 0 or b.size == 0:
        raise ValueError("cannot sync empty audio envelope")
    max_lag = int(max_lag_seconds * env_rate)
    n = 1
    while n < a.size + b.size:
        n *= 2
    corr = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    corr = np.concatenate((corr[-(b.size - 1) :], corr[: a.size]))
    lags = np.arange(-(b.size - 1), a.size)
    mask = np.abs(lags) <= max_lag
    if not np.any(mask):
        raise ValueError("max lag window is empty")
    scoped = corr[mask]
    scoped_lags = lags[mask]
    idx = int(np.argmax(scoped))
    lag_frames = int(scoped_lags[idx])
    return {
        "lag_seconds": lag_frames / env_rate,
        "meaning": "positive means second input starts earlier than first input by this many seconds",
        "score": float(scoped[idx] / max(1, min(a.size, b.size))),
    }
