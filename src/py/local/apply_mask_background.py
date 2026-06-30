from __future__ import annotations

from ._product_background_utils import (
    _apply_background,
    _image_tensor_to_uint8_rgb,
    _pil_to_tensor,
    _prepare_masks,
    _union_masks,
)


class KSApplyMaskBackground:
    DESCRIPTION = "根据输入遮罩保留前景，并输出白底或透明底的整图版本。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "原始图片。输出保持输入尺寸，只替换遮罩外区域。"}),
                "masks": ("MASK", {"tooltip": "一个或多个前景遮罩。多个遮罩会合并为一个 union mask。"}),
                "background_mode": (
                    ["white", "transparent"],
                    {"tooltip": "背景模式。white 输出白底 RGB 图；transparent 输出带 alpha 通道的透明底图。"},
                ),
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
        "与输入尺寸一致的白底或透明底图片。",
    )
    FUNCTION = "process"
    CATEGORY = "Kongshan/Local/Image"

    def process(
        self,
        image,
        masks,
        background_mode,
        edge_feather=0.8,
        mask_threshold=0.5,
        min_mask_component_area=64,
        mask_close_radius=4,
        mask_expand_pixels=2,
        fill_mask_holes=True,
    ):
        if image.shape[0] == 0 or masks.shape[0] == 0:
            raise RuntimeError("Empty image or masks list received.")

        processed_masks = _prepare_masks(
            masks,
            mask_threshold,
            min_mask_component_area,
            mask_close_radius,
            mask_expand_pixels,
            fill_mask_holes,
        )
        source_array = _image_tensor_to_uint8_rgb(image[0])
        union_mask = _union_masks(processed_masks, source_array.shape[:2])
        result = _apply_background(source_array, union_mask, background_mode, edge_feather)
        return (_pil_to_tensor(result),)


NODE_CLASS_MAPPINGS = {
    "KSApplyMaskBackground": KSApplyMaskBackground,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSApplyMaskBackground": "遮罩生成背景图",
}
