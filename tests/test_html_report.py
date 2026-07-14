from pathlib import Path
import uuid

from bibl_windows.reports.html import write_report
from bibl_windows.timeline.models import CutCandidate


def test_html_report_includes_timeline_summary():
    test_dir = Path.cwd() / ".test_tmp_manual" / f"html_report_{uuid.uuid4().hex}"
    test_dir.mkdir(parents=True)
    out = test_dir / "report.html"
    try:
        write_report(
            out,
            "sample",
            [
                CutCandidate(
                    start=1.0,
                    end=2.0,
                    reason="long_silence",
                    confidence=0.8,
                    auto_delete=True,
                    requires_review=False,
                    metadata={},
                )
            ],
            {
                "preset": "standard",
                "duration": 10.0,
                "edited_duration": 8.0,
                "removed_duration": 2.0,
                "keep_ranges": 2,
                "deletion_ranges": 1,
                "auto_delete_candidates": 1,
                "review_candidates": 0,
                "rejected_ranges": [{"start": 1.0, "end": 2.0, "duration": 1.0}],
                "choppy_sections": [],
            },
        )

        html = out.read_text(encoding="utf-8")
        assert "Edited duration" in html
        assert "8.00s" in html
        assert "Review candidates" in html
        assert "Rejected Ranges" in html
        assert "00:00:01.00 - 00:00:02.00" in html
    finally:
        if out.exists():
            out.unlink()
        try:
            test_dir.rmdir()
            test_dir.parent.rmdir()
        except OSError:
            pass
