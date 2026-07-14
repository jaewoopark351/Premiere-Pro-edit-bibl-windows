from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .cuda_probe import collect_cuda_diagnostics
from .ffmpeg_tools import ToolError, tool_info
from .io_json import read_json, write_json
from .media_probe import probe_media
from .paths import PathSafetyError
from .paths import localhost_file_uri, premiere_fcp7_pathurl, premiere_legacy_drive_file_uri, standards_compliant_file_uri
from .pipeline import PipelineOptions, WindowsEditPipeline, load_transcript_words
from .runtime import RuntimeContext, RuntimeErrorWithHint
from .shorts.generator import ShortArtifact, build_vertical_xml, parse_range, render_vertical_mp4, write_short_subtitles
from .timeline.models import TimeRange
from .multicam.sync import best_lag_seconds, extract_envelope
from .multicam.switching import build_auto_switched_multicam_xml, plan_camera_switches
from .multicam.xml import build_multicam_xml
from .premiere.automation import find_premiere_executable, launch_premiere, write_import_render_script
from .premiere.fcp7 import build_fcp7_xml
from .premiere.xml_validation import validate_fcp7_xml_pathurls
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


def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        report = build_doctor_report()
    except Exception as exc:
        data = {"diagnostic_error": str(exc)}
        print("Error: doctor diagnostics failed before all checks could run.", file=sys.stderr)
        print_json(data)
        return 3
    if args.strict:
        issues = strict_doctor_issues(report)
        report["strict"] = {"ok": not issues, "issues": issues}
        if issues:
            print("Error: strict doctor checks failed:", file=sys.stderr)
            for issue in issues:
                print(f"- {issue}", file=sys.stderr)
            print_json(report)
            return 2
    print_json(report)
    return 0


def build_doctor_report() -> dict:
    context = RuntimeContext.discover()
    ffmpeg = tool_info("ffmpeg.exe")
    ffprobe = tool_info("ffprobe.exe")
    cuda = collect_cuda_diagnostics()
    return {
        "ffmpeg": ffmpeg.__dict__ | {"path": str(ffmpeg.path) if ffmpeg.path else None},
        "ffprobe": ffprobe.__dict__ | {"path": str(ffprobe.path) if ffprobe.path else None},
        "cuda": cuda.to_dict(),
        "claude": context.claude.summary(),
    }


def strict_doctor_issues(report: dict) -> list[str]:
    issues: list[str] = []
    if not report.get("ffmpeg", {}).get("path"):
        issues.append("ffmpeg.exe was not found on PATH.")
    if not report.get("ffprobe", {}).get("path"):
        issues.append("ffprobe.exe was not found on PATH.")
    cuda = report.get("cuda", {})
    if not cuda.get("torch_available"):
        issues.append("PyTorch could not be imported.")
    if not cuda.get("cuda_available"):
        issues.append("torch.cuda.is_available() returned false.")
    return issues


def cmd_claude(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    data = context.claude.to_dict(include_body=args.include_body) if args.verbose else context.claude.summary()
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
        reuse_transcript_cache=not args.no_transcript_cache,
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
        limit_seconds=args.limit_seconds,
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
        limit_seconds=args.limit_seconds,
        output_dir=args.output_dir,
        output_name=args.output_name,
        overwrite=args.overwrite,
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
        stt_limit_seconds=args.stt_limit_seconds,
        allow_cpu_fallback=args.allow_cpu_fallback,
        clean_wav=args.clean_wav,
        audio_preset=args.audio_preset,
        extra_exports=not args.no_extra_exports,
        advanced_audio_analysis=not args.no_advanced_audio_analysis,
        output_dir=args.output_dir,
        output_name=args.output_name,
        overwrite=args.overwrite,
        reuse_transcript_cache=not args.no_transcript_cache,
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
    for clip_range in ranges:
        if clip_range.end > media.duration:
            raise RuntimeErrorWithHint(
                f"Shorts range {clip_range.start:.3f}-{clip_range.end:.3f}s exceeds media duration {media.duration:.3f}s."
            )
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


def cmd_auto_multicam_xml(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    _ffmpeg, ffprobe = context.tools.require_media_tools()
    master_path = Path(args.master)
    master = probe_media(ffprobe, master_path)
    cameras = [(probe_media(ffprobe, Path(path)), float(offset)) for path, offset in parse_camera_args(args.camera)]
    keeps = load_keep_ranges(Path(args.keep_ranges)) if args.keep_ranges else default_keep_ranges(context, master_path, master.duration)
    clean_audio = Path(args.clean_audio) if args.clean_audio else None
    switches = plan_camera_switches(
        master,
        cameras,
        keeps,
        switch_interval=args.switch_interval,
        min_segment=args.min_segment,
    )
    output = output_path_arg(context, args.output, f"{master_path.stem}_auto_multicam.xml")
    output.write_text(
        build_auto_switched_multicam_xml(
            master,
            cameras,
            switches,
            f"{master_path.stem} auto multicam",
            clean_audio=clean_audio,
        ),
        encoding="utf-8",
        newline="\n",
    )
    plan_path = output.with_suffix(".switches.json")
    write_json(
        plan_path,
        {
            "master": str(master_path),
            "cameras": [{"path": path, "offset": float(offset)} for path, offset in parse_camera_args(args.camera)],
            "switch_interval": args.switch_interval,
            "min_segment": args.min_segment,
            "switches": [item.to_dict() for item in switches],
        },
    )
    print(f"auto_multicam_xml={output}")
    print(f"switch_plan_json={plan_path}")
    return 0


def cmd_validate_xml(args: argparse.Namespace) -> int:
    report = validate_fcp7_xml_pathurls(
        Path(args.xml),
        expected_media=Path(args.media) if args.media else None,
        expected_clean_audio=Path(args.clean_audio) if args.clean_audio else None,
    )
    print_json(report)
    return 0 if report["ok"] else 2


def cmd_premiere_path_tests(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    _ffmpeg, ffprobe = context.tools.require_media_tools()
    media_path = Path(args.input)
    if not media_path.exists():
        raise RuntimeErrorWithHint(f"Input media file was not found: {media_path}")
    media = probe_media(ffprobe, media_path)
    clip_end = min(media.duration, max(0.1, args.duration_seconds))
    keeps = [TimeRange(0.0, clip_end)]
    variants = {
        "literal": premiere_fcp7_pathurl,
        "encoded": standards_compliant_file_uri,
        "legacy_drive_literal": lambda path: premiere_legacy_drive_file_uri(path, encoded=False),
        "legacy_drive_encoded": lambda path: premiere_legacy_drive_file_uri(path, encoded=True),
        "localhost_literal": lambda path: localhost_file_uri(path, encoded=False),
        "localhost_encoded": lambda path: localhost_file_uri(path, encoded=True),
        "localhost_colon_encoded": lambda path: localhost_file_uri(path, encoded=True, encode_drive_colon=True),
    }
    variant_reports: dict[str, dict] = {}
    variant_files: dict[str, str] = {}
    variant_pathurls: dict[str, str] = {}
    for variant, factory in variants.items():
        xml_path = context.paths.output_path(f"{media_path.stem}_{variant}_path_test.xml")
        xml_path.write_text(
            build_fcp7_xml(
                media,
                keeps,
                f"{media_path.stem} {variant} pathurl test",
                None,
                pathurl_factory=factory,
            ),
            encoding="utf-8",
            newline="\n",
        )
        variant_files[variant] = str(xml_path)
        variant_pathurls[variant] = factory(media.path)
        variant_reports[variant] = validate_fcp7_xml_pathurls(xml_path, expected_media=media.path)
    report = {
        "input": str(media.path),
        "duration_seconds": clip_end,
        "variants": variant_files,
        "pathurls": variant_pathurls,
        "validation": variant_reports,
        "premiere_manual_check": "Import each XML file in Premiere Pro. Use whichever one auto-links without the Locate Media dialog.",
    }
    report_path = context.paths.output_path(f"{media_path.stem}_path_test_report.json")
    write_json(report_path, report)
    for variant, xml_path in variant_files.items():
        print(f"{variant}_xml={xml_path}")
    print(f"path_test_report_json={report_path}")
    return 0 if all(item["ok"] for item in variant_reports.values()) else 2


def cmd_premiere_structure_tests(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    _ffmpeg, ffprobe = context.tools.require_media_tools()
    media_path = Path(args.input)
    if not media_path.exists():
        raise RuntimeErrorWithHint(f"Input media file was not found: {media_path}")
    media = probe_media(ffprobe, media_path)
    clean_audio = Path(args.clean_audio) if args.clean_audio else None
    if clean_audio is not None and not clean_audio.exists():
        raise RuntimeErrorWithHint(f"Clean audio file was not found: {clean_audio}")
    clip_end = min(media.duration, max(0.1, args.duration_seconds))
    keeps = [TimeRange(0.0, clip_end)]
    pathurl_styles = {
        "encoded": standards_compliant_file_uri,
        "legacy_drive_encoded": lambda path: premiere_legacy_drive_file_uri(path, encoded=True),
        "localhost_encoded": lambda path: localhost_file_uri(path, encoded=True),
    }
    media_modes = ("full", "video-only", "none")
    reports: dict[str, dict] = {}
    files: dict[str, str] = {}
    for style, factory in pathurl_styles.items():
        for mode in media_modes:
            key = f"{style}_{mode}"
            xml_path = context.paths.output_path(f"{media_path.stem}_{key}_structure_test.xml")
            xml_path.write_text(
                build_fcp7_xml(
                    media,
                    keeps,
                    f"{media_path.stem} {key} structure test",
                    clean_audio,
                    pathurl_factory=factory,
                    video_file_media=mode,
                ),
                encoding="utf-8",
                newline="\n",
            )
            files[key] = str(xml_path)
            reports[key] = validate_fcp7_xml_pathurls(xml_path, expected_media=media.path, expected_clean_audio=clean_audio)
    report = {
        "input": str(media.path),
        "clean_audio": str(clean_audio) if clean_audio else None,
        "duration_seconds": clip_end,
        "variants": files,
        "validation": reports,
        "premiere_manual_check": "Import each XML file in Premiere Pro. This isolates video <file><media> structure from pathurl formatting.",
    }
    report_path = context.paths.output_path(f"{media_path.stem}_structure_test_report.json")
    write_json(report_path, report)
    for key, xml_path in files.items():
        print(f"{key}_xml={xml_path}")
    print(f"structure_test_report_json={report_path}")
    return 0 if all(item["ok"] for item in reports.values()) else 2


def cmd_premiere_script(args: argparse.Namespace) -> int:
    context = RuntimeContext.discover()
    xml_path = Path(args.xml)
    if not xml_path.exists():
        raise RuntimeErrorWithHint(f"Premiere XML file was not found: {xml_path}")
    srt_path = Path(args.srt) if args.srt else None
    if srt_path is not None and not srt_path.exists():
        raise RuntimeErrorWithHint(f"Subtitle file was not found: {srt_path}")
    encoder_preset = Path(args.encoder_preset) if args.encoder_preset else None
    if encoder_preset is not None and not encoder_preset.exists():
        raise RuntimeErrorWithHint(f"Adobe encoder preset was not found: {encoder_preset}")
    export_mp4 = output_path_arg(context, args.export_mp4, Path(args.xml).stem + "_premiere_export.mp4") if args.export_mp4 else None
    output = output_path_arg(context, args.output, Path(args.xml).stem + "_premiere_import.jsx")
    write_import_render_script(
        output,
        xml_path,
        srt_path=srt_path,
        export_path=export_mp4,
        encoder_preset=encoder_preset,
    )
    print(f"premiere_script={output}")
    if export_mp4:
        print(f"planned_export_mp4={export_mp4}")
    return 0


def cmd_premiere_launch(args: argparse.Namespace) -> int:
    premiere_exe = find_premiere_executable(Path(args.premiere_exe) if args.premiere_exe else None)
    if premiere_exe is None:
        raise RuntimeErrorWithHint(
            "Adobe Premiere Pro executable was not found. Pass --premiere-exe with the full path to Adobe Premiere Pro.exe."
        )
    xml_path = Path(args.xml) if args.xml else None
    script_path = Path(args.script) if args.script else None
    if xml_path is not None and not xml_path.exists():
        raise RuntimeErrorWithHint(f"Premiere XML file was not found: {xml_path}")
    if script_path is not None and not script_path.exists():
        raise RuntimeErrorWithHint(f"Premiere script file was not found: {script_path}")
    process = launch_premiere(premiere_exe, xml_path=xml_path, script_path=script_path)
    print(f"premiere_pid={process.pid}")
    print(f"premiere_exe={premiere_exe}")
    if script_path is not None:
        print("warning=Premiere Pro for Windows does not support command-line JSX auto-run with -r; opened Premiere without passing the script.")
        print(f"manual_script={script_path.resolve()}")
        print("manual_steps=Create or open a Premiere project, then import the XML/SRT manually. If your Premiere build exposes a script runner, run the JSX from inside Premiere.")
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
    parser.add_argument("--debug", action="store_true", help="show full Python traceback on errors")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    doctor.add_argument("--strict", action="store_true", help="fail if ffmpeg, ffprobe, PyTorch, or CUDA are unavailable")
    doctor.set_defaults(func=cmd_doctor)

    claude = sub.add_parser("claude")
    claude.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    claude.add_argument("--verbose", "--full", action="store_true", help="include full agent and skill descriptions")
    claude.add_argument("--include-body", action="store_true", help="include full .claude agent/skill markdown bodies with --full")
    claude.add_argument("--output", help="write JSON to a UTF-8 file instead of printing it")
    claude.add_argument("--ascii-output", action="store_true", help="escape non-ASCII characters in --output JSON")
    claude.set_defaults(func=cmd_claude)

    probe = sub.add_parser("probe")
    probe.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    probe.add_argument("input")
    probe.set_defaults(func=cmd_probe)

    transcribe = sub.add_parser("transcribe")
    transcribe.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    transcribe.add_argument("input")
    transcribe.add_argument("--preset", default="standard", choices=PRESETS)
    transcribe.add_argument("--limit-seconds", "--seconds", type=float, default=None, dest="limit_seconds")
    transcribe.add_argument("--model", default="openai/whisper-large-v3")
    transcribe.add_argument("--language", default="ko")
    transcribe.add_argument("--stt-batch-size", type=int, default=1)
    transcribe.add_argument("--stt-chunk-seconds", type=float, default=25.0)
    transcribe.add_argument("--allow-cpu-fallback", action="store_true")
    transcribe.add_argument("--no-transcript-cache", action="store_true", help="force Whisper even if a matching transcript JSON exists")
    transcribe.set_defaults(func=cmd_transcribe)

    analyze = sub.add_parser("analyze-cuts")
    analyze.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    analyze.add_argument("input")
    analyze.add_argument("--preset", default="standard", choices=PRESETS)
    analyze.add_argument("--transcript")
    analyze.add_argument("--limit-seconds", type=float, default=None)
    analyze.set_defaults(func=cmd_analyze_cuts)

    export = sub.add_parser("export")
    export.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    export.add_argument("input")
    export.add_argument("--preset", default="standard", choices=PRESETS)
    export.add_argument("--transcript")
    export.add_argument("--candidates", required=True)
    export.add_argument("--clean-wav", action="store_true", default=True)
    export.add_argument("--no-clean-wav", action="store_false", dest="clean_wav")
    export.add_argument("--audio-preset", default="natural", choices=AUDIO_PRESETS)
    export.add_argument("--stt-audio")
    export.add_argument("--no-extra-exports", action="store_true")
    export.add_argument("--limit-seconds", type=float, default=None)
    export.add_argument("--output-dir")
    export.add_argument("--output-name")
    export.add_argument("--overwrite", action="store_true")
    export.set_defaults(func=cmd_export)

    run = sub.add_parser("run")
    run.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    run.add_argument("input")
    run.add_argument("--preset", default="standard", choices=PRESETS)
    run.add_argument(
        "--limit-seconds",
        "--smoke-seconds",
        type=float,
        default=None,
        dest="limit_seconds",
        help="limit the whole pipeline to the first N seconds",
    )
    run.add_argument(
        "--stt-limit-seconds",
        "--transcribe-seconds",
        type=float,
        default=None,
        dest="stt_limit_seconds",
        help="limit only the audio passed to Whisper",
    )
    run.add_argument("--model", default="openai/whisper-large-v3")
    run.add_argument("--language", default="ko")
    run.add_argument("--stt-batch-size", type=int, default=1)
    run.add_argument("--stt-chunk-seconds", type=float, default=25.0)
    run.add_argument("--allow-cpu-fallback", action="store_true")
    run.add_argument("--clean-wav", action="store_true", default=True)
    run.add_argument("--no-clean-wav", action="store_false", dest="clean_wav")
    run.add_argument("--audio-preset", default="natural", choices=AUDIO_PRESETS)
    run.add_argument("--no-extra-exports", action="store_true")
    run.add_argument("--no-advanced-audio-analysis", action="store_true")
    run.add_argument("--no-transcript-cache", action="store_true", help="force Whisper even if a matching transcript JSON exists")
    run.add_argument("--output-dir", help="relative subdirectory under output")
    run.add_argument("--output-name", help="base name for generated artifacts")
    run.add_argument("--overwrite", action="store_true", help="reuse the requested output base even if a manifest exists")
    run.add_argument("--dry-run", action="store_true", help="validate inputs and show the planned outputs without STT or export")
    run.set_defaults(func=cmd_run)

    analyze_video_parser = sub.add_parser("analyze-video")
    analyze_video_parser.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    analyze_video_parser.add_argument("input")
    analyze_video_parser.add_argument("--output")
    analyze_video_parser.add_argument("--print", action="store_true")
    analyze_video_parser.set_defaults(func=cmd_analyze_video)

    recommend = sub.add_parser("recommend-preset")
    recommend.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    recommend.add_argument("input")
    recommend.set_defaults(func=cmd_recommend_preset)

    shorts = sub.add_parser("shorts")
    shorts.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    shorts.add_argument("input")
    shorts.add_argument("ranges", nargs="+", help='time ranges such as "00:12-00:28"')
    shorts.add_argument("--transcript")
    shorts.add_argument("--render-mp4", action="store_true", help="also render vertical MP4 with FFmpeg/NVENC")
    shorts.set_defaults(func=cmd_shorts)

    sync = sub.add_parser("sync-2cam")
    sync.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    sync.add_argument("first")
    sync.add_argument("second")
    sync.add_argument("--max-lag-seconds", type=float, default=300.0)
    sync.add_argument("--env-rate", type=int, default=100)
    sync.set_defaults(func=cmd_sync_2cam)

    multicam = sub.add_parser("multicam-xml")
    multicam.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    multicam.add_argument("master")
    multicam.add_argument("--camera", nargs=2, action="append", default=[], metavar=("PATH", "OFFSET_SECONDS"))
    multicam.add_argument("--keep-ranges")
    multicam.add_argument("--clean-audio")
    multicam.add_argument("--output")
    multicam.set_defaults(func=cmd_multicam_xml)

    auto_multicam = sub.add_parser("auto-multicam-xml")
    auto_multicam.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    auto_multicam.add_argument("master")
    auto_multicam.add_argument("--camera", nargs=2, action="append", default=[], metavar=("PATH", "OFFSET_SECONDS"))
    auto_multicam.add_argument("--keep-ranges")
    auto_multicam.add_argument("--clean-audio")
    auto_multicam.add_argument("--switch-interval", type=float, default=6.0)
    auto_multicam.add_argument("--min-segment", type=float, default=1.0)
    auto_multicam.add_argument("--output")
    auto_multicam.set_defaults(func=cmd_auto_multicam_xml)

    validate_xml = sub.add_parser("validate-xml")
    validate_xml.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    validate_xml.add_argument("xml")
    validate_xml.add_argument("--media")
    validate_xml.add_argument("--clean-audio")
    validate_xml.set_defaults(func=cmd_validate_xml)

    path_tests = sub.add_parser("premiere-path-tests")
    path_tests.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    path_tests.add_argument("input")
    path_tests.add_argument("--duration-seconds", type=float, default=1.0)
    path_tests.set_defaults(func=cmd_premiere_path_tests)

    structure_tests = sub.add_parser("premiere-structure-tests")
    structure_tests.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    structure_tests.add_argument("input")
    structure_tests.add_argument("--clean-audio")
    structure_tests.add_argument("--duration-seconds", type=float, default=1.0)
    structure_tests.set_defaults(func=cmd_premiere_structure_tests)

    premiere_script = sub.add_parser("premiere-script")
    premiere_script.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    premiere_script.add_argument("xml")
    premiere_script.add_argument("--srt")
    premiere_script.add_argument("--output")
    premiere_script.add_argument("--export-mp4")
    premiere_script.add_argument("--encoder-preset")
    premiere_script.set_defaults(func=cmd_premiere_script)

    premiere_launch = sub.add_parser("premiere-launch")
    premiere_launch.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    premiere_launch.add_argument("--premiere-exe")
    premiere_launch.add_argument("--xml", help="optional project/XML path to pass when no --script is provided")
    premiere_launch.add_argument(
        "--script",
        help="JSX path to validate and report for manual use; Windows Premiere is launched without unsupported -r auto-run",
    )
    premiere_launch.set_defaults(func=cmd_premiere_launch)

    note = sub.add_parser("note")
    note.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    note.add_argument("note")
    note.set_defaults(func=cmd_init_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (RuntimeErrorWithHint, ToolError, PathSafetyError, ValueError, json.JSONDecodeError) as exc:
        if getattr(args, "debug", False):
            raise
        print(format_user_error(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        if getattr(args, "debug", False):
            raise
        print(format_user_error(exc), file=sys.stderr)
        return 2


def format_user_error(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "Error: JSON file could not be parsed. Check that the transcript, candidates, or keep-ranges file is not corrupted."
    text = str(exc).strip()
    if isinstance(exc, ToolError):
        first = next((line for line in text.splitlines() if line.strip()), "FFmpeg command failed.")
        return "Error: " + first + "\nRun `python -m bibl_windows.cli doctor` and confirm ffmpeg.exe/ffprobe.exe are on PATH."
    if isinstance(exc, PathSafetyError):
        return "Error: " + text
    if isinstance(exc, RuntimeErrorWithHint):
        return "Error: " + text
    if isinstance(exc, ValueError):
        return "Error: invalid input: " + text
    return "Error: " + (text or exc.__class__.__name__) + "\nRun again with `--debug` for a full traceback."


if __name__ == "__main__":
    raise SystemExit(main())
