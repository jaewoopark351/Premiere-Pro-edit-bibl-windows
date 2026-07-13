from bibl_windows.cli import build_parser


def test_run_parser_defaults_to_full_transcription():
    args = build_parser().parse_args(["run", "sample.mp4"])
    assert args.limit_seconds is None


def test_run_parser_accepts_legacy_transcribe_seconds_alias():
    args = build_parser().parse_args(["run", "sample.mp4", "--transcribe-seconds", "23.5"])
    assert args.limit_seconds == 23.5


def test_run_parser_accepts_limit_seconds():
    args = build_parser().parse_args(["run", "sample.mp4", "--limit-seconds", "30"])
    assert args.limit_seconds == 30


def test_parser_accepts_claude_assets_command():
    args = build_parser().parse_args(["claude"])
    assert args.command == "claude"
    assert not args.verbose


def test_parser_accepts_claude_verbose_alias():
    args = build_parser().parse_args(["claude", "--full"])
    assert args.verbose


def test_parser_accepts_claude_output_path():
    args = build_parser().parse_args(["claude", "--full", "--output", "output/claude.json"])
    assert args.verbose
    assert args.output == "output/claude.json"
    assert not args.ascii_output


def test_parser_accepts_claude_ascii_output():
    args = build_parser().parse_args(["claude", "--full", "--output", "output/claude.json", "--ascii-output"])
    assert args.output == "output/claude.json"
    assert args.ascii_output
