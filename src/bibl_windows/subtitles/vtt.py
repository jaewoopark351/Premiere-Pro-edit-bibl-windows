from __future__ import annotations

from pathlib import Path

from .srt import srt_time


def vtt_time(seconds: float) -> str:
    return srt_time(seconds).replace(",", ".")


def write_vtt(cues: list[tuple[float, float, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("WEBVTT\n\n")
        for start, end, text in cues:
            fh.write(f"{vtt_time(start)} --> {vtt_time(end)}\n{text}\n\n")
