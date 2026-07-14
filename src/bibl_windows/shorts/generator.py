from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from ..ffmpeg_tools import media_input_arg, media_output_arg, run_checked
from ..media_probe import MediaInfo
from ..paths import windows_file_uri
from ..subtitles.ass import write_ass
from ..subtitles.srt import group_words, write_srt
from ..subtitles.vtt import write_vtt
from ..timeline.models import TimeRange, TranscriptWord


SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920


@dataclass(frozen=True)
class ShortArtifact:
    name: str
    start: float
    end: float
    xml: Path
    srt: Path | None = None
    vtt: Path | None = None
    ass: Path | None = None
    mp4: Path | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "xml": str(self.xml),
            "srt": str(self.srt) if self.srt else None,
            "vtt": str(self.vtt) if self.vtt else None,
            "ass": str(self.ass) if self.ass else None,
            "mp4": str(self.mp4) if self.mp4 else None,
        }


def parse_timecode(text: str) -> float:
    parts = text.strip().split(":")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def parse_range(text: str) -> TimeRange:
    match = re.match(r"^\s*(.+?)\s*-\s*(.+?)\s*$", text)
    if not match:
        raise ValueError(f"invalid short range, expected START-END: {text}")
    start = parse_timecode(match.group(1))
    end = parse_timecode(match.group(2))
    if start < 0:
        raise ValueError(f"short range start must be zero or later: {text}")
    if end <= start:
        raise ValueError(f"short range end must be after start: {text}")
    return TimeRange(start, end)


def build_vertical_xml(media: MediaInfo, clip_range: TimeRange, sequence_name: str) -> str:
    fps = media.video.fps
    timebase = int(round(fps))
    ntsc = "TRUE" if abs(fps - (timebase * 1000 / 1001)) < 0.02 else "FALSE"
    rate = f"<rate><timebase>{timebase}</timebase><ntsc>{ntsc}</ntsc></rate>"
    src_in = int(round(clip_range.start * fps))
    src_out = int(round(clip_range.end * fps))
    duration = max(1, src_out - src_in)
    total_frames = int(round(media.duration * fps))
    pathurl = escape(windows_file_uri(media.path))
    name = escape(media.path.name)
    scale = max(SHORT_WIDTH / max(1, media.video.width), SHORT_HEIGHT / max(1, media.video.height)) * 100
    motion = f"""
            <filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory><effecttype>motion</effecttype><mediatype>video</mediatype>
              <parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name><value>{scale:.4f}</value></parameter>
              <parameter authoringApp="PremierePro"><parameterid>center</parameterid><name>Center</name><value><horiz>0</horiz><vert>0</vert></value></parameter>
            </effect></filter>"""
    file_xml = f"""
            <file id="short-file-1"><name>{name}</name><pathurl>{pathurl}</pathurl>{rate}<duration>{total_frames}</duration>
              <media>
                <video><samplecharacteristics>{rate}<width>{media.video.width}</width><height>{media.video.height}</height><pixelaspectratio>square</pixelaspectratio></samplecharacteristics></video>
                <audio><samplecharacteristics><depth>16</depth><samplerate>{media.audio.sample_rate}</samplerate></samplecharacteristics><channelcount>{media.audio.channels}</channelcount></audio>
              </media>
            </file>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
  <sequence id="{escape(sequence_name)}">
    <name>{escape(sequence_name)}</name>
    <duration>{duration}</duration>
    {rate}
    <media>
      <video>
        <format><samplecharacteristics>{rate}<width>{SHORT_WIDTH}</width><height>{SHORT_HEIGHT}</height><pixelaspectratio>square</pixelaspectratio></samplecharacteristics></format>
        <track>
          <clipitem id="short-v1"><name>{name}</name>{rate}<start>0</start><end>{duration}</end><in>{src_in}</in><out>{src_out}</out>{file_xml}{motion}</clipitem>
        </track>
      </video>
      <audio>
        <format><samplecharacteristics><depth>16</depth><samplerate>{media.audio.sample_rate}</samplerate></samplecharacteristics></format>
        <track>
          <clipitem id="short-a1"><name>{name}</name>{rate}<start>0</start><end>{duration}</end><in>{src_in}</in><out>{src_out}</out><file id="short-file-1"/><sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>
        </track>
      </audio>
    </media>
  </sequence>
</xmeml>
"""


def write_short_subtitles(words: list[TranscriptWord], clip_range: TimeRange, stem: str, outdir: Path) -> tuple[Path, Path, Path]:
    shifted = [
        TranscriptWord(max(0.0, w.start - clip_range.start), max(0.0, w.end - clip_range.start), w.text, w.confidence)
        for w in words
        if clip_range.start <= (w.start + w.end) / 2 <= clip_range.end
    ]
    cues = group_words(shifted, max_chars=18, max_gap=0.55)
    srt = outdir / f"{stem}.srt"
    vtt = outdir / f"{stem}.vtt"
    ass = outdir / f"{stem}.ass"
    write_srt(cues, srt)
    write_vtt(cues, vtt)
    write_ass(cues, ass, title=stem, emphasize=True)
    return srt, vtt, ass


def render_vertical_mp4(ffmpeg: Path, media_path: Path, clip_range: TimeRange, output_mp4: Path) -> None:
    run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-ss",
            f"{clip_range.start:.3f}",
            "-t",
            f"{clip_range.duration:.3f}",
            "-i",
            media_input_arg(media_path),
            "-vf",
            f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase,crop={SHORT_WIDTH}:{SHORT_HEIGHT}",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p4",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            media_output_arg(output_mp4),
        ]
    )
