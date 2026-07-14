from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .cuda_probe import collect_cuda_diagnostics
from .ffmpeg_tools import tool_info
from .io_json import read_json, write_json
from .media_probe import probe_media
from .pipeline import PipelineOptions, WindowsEditPipeline, load_transcript_words
from .runtime import RuntimeContext, RuntimeErrorWithHint
from .shorts.generator import ShortArtifact, build_vertical_xml, parse_range, render_vertical_mp4, write_short_subtitles
from .timeline.models import TimeRange
from .multicam.sync import best_lag_seconds, extract_envelope
from .multicam.xml import build_multicam_xml
from .video.analyze import analyze_video


PRESETS = ("conservative", "standard", "aggressive")
AUDIO_PRESETS = ("standard", "natural", "podcast")


def print_json(data: dict, ensure_ascii: bool = False) -> None:
    text = json.dumps(data, ensure_ascii=ensure_ascii, indent=2)
    write_console_text(text)


def write_console_text(text: str) -> None:
    payload = text + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    encoding = preferred_stdout_bytes_encoding()
    if buffer is not None:
        buffer.write(payload.encode(encoding, errors="backslashreplace"))
        sys.stdout.flush()
        return
    try:
        sys.stdout.write(payload)
    except UnicodeEncodeError:
        fallback = payload.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
        sys.stdout.write(fallback)


def preferred_stdout_bytes_encoding() -> str:
    if sys.stdout.isatty():
        return windows_console_output_encoding() or sys.stdout.encoding or "utf-8"
    return "utf-8"


def windows_console_output_encoding() -> str | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        code_page = ctypes.windll.kernel32.GetConsoleOutputCP()
    except Exception:
        return None
    if not code_page:
        return None
    return f"cp{code_page}"


def print_artifacts(artifacts) -> None:
    for key, value in artifacts.__dict__.items():
        if value is not None:
            print(f"{key}={value}")


def cmd_doctor(_args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    ffmpeg = tool_info("ffmpeg.exe")
    ffprobe = tool_info("ffprobe.exe")
    cuda = collect_cuda_diagnostics()
    print_json(
        {
            "ffmpeg": ffmpeg.__dict__ | {"path": str(ffmpeg.path) if ffmpeg.path else None},
            "ffprobe": ffprobe.__dict__ | {"path": str(ffprobe.path) if ffprobe.path else None},
            "cuda": cuda.to_dict(),
            "claude": context.claude.summary(),
        }
    )
    return 0


def cmd_claude(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    data = context.claude.to_dict() if args.verbose else context.claude.summary()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_for_windows_reader(output_path, data, ensure_ascii=args.ascii_output)
        print(f"claude_json={output_path.resolve()}")
        return 0
    print_json(data, ensure_ascii=args.verbose)
    return 0


def write_json_for_windows_reader(path: Path, data: dict, ensure_ascii: bool = False) -> None:
    text = json.dumps(data, ensure_ascii=ensure_ascii, indent=2)
    encoding = "ascii" if ensure_ascii else "utf-8-sig"
    path.write_text(text, encoding=encoding, newline="\n")


def cmd_probe(args: argparse.Namespace) -> int:
    pipeline = WindowsEditPipeline()
    info = pipeline.probe(Path(args.input))
    print_json(info.to_dict())
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    pipeline = WindowsEditPipeline()
    options = PipelineOptions(
        input_path=Path(args.input),
        preset_name=args.preset,
        model=args.model,
        language=args.language,
        stt_batch_size=args.stt_batch_size,
        stt_chunk_seconds=args.stt_chunk_seconds,
        limit_seconds=args.limit_seconds,
        allow_cpu_fallback=args.allow_cpu_fallback,
        command=sys.argv,
    )
    result, transcript_json, stt_audio = pipeline.transcribe(options)
    print(f"transcript_json={transcript_json}")
    print(f"stt_audio={stt_audio}")
    if result.warnings:
        print("warnings=" + "; ".join(result.warnings))
    if result.validation_issues:
        print("validation_issues=" + "; ".join(result.validation_issues))
    return 0


def cmd_analyze_cuts(args: argparse.Namespace) -> int:
    pipeline = WindowsEditPipeline()
    _media, _candidates, candidates_json = pipeline.analyze_cuts(
        Path(args.input),
        args.preset,
        Path(args.transcript) if args.transcript else None,
    )
    print(f"cut_candidates_json={candidates_json}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    pipeline = WindowsEditPipeline()
    artifacts = pipeline.export(
        media_path=Path(args.input),
        preset_name=args.preset,
        candidates_json=Path(args.candidates),
        transcript_json=Path(args.transcript) if args.transcript else None,
        clean_wav_enabled=args.clean_wav,
        audio_preset=args.audio_preset,
        stt_audio_path=Path(args.stt_audio) if args.stt_audio else None,
        extra_exports=not args.no_extra_exports,
    )
    print_artifacts(artifacts)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    pipeline = WindowsEditPipeline()
    options = PipelineOptions(
        input_path=Path(args.input),
        preset_name=args.preset,
        model=args.model,
        language=args.language,
        stt_batch_size=args.stt_batch_size,
        stt_chunk_seconds=args.stt_chunk_seconds,
        limit_seconds=args.limit_seconds,
        allow_cpu_fallback=args.allow_cpu_fallback,
        clean_wav=args.clean_wav,
        audio_preset=args.audio_preset,
        extra_exports=not args.no_extra_exports,
        advanced_audio_analysis=not args.no_advanced_audio_analysis,
        command=sys.argv,
    )
    if args.dry_run:
        print_json(pipeline.dry_run(options))
        return 0
    artifacts = pipeline.run(options)
    print_artifacts(artifacts)
    return 0


def cmd_init_report(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    out = context.paths.output_path("manual_run_note.json")
    write_json(out, {"note": args.note})
    print(f"note_json={out}")
    return 0


def cmd_analyze_video(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    ffmpeg, ffprobe = context.tools.require_media_tools()
    data = analyze_video(ffmpeg, ffprobe, Path(args.input))
    out = output_path_arg(context, args.output, f"{Path(args.input).stem}_video_analysis.json")
    write_json(out, data)
    print(f"video_analysis_json={out}")
    if args.print:
        print_json(data)
    return 0


def cmd_recommend_preset(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    ffmpeg, ffprobe = context.tools.require_media_tools()
    data = analyze_video(ffmpeg, ffprobe, Path(args.input))
    print_json(data["recommended_preset"])
    return 0


def cmd_shorts(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    ffmpeg, ffprobe = context.tools.require_media_tools()
    media_path = Path(args.input)
    media = probe_media(ffprobe, media_path)
    ranges = [parse_range(text) for text in args.ranges]
    words = load_transcript_words(Path(args.transcript)) if args.transcript else []
    outdir = context.paths.output_path("shorts", ".placeholder").parent
    outdir.mkdir(parents=True, exist_ok=True)
    artifacts: list[ShortArtifact] = []
    for idx, clip_range in enumerate(ranges, 1):
        name = f"short_{idx:02d}"
        xml_path = outdir / f"{name}.xml"
        xml_path.write_text(build_vertical_xml(media, clip_range, name), encoding="utf-8", newline="\n")
        srt = vtt = ass = None
        if words:
            srt, vtt, ass = write_short_subtitles(words, clip_range, name, outdir)
        mp4 = None
        if args.render_mp4:
            mp4 = outdir / f"{name}.mp4"
            render_vertical_mp4(ffmpeg, media_path, clip_range, mp4)
        artifacts.append(ShortArtifact(name=name, start=clip_range.start, end=clip_range.end, xml=xml_path, srt=srt, vtt=vtt, ass=ass, mp4=mp4))
    manifest = context.paths.output_path("shorts", "shorts_manifest.json")
    write_json(manifest, {"source": str(media_path), "shorts": [item.to_dict() for item in artifacts]})
    print(f"shorts_manifest_json={manifest}")
    for item in artifacts:
        print(f"{item.name}_xml={item.xml}")
        if item.mp4:
            print(f"{item.name}_mp4={item.mp4}")
    return 0


def cmd_sync_2cam(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    ffmpeg, _ffprobe = context.tools.require_media_tools()
    env_a = extract_envelope(ffmpeg, Path(args.first), env_rate=args.env_rate)
    env_b = extract_envelope(ffmpeg, Path(args.second), env_rate=args.env_rate)
    result = best_lag_seconds(env_a, env_b, env_rate=args.env_rate, max_lag_seconds=args.max_lag_seconds)
    print_json(result)
    return 0


def cmd_multicam_xml(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    _ffmpeg, ffprobe = context.tools.require_media_tools()
    master_path = Path(args.master)
    master = probe_media(ffprobe, master_path)
    cameras = [(probe_media(ffprobe, Path(path)), float(offset)) for path, offset in parse_camera_args(args.camera)]
    keeps = load_keep_ranges(Path(args.keep_ranges)) if args.keep_ranges else default_keep_ranges(context, master_path, master.duration)
    clean_audio = Path(args.clean_audio) if args.clean_audio else None
    output = output_path_arg(context, args.output, f"{master_path.stem}_multicam.xml")
    output.write_text(
        build_multicam_xml(master, cameras, keeps, f"{master_path.stem} multicam", clean_audio=clean_audio),
        encoding="utf-8",
        newline="\n",
    )
    print(f"multicam_xml={output}")
    return 0


def parse_camera_args(values: list[list[str]] | None) -> list[tuple[str, str]]:
    return [(item[0], item[1]) for item in (values or [])]


def load_keep_ranges(path: Path) -> list[TimeRange]:
    data = read_json(path)
    return [TimeRange(float(item["start"]), float(item["end"])) for item in data.get("keeps", [])]


def default_keep_ranges(context: RuntimeContext, master_path: Path, duration: float) -> list[TimeRange]:
    candidate = context.paths.output_dir / f"{master_path.stem}_keep_ranges.json"
    if candidate.exists():
        keeps = load_keep_ranges(candidate)
        if keeps:
            return keeps
    return [TimeRange(0.0, duration)]


def output_path_arg(context: RuntimeContext, value: str | None, default_name: str) -> Path:
    raw = Path(value) if value else Path(default_name)
    if raw.is_absolute():
        raise RuntimeErrorWithHint("Output paths must be relative to the project output directory.")
    return context.paths.output_path(*raw.parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bibl-windows")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    claude = sub.add_parser("claude")
    claude.add_argument("--verbose", "--full", action="store_true", help="include full agent and skill descriptions")
    claude.add_argument("--output", help="write JSON to a UTF-8 file instead of printing it")
    claude.add_argument("--ascii-output", action="store_true", help="escape non-ASCII characters in --output JSON")
    claude.set_defaults(func=cmd_claude)

    probe = sub.add_parser("probe")
    probe.add_argument("input")
    probe.set_defaults(func=cmd_probe)

    transcribe = sub.add_parser("transcribe")
    transcribe.add_argument("input")
    transcribe.add_argument("--preset", default="standard", choices=PRESETS)
    transcribe.add_argument("--limit-seconds", "--seconds", type=float, default=None, dest="limit_seconds")
    transcribe.add_argument("--model", default="openai/whisper-large-v3")
    transcribe.add_argument("--language", default="ko")
    transcribe.add_argument("--stt-batch-size", type=int, default=1)
    transcribe.add_argument("--stt-chunk-seconds", type=float, default=25.0)
    transcribe.add_argument("--allow-cpu-fallback", action="store_true")
    transcribe.set_defaults(func=cmd_transcribe)

    analyze = sub.add_parser("analyze-cuts")
    analyze.add_argument("input")
    analyze.add_argument("--preset", default="standard", choices=PRESETS)
    analyze.add_argument("--transcript")
    analyze.set_defaults(func=cmd_analyze_cuts)

    export = sub.add_parser("export")
    export.add_argument("input")
    export.add_argument("--preset", default="standard", choices=PRESETS)
    export.add_argument("--transcript")
    export.add_argument("--candidates", required=True)
    export.add_argument("--clean-wav", action="store_true")
    export.add_argument("--audio-preset", default="standard", choices=AUDIO_PRESETS)
    export.add_argument("--stt-audio")
    export.add_argument("--no-extra-exports", action="store_true")
    export.set_defaults(func=cmd_export)

    run = sub.add_parser("run")
    run.add_argument("input")
    run.add_argument("--preset", default="standard", choices=PRESETS)
    run.add_argument("--limit-seconds", "--transcribe-seconds", type=float, default=None, dest="limit_seconds")
    run.add_argument("--model", default="openai/whisper-large-v3")
    run.add_argument("--language", default="ko")
    run.add_argument("--stt-batch-size", type=int, default=1)
    run.add_argument("--stt-chunk-seconds", type=float, default=25.0)
    run.add_argument("--allow-cpu-fallback", action="store_true")
    run.add_argument("--clean-wav", action="store_true")
    run.add_argument("--audio-preset", default="standard", choices=AUDIO_PRESETS)
    run.add_argument("--no-extra-exports", action="store_true")
    run.add_argument("--no-advanced-audio-analysis", action="store_true")
    run.add_argument("--dry-run", action="store_true", help="validate inputs and show the planned outputs without STT or export")
    run.set_defaults(func=cmd_run)

    analyze_video_parser = sub.add_parser("analyze-video")
    analyze_video_parser.add_argument("input")
    analyze_video_parser.add_argument("--output")
    analyze_video_parser.add_argument("--print", action="store_true")
    analyze_video_parser.set_defaults(func=cmd_analyze_video)

    recommend = sub.add_parser("recommend-preset")
    recommend.add_argument("input")
    recommend.set_defaults(func=cmd_recommend_preset)

    shorts = sub.add_parser("shorts")
    shorts.add_argument("input")
    shorts.add_argument("ranges", nargs="+", help='time ranges such as "00:12-00:28"')
    shorts.add_argument("--transcript")
    shorts.add_argument("--render-mp4", action="store_true", help="also render vertical MP4 with FFmpeg/NVENC")
    shorts.set_defaults(func=cmd_shorts)

    sync = sub.add_parser("sync-2cam")
    sync.add_argument("first")
    sync.add_argument("second")
    sync.add_argument("--max-lag-seconds", type=float, default=300.0)
    sync.add_argument("--env-rate", type=int, default=100)
    sync.set_defaults(func=cmd_sync_2cam)

    multicam = sub.add_parser("multicam-xml")
    multicam.add_argument("master")
    multicam.add_argument("--camera", nargs=2, action="append", default=[], metavar=("PATH", "OFFSET_SECONDS"))
    multicam.add_argument("--keep-ranges")
    multicam.add_argument("--clean-audio")
    multicam.add_argument("--output")
    multicam.set_defaults(func=cmd_multicam_xml)

    note = sub.add_parser("note")
    note.add_argument("note")
    note.set_defaults(func=cmd_init_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RuntimeErrorWithHint as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
