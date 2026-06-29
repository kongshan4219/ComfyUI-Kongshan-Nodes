from __future__ import annotations

import re
from pathlib import Path
import numpy as np
import torch
from PIL import Image


class KSDirectorySaveImages:
    DESCRIPTION = "把一批图片保存到自定义目录；未指定目录时可根据源图片路径自动创建 white_background 子目录。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "要保存的图片批次。批次中每张图都会按递增编号保存。"}),
                "output_directory": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "输出目录。填写后直接保存到该目录；留空且连接 source_image_path 时保存到源图片旁的 white_background 子目录。",
                    },
                ),
                "filename_prefix": ("STRING", {"default": "white_background", "tooltip": "文件名前缀。节点会清理非法字符，并生成 prefix_00001.ext 形式的递增文件名。"}),
                "image_format": (["png", "jpg", "webp"], {"tooltip": "保存格式。png 无损适合透明/后处理；jpg 体积小但有损；webp 体积更小且适合网页。"}),
            },
            "optional": {
                "source_image_path": ("STRING", {"forceInput": True, "tooltip": "源图片路径。output_directory 留空时用它推导输出目录；连接“从原始路径加载图片”的 source_image_path 最方便。"}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("saved_paths", "saved_count")
    RETURN_DESCRIPTIONS = (
        "所有已保存 file 路径，以换行分隔。",
        "实际保存的图片数量。",
    )
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Kongshan/Local"

    def save(self, images, output_directory, filename_prefix, image_format, source_image_path=""):
        if output_directory.strip():
            target = Path(output_directory.strip()).expanduser()
        elif source_image_path.strip():
            source = Path(source_image_path.strip()).expanduser()
            if not source.is_file():
                raise RuntimeError(f"Source image not found: {source}")
            target = source.parent / "white_background"
        else:
            raise RuntimeError(
                "Connect source_image_path or select a custom output directory."
            )
        target.mkdir(parents=True, exist_ok=True)
        if not target.is_dir():
            raise RuntimeError(f"Output path is not a directory: {target}")

        prefix = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename_prefix.strip()).strip(" .")
        if not prefix:
            prefix = "white_background"
        extension = image_format.lower()
        existing_numbers = []
        pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)[.]{re.escape(extension)}$", re.I)
        for path in target.iterdir():
            match = pattern.match(path.name) if path.is_file() else None
            if match:
                existing_numbers.append(int(match.group(1)))
        next_number = max(existing_numbers, default=0) + 1

        saved_paths = []
        for offset, tensor in enumerate(images):
            array = np.clip(tensor.detach().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
            if array.ndim != 3 or array.shape[2] not in (3, 4):
                raise RuntimeError(f"Unsupported image tensor shape for saving: {array.shape}")
            image_mode = "RGBA" if array.shape[2] == 4 else "RGB"
            image = Image.fromarray(array, mode=image_mode)
            path = target / f"{prefix}_{next_number + offset:05d}.{extension}"
            if extension == "jpg":
                image.convert("RGB").save(path, format="JPEG", quality=95, subsampling=0)
            elif extension == "webp":
                image.save(path, format="WEBP", quality=95, method=6)
            else:
                image.save(path, format="PNG", compress_level=4)
            saved_paths.append(str(path))

        return "\n".join(saved_paths), len(saved_paths)


NODE_CLASS_MAPPINGS = {
    "KSDirectorySaveImages": KSDirectorySaveImages,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSDirectorySaveImages": "保存图片到自定义目录",
}
