from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .claude_assets import ClaudeProjectAssets
from .ffmpeg_tools import ToolInfo, tool_info
from .paths import ProjectPaths
from .presets import load_preset


class RuntimeErrorWithHint(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeTools:
    ffmpeg: ToolInfo
    ffprobe: ToolInfo

    @classmethod
    def discover(cls) -> "RuntimeTools":
        return cls(ffmpeg=tool_info("ffmpeg.exe"), ffprobe=tool_info("ffprobe.exe"))

    def require_media_tools(self) -> tuple[Path, Path]:
        if not self.ffmpeg.path:
            raise RuntimeErrorWithHint("ffmpeg.exe was not found on PATH.")
        if not self.ffprobe.path:
            raise RuntimeErrorWithHint("ffprobe.exe was not found on PATH.")
        return self.ffmpeg.path, self.ffprobe.path


@dataclass(frozen=True)
class RuntimeContext:
    paths: ProjectPaths
    tools: RuntimeTools
    claude: ClaudeProjectAssets

    @classmethod
    def discover(cls) -> "RuntimeContext":
        paths = ProjectPaths.discover()
        return cls(paths=paths, tools=RuntimeTools.discover(), claude=ClaudeProjectAssets.discover(paths))

    def load_preset(self, name: str) -> dict:
        return load_preset(self.paths.root / "config" / f"{name}.json")
