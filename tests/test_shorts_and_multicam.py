from pathlib import Path

import pytest

from bibl_windows.media_probe import AudioStream, MediaInfo, VideoStream
from bibl_windows.multicam.switching import build_auto_switched_multicam_xml, plan_camera_switches
from bibl_windows.multicam.xml import build_multicam_xml
from bibl_windows.shorts.generator import build_vertical_xml, parse_range
from bibl_windows.timeline.models import TimeRange


def sample_media(path: str = r"C:\video sample\한글.mp4") -> MediaInfo:
    return MediaInfo(
        path=Path(path),
        duration=20,
        video=VideoStream(index=0, codec_name="h264", width=1920, height=1080, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )


def test_short_range_parser():
    item = parse_range("00:01-00:03.5")
    assert item.start == 1
    assert item.end == 3.5


def test_short_range_rejects_negative_start():
    with pytest.raises(ValueError):
        parse_range("-1-00:03")


def test_vertical_xml_uses_9x16_sequence():
    xml = build_vertical_xml(sample_media(), TimeRange(1, 3), "short")
    assert "<width>1080</width><height>1920</height>" in xml
    assert "file:C:/" in xml


def test_multicam_xml_contains_multiple_tracks():
    master = sample_media()
    cam = sample_media(r"C:\video sample\cam2.mp4")
    xml = build_multicam_xml(master, [(cam, 0.5)], [TimeRange(1, 3)], "mc")
    assert xml.count("<track>") >= 3
    assert "cam2.mp4" in xml


def test_auto_multicam_switches_between_sources():
    master = sample_media()
    cam = sample_media(r"C:\video sample\cam2.mp4")
    switches = plan_camera_switches(master, [(cam, 0.0)], [TimeRange(0, 6)], switch_interval=2, min_segment=1)
    xml = build_auto_switched_multicam_xml(master, [(cam, 0.0)], switches, "auto")
    assert [item.source_index for item in switches] == [0, 1, 0]
    assert "auto-mc-v1" in xml
    assert "cam2.mp4" in xml
