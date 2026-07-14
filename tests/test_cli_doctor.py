from bibl_windows import cli


def strict_report(**overrides):
    report = {
        "ffmpeg": {"path": r"C:\ffmpeg\bin\ffmpeg.exe"},
        "ffprobe": {"path": r"C:\ffmpeg\bin\ffprobe.exe"},
        "cuda": {
            "torch_available": True,
            "cuda_available": True,
            "gpu_name": "NVIDIA GeForce RTX 5070 Ti",
            "gpu_total_vram_bytes": 16 * 1024**3,
        },
        "claude": {"exists": True},
    }
    report.update(overrides)
    return report


def test_strict_doctor_issues_require_media_tools_and_cuda():
    report = strict_report(
        ffmpeg={"path": None},
        cuda={"torch_available": False, "cuda_available": False},
    )

    issues = cli.strict_doctor_issues(report)

    assert "ffmpeg.exe was not found on PATH." in issues
    assert "PyTorch could not be imported." in issues
    assert "torch.cuda.is_available() returned false." in issues


def test_doctor_strict_returns_nonzero_with_diagnostics(monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_doctor_report", lambda: strict_report(ffprobe={"path": None}))

    code = cli.main(["doctor", "--strict"])
    captured = capsys.readouterr()

    assert code == 2
    assert "strict doctor checks failed" in captured.err
    assert "\"strict\"" in captured.out
    assert "ffprobe.exe was not found on PATH." in captured.out


def test_doctor_strict_does_not_fail_for_lower_gpu_name(monkeypatch):
    monkeypatch.setattr(cli, "build_doctor_report", lambda: strict_report(cuda={"torch_available": True, "cuda_available": True, "gpu_name": "NVIDIA GeForce RTX 4060"}))

    assert cli.main(["doctor", "--strict"]) == 0
