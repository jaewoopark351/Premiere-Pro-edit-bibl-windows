from pathlib import Path

from bibl_windows.paths import (
    file_uri_to_windows_path,
    localhost_file_uri,
    media_stem,
    premiere_fcp7_pathurl,
    premiere_legacy_drive_file_uri,
    standards_compliant_file_uri,
    windows_file_uri,
)


def test_standards_compliant_file_uri_percent_encodes_non_ascii():
    uri = standards_compliant_file_uri(Path(r"C:\테스트 영상\한글 😀.mp4"))
    assert uri.startswith("file:///C:/")
    assert "%20" in uri
    assert "%ED%95%9C%EA%B8%80" in uri
    assert "%F0%9F%98%80" in uri


def test_premiere_fcp7_pathurl_uses_opaque_literal_drive_path():
    # Premiere Pro 2024 auto-linked this FCP7 form in a fresh project:
    # no slashes after file:, forward-slash drive path, literal spaces/Korean.
    uri = premiere_fcp7_pathurl(Path(r"C:\테스트 영상\한글 😀 공백.mp4"))
    assert uri.startswith("file:C:/")
    assert " " in uri
    assert "한글" in uri
    assert "😀" in uri
    assert "%20" not in uri
    assert "%ED%95%9C" not in uri


def test_premiere_fcp7_pathurl_keeps_drive_path_special_characters_literal():
    uri = premiere_fcp7_pathurl(Path(r"D:\테스트 영상\편집 원본 #1 & 50% what?.mp4"))
    assert uri.startswith("file:D:/")
    assert "#1" in uri
    assert "&" in uri
    assert "50%" in uri
    assert "what?" in uri
    assert str(file_uri_to_windows_path(uri)) == r"D:\테스트 영상\편집 원본 #1 & 50% what?.mp4"


def test_premiere_fcp7_pathurl_supports_unc_path():
    uri = premiere_fcp7_pathurl(Path(r"\\NAS01\VideoShare\test.mp4"))
    assert uri == "file://NAS01/VideoShare/test.mp4"


def test_file_uri_to_windows_path_restores_literal_and_encoded_drive_paths():
    opaque = "file:C:/테스트 영상/편집 원본 #1 & 50% what?.mp4"
    literal = "file:///C:/테스트%20영상/한글%20공백.mp4"
    encoded = "file:///D:/%ED%85%8C%EC%8A%A4%ED%8A%B8%20%EC%98%81%EC%83%81/%ED%8E%B8%EC%A7%91%20%EC%9B%90%EB%B3%B8%20%231%20&%2050%25.mp4"

    assert str(file_uri_to_windows_path(opaque)) == r"C:\테스트 영상\편집 원본 #1 & 50% what?.mp4"
    assert str(file_uri_to_windows_path(literal)) == r"C:\테스트 영상\한글 공백.mp4"
    assert str(file_uri_to_windows_path(encoded)) == r"D:\테스트 영상\편집 원본 #1 & 50%.mp4"


def test_file_uri_to_windows_path_restores_unc_path():
    assert str(file_uri_to_windows_path("file://NAS01/VideoShare/test.mp4")) == r"\\NAS01\VideoShare\test.mp4"


def test_localhost_file_uri_variants_restore_to_local_drive_path():
    path = Path(r"C:\테스트 영상\한글 공백.mp4")

    literal = localhost_file_uri(path, encoded=False)
    encoded = localhost_file_uri(path, encoded=True)
    colon_encoded = localhost_file_uri(path, encoded=True, encode_drive_colon=True)

    assert literal.startswith("file://localhost/C:/")
    assert "한글" in literal
    assert "%ED%95%9C" in encoded
    assert colon_encoded.startswith("file://localhost/C%3A/")
    assert file_uri_to_windows_path(literal) == path
    assert file_uri_to_windows_path(encoded) == path
    assert file_uri_to_windows_path(colon_encoded) == path


def test_premiere_legacy_drive_file_uri_restores_to_local_drive_path():
    path = Path(r"C:\테스트 영상\한글 공백 #1.mp4")

    literal = premiere_legacy_drive_file_uri(path, encoded=False)
    encoded = premiere_legacy_drive_file_uri(path, encoded=True)

    assert literal.startswith("file://C:/")
    assert encoded.startswith("file://C:/")
    assert "한글" in literal
    assert "%ED%95%9C" in encoded
    assert "%23" in encoded
    assert file_uri_to_windows_path(literal) == path
    assert file_uri_to_windows_path(encoded) == path


def test_windows_file_uri_remains_premiere_alias():
    assert windows_file_uri(Path(r"C:\테스트 영상\한글.mp4")) == premiere_fcp7_pathurl(Path(r"C:\테스트 영상\한글.mp4"))


def test_media_stem_removes_windows_invalid_name_characters():
    assert media_stem(Path("bad:name?.mp4")) == "bad_name_"
