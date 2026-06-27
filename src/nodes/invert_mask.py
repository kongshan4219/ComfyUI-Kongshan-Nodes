from __future__ import annotations


class InvertMask:
    DESCRIPTION = "反转遮罩，把前景和背景区域互换。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mask": ("MASK", {"tooltip": "待反转遮罩。输入值 1 会变为 0，输入值 0 会变为 1，中间灰度也会按 1-value 反转。"}),
            }
        }
    CATEGORY = "Kongshan/Local"
    FUNCTION = "main"
    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("mask",)
    RETURN_DESCRIPTIONS = (
        "反转后的遮罩。",
    )

    def main(self, mask):
        out = 1.0 - mask
        return (out,)


NODE_CLASS_MAPPINGS = {
    "KSInvertMask": InvertMask,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSInvertMask": "反转遮罩",
}
