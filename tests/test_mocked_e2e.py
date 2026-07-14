from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from uuid import uuid4

import pytest

from bibl_windows.claude_assets import ClaudeProjectAssets
from bibl_windows.ffmpeg_tools import tool_info
from bibl_windows.io_json import read_json
from bibl_windows.paths import ProjectPaths
from bibl_windows.pipeline import PipelineOptions, WindowsEditPipeline
from bibl_windows.runtime import RuntimeContext, RuntimeTools
from bibl_windows.stt.base import TranscriptResult
from bibl_windows.stt.transformers_whisper import TransformersWhisperBackend
from bibl_windows.timeline.models import TranscriptSegment, TranscriptWord


def workspace_tmp(name: str) -> Path:
    path = Path(".test_tmp_manual") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def copy_standard_config(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_dir = root / "config"
    config_dir.mkdir()
    shutil.copy2(repo_root / "config" / "standard.json", config_dir / "standard.json")


def make_test_mp4(root: Path) -> Path:
    ffmpeg = tool_info("ffmpeg.exe").path
    if ffmpeg is None:
        pytest.skip("ffmpeg.exe is not available")
    media = root / "한글 sample #1.mp4"
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=30:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=2",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(media),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip("ffmpeg could not create a test MP4: " + completed.stderr[:200])
    return media


def test_mocked_stt_e2e_generates_limited_xml_srt_and_manifest(monkeypatch):
    ffmpeg = tool_info("ffmpeg.exe")
    ffprobe = tool_info("ffprobe.exe")
    if ffmpeg.path is None or ffprobe.path is None:
        pytest.skip("ffmpeg.exe/ffprobe.exe are not available")
    root = workspace_tmp("mocked-e2e")
    copy_standard_config(root)
    media = make_test_mp4(root)
    paths = ProjectPaths(root)
    context = RuntimeContext(paths=paths, tools=RuntimeTools.discover(), claude=ClaudeProjectAssets.discover(paths))

    def fake_transcribe(
        self,
        audio_path,
        language="ko",
        allow_cpu_fallback=False,
        batch_size=1,
        chunk_length_s=25.0,
        **_kwargs,
    ):
        words = [
            TranscriptWord(0.10, 0.35, "안녕", 0.99),
            TranscriptWord(0.40, 0.70, "테스트", 0.99),
        ]
        segment = TranscriptSegment(0.10, 0.70, "안녕 테스트", words)
        return TranscriptResult(
            source_audio=str(audio_path),
            backend="fake-transformers-whisper",
            model=self.model,
            language=language,
            device="cuda:0",
            text="안녕 테스트",
            segments=[segment],
            words=words,
        )

    monkeypatch.setattr(TransformersWhisperBackend, "transcribe", fake_transcribe)
    artifacts = WindowsEditPipeline(context).run(
        PipelineOptions(input_path=media, limit_seconds=1.0, stt_batch_size=1, stt_chunk_seconds=10.0)
    )

    assert artifacts.xml and artifacts.xml.exists()
    assert artifacts.srt and artifacts.srt.exists()
    assert artifacts.manifest_json and artifacts.manifest_json.exists()
    ET.parse(artifacts.xml)
    candidates = read_json(artifacts.cut_candidates_json)
    keep_ranges = read_json(artifacts.keep_ranges_json)
    manifest = read_json(artifacts.manifest_json)
    xml_text = artifacts.xml.read_text(encoding="utf-8")
    assert candidates["analysis_duration"] == 1.0
    assert keep_ranges["timeline_duration"] == 1.0
    assert manifest["limit_seconds"] == 1.0
    # Premiere's FCP7 importer needs literal (non-percent-encoded) Korean text
    # in pathurl to auto-locate media; see paths.premiere_fcp7_pathurl.
    assert "한글" in xml_text
    assert "%ED%95%9C" not in xml_text
