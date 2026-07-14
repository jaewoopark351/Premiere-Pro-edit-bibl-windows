from pathlib import Path
import uuid

from bibl_windows.exports.transcript import paragraphs
from bibl_windows.subtitles.ass import build_ass
from bibl_windows.subtitles.srt import polish_cues
from bibl_windows.subtitles.vtt import write_vtt
from bibl_windows.timeline.models import TranscriptWord


def test_vtt_writer_outputs_webvtt():
    test_dir = Path.cwd() / ".test_tmp_manual" / f"subtitle_exports_{uuid.uuid4().hex}"
    test_dir.mkdir(parents=True)
    path = test_dir / "sample.vtt"
    try:
        write_vtt([(0, 1.2, "hello")], path)
        text = path.read_text(encoding="utf-8")
        assert text.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:01.200" in text
    finally:
        if path.exists():
            path.unlink()
        try:
            test_dir.rmdir()
            test_dir.parent.rmdir()
        except OSError:
            pass


def test_ass_emphasis_marks_fillers():
    ass = build_ass([(0, 1, "어 테스트")], title="x", emphasize=True)
    assert "[Events]" in ass
    assert "\\c&H39D7FF&" in ass


def test_polish_cues_splits_long_text():
    cues = polish_cues([(0, 4, "one two three four five six seven")], max_chars=12)
    assert len(cues) > 1


def test_transcript_paragraphs_split_on_gap():
    words = [TranscriptWord(0, 0.5, "a"), TranscriptWord(2, 2.4, "b")]
    assert len(paragraphs(words, max_gap=1.0)) == 2
