from __future__ import annotations

import json
from ._gemini_product_utils import DEFAULT_CONFIG, load_config, data_url, chat_json


class KSDesignStrategy:
    DESCRIPTION = "结合商品图、商品特征和参考图生成最终生图提示词与结构化设计策略。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "product_image": ("IMAGE", {"tooltip": "商品图片。模型会参考主体外观，生成更贴合商品的拍摄策略。"}),
            "product_profile": ("STRING", {"forceInput": True, "tooltip": "商品特征 JSON，通常来自“分析商品图”节点。"}),
            "reference": ("KS_REFERENCE", {"tooltip": "参考图对象。包含图像时会参与策略生成；为空时按纯 AI 设计处理。"}),
            "base_prompt": ("STRING", {"multiline": True, "default": "Create a high-quality professional e-commerce product photograph.", "tooltip": "基础正向要求。内容越具体，最终 final_prompt 越贴近目标风格、场景和用途。"}),
            "negative_prompt": ("STRING", {"multiline": True, "default": "low quality, blurry, text, watermark, distorted product", "tooltip": "负向要求。留空则不追加 Negative prompt；填写后用于约束低质量、文字、水印、变形等问题。"}),
            "config_path": ("STRING", {"default": str(DEFAULT_CONFIG), "tooltip": "节点配置文件路径。用于读取 VLM 供应商、模型和密钥配置。"}),
            "provider": (["default"], {"default": "default", "tooltip": "策略生成供应商。default 使用配置文件 vlm.defaults.provider。"}),
            "api_key": (["default"], {"default": "default", "tooltip": "API 密钥名称。default 使用配置文件默认密钥。"}),
            "model": (["default"], {"default": "default", "tooltip": "策略生成 VLM 模型。不同模型会影响策略细节、稳定性、速度和费用。"}),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("final_prompt", "design_strategy")
    RETURN_DESCRIPTIONS = (
        "最终生图提示词，包含 base_prompt、结构化设计策略和可选 negative_prompt。",
        "设计策略 JSON，包含光线、道具布局、镜头角度、色调等字段。",
    )
    FUNCTION = "formulate"
    CATEGORY = "Kongshan/API"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    def formulate(self, product_image, product_profile, reference, base_prompt, negative_prompt, config_path, provider, api_key, model):
        config = load_config(config_path)
        content = [
            {"type": "text", "text": f"Product profile:\n{product_profile}\n\nBase requirements:\n{base_prompt}\n\nAnalyze the product image and any reference image, then output only the design strategy JSON."},
            {"type": "image_url", "image_url": {"url": data_url(product_image)}},
        ]
        if reference.get("image") is not None:
            content.append({"type": "image_url", "image_url": {"url": data_url(reference["image"])}})
        messages = [
            {"role": "system", "content": "You are an art director for product photography. Output valid JSON with lighting, props_layout, camera_angle, and color_tone, all strings."},
            {"role": "user", "content": content},
        ]
        strategy = chat_json(config, provider, api_key, model, messages)
        prompt = f"{base_prompt.rstrip()}\n\nDesign Strategy:\n{json.dumps(strategy, ensure_ascii=False, indent=2)}"
        if negative_prompt.strip():
            prompt += f"\n\nNegative prompt:\n{negative_prompt.strip()}"
        return prompt, json.dumps(strategy, ensure_ascii=False, indent=2)


NODE_CLASS_MAPPINGS = {
    "KSDesignStrategy": KSDesignStrategy,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSDesignStrategy": "生成设计策略",
}
