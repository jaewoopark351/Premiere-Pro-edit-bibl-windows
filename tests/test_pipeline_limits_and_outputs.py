from pathlib import Path
from uuid import uuid4

from bibl_windows.artifacts import ArtifactManifest
from bibl_windows.claude_assets import ClaudeProjectAssets
from bibl_windows.ffmpeg_tools import ToolInfo
from bibl_windows.io_json import read_json, write_json
from bibl_windows.paths import ProjectPaths
from bibl_windows.pipeline import PipelineArtifacts, PipelineOptions, WindowsEditPipeline
from bibl_windows.runtime import RuntimeContext, RuntimeTools
from bibl_windows.stt.base import TranscriptResult


def workspace_tmp(name: str) -> Path:
    path = Path(".test_tmp_manual") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def make_context(root: Path) -> RuntimeContext:
    paths = ProjectPaths(root)
    tools = RuntimeTools(ffmpeg=ToolInfo("ffmpeg.exe", None, None), ffprobe=ToolInfo("ffprobe.exe", None, None))
    return RuntimeContext(paths=paths, tools=tools, claude=ClaudeProjectAssets.discover(paths))


def test_output_layout_adds_hash_when_manifest_points_to_different_media():
    root = workspace_tmp("collision")
    context = make_context(root)
    pipeline = WindowsEditPipeline(context)
    first = root / "shoot1" / "test.mp4"
    second = root / "shoot2" / "test.mp4"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manifest = ArtifactManifest(media_path=str(first), preset="standard", mode="full", command=[])
    manifest.write(context.paths.output_path("test_manifest.json"))

    layout = pipeline.output_layout_for(second)

    assert layout.stem.startswith("test_")
    assert layout.stem != "test"


def test_output_layout_honors_explicit_output_name_and_dir():
    root = workspace_tmp("layout")
    context = make_context(root)
    pipeline = WindowsEditPipeline(context)
    media = root / "input.mp4"
    media.write_bytes(b"media")

    layout = pipeline.output_layout_for(media, output_dir="한글 session", output_name="rough:cut?")

    assert layout.dir_parts == ("한글 session",)
    assert layout.stem == "rough_cut_"


def test_run_forwards_limit_seconds_to_analysis_and_export(monkeypatch):
    root = workspace_tmp("limit")
    context = make_context(root)
    pipeline = WindowsEditPipeline(context)
    media = root / "sample.mp4"
    media.write_bytes(b"media")
    captured = {}

    def fake_transcribe(options):
        transcript = context.paths.output_path("sample_transcript.json")
        audio = context.paths.output_path("sample_stt_audio.wav")
        write_json(transcript, {"words": []})
        audio.write_bytes(b"wav")
        result = TranscriptResult(
            source_audio=str(audio),
            backend="fake",
            model=options.model,
            language=options.language,
            device="cpu",
            text="",
            segments=[],
            words=[],
        )
        return result, transcript, audio

    def fake_analyze(media_path, preset_name, transcript_json, stt_audio_path=None, advanced_audio_analysis=True, **kwargs):
        captured["analyze_limit"] = kwargs["limit_seconds"]
        candidates = context.paths.output_path("sample_cut_candidates.json")
        write_json(candidates, {"audio_analysis": {}, "candidates": []})
        return None, [], candidates

    def fake_export(media_path, preset_name, candidates_json, transcript_json, clean_wav_enabled, **kwargs):
        captured["export_limit"] = kwargs["limit_seconds"]
        xml = context.paths.output_path("sample_cut.xml")
        xml.write_text("<xmeml/>", encoding="utf-8")
        return PipelineArtifacts(xml=xml)

    monkeypatch.setattr(pipeline, "transcribe", fake_transcribe)
    monkeypatch.setattr(pipeline, "analyze_cuts", fake_analyze)
    monkeypatch.setattr(pipeline, "export", fake_export)

    artifacts = pipeline.run(PipelineOptions(input_path=media, limit_seconds=30.0))
    manifest = read_json(artifacts.manifest_json)

    assert captured == {"analyze_limit": 30.0, "export_limit": 30.0}
    assert manifest["limit_seconds"] == 30.0
    assert manifest["metadata"]["output"]["transcription_limit_seconds"] == 30.0
