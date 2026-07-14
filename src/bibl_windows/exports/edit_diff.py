from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_json import write_json
from ..timeline.models import TimeRange, TranscriptWord


def summarize_edit_diff(words: list[TranscriptWord], deletions: list[TimeRange], edited_duration: float, source_duration: float) -> dict[str, Any]:
    deleted_words: list[dict[str, Any]] = []
    kept_words = 0
    for word in words:
        midpoint = (word.start + word.end) / 2.0
        deletion = next((d for d in deletions if d.start <= midpoint <= d.end), None)
        if deletion:
            deleted_words.append(
                {
                    "start": word.start,
                    "end": word.end,
                    "text": word.text,
                    "deletion_start": deletion.start,
                    "deletion_end": deletion.end,
                }
            )
        else:
            kept_words += 1
    removed_duration = max(0.0, source_duration - edited_duration)
    return {
        "source_duration": source_duration,
        "edited_duration": edited_duration,
        "removed_duration": removed_duration,
        "removed_ratio": removed_duration / source_duration if source_duration > 0 else 0.0,
        "deleted_ranges": [d.__dict__ for d in deletions],
        "deleted_word_count": len(deleted_words),
        "kept_word_count": kept_words,
        "deleted_words_preview": deleted_words[:200],
    }


def write_edit_diff(summary: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    write_json(json_path, summary)
    lines = [
        "# Edit Diff",
        "",
        f"- Source duration: {summary['source_duration']:.2f}s",
        f"- Edited duration: {summary['edited_duration']:.2f}s",
        f"- Removed duration: {summary['removed_duration']:.2f}s",
        f"- Deleted ranges: {len(summary['deleted_ranges'])}",
        f"- Deleted words: {summary['deleted_word_count']}",
        "",
        "## Deleted Word Preview",
        "",
    ]
    for item in summary["deleted_words_preview"]:
        lines.append(f"- {item['start']:.2f}-{item['end']:.2f}: {item['text']}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
