from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io_json import write_json


@dataclass
class ArtifactManifest:
    media_path: str
    preset: str
    mode: str
    command: list[str]
    limit_seconds: float | None = None
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, path: Path | None) -> None:
        if path is not None:
            self.files[key] = str(path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "media_path": self.media_path,
            "preset": self.preset,
            "mode": self.mode,
            "command": self.command,
            "limit_seconds": self.limit_seconds,
            "files": self.files,
            "metadata": self.metadata,
        }

    def write(self, path: Path) -> None:
        write_json(path, self.to_dict())

