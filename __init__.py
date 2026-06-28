from __future__ import annotations

import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from py.api import gemini_models as _gemini_models  # Register HTTP routes.
from py._registry import collect_nodes


NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = collect_nodes()
WEB_DIRECTORY = str(Path(__file__).resolve().parent / "web")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
