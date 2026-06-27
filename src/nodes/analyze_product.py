from __future__ import annotations

import json
from ._gemini_product_utils import DEFAULT_CONFIG, load_config, data_url, chat_json


class KSAnalyzeProduct:
    DESCRIPTION = "分析商品图片并生成结构化商品特征 JSON，供后续参考图匹配和设计策略节点使用。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE", {"tooltip": "待分析的商品图片。节点会把它发送给视觉语言模型，并原样传递到输出 image。"}),
            "config_path": ("STRING", {"default": str(DEFAULT_CONFIG), "tooltip": "节点配置文件路径。留默认值使用内置 pipeline.config.json；改成其他 JSON 可切换供应商、模型和密钥配置。"}),
            "provider": (["default"], {"default": "default", "tooltip": "视觉语言模型供应商。default 使用配置文件 vlm.defaults.provider；选择具体供应商会覆盖默认值。"}),
            "api_key": (["default"], {"default": "default", "tooltip": "API 密钥名称。default 使用配置文件默认密钥；选择其他名称会读取对应密钥或环境变量。"}),
            "model": (["default"], {"default": "default", "tooltip": "分析商品图用的 VLM 模型。default 使用配置文件 vlm.defaults.model；不同模型会影响识别细节、速度和费用。"}),
        }}

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "product_profile")
    RETURN_DESCRIPTIONS = (
        "原始输入图片，便于继续连接到设计、生成或保存节点。",
        "商品特征 JSON 字符串，包含主体、颜色、材质、形状、风格标签等信息。",
    )
    FUNCTION = "analyze"
    CATEGORY = "Kongshan/API"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    def analyze(self, image, config_path, provider, api_key, model):
        config = load_config(config_path)
        messages = [
            {"role": "system", "content": "You are a professional product image analyst. Output valid JSON with subject (string), main_colors (string array), material (string), shape (string), and style_tags (string array)."},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this product image and output only the requested JSON."},
                {"type": "image_url", "image_url": {"url": data_url(image)}},
            ]},
        ]
        profile = chat_json(config, provider, api_key, model, messages)
        return image, json.dumps(profile, ensure_ascii=False, indent=2)


NODE_CLASS_MAPPINGS = {
    "KSAnalyzeProduct": KSAnalyzeProduct,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSAnalyzeProduct": "分析商品图",
}
