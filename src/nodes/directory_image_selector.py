from __future__ import annotations

import re
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageOps

# Import to register API routes for selection
from . import _image_files_utils


def natural_sort_key(path: Path) -> list:
    """Helper function to split path name into parts of numbers and non-numbers for natural sorting."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", path.name)]


class KSDirectoryImageSelector:
    DESCRIPTION = "从指定目录中过滤出所有图片，并根据索引加载其中一张，输出图片、遮罩、绝对路径及文件名。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "要读取的图片目录路径。",
                    },
                ),
                "index": (
                    [""],
                    {
                        "default": "",
                        "tooltip": "要加载的源图片名。下拉框会自动读取目录中的图片文件。",
                    },
                ),
                "pattern": (
                    "STRING",
                    {
                        "default": "*.png, *.jpg, *.jpeg, *.webp, *.bmp",
                        "tooltip": "过滤文件后缀名，多个以逗号或分号分隔。留空时匹配所有支持的图片格式。",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING", "INT")
    RETURN_NAMES = ("image", "mask", "source_image_path", "filename", "total_images")
    RETURN_DESCRIPTIONS = (
        "加载后的 RGB 图片张量。",
        "由透明通道生成的遮罩；无透明通道时输出全黑遮罩。",
        "选中图片的绝对路径，可连接到保存节点用于自动定位输出目录。",
        "选中图片的文件名（含后缀）。",
        "目录中匹配到的图片总数。",
    )
    FUNCTION = "load_image_from_dir"
    CATEGORY = "Kongshan/Local"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    def load_image_from_dir(self, directory_path, index, pattern):
        dir_path = Path(directory_path.strip()).expanduser()
        if not dir_path.is_dir():
            raise RuntimeError(f"Directory not found: {dir_path}")

        # Parse pattern
        extensions = []
        if pattern.strip():
            parts = re.split(r"[,;]+", pattern)
            for p in parts:
                p_clean = p.strip().lower()
                if p_clean:
                    p_clean = p_clean.lstrip("*").lstrip(".")
                    if p_clean:
                        extensions.append("." + p_clean)
        if not extensions:
            extensions = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"]

        # List files sorted by natural sort order by name
        files = sorted(
            [
                p for p in dir_path.iterdir()
                if p.is_file() and p.suffix.lower() in extensions
            ],
            key=natural_sort_key
        )

        total = len(files)
        if total == 0:
            raise RuntimeError(f"No matching images found in directory: {dir_path} with extensions {extensions}")

        index_text = str(index).strip()
        if not index_text:
            selected_file = files[0]
        else:
            name_text = re.split(r"[\\/]", index_text)[-1].lower()
            selected_file = next(
                (path for path in files if path.name.lower() == name_text),
                None,
            )
        if selected_file is None:
            available = ", ".join(path.name for path in files[:20])
            raise RuntimeError(
                f"Image name not found in directory: {index_text}. "
                f"Available examples: {available}"
            )

        image = Image.open(selected_file)
        image = ImageOps.exif_transpose(image)
        if image.mode == "I":
            image = image.point(lambda value: value * (1 / 255))

        if "A" in image.getbands():
            alpha = np.asarray(image.getchannel("A")).astype(np.float32) / 255.0
            mask = torch.from_numpy(1.0 - alpha)[None,]
        else:
            mask = torch.zeros((1, image.height, image.width), dtype=torch.float32)

        image = image.convert("RGB")
        image_array = np.asarray(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array)[None,]

        return (image_tensor, mask, str(selected_file.resolve()), selected_file.name, total)


NODE_CLASS_MAPPINGS = {
    "KSDirectoryImageSelector": KSDirectoryImageSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSDirectoryImageSelector": "目录图片选择加载器",
}
