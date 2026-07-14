from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal
from xml.sax.saxutils import escape

from ..media_probe import MediaInfo
from ..paths import premiere_fcp7_pathurl
from ..timeline.models import TimeRange


def _frames(seconds: float, fps: float) -> int:
    return int(round(seconds * fps))


def _rate_xml(fps: float) -> str:
    timebase = int(round(fps))
    ntsc = "TRUE" if abs(fps - (timebase * 1000 / 1001)) < 0.02 else "FALSE"
    return f"<rate><timebase>{timebase}</timebase><ntsc>{ntsc}</ntsc></rate>"


PathUrlFactory = Callable[[Path], str]
VideoFileMediaMode = Literal["full", "video-only", "none"]


def build_fcp7_xml(
    media: MediaInfo,
    keeps: list[TimeRange],
    sequence_name: str,
    clean_audio: Path | None = None,
    *,
    pathurl_factory: PathUrlFactory = premiere_fcp7_pathurl,
    video_file_media: VideoFileMediaMode = "full",
) -> str:
    fps = media.video.fps
    rate = _rate_xml(fps)
    total_frames = _frames(media.duration, fps)
    video_uri = escape(pathurl_factory(media.path))
    video_name = escape(media.path.name)
    use_clean_audio = clean_audio is not None
    audio_uri = escape(pathurl_factory(clean_audio)) if clean_audio else video_uri
    audio_name = escape(clean_audio.name) if clean_audio else video_name

    video_media = _video_file_media_xml(media, rate, video_file_media)
    video_file = f"""
            <file id="file-video">
              <name>{video_name}</name>
              <pathurl>{video_uri}</pathurl>
              {rate}
              <duration>{total_frames}</duration>
              {video_media}
            </file>"""
    audio_file = f"""
            <file id="file-audio">
              <name>{audio_name}</name>
              <pathurl>{audio_uri}</pathurl>
              {rate}
              <duration>{total_frames}</duration>
              <media><audio><samplecharacteristics><depth>16</depth><samplerate>{media.audio.sample_rate}</samplerate></samplecharacteristics><channelcount>{media.audio.channels}</channelcount></audio></media>
            </file>""" if use_clean_audio else '<file id="file-video"/>'

    video_clips: list[str] = []
    audio_clips: list[str] = []
    timeline_frame = 0
    for idx, keep in enumerate(keeps, 1):
        src_in = _frames(keep.start, fps)
        src_out = _frames(keep.end, fps)
        dur = max(0, src_out - src_in)
        if dur <= 0:
            continue
        start = timeline_frame
        end = timeline_frame + dur
        timeline_frame = end
        video_ref = video_file if idx == 1 else '<file id="file-video"/>'
        audio_ref = audio_file if idx == 1 else ('<file id="file-audio"/>' if use_clean_audio else '<file id="file-video"/>')
        vid = f"v{idx}"
        aid = f"a{idx}"
        link = f"""
            <link><linkclipref>{vid}</linkclipref><mediatype>video</mediatype><trackindex>1</trackindex><clipindex>{idx}</clipindex></link>
            <link><linkclipref>{aid}</linkclipref><mediatype>audio</mediatype><trackindex>1</trackindex><clipindex>{idx}</clipindex></link>"""
        video_clips.append(
            f"""
          <clipitem id="{vid}">
            <name>{video_name}</name>{rate}
            <start>{start}</start><end>{end}</end><in>{src_in}</in><out>{src_out}</out>
            {video_ref}
            {link}
          </clipitem>"""
        )
        audio_clips.append(
            f"""
          <clipitem id="{aid}">
            <name>{audio_name}</name>{rate}
            <start>{start}</start><end>{end}</end><in>{src_in}</in><out>{src_out}</out>
            {audio_ref}
            <sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>
            {link}
          </clipitem>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
  <sequence id="sequence-1">
    <name>{escape(sequence_name)}</name>
    <duration>{timeline_frame}</duration>
    {rate}
    <media>
      <video>
        <format><samplecharacteristics>{rate}<width>{media.video.width}</width><height>{media.video.height}</height><pixelaspectratio>square</pixelaspectratio></samplecharacteristics></format>
        <track>{''.join(video_clips)}
        </track>
      </video>
      <audio>
        <format><samplecharacteristics><depth>16</depth><samplerate>{media.audio.sample_rate}</samplerate></samplecharacteristics></format>
        <track>{''.join(audio_clips)}
        </track>
      </audio>
    </media>
  </sequence>
</xmeml>
"""


def _video_file_media_xml(media: MediaInfo, rate: str, mode: VideoFileMediaMode) -> str:
    video_xml = (
        f"<video><samplecharacteristics>{rate}<width>{media.video.width}</width>"
        f"<height>{media.video.height}</height><pixelaspectratio>square</pixelaspectratio>"
        "</samplecharacteristics></video>"
    )
    audio_xml = (
        f"<audio><samplecharacteristics><depth>16</depth><samplerate>{media.audio.sample_rate}</samplerate>"
        f"</samplecharacteristics><channelcount>{media.audio.channels}</channelcount></audio>"
    )
    if mode == "full":
        return f"<media>{video_xml}{audio_xml}</media>"
    if mode == "video-only":
        return f"<media>{video_xml}</media>"
    if mode == "none":
        return ""
    raise ValueError(f"Unsupported video file media mode: {mode}")
