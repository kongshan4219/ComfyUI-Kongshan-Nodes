from __future__ import annotations

import json

import torch
from PIL import Image

from ._product_background_utils import (
    _apply_background,
    _collect_mask_instances,
    _feather_mask,
    _image_tensor_to_uint8_rgb,
    _pil_to_tensor,
    _prepare_masks,
    _resize_mask_to_shape,
    _union_masks,
)


class KSProductsToBackground:
    DESCRIPTION = "把分割出的多个商品实例裁切、居中并输出白底或透明底商品图。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "segmented_images": ("IMAGE", {"tooltip": "分割后的商品实例图片批次，通常来自 SAM 分割节点。未连接 original_image 时会作为裁切来源。"}),
                "masks": ("MASK", {"tooltip": "每个商品实例对应的遮罩批次。遮罩越准确，裁切边缘越干净。"}),
                "background_mode": (
                    ["white", "transparent"],
                    {"tooltip": "背景模式。white 输出白底商品图；transparent 输出带 alpha 通道的透明底商品图。"},
                ),
                "output_size": (
                    "INT",
                    {"default": 1024, "min": 256, "max": 4096, "step": 64, "tooltip": "每个输出商品图的正方形边长。值越大细节越多但文件更大、处理更慢。"},
                ),
                "margin_percent": (
                    "FLOAT",
                    {"default": 10.0, "min": 0.0, "max": 40.0, "step": 0.5, "tooltip": "商品四周留边比例。0 会尽量铺满画布；数值越大，商品越小、留边越多。"},
                ),
                "edge_feather": (
                    "FLOAT",
                    {"default": 0.8, "min": 0.0, "max": 8.0, "step": 0.1, "tooltip": "遮罩边缘羽化半径。0 保持硬边；数值越大边缘越柔和。"},
                ),
                "sort_order": (["top_to_bottom", "left_to_right"], {"tooltip": "输出排序。top_to_bottom 按从上到下、再从左到右编号；left_to_right 按从左到右、再从上到下编号。"}),
            },
            "optional": {
                "original_image": ("IMAGE", {"tooltip": "原始完整图片。连接后会从原图裁切商品，通常比使用分割图保留更多真实纹理和颜色。"}),
                "mask_threshold": (
                    "FLOAT",
                    {"default": 0.5, "min": 0.05, "max": 0.95, "step": 0.05, "tooltip": "遮罩二值化阈值。降低会保留更多边缘/半透明区域；提高会收紧主体范围。"},
                ),
                "min_mask_component_area": (
                    "INT",
                    {"default": 64, "min": 0, "max": 4096, "step": 16, "tooltip": "最小连通区域面积。0 不过滤；值越大越容易去掉小噪点，也可能误删小商品部件。"},
                ),
                "mask_close_radius": (
                    "INT",
                    {"default": 4, "min": 0, "max": 32, "step": 1, "tooltip": "遮罩闭运算半径。0 不处理；值越大越能连接小缝隙、平滑边缘，但可能粘连相邻物体。"},
                ),
                "mask_expand_pixels": (
                    "INT",
                    {"default": 2, "min": 0, "max": 32, "step": 1, "tooltip": "遮罩向外扩展像素数。0 不扩展；值越大越能避免裁掉边缘，也越可能带入背景。"},
                ),
                "fill_mask_holes": ("BOOLEAN", {"default": True, "tooltip": "是否填充遮罩内部空洞。开启适合实心商品；关闭适合保留真实镂空区域。"}),
                "prefer_grouped_product_masks": ("BOOLEAN", {"default": True, "tooltip": "多个小部件被一个大遮罩覆盖时，优先保留完整商品大遮罩。关闭后会保留更多单独部件。"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "INT", "IMAGE")
    RETURN_NAMES = (
        "products",
        "manifest",
        "product_count",
        "original_background",
    )
    RETURN_DESCRIPTIONS = (
        "逐个商品裁切、缩放、居中后的白底或透明底图批次。",
        "JSON 清单，记录商品数量、输出序号、源实例索引和原图裁切框。",
        "最终输出的商品图数量。",
        "把所有检测到的商品一起保留在原始画幅中的白底或透明底整图。",
    )
    FUNCTION = "process"
    CATEGORY = "Kongshan/Local/Product"

    def process(
        self,
        segmented_images,
        masks,
        background_mode,
        output_size,
        margin_percent,
        edge_feather,
        sort_order,
        original_image=None,
        mask_threshold=0.5,
        min_mask_component_area=64,
        mask_close_radius=4,
        mask_expand_pixels=2,
        fill_mask_holes=True,
        prefer_grouped_product_masks=True,
    ):
        count = min(segmented_images.shape[0], masks.shape[0])
        if count == 0:
            raise RuntimeError("No product instances were received from the segmentation node.")

        processed_masks = _prepare_masks(
            masks[:count],
            mask_threshold,
            min_mask_component_area,
            mask_close_radius,
            mask_expand_pixels,
            fill_mask_holes,
        )
        instances = _collect_mask_instances(processed_masks, prefer_grouped_product_masks)
        if not instances:
            raise RuntimeError(
                "The detector returned instances, but all masks were empty. Lower the GroundingDINO threshold or revise the prompt."
            )

        if sort_order == "left_to_right":
            instances.sort(key=lambda item: (item["x1"], item["y1"]))
        else:
            instances.sort(key=lambda item: (item["y1"], item["x1"]))

        final_images = []
        manifest_items = []
        target_size = int(output_size)
        margin = max(0, round(target_size * float(margin_percent) / 100.0))
        available = max(1, target_size - margin * 2)

        for output_index, item in enumerate(instances, start=1):
            source_index = item["source_index"]
            source_tensor = original_image[0] if original_image is not None else segmented_images[source_index]
            source_rgb = _image_tensor_to_uint8_rgb(source_tensor)
            mask = _resize_mask_to_shape(processed_masks[source_index], source_rgb.shape[:2])

            x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
            crop_rgb = Image.fromarray(source_rgb[y1:y2, x1:x2], mode="RGB")
            crop_mask = Image.fromarray(mask[y1:y2, x1:x2], mode="L")
            scale = min(available / crop_rgb.width, available / crop_rgb.height)
            new_width = max(1, round(crop_rgb.width * scale))
            new_height = max(1, round(crop_rgb.height * scale))
            crop_rgb = crop_rgb.resize((new_width, new_height), Image.Resampling.LANCZOS)
            crop_mask = crop_mask.resize((new_width, new_height), Image.Resampling.LANCZOS)
            crop_mask = _feather_mask(crop_mask, edge_feather)

            paste_x = (target_size - new_width) // 2
            paste_y = (target_size - new_height) // 2
            if background_mode == "transparent":
                crop_rgba = crop_rgb.convert("RGBA")
                crop_rgba.putalpha(crop_mask)
                canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
                canvas.alpha_composite(crop_rgba, (paste_x, paste_y))
            else:
                canvas = Image.new("RGB", (target_size, target_size), "white")
                canvas.paste(crop_rgb, (paste_x, paste_y), crop_mask)

            final_images.append(_pil_to_tensor(canvas))
            manifest_items.append(
                {
                    "output_index": output_index,
                    "source_instance": source_index,
                    "source_box": [x1, y1, x2, y2],
                    "background_mode": background_mode,
                }
            )

        source_tensor = original_image[0] if original_image is not None else segmented_images[0]
        source_array = _image_tensor_to_uint8_rgb(source_tensor)
        union_mask = _union_masks(
            [processed_masks[item["source_index"]] for item in instances],
            source_array.shape[:2],
        )
        original_background = _pil_to_tensor(
            _apply_background(source_array, union_mask, background_mode, edge_feather)
        )

        manifest = json.dumps(
            {
                "background_mode": background_mode,
                "product_count": len(final_images),
                "products": manifest_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        return (
            torch.cat(final_images, dim=0),
            manifest,
            len(final_images),
            original_background,
        )


NODE_CLASS_MAPPINGS = {
    "KSProductsToBackground": KSProductsToBackground,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSProductsToBackground": "实例商品裁切为背景图",
}
