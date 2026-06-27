from __future__ import annotations

import numpy as np
from PIL import Image

from ._sam_grounding_dino_utils import groundingdino_predict


class GroundingDinoDetect:
    DESCRIPTION = "使用 GroundingDINO 根据文本提示在图片中检测目标框，并输出检测框列表和数量。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "grounding_dino_model": ("GROUNDING_DINO_MODEL", {"tooltip": "已加载的 GroundingDINO 模型。"}),
                "image": ("IMAGE", {"tooltip": "待检测图片批次。每张图都会按相同 prompt 检测目标框。"}),
                "prompt": ("STRING", {"tooltip": "检测目标文本，例如 product、bottle、shoe。越具体越少误检，但过窄可能漏检。"}),
                "threshold": (
                    "FLOAT",
                    {"default": 0.3, "min": 0, "max": 1.0, "step": 0.01, "tooltip": "检测置信度阈值。降低会找到更多框但误检增加；提高会更严格但可能漏掉目标。"},
                ),
            }
        }
    CATEGORY = "Kongshan/Local"
    FUNCTION = "main"
    RETURN_TYPES = ("KS_DINO_BOXES", "INT")
    RETURN_NAMES = ("boxes", "box_count")
    RETURN_DESCRIPTIONS = (
        "每张输入图对应的检测框列表，可连接到 SAM 按框分割节点。",
        "所有输入图检测到的框总数。0 表示没有目标通过阈值。",
    )

    def main(self, grounding_dino_model, image, prompt, threshold):
        box_batches = []
        total_boxes = 0
        for item in image:
            item_image = Image.fromarray(
                np.clip(255. * item.cpu().numpy(), 0, 255).astype(np.uint8)
            ).convert("RGBA")
            boxes = groundingdino_predict(
                grounding_dino_model,
                item_image,
                prompt,
                threshold,
            )
            total_boxes += int(boxes.shape[0])
            box_batches.append(boxes)
        return (box_batches, total_boxes)


NODE_CLASS_MAPPINGS = {
    "KSGroundingDinoDetect": GroundingDinoDetect,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSGroundingDinoDetect": "GroundingDINO 检测框",
}
