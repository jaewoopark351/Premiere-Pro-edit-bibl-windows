from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from ..media_probe import MediaInfo
from ..paths import premiere_fcp7_pathurl
from ..timeline.models import TimeRange


def build_multicam_xml(
    master: MediaInfo,
    cameras: list[tuple[MediaInfo, float]],
    keeps: list[TimeRange],
    sequence_name: str,
    clean_audio: Path | None = None,
) -> str:
    fps = master.video.fps
    timebase = int(round(fps))
    ntsc = "TRUE" if abs(fps - (timebase * 1000 / 1001)) < 0.02 else "FALSE"
    rate = f"<rate><timebase>{timebase}</timebase><ntsc>{ntsc}</ntsc></rate>"
    seq_frames = int(round(sum(k.duration for k in keeps) * fps))
    sources = [(master, 0.0)] + cameras
    video_tracks = []
    for source_idx, (media, offset) in enumerate(sources, 1):
        clips = []
        timeline = 0.0
        for keep_idx, keep in enumerate(keeps, 1):
            start = int(round(timeline * fps))
            end = int(round((timeline + keep.duration) * fps))
            timeline += keep.duration
            src_start_seconds = keep.start - offset
            src_end_seconds = keep.end - offset
            if src_start_seconds < 0 or src_end_seconds > media.duration:
                continue
            src_in = int(round(src_start_seconds * media.video.fps))
            src_out = int(round(src_end_seconds * media.video.fps))
            fid = f"mc-file-{source_idx}"
            file_ref = file_definition(fid, media, rate) if keep_idx == 1 else f'<file id="{fid}"/>'
            scale = 1920 / max(1, media.video.width) * 100
            clips.append(
                f"""
          <clipitem id="mc-v{source_idx}-{keep_idx}"><name>{escape(media.path.name)}</name>{rate}<start>{start}</start><end>{end}</end><in>{src_in}</in><out>{src_out}</out>{file_ref}{motion(scale)}</clipitem>"""
            )
        video_tracks.append(f"<track>{''.join(clips)}\n        </track>")
    audio_track = build_audio_track(master, keeps, fps, rate, clean_audio)
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
        {''.join(video_tracks)}
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


def motion(scale: float) -> str:
    return f"""
            <filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory><effecttype>motion</effecttype><mediatype>video</mediatype>
              <parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name><value>{scale:.4f}</value></parameter>
            </effect></filter>"""


def build_audio_track(master: MediaInfo, keeps: list[TimeRange], fps: float, rate: str, clean_audio: Path | None) -> str:
    clips = []
    timeline = 0.0
    audio_name = clean_audio.name if clean_audio else master.path.name
    audio_uri = premiere_fcp7_pathurl(clean_audio) if clean_audio else premiere_fcp7_pathurl(master.path)
    total_frames = int(round(master.duration * fps))
    file_def = f"""
            <file id="mc-audio"><name>{escape(audio_name)}</name><pathurl>{escape(audio_uri)}</pathurl>{rate}<duration>{total_frames}</duration>
              <media><audio><samplecharacteristics><depth>16</depth><samplerate>{master.audio.sample_rate}</samplerate></samplecharacteristics><channelcount>{master.audio.channels}</channelcount></audio></media>
            </file>"""
    for idx, keep in enumerate(keeps, 1):
        start = int(round(timeline * fps))
        end = int(round((timeline + keep.duration) * fps))
        timeline += keep.duration
        src_in = int(round(keep.start * fps))
        src_out = int(round(keep.end * fps))
        ref = file_def if idx == 1 else '<file id="mc-audio"/>'
        clips.append(
            f"""
          <clipitem id="mc-a{idx}"><name>{escape(audio_name)}</name>{rate}<start>{start}</start><end>{end}</end><in>{src_in}</in><out>{src_out}</out>{ref}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>"""
        )
    return "".join(clips)
