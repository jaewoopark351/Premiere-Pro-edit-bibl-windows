from bibl_windows.cli import build_parser


def test_run_parser_defaults_to_full_transcription():
    args = build_parser().parse_args(["run", "sample.mp4"])
    assert args.limit_seconds is None


def test_run_parser_accepts_legacy_transcribe_seconds_alias():
    args = build_parser().parse_args(["run", "sample.mp4", "--transcribe-seconds", "23.5"])
    assert args.stt_limit_seconds == 23.5


def test_run_parser_accepts_limit_seconds():
    args = build_parser().parse_args(["run", "sample.mp4", "--limit-seconds", "30"])
    assert args.limit_seconds == 30


def test_run_parser_accepts_smoke_seconds_as_pipeline_limit():
    args = build_parser().parse_args(["run", "sample.mp4", "--smoke-seconds", "15"])
    assert args.limit_seconds == 15


def test_run_parser_accepts_stt_limit_seconds():
    args = build_parser().parse_args(["run", "sample.mp4", "--stt-limit-seconds", "12"])
    assert args.stt_limit_seconds == 12


def test_run_parser_accepts_dry_run():
    args = build_parser().parse_args(["run", "sample.mp4", "--dry-run"])
    assert args.dry_run


def test_doctor_parser_accepts_strict():
    args = build_parser().parse_args(["doctor", "--strict"])
    assert args.strict is True


def test_run_parser_accepts_stt_batch_size():
    args = build_parser().parse_args(["run", "sample.mp4", "--stt-batch-size", "2"])
    assert args.stt_batch_size == 2


def test_run_parser_defaults_to_safe_stt_batch_size():
    args = build_parser().parse_args(["run", "sample.mp4"])
    assert args.stt_batch_size == 1


def test_run_parser_accepts_stt_chunk_seconds():
    args = build_parser().parse_args(["run", "sample.mp4", "--stt-chunk-seconds", "20"])
    assert args.stt_chunk_seconds == 20


def test_run_parser_defaults_to_5070ti_safe_stt_chunk_seconds():
    args = build_parser().parse_args(["run", "sample.mp4"])
    assert args.stt_chunk_seconds == 25.0


def test_run_parser_accepts_phase_2_3_options():
    args = build_parser().parse_args(["run", "sample.mp4", "--audio-preset", "podcast", "--no-extra-exports"])
    assert args.audio_preset == "podcast"
    assert args.no_extra_exports


def test_run_parser_defaults_to_original_audio_cleanup():
    args = build_parser().parse_args(["run", "sample.mp4"])
    assert args.clean_wav is True
    assert args.audio_preset == "natural"


def test_run_parser_can_disable_default_clean_wav():
    args = build_parser().parse_args(["run", "sample.mp4", "--no-clean-wav"])
    assert args.clean_wav is False


def test_run_parser_accepts_output_controls():
    args = build_parser().parse_args(
        ["run", "sample.mp4", "--output-dir", "session 1", "--output-name", "custom", "--overwrite"]
    )
    assert args.output_dir == "session 1"
    assert args.output_name == "custom"
    assert args.overwrite


def test_run_parser_accepts_no_transcript_cache():
    args = build_parser().parse_args(["run", "sample.mp4", "--no-transcript-cache"])
    assert args.no_transcript_cache


def test_transcribe_parser_accepts_no_transcript_cache():
    args = build_parser().parse_args(["transcribe", "sample.mp4", "--no-transcript-cache"])
    assert args.no_transcript_cache


def test_parser_accepts_shorts_command():
    args = build_parser().parse_args(["shorts", "sample.mp4", "00:01-00:05", "--transcript", "out.json"])
    assert args.command == "shorts"
    assert args.ranges == ["00:01-00:05"]


def test_parser_accepts_multicam_command():
    args = build_parser().parse_args(["multicam-xml", "master.mp4", "--camera", "cam.mp4", "1.25"])
    assert args.command == "multicam-xml"
    assert args.camera == [["cam.mp4", "1.25"]]


def test_parser_accepts_auto_multicam_command():
    args = build_parser().parse_args(
        ["auto-multicam-xml", "master.mp4", "--camera", "cam.mp4", "1.25", "--switch-interval", "4"]
    )
    assert args.command == "auto-multicam-xml"
    assert args.switch_interval == 4


def test_parser_accepts_premiere_script_command():
    args = build_parser().parse_args(["premiere-script", "out.xml", "--srt", "out.srt", "--export-mp4", "render.mp4"])
    assert args.command == "premiere-script"
    assert args.export_mp4 == "render.mp4"


def test_parser_accepts_premiere_launch_command():
    args = build_parser().parse_args(["premiere-launch", "--xml", "out.xml"])
    assert args.command == "premiere-launch"
    assert args.xml == "out.xml"


def test_parser_accepts_claude_assets_command():
    args = build_parser().parse_args(["claude"])
    assert args.command == "claude"
    assert not args.verbose


def test_parser_accepts_claude_verbose_alias():
    args = build_parser().parse_args(["claude", "--full"])
    assert args.verbose


def test_parser_accepts_claude_include_body():
    args = build_parser().parse_args(["claude", "--full", "--include-body"])
    assert args.verbose
    assert args.include_body


def test_parser_accepts_claude_output_path():
    args = build_parser().parse_args(["claude", "--full", "--output", "output/claude.json"])
    assert args.verbose
    assert args.output == "output/claude.json"
    assert not args.ascii_output


def test_parser_accepts_claude_ascii_output():
    args = build_parser().parse_args(["claude", "--full", "--output", "output/claude.json", "--ascii-output"])
    assert args.output == "output/claude.json"
    assert args.ascii_output
