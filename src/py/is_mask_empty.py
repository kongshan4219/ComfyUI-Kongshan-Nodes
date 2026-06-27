from __future__ import annotations

import torch


class IsMaskEmptyNode:
    DESCRIPTION = "检查遮罩是否完全为空，并输出可用于条件判断的数字。"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mask": ("MASK", {"tooltip": "待检查遮罩。所有像素都为 0 时视为空遮罩。"}),
            },
        }
    RETURN_TYPES = ["NUMBER"]
    RETURN_NAMES = ["boolean_number"]
    RETURN_DESCRIPTIONS = [
        "遮罩为空时输出 1，不为空时输出 0。可作为流程判断或调试信号。",
    ]

    FUNCTION = "main"
    CATEGORY = "Kongshan/Local"

    def main(self, mask):
        return (torch.all(mask == 0).int().item(), )


NODE_CLASS_MAPPINGS = {
    "KSIsMaskEmpty": IsMaskEmptyNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSIsMaskEmpty": "检查空遮罩",
}
