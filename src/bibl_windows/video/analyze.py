from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..ffmpeg_tools import detect_silence, media_input_arg
from ..media_probe import MediaInfo, probe_media


def analyze_video(ffmpeg: Path, ffprobe: Path, media_path: Path) -> dict[str, Any]:
    media = probe_media(ffprobe, media_path)
    loudness = measure_loudness(ffmpeg, media_path)
    silences = detect_silence(ffmpeg, media_path, -40.0, 0.5, media.duration)
    silence_duration = sum(item.duration for item in silences)
    data = {
        "media": media.to_dict(),
        "orientation": orientation(media),
        "silence_count": len(silences),
        "silence_duration": silence_duration,
        "silence_ratio": silence_duration / media.duration if media.duration > 0 else 0.0,
        "loudness": loudness,
    }
    data["recommended_preset"] = recommend_preset(data)
    return data


def orientation(media: MediaInfo) -> str:
    if media.video.height > media.video.width:
        return "vertical"
    if media.video.width == media.video.height:
        return "square"
    return "horizontal"


def measure_loudness(ffmpeg: Path, media_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostats",
            "-i",
            media_input_arg(media_path),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return {"available": False, "error": completed.stderr.strip()}
    match = re.search(r"\{[\s\S]*?\}", completed.stderr)
    if not match:
        return {"available": False, "error": "loudnorm JSON was not found"}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return {"available": False, "error": str(exc)}
    parsed["available"] = True
    return parsed


def recommend_preset(analysis: dict[str, Any]) -> dict[str, Any]:
    silence_ratio = float(analysis.get("silence_ratio", 0.0))
    loudness = analysis.get("loudness", {})
    input_i = _float_or_none(loudness.get("input_i"))
    reasons: list[str] = []
    preset = "standard"
    if silence_ratio >= 0.38:
        preset = "aggressive"
        reasons.append("many long silent sections")
    elif silence_ratio <= 0.12:
        preset = "conservative"
        reasons.append("dense speech or music with few silent sections")
    if input_i is not None and input_i > -18:
        reasons.append("loud background or mastered audio detected")
        if preset == "aggressive":
            preset = "standard"
    if not reasons:
        reasons.append("balanced silence and loudness profile")
    return {"preset": preset, "reasons": reasons}


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
