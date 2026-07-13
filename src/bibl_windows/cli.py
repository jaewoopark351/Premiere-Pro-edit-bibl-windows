from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .cuda_probe import collect_cuda_diagnostics
from .ffmpeg_tools import tool_info
from .io_json import write_json
from .pipeline import PipelineOptions, WindowsEditPipeline
from .runtime import RuntimeContext, RuntimeErrorWithHint


PRESETS = ("conservative", "standard", "aggressive")


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
        limit_seconds=args.limit_seconds,
        allow_cpu_fallback=args.allow_cpu_fallback,
        clean_wav=args.clean_wav,
        command=sys.argv,
    )
    artifacts = pipeline.run(options)
    print_artifacts(artifacts)
    return 0


def cmd_init_report(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    out = context.paths.output_path("manual_run_note.json")
    write_json(out, {"note": args.note})
    print(f"note_json={out}")
    return 0


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
    export.set_defaults(func=cmd_export)

    run = sub.add_parser("run")
    run.add_argument("input")
    run.add_argument("--preset", default="standard", choices=PRESETS)
    run.add_argument("--limit-seconds", "--transcribe-seconds", type=float, default=None, dest="limit_seconds")
    run.add_argument("--model", default="openai/whisper-large-v3")
    run.add_argument("--language", default="ko")
    run.add_argument("--allow-cpu-fallback", action="store_true")
    run.add_argument("--clean-wav", action="store_true")
    run.set_defaults(func=cmd_run)

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
