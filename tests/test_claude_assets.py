from pathlib import Path
import uuid

from bibl_windows.claude_assets import ClaudeProjectAssets
from bibl_windows.paths import ProjectPaths


def test_discovers_project_local_claude_agents_and_skills():
    project = _make_project_root()
    try:
        agents_dir = project / ".claude" / "agents"
        skills_dir = project / ".claude" / "skills" / "cut-editing"
        agents_dir.mkdir(parents=True)
        skills_dir.mkdir(parents=True)
        (agents_dir / "edit-director.md").write_text(
            "---\nname: edit-director\ndescription: Directs edits\nmodel: opus\n---\n# Body\n",
            encoding="utf-8",
        )
        (skills_dir / "SKILL.md").write_text(
            "---\nname: cut-editing\ndescription: Builds rough cuts\n---\n# Body\n",
            encoding="utf-8",
        )

        assets = ClaudeProjectAssets.discover(ProjectPaths(project))

        assert assets.exists
        assert [agent.name for agent in assets.agents] == ["edit-director"]
        assert assets.agents[0].model == "opus"
        assert [skill.name for skill in assets.skills] == ["cut-editing"]
        assert assets.summary()["agent_count"] == 1
        assert assets.summary()["skill_count"] == 1
    finally:
        _cleanup_project_root(project)


def test_missing_claude_directory_is_reported_as_empty():
    project = _make_project_root()
    try:
        assets = ClaudeProjectAssets.discover(ProjectPaths(project))

        assert not assets.exists
        assert assets.agents == []
        assert assets.skills == []
    finally:
        _cleanup_project_root(project)


def _make_project_root() -> Path:
    test_tmp = Path.cwd() / ".test_tmp_manual"
    test_tmp.mkdir(parents=True, exist_ok=True)
    root = test_tmp / f"claude_assets_{uuid.uuid4().hex}"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    return root


def _cleanup_stale_project_roots(test_tmp: Path) -> None:
    return None


def _cleanup_project_root(root: Path) -> None:
    return None


def _remove_empty_dir(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass
