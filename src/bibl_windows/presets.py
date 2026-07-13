from __future__ import annotations

import json
from pathlib import Path


def load_preset(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)

