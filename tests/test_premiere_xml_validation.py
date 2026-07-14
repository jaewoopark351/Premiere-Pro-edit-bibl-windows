from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from bibl_windows.media_probe import AudioStream, MediaInfo, VideoStream
from bibl_windows.premiere.fcp7 import build_fcp7_xml
from bibl_windows.premiere.xml_validation import validate_fcp7_xml_pathurls
from bibl_windows.timeline.models import TimeRange


def test_validates_korean_space_pathurl_roundtrip():
    root = _make_root("korean-space")
    media_path = root / "C 테스트 영상" / "한글 공백.mp4"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"mp4")
    xml_path = root / "한글 공백_cut.xml"
    xml_path.write_text(build_fcp7_xml(_media(media_path), [TimeRange(0, 1)], "korean"), encoding="utf-8")

    report = validate_fcp7_xml_pathurls(xml_path, expected_media=media_path)

    assert report["ok"], report["issues"]
    assert report["pathurls"][0]["exists"] is True
    assert report["pathurls"][0]["has_backslash_in_uri"] is False


def test_validates_special_characters_and_clean_audio_pathurls():
    root = _make_root("special-clean")
    media_path = root / "D 테스트 영상" / "편집 원본 #1 & 50%.mp4"
    clean_audio = root / "D 테스트 영상" / "편집 원본 #1 & 50%_cut_audio.wav"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"mp4")
    clean_audio.write_bytes(b"wav")
    xml_path = root / "special_cut.xml"
    xml_path.write_text(
        build_fcp7_xml(_media(media_path), [TimeRange(0, 1)], "special", clean_audio),
        encoding="utf-8",
    )

    report = validate_fcp7_xml_pathurls(xml_path, expected_media=media_path, expected_clean_audio=clean_audio)

    assert report["ok"], report["issues"]
    pathurls = [item["pathurl"] for item in report["pathurls"]]
    assert any("#1" in item for item in pathurls)
    assert any("50%" in item for item in pathurls)
    assert any("&" in item for item in pathurls)


def test_validator_reports_missing_media_file():
    root = _make_root("missing")
    media_path = root / "missing.mp4"
    xml_path = root / "missing.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?><xmeml><file id="missing"><name>missing.mp4</name><pathurl>file:///C:/does/not/exist.mp4</pathurl></file></xmeml>""",
        encoding="utf-8",
    )

    report = validate_fcp7_xml_pathurls(xml_path, expected_media=media_path)

    assert not report["ok"]
    assert any("does not resolve" in issue for issue in report["issues"])


def test_actual_repository_korean_input_if_present():
    media_path = Path.cwd() / "input" / "목요일 밤 - 어반 자카파 ver LAVI.mp4"
    if not media_path.exists():
        pytest.skip("local Korean input fixture is not present")
    xml_path = _make_root("actual-input") / "actual_input.xml"
    xml_path.write_text(build_fcp7_xml(_media(media_path), [TimeRange(0, 1)], "actual"), encoding="utf-8")

    report = validate_fcp7_xml_pathurls(xml_path, expected_media=media_path)

    assert report["ok"], report["issues"]


def _media(path: Path) -> MediaInfo:
    return MediaInfo(
        path=path.resolve(),
        duration=2,
        video=VideoStream(index=0, codec_name="h264", width=1920, height=1080, fps=30, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )


def _make_root(name: str) -> Path:
    root = Path.cwd() / ".test_tmp_manual" / f"premiere_xml_{name}_{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root
