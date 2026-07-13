from pathlib import Path

from bibl_windows.paths import windows_file_uri


def test_windows_file_uri_encodes_spaces_and_korean():
    uri = windows_file_uri(Path(r"C:\테스트 영상\한글 공백.mp4"))
    assert uri.startswith("file:///C:/")
    assert "%20" in uri
    assert "%ED%95%9C%EA%B8%80" in uri

