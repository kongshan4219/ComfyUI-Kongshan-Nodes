from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _save_tensor_png(image, path: Path) -> str:
    tensor = image[0]
    array = np.clip(tensor.detach().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(array, mode="RGB").save(path, format="PNG")
    return str(path)


def _load_tensor(path: Path):
    with Image.open(path) as image:
        array = np.asarray(image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(array)[None,]


def _image_files(directory: Path) -> Iterable[Path]:
    if not directory.is_dir():
        return []
    return (
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _path_candidates(text: str) -> Iterable[Path]:
    pattern = re.compile(
        r"""(?:"([^"]+\.(?:png|jpg|jpeg|webp|bmp|tif|tiff))"|'([^']+\.(?:png|jpg|jpeg|webp|bmp|tif|tiff))'|(\S+\.(?:png|jpg|jpeg|webp|bmp|tif|tiff)))""",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        raw = next(group for group in match.groups() if group)
        yield Path(raw).expanduser()


def _resolve_image_path(path: Path, working_directory: Path) -> Path | None:
    candidates = [path] if path.is_absolute() else [working_directory / path, Path.cwd() / path]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and resolved.suffix.lower() in IMAGE_EXTENSIONS:
            return resolved
    return None


def _latest_image(directory: Path) -> Path | None:
    existing = [path for path in _image_files(directory)]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime_ns)
