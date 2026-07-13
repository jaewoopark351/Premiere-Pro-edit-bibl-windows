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
  <p>Preset: <code>{escape(str(summary.get('preset', 'unknown')))}</code></p>
  <p>Duration: {summary.get('duration', 0):.2f}s, candidates: {len(candidates)}</p>
  <table>
    <thead><tr><th>Time</th><th>Reason</th><th>Confidence</th><th>Auto delete</th><th>Review</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8", newline="\n")

