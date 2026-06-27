from __future__ import annotations

import numpy as np
import torch
from PIL import Image, ImageFilter

from ._product_background_utils import _prepare_mask


class KSImageToWhiteBackground:
    """Apply mask(s) to the original image and place the foreground on a white background."""
    DESCRIPTION = "把输入图片中的遮罩区域保留在白底上，适合生成整张原图的白底版本。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "原始图片。输出会保持原图尺寸，只把遮罩外区域变成白色。"}),
                "masks": ("MASK", {"tooltip": "一个或多个前景遮罩。多个遮罩会合并为一个 union mask。"}),
            },
            "optional": {
                "edge_feather": (
                    "FLOAT",
                    {"default": 0.8, "min": 0.0, "max": 8.0, "step": 0.1, "tooltip": "遮罩边缘羽化半径。0 为硬边；数值越大边缘越柔和。"},
                ),
                "mask_threshold": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.05, "max": 0.95, "step": 0.05, "tooltip": "遮罩二值化阈值。降低保留更多边缘；提高会收紧主体。"},
                ),
                "min_mask_component_area": (
                    "INT",
                    {"default": 64, "min": 0, "max": 4096, "step": 16, "tooltip": "最小连通区域面积。0 不过滤；值越大越能去噪，也越可能丢失小细节。"},
                ),
                "mask_close_radius": (
                    "INT",
                    {"default": 4, "min": 0, "max": 32, "step": 1, "tooltip": "遮罩闭运算半径。用于连接小缝隙和平滑边缘；过大会扩张或粘连主体。"},
                ),
                "mask_expand_pixels": (
                    "INT",
                    {"default": 2, "min": 0, "max": 32, "step": 1, "tooltip": "遮罩向外扩展像素数。提高可避免边缘被裁掉，但可能保留少量背景。"},
                ),
                "fill_mask_holes": ("BOOLEAN", {"default": True, "tooltip": "是否填充遮罩内部空洞。开启适合实心商品；关闭适合保留镂空或透明结构。"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    RETURN_DESCRIPTIONS = (
        "与输入尺寸一致的白底图片。",
    )
    FUNCTION = "process"
    CATEGORY = "Kongshan/Local"

    def process(
        self,
        image,
        masks,
        edge_feather=0.8,
        mask_threshold=0.5,
        min_mask_component_area=64,
        mask_close_radius=4,
        mask_expand_pixels=2,
        fill_mask_holes=True,
    ):
        image_count = image.shape[0]
        mask_count = masks.shape[0]
        if image_count == 0 or mask_count == 0:
            raise RuntimeError("Empty image or masks list received.")

        processed_masks = [
            _prepare_mask(
                masks[index],
                mask_threshold,
                min_mask_component_area,
                mask_close_radius,
                mask_expand_pixels,
                fill_mask_holes,
            )
            for index in range(mask_count)
        ]

        source_tensor = image[0]
        source_array = np.clip(
            source_tensor.detach().cpu().numpy() * 255.0,
            0,
            255,
        ).astype(np.uint8)

        union_mask = np.zeros(source_array.shape[:2], dtype=np.uint8)
        for processed_mask in processed_masks:
            mask_np = np.asarray(processed_mask)
            if mask_np.shape != union_mask.shape:
                mask_np = np.asarray(
                    Image.fromarray(mask_np, mode="L").resize(
                        (union_mask.shape[1], union_mask.shape[0]),
                        Image.Resampling.NEAREST,
                    )
                )
            union_mask = np.maximum(union_mask, mask_np)

        full_mask = Image.fromarray(union_mask, mode="L")
        if edge_feather > 0:
            full_mask = full_mask.filter(ImageFilter.GaussianBlur(float(edge_feather)))

        full_canvas = Image.new(
            "RGB",
            (source_array.shape[1], source_array.shape[0]),
            "white",
        )
        full_canvas.paste(Image.fromarray(source_array, mode="RGB"), (0, 0), full_mask)

        original_white_background = torch.from_numpy(
            np.asarray(full_canvas).astype(np.float32) / 255.0
        )[None,]

        return (original_white_background,)


NODE_CLASS_MAPPINGS = {
    "KSImageToWhiteBackground": KSImageToWhiteBackground,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSImageToWhiteBackground": "获取输入图片白底图",
}
