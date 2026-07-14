from pathlib import Path

from bibl_windows.paths import media_stem, windows_file_uri


def test_windows_file_uri_encodes_spaces_but_keeps_korean_literal():
    # Premiere Pro's FCP7 XML importer cannot auto-locate media whose pathurl
    # percent-encodes non-ASCII text, so Korean must survive as literal UTF-8.
    uri = windows_file_uri(Path(r"C:\테스트 영상\한글 공백.mp4"))
    assert uri.startswith("file:///C:/")
    assert "%20" in uri
    assert "한글" in uri
    assert "%ED%95%9C" not in uri


def test_windows_file_uri_encodes_drive_path_special_characters():
    uri = windows_file_uri(Path(r"D:\테스트 영상\편집 원본 #1 & 50%.mp4"))
    assert uri.startswith("file:///D:/")
    assert "%23" in uri
    assert "&" in uri
    assert "%25" in uri


def test_windows_file_uri_supports_unc_path():
    uri = windows_file_uri(Path(r"\\NAS01\VideoShare\test.mp4"))
    assert uri == "file://NAS01/VideoShare/test.mp4"


def test_media_stem_removes_windows_invalid_name_characters():
    assert media_stem(Path("bad:name?.mp4")) == "bad_name_"
