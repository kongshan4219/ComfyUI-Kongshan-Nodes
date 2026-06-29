from __future__ import annotations

from pathlib import Path

# Import to register API routes for selection
from . import _image_files_utils
from ._load_image_utils import image_file_hash, load_image_like_comfy, resolve_image_path


class KSLoadImageWithPath:
    DESCRIPTION = "从磁盘绝对路径或用户目录路径加载图片，同时输出原始路径，便于后续按源文件位置保存结果。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "输入图片路径。支持 png、jpg、jpeg、webp、bmp、tif、tiff 等 PIL 可读取格式；按钮可打开系统文件选择器。",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "source_image_path")
    RETURN_DESCRIPTIONS = (
        "加载后的 RGB 图片张量。",
        "由透明通道生成的遮罩；无透明通道时输出全黑遮罩。",
        "解析后的源图片绝对路径，可连接到保存节点用于自动定位输出目录。",
    )
    FUNCTION = "load_image_with_path"
    CATEGORY = "Kongshan/Local"

    @classmethod
    def IS_CHANGED(cls, image_path):
        source = resolve_image_path(image_path)
        if not source.is_file():
            return ""
        return image_file_hash(source)

    @classmethod
    def VALIDATE_INPUTS(cls, image_path):
        source = resolve_image_path(image_path)
        if not source.is_file():
            return f"Invalid image file: {image_path}"
        return True

    def load_image_with_path(self, image_path):
        source = resolve_image_path(image_path)
        if not source.is_file():
            raise RuntimeError(f"Source image not found: {source}")

        image_tensor, mask = load_image_like_comfy(source)
        return (image_tensor, mask, str(source.resolve()))


NODE_CLASS_MAPPINGS = {
    "KSLoadImageWithPath": KSLoadImageWithPath,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSLoadImageWithPath": "从原始路径加载图片",
}
