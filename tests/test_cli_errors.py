from bibl_windows.cli import main


def test_cli_hides_traceback_for_missing_input(capsys):
    rc = main(["run", "does-not-exist.mp4", "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "Error:" in captured.err
    assert "Traceback" not in captured.err
    assert "Input media file was not found" in captured.err
