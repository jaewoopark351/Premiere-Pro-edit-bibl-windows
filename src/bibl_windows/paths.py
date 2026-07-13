from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


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


def windows_file_uri(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").upper()
    if not drive:
        raise PathSafetyError(f"Windows file URI requires an absolute drive path: {resolved}")
    parts = [quote(part) for part in resolved.parts[1:]]
    return f"file:///{drive}:/" + "/".join(parts)


def media_stem(path: Path) -> str:
    stem = path.stem.strip()
    return stem or "media"
