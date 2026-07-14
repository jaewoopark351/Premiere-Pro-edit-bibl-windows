from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .audio.presets import build_audio_filter_chain
from .timeline.models import TimeRange


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolInfo:
    name: str
    path: Path | None
    version_line: str | None

    @property
    def available(self) -> bool:
        return self.path is not None


def find_executable(name: str, explicit: Path | None = None) -> Path | None:
    if explicit:
        candidate = explicit.resolve()
        return candidate if candidate.exists() else None
    found = shutil.which(name)
    return Path(found).resolve() if found else None


def version_line(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    line = (completed.stdout or completed.stderr).splitlines()
    return line[0] if line else ""


def tool_info(name: str, explicit: Path | None = None) -> ToolInfo:
    exe = find_executable(name, explicit)
    if exe is None:
        return ToolInfo(name=name, path=None, version_line=None)
    return ToolInfo(name=name, path=exe, version_line=version_line(exe))


def run_checked(args: list[str | Path]) -> subprocess.CompletedProcess[str]:
    cmd = [str(a) for a in args]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise ToolError(
            "command failed: "
            + " ".join(cmd)
            + "\nSTDOUT:\n"
            + completed.stdout
            + "\nSTDERR:\n"
            + completed.stderr
        )
    return completed


def windows_native_path(path: Path) -> str:
    """Return a Windows-native path that ffmpeg/ffprobe can open reliably.

    Gyan FFmpeg can fail with "Illegal byte sequence" for some non-ASCII
    absolute paths. Passing an extended-length Windows path keeps the argument
    in the native filesystem namespace without shell quoting tricks.
    """
    resolved = path.resolve()
    text = str(resolved)
    if os.name != "nt":
        return text
    if text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def media_input_arg(path: Path) -> str:
    return windows_native_path(path)


def ffprobe_json(ffprobe: Path, media: Path) -> dict:
    completed = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels",
            "-of",
            "json",
            media_input_arg(media),
        ]
    )
    return json.loads(completed.stdout)


def detect_silence(ffmpeg: Path, media: Path, noise_db: float, min_silence: float, duration: float) -> list[TimeRange]:
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostats",
            "-i",
            media_input_arg(media),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
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
        raise ToolError(completed.stderr)
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?\d+\.?\d*)", completed.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?\d+\.?\d*)", completed.stderr)]
    silences: list[TimeRange] = []
    for idx, start in enumerate(starts):
        end = ends[idx] if idx < len(ends) else duration
        silences.append(TimeRange(start=max(0.0, start), end=min(duration, end)))
    return silences


def make_clean_wav(
    ffmpeg: Path,
    media: Path,
    output_wav: Path,
    sample_rate: int,
    channels: int,
    audio_preset: str = "standard",
    noise_floor_db: float | None = None,
    breath_ranges: list[TimeRange] | None = None,
) -> None:
    filter_chain = build_audio_filter_chain(audio_preset, noise_floor_db=noise_floor_db, breath_ranges=breath_ranges)
    run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            media_input_arg(media),
            "-af",
            filter_chain,
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            output_wav,
        ]
    )

def extract_audio_for_stt(ffmpeg: Path, media: Path, output_wav: Path, limit_seconds: float | None = None) -> None:
    args: list[str | Path] = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        media_input_arg(media),
    ]
    if limit_seconds is not None:
        args += ["-t", f"{limit_seconds:.3f}"]
    args += [
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        output_wav,
    ]
    run_checked(args)
