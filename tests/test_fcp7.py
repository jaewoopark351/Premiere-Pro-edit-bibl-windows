from pathlib import Path
import xml.etree.ElementTree as ET

from bibl_windows.media_probe import AudioStream, MediaInfo, VideoStream
from bibl_windows.premiere.fcp7 import build_fcp7_xml
from bibl_windows.timeline.models import TimeRange


def test_fcp7_contains_windows_uri_and_links():
    media = MediaInfo(
        path=Path(r"C:\테스트 영상\한글 공백.mp4"),
        duration=10,
        video=VideoStream(index=0, codec_name="h264", width=1920, height=1080, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    xml = build_fcp7_xml(media, [TimeRange(0, 2), TimeRange(4, 6)], "test")
    assert "file:///C:/" in xml
    assert "%20" in xml
    assert "<linkclipref>v1</linkclipref>" in xml
    assert "<samplerate>48000</samplerate>" in xml


def test_fcp7_xml_parses_and_escapes_media_uri_special_characters():
    media = MediaInfo(
        path=Path(r"D:\테스트 영상\편집 원본 #1 & 50%.mp4"),
        duration=5,
        video=VideoStream(index=0, codec_name="h264", width=1280, height=720, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    xml = build_fcp7_xml(media, [TimeRange(0, 1)], "uri test")
    root = ET.fromstring(xml)
    pathurl = root.find(".//pathurl")
    assert pathurl is not None
    assert "%23" in pathurl.text
    assert "%26" in pathurl.text
    assert "%25" in pathurl.text


def test_fcp7_uses_clean_wav_audio_link():
    media = MediaInfo(
        path=Path(r"C:\테스트 영상\source.mp4"),
        duration=5,
        video=VideoStream(index=0, codec_name="h264", width=1280, height=720, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )

    xml = build_fcp7_xml(media, [TimeRange(0, 1)], "clean audio", Path(r"C:\테스트 영상\source_cut_audio.wav"))

    root = ET.fromstring(xml)
    pathurls = [node.text for node in root.findall(".//pathurl")]
    assert any(text and text.endswith("source_cut_audio.wav") for text in pathurls)
    assert "<file id=\"file-audio\">" in xml


def test_fcp7_ntsc_frame_rates_have_ntsc_rate_and_expected_frames():
    for fps, timebase in ((24000 / 1001, "24"), (30000 / 1001, "30"), (60000 / 1001, "60")):
        media = MediaInfo(
            path=Path(r"D:\video\clip.mp4"),
            duration=10,
            video=VideoStream(index=0, codec_name="h264", width=1920, height=1080, fps=fps, fps_text=f"{timebase}000/1001"),
            audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
        )

        xml = build_fcp7_xml(media, [TimeRange(0, 10)], f"{fps} fps")

        assert f"<timebase>{timebase}</timebase><ntsc>TRUE</ntsc>" in xml
        assert f"<duration>{round(10 * fps)}</duration>" in xml
