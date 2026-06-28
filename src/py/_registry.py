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


def _load_node_modules(package_name: str) -> list[ModuleType]:
    package = importlib.import_module(package_name)
    return [
        importlib.import_module(item.name)
        for item in sorted(
            pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."),
            key=lambda item: item.name,
        )
        if not item.ispkg and not item.name.rsplit(".", 1)[-1].startswith("_")
    ]


def collect_nodes() -> tuple[dict[str, type], dict[str, str]]:
    """Load node modules from the api, cli, and local node packages."""
    modules: list[ModuleType] = []
    for package_name in ("py.api", "py.cli", "py.local"):
        modules.extend(_load_node_modules(package_name))
    return _merge(modules)
