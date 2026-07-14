from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from ..media_probe import MediaInfo
from ..paths import premiere_fcp7_pathurl
from ..timeline.models import TimeRange
from .xml import motion


@dataclass(frozen=True)
class CameraSource:
    media: MediaInfo
    offset: float


@dataclass(frozen=True)
class CameraSwitch:
    start: float
    end: float
    source_index: int
    source_name: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "source_index": self.source_index,
            "source_name": self.source_name,
        }


def plan_camera_switches(
    master: MediaInfo,
    cameras: list[tuple[MediaInfo, float]],
    keeps: list[TimeRange],
    switch_interval: float = 6.0,
    min_segment: float = 1.0,
) -> list[CameraSwitch]:
    if switch_interval <= 0:
        raise ValueError("switch interval must be greater than zero")
    if min_segment <= 0:
        raise ValueError("minimum segment must be greater than zero")

    sources = [CameraSource(master, 0.0)] + [CameraSource(media, offset) for media, offset in cameras]
    switches: list[CameraSwitch] = []
    cursor = 0
    for keep in keeps:
        segment_start = keep.start
        while segment_start < keep.end:
            segment_end = min(keep.end, segment_start + switch_interval)
            if segment_end - segment_start < min_segment and switches:
                previous = switches[-1]
                switches[-1] = CameraSwitch(previous.start, segment_end, previous.source_index, previous.source_name)
                break
            preferred = cursor % len(sources)
            source_index = first_available_source(sources, segment_start, segment_end, preferred)
            switches.append(
                CameraSwitch(
                    start=round(segment_start, 3),
                    end=round(segment_end, 3),
                    source_index=source_index,
                    source_name=sources[source_index].media.path.name,
                )
            )
            cursor += 1
            segment_start = segment_end
    return switches


def first_available_source(sources: list[CameraSource], start: float, end: float, preferred: int) -> int:
    order = list(range(preferred, len(sources))) + list(range(0, preferred))
    for idx in order:
        source = sources[idx]
        src_start = start - source.offset
        src_end = end - source.offset
        if src_start >= 0 and src_end <= source.media.duration:
            return idx
    return 0


def build_auto_switched_multicam_xml(
    master: MediaInfo,
    cameras: list[tuple[MediaInfo, float]],
    switches: list[CameraSwitch],
    sequence_name: str,
    clean_audio: Path | None = None,
) -> str:
    sources = [CameraSource(master, 0.0)] + [CameraSource(media, offset) for media, offset in cameras]
    fps = master.video.fps
    timebase = int(round(fps))
    ntsc = "TRUE" if abs(fps - (timebase * 1000 / 1001)) < 0.02 else "FALSE"
    rate = f"<rate><timebase>{timebase}</timebase><ntsc>{ntsc}</ntsc></rate>"
    seq_frames = int(round(sum(item.duration for item in switches) * fps))
    file_defs: set[int] = set()
    video_clips: list[str] = []
    timeline = 0.0
    for idx, item in enumerate(switches, 1):
        if item.source_index < 0 or item.source_index >= len(sources):
            raise ValueError(f"camera switch source index is out of range: {item.source_index}")
        source = sources[item.source_index]
        media = source.media
        src_start = item.start - source.offset
        src_end = item.end - source.offset
        if src_start < 0 or src_end > media.duration:
            source = sources[0]
            media = source.media
            src_start = item.start
            src_end = item.end
        start_frame = int(round(timeline * fps))
        end_frame = int(round((timeline + item.duration) * fps))
        timeline += item.duration
        fid = f"auto-mc-file-{item.source_index + 1}"
        file_xml = file_definition(fid, media, rate) if item.source_index not in file_defs else f'<file id="{fid}"/>'
        file_defs.add(item.source_index)
        scale = 1920 / max(1, media.video.width) * 100
        video_clips.append(
            f"""
          <clipitem id="auto-mc-v{idx}"><name>{escape(media.path.name)}</name>{rate}<start>{start_frame}</start><end>{end_frame}</end><in>{int(round(src_start * media.video.fps))}</in><out>{int(round(src_end * media.video.fps))}</out>{file_xml}{motion(scale)}</clipitem>"""
        )
    audio_track = build_switched_audio_track(master, switches, fps, rate, clean_audio)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
  <sequence id="{escape(sequence_name)}">
    <name>{escape(sequence_name)}</name>
    <duration>{seq_frames}</duration>
    {rate}
    <media>
      <video>
        <format><samplecharacteristics>{rate}<width>1920</width><height>1080</height><pixelaspectratio>square</pixelaspectratio></samplecharacteristics></format>
        <track>{''.join(video_clips)}
        </track>
      </video>
      <audio>
        <format><samplecharacteristics><depth>16</depth><samplerate>{master.audio.sample_rate}</samplerate></samplecharacteristics></format>
        <track>{audio_track}
        </track>
      </audio>
    </media>
  </sequence>
</xmeml>
"""


def file_definition(fid: str, media: MediaInfo, rate: str) -> str:
    total_frames = int(round(media.duration * media.video.fps))
    return f"""
            <file id="{fid}"><name>{escape(media.path.name)}</name><pathurl>{escape(premiere_fcp7_pathurl(media.path))}</pathurl>{rate}<duration>{total_frames}</duration>
              <media>
                <video><samplecharacteristics>{rate}<width>{media.video.width}</width><height>{media.video.height}</height><pixelaspectratio>square</pixelaspectratio></samplecharacteristics></video>
                <audio><samplecharacteristics><depth>16</depth><samplerate>{media.audio.sample_rate}</samplerate></samplecharacteristics><channelcount>{media.audio.channels}</channelcount></audio>
              </media>
            </file>"""


def build_switched_audio_track(
    master: MediaInfo,
    switches: list[CameraSwitch],
    fps: float,
    rate: str,
    clean_audio: Path | None,
) -> str:
    clips = []
    audio_name = clean_audio.name if clean_audio else master.path.name
    audio_uri = premiere_fcp7_pathurl(clean_audio) if clean_audio else premiere_fcp7_pathurl(master.path)
    total_frames = int(round(master.duration * fps))
    file_def = f"""
            <file id="auto-mc-audio"><name>{escape(audio_name)}</name><pathurl>{escape(audio_uri)}</pathurl>{rate}<duration>{total_frames}</duration>
              <media><audio><samplecharacteristics><depth>16</depth><samplerate>{master.audio.sample_rate}</samplerate></samplecharacteristics><channelcount>{master.audio.channels}</channelcount></audio></media>
            </file>"""
    timeline = 0.0
    for idx, item in enumerate(switches, 1):
        start = int(round(timeline * fps))
        end = int(round((timeline + item.duration) * fps))
        timeline += item.duration
        ref = file_def if idx == 1 else '<file id="auto-mc-audio"/>'
        clips.append(
            f"""
          <clipitem id="auto-mc-a{idx}"><name>{escape(audio_name)}</name>{rate}<start>{start}</start><end>{end}</end><in>{int(round(item.start * fps))}</in><out>{int(round(item.end * fps))}</out>{ref}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>"""
        )
    return "".join(clips)
