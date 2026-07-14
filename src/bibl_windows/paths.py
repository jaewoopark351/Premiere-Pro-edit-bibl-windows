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
    """Un-escape percent-encoded non-ASCII text in comparison file:// URIs.

    The confirmed Premiere FCP7 default is produced by
    ``premiere_fcp7_pathurl``. This helper is retained for pathurl comparison
    XMLs that still need a hierarchical ``file://...`` form with readable Korean
    text.
    """
    decoded = urllib.parse.unquote(uri, encoding="utf-8", errors="strict")
    return _URI_MUST_ESCAPE.sub(lambda m: f"%{ord(m.group(0)):02X}", decoded)


def standards_compliant_file_uri(path: Path) -> str:
    resolved = path if path.is_absolute() else path.resolve()
    try:
        return resolved.as_uri()
    except ValueError as exc:
        raise PathSafetyError(
            "Could not convert media path to a file URI: "
            + str(resolved)
            + "\nUse an absolute drive path such as C:\\Videos\\clip.mp4. "
            + "For network shares, map the share to a drive letter if Premiere cannot import the UNC URI."
        ) from exc


def premiere_fcp7_pathurl(path: Path) -> str:
    """Return the pathurl form Premiere Pro 2024 auto-links in FCP7 XML.

    Manual import testing on Windows showed that Premiere's FCP7 XML importer
    treats the RFC 8089 drive URI form (``file:///C:/...``) as a malformed
    local-drive-as-UNC path. The form that auto-linked in a completely fresh
    Premiere Pro 2024 project was the older FCP7-style opaque file path,
    ``file:C:/...``, with spaces and Korean text left literal. UNC paths still
    naturally become ``file://server/share/...``.
    """
    resolved = path if path.is_absolute() else path.resolve()
    text = str(resolved).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", text) or text.startswith("//"):
        return "file:" + text
    raise PathSafetyError(
        "Could not convert media path to a Premiere FCP7 pathurl: "
        + str(resolved)
        + "\nUse an absolute drive path such as C:\\Videos\\clip.mp4. "
        + "For network shares, map the share to a drive letter if Premiere cannot import the UNC pathurl."
    )


def localhost_file_uri(path: Path, *, encoded: bool = True, encode_drive_colon: bool = False) -> str:
    uri = standards_compliant_file_uri(path)
    if uri.startswith("file://") and not uri.startswith("file:///"):
        return uri
    if not uri.startswith("file:///"):
        raise PathSafetyError(f"Could not convert local path to localhost file URI: {path}")
    tail = uri[len("file:///") :]
    if encode_drive_colon:
        tail = tail.replace(":", "%3A", 1)
    localhost_uri = "file://localhost/" + tail
    return localhost_uri if encoded else _relax_non_ascii_uri_escaping(localhost_uri)


def premiere_legacy_drive_file_uri(path: Path, *, encoded: bool = True) -> str:
    """Return a Premiere FCP7 test URI like ``file://C:/path`` for drive paths.

    This is intentionally not the standards-compliant URI produced by
    ``Path.as_uri()``. It exists only as a Premiere importer compatibility
    candidate for cases where Premiere displays a local drive URI with a
    malformed leading UNC prefix.
    UNC paths already use the two-slash ``file://server/share`` form and should
    keep the standard conversion.
    """
    uri = standards_compliant_file_uri(path)
    if uri.startswith("file://") and not uri.startswith("file:///"):
        return uri
    if not uri.startswith("file:///"):
        raise PathSafetyError(f"Could not convert local path to legacy drive file URI: {path}")
    legacy_uri = "file://" + uri[len("file:///") :]
    return legacy_uri if encoded else _relax_non_ascii_uri_escaping(legacy_uri)


def file_uri_to_windows_path(uri: str) -> Path:
    opaque_drive = re.match(r"^file:([A-Za-z]:[/\\].*)$", uri, flags=re.IGNORECASE)
    if opaque_drive:
        return Path(opaque_drive.group(1).replace("/", "\\"))
    parsed = urllib.parse.urlsplit(uri)
    if parsed.scheme.lower() != "file":
        raise PathSafetyError(f"pathurl is not a file URI: {uri}")
    decoded_path = urllib.parse.unquote(parsed.path, encoding="utf-8", errors="strict")
    if re.fullmatch(r"[A-Za-z]:", parsed.netloc):
        return Path((parsed.netloc + decoded_path).replace("/", "\\"))
    if parsed.netloc and parsed.netloc.lower() != "localhost":
        return Path("\\\\" + parsed.netloc + decoded_path.replace("/", "\\"))
    if decoded_path.startswith("/") and len(decoded_path) >= 3 and decoded_path[2] == ":":
        decoded_path = decoded_path[1:]
    return Path(decoded_path.replace("/", "\\"))


def windows_file_uri(path: Path) -> str:
    """Backward-compatible alias for Premiere FCP7 XML pathurl values."""
    return premiere_fcp7_pathurl(path)


def media_stem(path: Path) -> str:
    return safe_output_component(path.stem)


_INVALID_WINDOWS_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_output_component(value: str) -> str:
    cleaned = _INVALID_WINDOWS_NAME_CHARS.sub("_", value.strip()).rstrip(". ")
    return cleaned or "media"


def short_path_hash(path: Path, length: int = 8) -> str:
    resolved = str(path.resolve()).casefold()
    return hashlib.sha1(resolved.encode("utf-8", errors="surrogatepass")).hexdigest()[:length]
