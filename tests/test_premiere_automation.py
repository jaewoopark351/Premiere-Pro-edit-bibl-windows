from pathlib import Path
from uuid import uuid4

from bibl_windows.premiere.automation import jsx_string, write_import_render_script


def workspace_tmp(name: str) -> Path:
    path = Path(".test_tmp_manual") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def test_premiere_import_render_script_contains_xml_srt_and_export_paths():
    root = workspace_tmp("premiere-script")
    xml = root / "sample_cut.xml"
    srt = root / "sample_cut.srt"
    out = root / "script.jsx"
    export = root / "render.mp4"
    xml.write_text("<xmeml/>", encoding="utf-8")
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    write_import_render_script(out, xml, srt_path=srt, export_path=export)

    text = out.read_text(encoding="utf-8")
    assert "app.project.importFiles" in text
    assert "sample_cut.xml" in text
    assert "sample_cut.srt" in text
    assert "render.mp4" in text


def test_jsx_string_uses_forward_slashes_and_quotes():
    text = jsx_string(Path(r"C:\테스트 영상\a b.xml"))
    assert text.startswith('"')
    assert text.endswith('"')
    assert "/" in text
    assert "\\테스트" not in text
