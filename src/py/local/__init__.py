"""Local ComfyUI nodes and bundled model dependencies."""

from __future__ import annotations

import importlib
import sys


def _alias_dependency(public_name: str, package_name: str) -> None:
    if public_name not in sys.modules:
        sys.modules[public_name] = importlib.import_module(package_name)


_alias_dependency("local_groundingdino", f"{__name__}.local_groundingdino")
_alias_dependency("sam_hq", f"{__name__}.sam_hq")
