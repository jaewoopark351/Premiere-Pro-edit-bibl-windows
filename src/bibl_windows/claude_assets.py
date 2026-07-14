from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io_json import write_json
from .paths import ProjectPaths


@dataclass(frozen=True)
class ClaudeAsset:
    kind: str
    name: str
    path: Path
    description: str | None = None
    model: str | None = None
    body: str = ""

    def to_dict(self, root: Path, include_body: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "path": str(self.path.relative_to(root)),
        }
        if self.description:
            data["description"] = self.description
        if self.model:
            data["model"] = self.model
        if include_body:
            data["body"] = self.body
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

    def to_dict(self, include_body: bool = False) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "path": str(self.claude_dir),
            "agents_dir": str(self.agents_dir),
            "skills_dir": str(self.skills_dir),
            "agents": [agent.to_dict(self.root, include_body=include_body) for agent in self.agents],
            "skills": [skill.to_dict(self.root, include_body=include_body) for skill in self.skills],
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

    def workflow_map(self) -> dict[str, Any]:
        return {
            "workspace_dir": "output/_workspace/<output-name>/",
            "agents": [
                {"name": asset.name, "description": asset.description, "model": asset.model, "path": str(asset.path.relative_to(self.root))}
                for asset in self.agents
            ],
            "skills": [
                {"name": asset.name, "description": asset.description, "path": str(asset.path.relative_to(self.root))}
                for asset in self.skills
            ],
            "handoff_files": [
                "00_claude_context.md",
                "30_cut_result.md",
                "99_director_handoff.md",
            ],
        }


def _discover_agents(agents_dir: Path, root: Path) -> list[ClaudeAsset]:
    if not agents_dir.is_dir():
        return []
    assets = []
    for path in sorted(agents_dir.glob("*.md")):
        metadata, body = _read_front_matter_and_body(path)
        assets.append(
            ClaudeAsset(
                kind="agent",
                name=str(metadata.get("name") or path.stem),
                path=path.resolve(),
                description=_optional_str(metadata.get("description")),
                model=_optional_str(metadata.get("model")),
                body=body,
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
        metadata, body = _read_front_matter_and_body(skill_md)
        assets.append(
            ClaudeAsset(
                kind="skill",
                name=str(metadata.get("name") or skill_dir.name),
                path=skill_md.resolve(),
                description=_optional_str(metadata.get("description")),
                body=body,
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
    return _read_front_matter_and_body(path)[0]


def _read_front_matter_and_body(path: Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    metadata: dict[str, str] = {}
    body_start = 0
    for idx, line in enumerate(lines[1:], 1):
        stripped = line.strip()
        if stripped == "---":
            body_start = idx + 1
            break
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            metadata[key] = value
    body = "\n".join(lines[body_start:]).strip() if body_start else ""
    return metadata, body


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def write_claude_workspace(
    assets: ClaudeProjectAssets,
    workspace_dir: Path,
    *,
    input_path: str,
    preset: str,
    mode: str,
    command: list[str],
    files: dict[str, str],
    metadata: dict[str, Any],
) -> dict[str, Path]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    context_json = workspace_dir / "00_claude_context.json"
    context_md = workspace_dir / "00_claude_context.md"
    cut_result_md = workspace_dir / "30_cut_result.md"
    handoff_md = workspace_dir / "99_director_handoff.md"

    payload = {
        "input_path": input_path,
        "preset": preset,
        "mode": mode,
        "command": command,
        "files": files,
        "metadata": metadata,
        "claude": assets.to_dict(include_body=True),
        "workflow": assets.workflow_map(),
    }
    write_json(context_json, payload)
    context_md.write_text(render_context_markdown(payload), encoding="utf-8", newline="\n")
    cut_result_md.write_text(render_cut_result_markdown(payload), encoding="utf-8", newline="\n")
    handoff_md.write_text(render_handoff_markdown(payload), encoding="utf-8", newline="\n")
    return {
        "claude_context_json": context_json,
        "claude_context_md": context_md,
        "claude_cut_result_md": cut_result_md,
        "claude_handoff_md": handoff_md,
    }


def render_context_markdown(payload: dict[str, Any]) -> str:
    claude = payload["claude"]
    files = payload["files"]
    metadata = payload["metadata"]
    lines = [
        "# Claude Editing Context",
        "",
        "이 파일은 Windows 포팅 파이프라인이 `.claude/agents`와 `.claude/skills`를 실제 실행 결과에 연결하기 위해 자동 생성한 Claude Code용 브리핑입니다.",
        "",
        "## Run",
        "",
        f"- input: `{payload['input_path']}`",
        f"- preset: `{payload['preset']}`",
        f"- mode: `{payload['mode']}`",
        f"- command: `{' '.join(payload.get('command') or [])}`",
        "",
        "## Primary Artifacts",
        "",
    ]
    for key in (
        "transcript_json",
        "cut_candidates_json",
        "xml",
        "srt",
        "vtt",
        "ass",
        "emphasis_ass",
        "clean_wav",
        "report",
        "keep_ranges_json",
        "cut_review_json",
        "edit_diff_md",
    ):
        if key in files:
            lines.append(f"- {key}: `{files[key]}`")
    lines += [
        "",
        "## Agent Team",
        "",
    ]
    for agent in claude.get("agents", []):
        desc = agent.get("description") or ""
        model = agent.get("model") or "default"
        lines.append(f"- `{agent['name']}` ({model}): {desc}")
    lines += [
        "",
        "## Skills",
        "",
    ]
    for skill in claude.get("skills", []):
        lines.append(f"- `{skill['name']}`: {skill.get('description') or ''}")
    lines += [
        "",
        "## Next Claude Actions",
        "",
        "1. `30_cut_result.md`를 기준으로 컷 후보, 제거율, choppy 구간을 검수한다.",
        "2. 리서치가 필요하면 transcript export와 SRT를 읽고 `10_research.md`와 선택적 `_content_cuts.json`을 만든다.",
        "3. 자막 검수가 필요하면 SRT/VTT/ASS를 실제 타임코드 기준으로 점검하고 `40_subtitle_notes.md`를 만든다.",
        "4. Premiere 검증은 자동 완료로 표시하지 말고 `99_director_handoff.md`에 수동 확인 항목으로 남긴다.",
        "",
        "## Diagnostics",
        "",
        f"- stt: `{metadata.get('stt', {})}`",
        f"- cut_candidates: `{metadata.get('cut_candidates', {})}`",
        f"- audio_analysis keys: `{list((metadata.get('audio_analysis') or {}).keys())}`",
        "",
    ]
    return "\n".join(lines)


def render_cut_result_markdown(payload: dict[str, Any]) -> str:
    files = payload["files"]
    metadata = payload["metadata"]
    stt = metadata.get("stt", {})
    cut_candidates = metadata.get("cut_candidates", {})
    output = metadata.get("output", {})
    lines = [
        "# Cut Result",
        "",
        "## Summary",
        "",
        f"- preset: `{payload['preset']}`",
        f"- input: `{payload['input_path']}`",
        f"- transcription_limit_seconds: `{output.get('transcription_limit_seconds')}`",
        f"- stt_backend: `{stt.get('backend')}`",
        f"- stt_device: `{stt.get('device')}`",
        f"- stt_words: `{stt.get('words')}`",
        f"- cut_candidate_count: `{cut_candidates.get('count')}`",
        "",
        "## Files To Inspect",
        "",
    ]
    for key, value in files.items():
        lines.append(f"- {key}: `{value}`")
    lines += [
        "",
        "## Review Notes For Claude",
        "",
        "- `cut_review_json`과 `report`가 있으면 auto-delete와 review-only 후보를 분리해서 본다.",
        "- `keep_ranges_json`에서 speech boundary protection과 choppy 구간을 확인한다.",
        "- `xml`은 Premiere Pro 수동 import 전까지 자동 검증 완료라고 말하지 않는다.",
        "- 필요하면 edit-director 기준으로 보수/표준/공격 프리셋 재실행 여부를 판단한다.",
        "",
    ]
    return "\n".join(lines)


def render_handoff_markdown(payload: dict[str, Any]) -> str:
    files = payload["files"]
    lines = [
        "# Director Handoff Draft",
        "",
        "이 문서는 자동 초안입니다. Claude Code의 edit-director가 실제 SRT/XML/report를 읽고 보완해야 합니다.",
        "",
        "## Import In Premiere",
        "",
    ]
    if files.get("xml"):
        lines.append(f"- FCP7 XML: `{files['xml']}`")
    if files.get("srt"):
        lines.append(f"- SRT: `{files['srt']}`")
    if files.get("clean_wav"):
        lines.append(f"- Clean WAV linked by XML: `{files['clean_wav']}`")
    lines += [
        "",
        "## Manual Verification Required",
        "",
        "- Premiere Pro에서 XML import 후 media offline 여부 확인",
        "- SRT/VTT/ASS 자막 위치와 타임코드 확인",
        "- cut 지점의 말끝/단어 중간 잘림 표본 확인",
        "- 긴 영상이면 제거율과 choppy 구간을 report 기준으로 검수",
        "",
        "## Claude Follow-up Slots",
        "",
        "- content-researcher: 핵심 메시지, 챕터, 내용 컷 후보",
        "- video-planner: 인트로 훅, B-roll/강조 마커, 프리셋 재추천",
        "- subtitle-editor: 고유명사/줄 길이/빈 구간 검수",
        "- shorts-producer: 요청 시 쇼츠 구간과 XML/MP4 생성",
        "",
    ]
    return "\n".join(lines)
