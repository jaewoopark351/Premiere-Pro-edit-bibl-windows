from __future__ import annotations

import re
from pathlib import Path


DEFAULT_EMPHASIS_TERMS = (
    "어",
    "음",
    "엄",
    "아",
    "그",
    "저",
    "그러니까",
    "이제",
)


def ass_time(seconds: float) -> str:
    t = max(0.0, seconds)
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    t -= m * 60
    s = int(t)
    cs = int(round((t - s) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def write_ass(
    cues: list[tuple[float, float, str]],
    path: Path,
    title: str = "Bibl Windows Subtitles",
    emphasize: bool = False,
) -> None:
    path.write_text(build_ass(cues, title=title, emphasize=emphasize), encoding="utf-8", newline="\n")


def build_ass(cues: list[tuple[float, float, str]], title: str, emphasize: bool = False) -> str:
    lines = [
        "[Script Info]",
        f"Title: {title}",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Bibl,Pretendard,54,&H00FFFFFF,&H0000FFFF,&H00111111,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,80,80,120,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for start, end, text in cues:
        rendered = render_text(text, emphasize=emphasize)
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Bibl,,0,0,0,,{rendered}")
    return "\n".join(lines) + "\n"


def render_text(text: str, emphasize: bool = False) -> str:
    escaped = ass_escape(text)
    if not emphasize:
        return escaped
    return emphasize_terms(escaped)


def emphasize_terms(text: str, terms: tuple[str, ...] = DEFAULT_EMPHASIS_TERMS) -> str:
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w)({re.escape(term)})(?!\w)")
        text = pattern.sub(r"{\\c&H39D7FF&\\bord5}\1{\\rBibl}", text)
    return text
