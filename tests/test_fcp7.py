from pathlib import Path

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

