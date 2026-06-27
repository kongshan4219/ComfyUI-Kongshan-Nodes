from __future__ import annotations

from ._sam_grounding_dino_utils import list_groundingdino_model, load_groundingdino_model


class GroundingDinoModelLoader:
    DESCRIPTION = "加载 GroundingDINO 文本检测模型，用自然语言 prompt 在图片中找目标框。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (list_groundingdino_model(), {"tooltip": "GroundingDINO 模型版本。SwinB 通常更强但更大更慢；SwinT 体积较小、速度更快。"}),
            }
        }
    CATEGORY = "Kongshan/Local"
    FUNCTION = "main"
    RETURN_TYPES = ("GROUNDING_DINO_MODEL", )
    RETURN_NAMES = ("grounding_dino_model",)
    RETURN_DESCRIPTIONS = (
        "已加载的 GroundingDINO 模型对象，用于检测框节点或一体化分割节点。",
    )

    def main(self, model_name):
        dino_model = load_groundingdino_model(model_name)
        return (dino_model, )


NODE_CLASS_MAPPINGS = {
    "KSGroundingDinoModelLoader": GroundingDinoModelLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSGroundingDinoModelLoader": "加载 GroundingDINO 模型",
}
