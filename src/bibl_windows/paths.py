from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path


class PathSafetyError(ValueError):
    pass


def find_project_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
            return candidate
    return cur


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> "ProjectPaths":
        return cls(find_project_root(start))

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def claude_dir(self) -> Path:
        return self.root / ".claude"

    @property
    def claude_agents_dir(self) -> Path:
        return self.claude_dir / "agents"

    @property
    def claude_skills_dir(self) -> Path:
        return self.claude_dir / "skills"

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir

    def output_path(self, *parts: str) -> Path:
        path = (self.output_dir.joinpath(*parts)).resolve()
        ensure_inside(path, self.output_dir.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def ensure_inside(path: Path, parent: Path) -> None:
    p = path.resolve()
    root = parent.resolve()
    try:
        p.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError(f"path is outside allowed directory: {p}") from exc


_URI_MUST_ESCAPE = re.compile(r'[ %#?\x00-\x1f]')


def _relax_non_ascii_uri_escaping(uri: str) -> str:
    """Un-escape percent-encoded non-ASCII path segments in a file:// URI.

    `Path.as_uri()` percent-encodes every non-ASCII byte per RFC 3986, which is
    correct but Adobe Premiere Pro's FCP7 XML importer fails to auto-locate
    media whose `pathurl` uses percent-encoded Korean/CJK text (confirmed by
    hand: an XML with the same path written as literal UTF-8 auto-links, the
    percent-encoded version always prompts a manual "Locate Media" dialog).
    Decoding back to literal characters and only re-escaping the handful of
    ASCII characters that are unsafe in a URI keeps Premiere's importer happy
    without touching UNC/drive-letter handling from `as_uri()`.
    """
    decoded = urllib.parse.unquote(uri, encoding="utf-8", errors="strict")
    return _URI_MUST_ESCAPE.sub(lambda m: f"%{ord(m.group(0)):02X}", decoded)


def windows_file_uri(path: Path) -> str:
    resolved = path if path.is_absolute() else path.resolve()
    try:
        return _relax_non_ascii_uri_escaping(resolved.as_uri())
    except ValueError as exc:
        raise PathSafetyError(
            "Could not convert media path to a Premiere file URI: "
            + str(resolved)
            + "\nUse an absolute drive path such as C:\\Videos\\clip.mp4. "
            + "For network shares, map the share to a drive letter if Premiere cannot import the UNC URI."
        ) from exc


def media_stem(path: Path) -> str:
    return safe_output_component(path.stem)


_INVALID_WINDOWS_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_output_component(value: str) -> str:
    cleaned = _INVALID_WINDOWS_NAME_CHARS.sub("_", value.strip()).rstrip(". ")
    return cleaned or "media"


def short_path_hash(path: Path, length: int = 8) -> str:
    resolved = str(path.resolve()).casefold()
    return hashlib.sha1(resolved.encode("utf-8", errors="surrogatepass")).hexdigest()[:length]
