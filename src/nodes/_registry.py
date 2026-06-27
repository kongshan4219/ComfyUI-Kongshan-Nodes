from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType


def _merge(modules: list[ModuleType]) -> tuple[dict[str, type], dict[str, str]]:
    classes: dict[str, type] = {}
    display_names: dict[str, str] = {}

    for module in modules:
        module_classes = getattr(module, "NODE_CLASS_MAPPINGS", {})
        duplicates = classes.keys() & module_classes.keys()
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise RuntimeError(f"Duplicate ComfyUI node names: {names}")
        classes.update(module_classes)
        display_names.update(getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {}))

    return classes, display_names


def collect_nodes() -> tuple[dict[str, type], dict[str, str]]:
    """Load node modules from the flat top-level nodes package."""
    nodes_package = importlib.import_module("nodes")
    modules = [
        importlib.import_module(item.name)
        for item in sorted(
            pkgutil.walk_packages(
                nodes_package.__path__,
                prefix=f"{nodes_package.__name__}.",
            ),
            key=lambda item: item.name,
        )
        if not item.name.rsplit(".", 1)[-1].startswith("_")
    ]
    return _merge(modules)
