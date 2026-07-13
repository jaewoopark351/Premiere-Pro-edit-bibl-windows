from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path

from .ffmpeg_tools import ffprobe_json


@dataclass(frozen=True)
class VideoStream:
    index: int
    codec_name: str | None
    width: int
    height: int
    fps: float
    fps_text: str


@dataclass(frozen=True)
class AudioStream:
    index: int
    codec_name: str | None
    sample_rate: int
    channels: int


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float
    video: VideoStream
    audio: AudioStream

    def to_dict(self) -> dict:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


def parse_fps(value: str | None) -> tuple[float, str]:
    text = value or "0/1"
    try:
        frac = Fraction(text)
        return float(frac), text
    except Exception:
        return 0.0, text


def probe_media(ffprobe: Path, media: Path) -> MediaInfo:
    raw = ffprobe_json(ffprobe, media)
    streams = raw.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise ValueError(f"no video stream found: {media}")
    if audio_stream is None:
        raise ValueError(f"no audio stream found: {media}")
    fps, fps_text = parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
    if fps <= 0:
        fps, fps_text = parse_fps(video_stream.get("r_frame_rate"))
    duration = float(raw.get("format", {}).get("duration", 0.0))
    return MediaInfo(
        path=media.resolve(),
        duration=duration,
        video=VideoStream(
            index=int(video_stream.get("index", 0)),
            codec_name=video_stream.get("codec_name"),
            width=int(video_stream["width"]),
            height=int(video_stream["height"]),
            fps=fps,
            fps_text=fps_text,
        ),
        audio=AudioStream(
            index=int(audio_stream.get("index", 0)),
            codec_name=audio_stream.get("codec_name"),
            sample_rate=int(audio_stream.get("sample_rate", 48000)),
            channels=int(audio_stream.get("channels", 2)),
        ),
    )

