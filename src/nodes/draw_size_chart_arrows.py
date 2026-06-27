from __future__ import annotations

import math

import numpy as np
import torch
from PIL import Image, ImageColor, ImageDraw


class KSDrawSizeChartArrows:
    """Draw size-chart guide lines and arrow heads in one raster pass."""

    DESCRIPTION = "Draw integrated product size-chart arrow lines from a detected product bounding box."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Base image to draw on."}),
                "bbox_x": ("INT", {"forceInput": True}),
                "bbox_y": ("INT", {"forceInput": True}),
                "bbox_width": ("INT", {"forceInput": True}),
                "bbox_height": ("INT", {"forceInput": True}),
            },
            "optional": {
                "color": ("STRING", {"default": "#111111"}),
                "stroke_width": ("INT", {"default": 4, "min": 1, "max": 32, "step": 1}),
                "arrow_head_size": ("INT", {"default": 14, "min": 4, "max": 96, "step": 1}),
                "horizontal_gap": ("INT", {"default": 24, "min": -512, "max": 1024, "step": 1}),
                "vertical_gap": ("INT", {"default": 24, "min": -512, "max": 1024, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "draw"
    CATEGORY = "Kongshan/Local"

    @staticmethod
    def _normalize_color(color):
        if not isinstance(color, str):
            return "#111111"
        color = color.strip()
        try:
            ImageColor.getrgb(color)
        except ValueError:
            return "#111111"
        return color

    def draw(
        self,
        image,
        bbox_x,
        bbox_y,
        bbox_width,
        bbox_height,
        color="#111111",
        stroke_width=4,
        arrow_head_size=14,
        horizontal_gap=24,
        vertical_gap=24,
    ):
        image_count = image.shape[0]
        if image_count == 0:
            raise RuntimeError("Empty image list received.")

        color = self._normalize_color(color)
        output_images = []
        for tensor in image:
            array = np.clip(tensor.detach().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
            canvas = Image.fromarray(array, mode="RGB")
            drawer = ImageDraw.Draw(canvas)

            x = int(round(bbox_x))
            y = int(round(bbox_y))
            width = int(round(bbox_width))
            height = int(round(bbox_height))
            stroke = max(1, int(stroke_width))
            head = max(stroke + 2, int(arrow_head_size))
            half = max(2, int(math.ceil(head * 0.45)))

            right_x = x + width + int(horizontal_gap)
            bottom_y = y + height + int(vertical_gap)

            drawer.line((x, bottom_y, right_x, bottom_y), fill=color, width=stroke)
            drawer.polygon(
                (
                    (x, bottom_y),
                    (x + head, bottom_y - half),
                    (x + head, bottom_y + half),
                ),
                fill=color,
            )

            drawer.line((right_x, y, right_x, bottom_y), fill=color, width=stroke)
            drawer.polygon(
                (
                    (right_x, y),
                    (right_x - half, y + head),
                    (right_x + half, y + head),
                ),
                fill=color,
            )

            output_images.append(
                torch.from_numpy(np.asarray(canvas).astype(np.float32) / 255.0)[None,]
            )

        return (torch.cat(output_images, dim=0),)


NODE_CLASS_MAPPINGS = {
    "KSDrawSizeChartArrows": KSDrawSizeChartArrows,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSDrawSizeChartArrows": "Draw Size Chart Arrows",
}
