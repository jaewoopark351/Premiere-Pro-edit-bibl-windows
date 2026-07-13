from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import ProjectPaths


@dataclass(frozen=True)
class ClaudeAsset:
    kind: str
    name: str
    path: Path
    description: str | None = None
    model: str | None = None

    def to_dict(self, root: Path) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "path": str(self.path.relative_to(root)),
        }
        if self.description:
            data["description"] = self.description
        if self.model:
            data["model"] = self.model
        return data


@dataclass(frozen=True)
class ClaudeProjectAssets:
    root: Path
    claude_dir: Path
    agents_dir: Path
    skills_dir: Path
    agents: list[ClaudeAsset] = field(default_factory=list)
    skills: list[ClaudeAsset] = field(default_factory=list)

    @classmethod
    def discover(cls, paths: ProjectPaths) -> "ClaudeProjectAssets":
        agents = _discover_agents(paths.claude_agents_dir, paths.root)
        skills = _discover_skills(paths.claude_skills_dir, paths.root)
        return cls(
            root=paths.root,
            claude_dir=paths.claude_dir,
            agents_dir=paths.claude_agents_dir,
            skills_dir=paths.claude_skills_dir,
            agents=agents,
            skills=skills,
        )

    @property
    def exists(self) -> bool:
        return self.claude_dir.is_dir()

    def to_dict(self) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "path": str(self.claude_dir),
            "agents_dir": str(self.agents_dir),
            "skills_dir": str(self.skills_dir),
            "agents": [agent.to_dict(self.root) for agent in self.agents],
            "skills": [skill.to_dict(self.root) for skill in self.skills],
        }

    def summary(self) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "path": str(self.claude_dir),
            "agent_count": len(self.agents),
            "skill_count": len(self.skills),
            "agents": [agent.name for agent in self.agents],
            "skills": [skill.name for skill in self.skills],
        }


def _discover_agents(agents_dir: Path, root: Path) -> list[ClaudeAsset]:
    if not agents_dir.is_dir():
        return []
    assets = []
    for path in sorted(agents_dir.glob("*.md")):
        metadata = _read_front_matter(path)
        assets.append(
            ClaudeAsset(
                kind="agent",
                name=str(metadata.get("name") or path.stem),
                path=path.resolve(),
                description=_optional_str(metadata.get("description")),
                model=_optional_str(metadata.get("model")),
            )
        )
    return _inside_root_only(assets, root)


def _discover_skills(skills_dir: Path, root: Path) -> list[ClaudeAsset]:
    if not skills_dir.is_dir():
        return []
    assets = []
    for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        metadata = _read_front_matter(skill_md)
        assets.append(
            ClaudeAsset(
                kind="skill",
                name=str(metadata.get("name") or skill_dir.name),
                path=skill_md.resolve(),
                description=_optional_str(metadata.get("description")),
            )
        )
    return _inside_root_only(assets, root)


def _inside_root_only(assets: list[ClaudeAsset], root: Path) -> list[ClaudeAsset]:
    resolved_root = root.resolve()
    safe = []
    for asset in assets:
        try:
            asset.path.relative_to(resolved_root)
        except ValueError:
            continue
        safe.append(asset)
    return safe


def _read_front_matter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    metadata: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            metadata[key] = value
    return metadata


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
