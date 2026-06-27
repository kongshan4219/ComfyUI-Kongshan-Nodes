from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from ._sam_grounding_dino_utils import sam_segment


class SAMSegmentByBoxes:
    DESCRIPTION = "用 SAM 模型按 GroundingDINO 检测框切出实例图片和遮罩。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sam_model": ("SAM_MODEL", {"tooltip": "已加载的 SAM 模型。模型越大通常边缘越准，防爆和显存占用更高。"}),
                "image": ("IMAGE", {"tooltip": "原始图片批次，应与 boxes 所属图片保持一致。"}),
                "boxes": ("KS_DINO_BOXES", {"tooltip": "GroundingDINO 输出的检测框列表。无框时节点会输出空遮罩占位。"}),
            }
        }
    CATEGORY = "Kongshan/Local"
    FUNCTION = "main"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("segmented_images", "masks")
    RETURN_DESCRIPTIONS = (
        "按实例输出的分割图片批次，背景为透明/黑色区域。",
        "每个实例对应的遮罩批次，可连接白底处理节点。",
    )

    def main(self, sam_model, image, boxes):
        res_images = []
        res_masks = []
        for item, item_boxes in zip(image, boxes):
            if item_boxes.shape[0] == 0:
                continue
            item_image = Image.fromarray(
                np.clip(255. * item.cpu().numpy(), 0, 255).astype(np.uint8)
            ).convert("RGBA")
            segmented = sam_segment(sam_model, item_image, item_boxes)
            if segmented is None:
                continue
            images, masks = segmented
            res_images.extend(images)
            res_masks.extend(masks)
        if len(res_images) == 0:
            _, height, width, _ = image.size()
            empty_image = torch.zeros((1, height, width, 3), dtype=image.dtype, device=image.device)
            empty_mask = torch.zeros((1, height, width), dtype=torch.float32, device=image.device)
            return (empty_image, empty_mask)
        return (torch.cat(res_images, dim=0), torch.cat(res_masks, dim=0))


NODE_CLASS_MAPPINGS = {
    "KSSAMSegmentByBoxes": SAMSegmentByBoxes,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSSAMSegmentByBoxes": "SAM 按框分割",
}
