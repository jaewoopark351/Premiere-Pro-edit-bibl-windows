from pathlib import Path
import xml.etree.ElementTree as ET

from bibl_windows.media_probe import AudioStream, MediaInfo, VideoStream
from bibl_windows.premiere.fcp7 import build_fcp7_xml
from bibl_windows.paths import file_uri_to_windows_path, standards_compliant_file_uri
from bibl_windows.timeline.models import TimeRange


def test_fcp7_contains_windows_uri_and_links():
    media = MediaInfo(
        path=Path(r"C:\테스트 영상\한글 공백.mp4"),
        duration=10,
        video=VideoStream(index=0, codec_name="h264", width=1920, height=1080, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    xml = build_fcp7_xml(media, [TimeRange(0, 2), TimeRange(4, 6)], "test")
    assert "file:C:/" in xml
    assert "한글 공백.mp4" in xml
    assert "%20" not in xml
    assert "<linkclipref>v1</linkclipref>" in xml
    assert "<samplerate>48000</samplerate>" in xml


def test_fcp7_xml_parses_and_escapes_media_uri_special_characters():
    media = MediaInfo(
        path=Path(r"D:\테스트 영상\편집 원본 #1 & 50% what? 😀.mp4"),
        duration=5,
        video=VideoStream(index=0, codec_name="h264", width=1280, height=720, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    xml = build_fcp7_xml(media, [TimeRange(0, 1)], "uri test")
    root = ET.fromstring(xml)
    pathurl = root.find(".//pathurl")
    assert pathurl is not None
    assert pathurl.text.startswith("file:D:/")
    assert "#1" in pathurl.text
    assert "&" in pathurl.text
    assert "50%" in pathurl.text
    assert "what?" in pathurl.text
    assert "😀" in pathurl.text
    assert str(file_uri_to_windows_path(pathurl.text)) == r"D:\테스트 영상\편집 원본 #1 & 50% what? 😀.mp4"
    roundtrip = ET.tostring(root, encoding="unicode")
    reparsed = ET.fromstring(roundtrip)
    assert reparsed.find(".//pathurl").text == pathurl.text


def test_fcp7_can_emit_standards_compliant_encoded_pathurl_variant():
    media = MediaInfo(
        path=Path(r"C:\테스트 영상\한글 공백.mp4"),
        duration=5,
        video=VideoStream(index=0, codec_name="h264", width=1280, height=720, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    xml = build_fcp7_xml(media, [TimeRange(0, 1)], "encoded uri test", pathurl_factory=standards_compliant_file_uri)
    pathurl = ET.fromstring(xml).find(".//pathurl")
    assert pathurl is not None
    assert "%ED%95%9C%EA%B8%80" in pathurl.text


def test_fcp7_can_omit_audio_from_video_file_media_for_premiere_probe():
    media = MediaInfo(
        path=Path(r"C:\테스트 영상\한글 공백.mp4"),
        duration=5,
        video=VideoStream(index=0, codec_name="h264", width=1280, height=720, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    video_only = build_fcp7_xml(media, [TimeRange(0, 1)], "video only", video_file_media="video-only")
    no_media = build_fcp7_xml(media, [TimeRange(0, 1)], "no media", video_file_media="none")

    first_video_file = ET.fromstring(video_only).find('.//clipitem[@id="v1"]/file')
    assert first_video_file is not None
    assert first_video_file.find(".//video") is not None
    assert first_video_file.find(".//audio") is None
    first_no_media_file = ET.fromstring(no_media).find('.//clipitem[@id="v1"]/file')
    assert first_no_media_file is not None
    assert first_no_media_file.find("media") is None


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
