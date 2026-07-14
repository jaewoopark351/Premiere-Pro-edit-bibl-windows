from pathlib import Path
import uuid

from bibl_windows.claude_assets import ClaudeProjectAssets, write_claude_workspace
from bibl_windows.io_json import read_json
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
        assert "Body" in assets.agents[0].body
        assert [skill.name for skill in assets.skills] == ["cut-editing"]
        assert "Body" in assets.skills[0].body
        assert assets.summary()["agent_count"] == 1
        assert assets.summary()["skill_count"] == 1
        assert "body" not in assets.to_dict()["agents"][0]
        assert "body" in assets.to_dict(include_body=True)["agents"][0]
        assert assets.workflow_map()["handoff_files"] == [
            "00_claude_context.md",
            "30_cut_result.md",
            "99_director_handoff.md",
        ]
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


def test_write_claude_workspace_includes_asset_bodies_and_handoff_files():
    project = _make_project_root()
    try:
        agents_dir = project / ".claude" / "agents"
        skills_dir = project / ".claude" / "skills" / "video-edit-pipeline"
        agents_dir.mkdir(parents=True)
        skills_dir.mkdir(parents=True)
        (agents_dir / "cut-editor.md").write_text(
            "---\nname: cut-editor\ndescription: Runs cuts\nmodel: opus\n---\n# Agent Body\n",
            encoding="utf-8",
        )
        (skills_dir / "SKILL.md").write_text(
            "---\nname: video-edit-pipeline\ndescription: Runs the whole flow\n---\n# Skill Body\n",
            encoding="utf-8",
        )
        assets = ClaudeProjectAssets.discover(ProjectPaths(project))
        workspace = project / "output" / "_workspace" / "sample"

        files = write_claude_workspace(
            assets,
            workspace,
            input_path="input/sample.mp4",
            preset="standard",
            mode="full",
            command=["run", "input/sample.mp4"],
            files={"xml": "output/sample_cut.xml", "srt": "output/sample_cut.srt"},
            metadata={"stt": {"backend": "mock"}, "cut_candidates": {"count": 2}},
        )

        payload = read_json(files["claude_context_json"])
        assert payload["claude"]["agents"][0]["body"].startswith("# Agent Body")
        assert payload["claude"]["skills"][0]["body"].startswith("# Skill Body")
        assert files["claude_context_md"].exists()
        assert files["claude_cut_result_md"].exists()
        assert files["claude_handoff_md"].exists()
        assert "cut-editor" in files["claude_context_md"].read_text(encoding="utf-8")
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
