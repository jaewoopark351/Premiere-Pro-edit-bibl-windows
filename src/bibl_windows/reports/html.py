from __future__ import annotations

from html import escape
from pathlib import Path

from ..timeline.models import CutCandidate


def _tc(t: float) -> str:
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    s = t - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def write_report(path: Path, title: str, candidates: list[CutCandidate], summary: dict) -> None:
    stats = [
        ("Preset", str(summary.get("preset", "unknown"))),
        ("Source duration", f"{float(summary.get('duration', 0.0)):.2f}s"),
        ("Edited duration", f"{float(summary.get('edited_duration', 0.0)):.2f}s"),
        ("Removed duration", f"{float(summary.get('removed_duration', 0.0)):.2f}s"),
        ("Keep ranges", str(summary.get("keep_ranges", "unknown"))),
        ("Deletion ranges", str(summary.get("deletion_ranges", "unknown"))),
        ("Auto candidates", str(summary.get("auto_delete_candidates", 0))),
        ("Review candidates", str(summary.get("review_candidates", 0))),
    ]
    stat_rows = "\n".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in stats
    )
    rows = "\n".join(
        "<tr>"
        f"<td>{_tc(c.start)} - {_tc(c.end)}</td>"
        f"<td>{escape(c.reason)}</td>"
        f"<td>{c.confidence:.2f}</td>"
        f"<td>{'yes' if c.auto_delete else 'no'}</td>"
        f"<td>{'yes' if c.requires_review else 'no'}</td>"
        "</tr>"
        for c in candidates
    )
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: Segoe UI, Pretendard, sans-serif; margin: 24px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #f3f4f6; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <h2>Summary</h2>
  <table>
    <tbody>{stat_rows}</tbody>
  </table>
  <h2>Cut Candidates</h2>
  <p>Candidates: {len(candidates)}</p>
  <table>
    <thead><tr><th>Time</th><th>Reason</th><th>Confidence</th><th>Auto delete</th><th>Review</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8", newline="\n")
