from __future__ import annotations

from ._sam_grounding_dino_utils import list_sam_model, load_sam_model


class SAMModelLoader:
    DESCRIPTION = "加载 Segment Anything / SAM-HQ 模型，供后续按检测框分割使用。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (list_sam_model(), {"tooltip": "SAM 模型版本。vit_h/hq_vit_h 质量更高但显存和下载体积更大；vit_b/mobile_sam 更轻更快但边缘细节可能较弱。"}),
            }
        }
    CATEGORY = "Kongshan/Local"
    FUNCTION = "main"
    RETURN_TYPES = ("SAM_MODEL", )
    RETURN_NAMES = ("sam_model",)
    RETURN_DESCRIPTIONS = (
        "已加载的 SAM 模型对象，用于 SAM 按框分割或 GroundingDINO + SAM 分割节点。",
    )

    def main(self, model_name):
        sam_model = load_sam_model(model_name)
        return (sam_model, )


NODE_CLASS_MAPPINGS = {
    "KSSAMModelLoader": SAMModelLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSSAMModelLoader": "加载 SAM 模型",
}
