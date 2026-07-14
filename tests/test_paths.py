from pathlib import Path

from bibl_windows.paths import media_stem, premiere_fcp7_pathurl, standards_compliant_file_uri, windows_file_uri


def test_standards_compliant_file_uri_percent_encodes_non_ascii():
    uri = standards_compliant_file_uri(Path(r"C:\테스트 영상\한글 😀.mp4"))
    assert uri.startswith("file:///C:/")
    assert "%20" in uri
    assert "%ED%95%9C%EA%B8%80" in uri
    assert "%F0%9F%98%80" in uri


def test_premiere_fcp7_pathurl_encodes_spaces_but_keeps_non_ascii_literal():
    # Premiere Pro's FCP7 XML importer cannot auto-locate media whose pathurl
    # percent-encodes non-ASCII text, so Korean must survive as literal UTF-8.
    uri = premiere_fcp7_pathurl(Path(r"C:\테스트 영상\한글 😀 공백.mp4"))
    assert uri.startswith("file:///C:/")
    assert "%20" in uri
    assert "한글" in uri
    assert "😀" in uri
    assert "%ED%95%9C" not in uri


def test_premiere_fcp7_pathurl_encodes_drive_path_special_characters():
    uri = premiere_fcp7_pathurl(Path(r"D:\테스트 영상\편집 원본 #1 & 50% what?.mp4"))
    assert uri.startswith("file:///D:/")
    assert "%23" in uri
    assert "&" in uri
    assert "%25" in uri
    assert "%3F" in uri


def test_premiere_fcp7_pathurl_supports_unc_path():
    uri = premiere_fcp7_pathurl(Path(r"\\NAS01\VideoShare\test.mp4"))
    assert uri == "file://NAS01/VideoShare/test.mp4"


def test_windows_file_uri_remains_premiere_alias():
    assert windows_file_uri(Path(r"C:\테스트 영상\한글.mp4")) == premiere_fcp7_pathurl(Path(r"C:\테스트 영상\한글.mp4"))


def test_media_stem_removes_windows_invalid_name_characters():
    assert media_stem(Path("bad:name?.mp4")) == "bad_name_"
