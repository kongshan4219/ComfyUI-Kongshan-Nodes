from __future__ import annotations

import numpy as np
import torch
from PIL import Image

from ._sam_grounding_dino_utils import groundingdino_predict, sam_segment


class GroundingDinoSAMSegment:
    DESCRIPTION = "快捷组合节点：一体化执行 GroundingDINO 检测和 SAM 分割，适合快速从文本 prompt 得到实例图片与遮罩。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sam_model": ('SAM_MODEL', {"tooltip": "已加载的 SAM 模型，用于根据检测框生成精细遮罩。"}),
                "grounding_dino_model": ('GROUNDING_DINO_MODEL', {"tooltip": "已加载的 GroundingDINO 模型，用于根据 prompt 找目标框。"}),
                "image": ('IMAGE', {"tooltip": "待检测和分割的图片批次。"}),
                "prompt": ("STRING", {"tooltip": "检测目标文本。比如 product 会倾向于找商品整体；更具体的词会改变检测范围。"}),
                "threshold": ("FLOAT", {
                    "default": 0.3,
                    "min": 0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "GroundingDINO 检测阈值。降低更容易检出多个目标但误检增加；提高更严格但可能没有框。",
                }),
            }
        }
    CATEGORY = "Kongshan/Local"
    FUNCTION = "main"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("segmented_images", "masks")
    RETURN_DESCRIPTIONS = (
        "按检测目标输出的分割图片批次。",
        "每个分割实例对应的遮罩批次。",
    )

    def main(self, grounding_dino_model, sam_model, image, prompt, threshold):
        res_images = []
        res_masks = []
        for item in image:
            item_pil = Image.fromarray(
                np.clip(255. * item.cpu().numpy(), 0, 255).astype(np.uint8)).convert('RGBA')
            boxes = groundingdino_predict(
                grounding_dino_model,
                item_pil,
                prompt,
                threshold
            )
            if boxes.shape[0] == 0:
                break
            segmented = sam_segment(
                sam_model,
                item_pil,
                boxes
            )
            if segmented is not None:
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
    "KSGroundedSAMSegment": GroundingDinoSAMSegment,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSGroundedSAMSegment": "GroundingDINO + SAM 分割",
}
