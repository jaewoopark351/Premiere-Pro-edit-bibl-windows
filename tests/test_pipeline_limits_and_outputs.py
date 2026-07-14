from pathlib import Path
import xml.etree.ElementTree as ET
from uuid import uuid4

from bibl_windows.artifacts import ArtifactManifest
from bibl_windows.claude_assets import ClaudeProjectAssets
from bibl_windows.ffmpeg_tools import ToolInfo
from bibl_windows.io_json import read_json, write_json
from bibl_windows.media_probe import AudioStream, MediaInfo, VideoStream
from bibl_windows.paths import ProjectPaths
from bibl_windows.pipeline import (
    PipelineArtifacts,
    PipelineOptions,
    WindowsEditPipeline,
    transcript_cache_metadata,
)
from bibl_windows.runtime import RuntimeContext, RuntimeTools
from bibl_windows.stt.base import TranscriptResult
from bibl_windows.stt.transformers_whisper import TransformersWhisperBackend
from bibl_windows.timeline.models import TranscriptSegment, TranscriptWord


def workspace_tmp(name: str) -> Path:
    path = Path(".test_tmp_manual") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def make_context(root: Path) -> RuntimeContext:
    paths = ProjectPaths(root)
    tools = RuntimeTools(ffmpeg=ToolInfo("ffmpeg.exe", None, None), ffprobe=ToolInfo("ffprobe.exe", None, None))
    return RuntimeContext(paths=paths, tools=tools, claude=ClaudeProjectAssets.discover(paths))


def make_context_with_tools(root: Path) -> RuntimeContext:
    paths = ProjectPaths(root)
    tools = RuntimeTools(
        ffmpeg=ToolInfo("ffmpeg.exe", Path("ffmpeg.exe"), "fake ffmpeg"),
        ffprobe=ToolInfo("ffprobe.exe", Path("ffprobe.exe"), "fake ffprobe"),
    )
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


def test_transcribe_reuses_matching_transcript_cache(monkeypatch):
    root = workspace_tmp("stt-cache")
    context = make_context_with_tools(root)
    pipeline = WindowsEditPipeline(context)
    media = root / "sample.mp4"
    media.write_bytes(b"media")
    options = PipelineOptions(input_path=media, model="fake-model", language="ko")
    layout = pipeline.output_layout(options)
    transcript = layout.output_path(context, f"{layout.stem}_transcript.json")
    words = [TranscriptWord(0.1, 0.3, "cached", 0.99)]
    write_json(
        transcript,
        {
            "source_audio": "",
            "backend": "fake",
            "model": "fake-model",
            "language": "ko",
            "device": "cuda:0",
            "text": "cached",
            "segments": [{"start": 0.1, "end": 0.3, "text": "cached", "words": [words[0].__dict__]}],
            "words": [words[0].__dict__],
            "warnings": [],
            "validation_issues": [],
            "metadata": transcript_cache_metadata(options, None),
        },
    )

    def fake_extract(_ffmpeg, _media, output_wav, _limit_seconds=None):
        output_wav.write_bytes(b"wav")

    def fail_transcribe(*_args, **_kwargs):
        raise AssertionError("Whisper should not run when a matching transcript cache exists")

    monkeypatch.setattr("bibl_windows.pipeline.extract_audio_for_stt", fake_extract)
    monkeypatch.setattr(TransformersWhisperBackend, "transcribe", fail_transcribe)

    result, transcript_json, stt_audio = pipeline.transcribe(options)

    assert transcript_json == transcript
    assert stt_audio.exists()
    assert result.text == "cached"
    assert any("Reused matching transcript cache" in warning for warning in result.warnings)


def test_export_writes_review_json_and_rejected_xml(monkeypatch):
    root = workspace_tmp("review-export")
    context = make_context_with_tools(root)
    pipeline = WindowsEditPipeline(context)
    media = root / "sample.mp4"
    media.write_bytes(b"media")
    candidates = context.paths.output_path("sample_cut_candidates.json")
    write_json(
        candidates,
        {
            "candidates": [
                {
                    "start": 0.5,
                    "end": 1.0,
                    "reason": "long_silence",
                    "confidence": 0.9,
                    "auto_delete": True,
                    "requires_review": False,
                    "metadata": {},
                },
                {
                    "start": 2.0,
                    "end": 2.2,
                    "reason": "false_start_prefix",
                    "confidence": 0.68,
                    "auto_delete": False,
                    "requires_review": True,
                    "metadata": {},
                },
            ]
        },
    )
    fake_media = MediaInfo(
        path=media,
        duration=5.0,
        video=VideoStream(index=0, codec_name="h264", width=1920, height=1080, fps=30.0, fps_text="30/1"),
        audio=AudioStream(index=1, codec_name="aac", sample_rate=48000, channels=2),
    )
    monkeypatch.setattr("bibl_windows.pipeline.probe_media", lambda _ffprobe, _media: fake_media)

    artifacts = pipeline.export(
        media,
        "standard",
        candidates,
        transcript_json=None,
        clean_wav_enabled=False,
        extra_exports=True,
    )

    assert artifacts.cut_review_json and artifacts.cut_review_json.exists()
    assert artifacts.rejected_xml and artifacts.rejected_xml.exists()
    review = read_json(artifacts.cut_review_json)
    assert len(review["rejected_ranges"]) == 1
    assert review["review_candidate_count"] == 1
    ET.parse(artifacts.rejected_xml)
