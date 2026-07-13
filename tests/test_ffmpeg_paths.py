from pathlib import Path

from bibl_windows.ffmpeg_tools import windows_native_path


def test_windows_native_path_uses_extended_prefix_for_drive_path():
    converted = windows_native_path(Path(r"C:\영상 폴더\실제 영상.mp4"))
    assert converted.startswith("\\\\?\\C:\\")


def test_windows_native_path_preserves_extended_prefix():
    converted = windows_native_path(Path(r"\\?\C:\영상 폴더\실제 영상.mp4"))
    assert converted.startswith("\\\\?\\")
