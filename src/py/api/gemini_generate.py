from __future__ import annotations

import base64
import io
import json
import time
from pathlib import Path
from typing import Any

import requests
import torch
from PIL import Image

import folder_paths
from ._gemini_product_utils import load_config, resolve_provider, tensor_to_png, load_image


class KSGeminiGenerate:
    DESCRIPTION = "调用配置中的图像生成模型，基于商品图、参考图和最终提示词生成一张新商品图并保存到输出目录。"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "product_image": ("IMAGE", {"tooltip": "源商品图。Gemini 模式会把它作为图像输入，要求保留商品身份并重做背景、光线和构图。"}),
            "final_prompt": ("STRING", {"forceInput": True, "tooltip": "最终生图提示词，通常来自“生成设计策略”节点。提示越明确，输出越可控。"}),
            "reference": ("KS_REFERENCE", {"tooltip": "可选参考图对象。包含图像时会一起提交给 Gemini；为空时仅依据商品图和提示词生成。"}),
            "output_prefix": ("STRING", {"default": "image_pipeline/result", "tooltip": "输出文件名前缀，相对于 ComfyUI output 目录。节点会自动追加时间戳和 .png，路径必须留在 output 内。"}),
            "provider": (["default"], {"default": "default", "tooltip": "图像生成供应商。default 使用配置文件 image_gen.defaults.provider；gemini 走 generateContent，多数其他供应商走 OpenAI 兼容 images/generations。"}),
            "api_key": (["default"], {"default": "default", "tooltip": "图像生成 API 密钥名称。default 使用配置文件默认密钥；不同密钥可能对应免费/付费额度。"}),
            "model": (["default"], {"default": "default", "tooltip": "图像生成模型。不同模型会影响画质、提示词遵循度、速度、尺寸能力和费用。"}),
        }}

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "output_path")
    RETURN_DESCRIPTIONS = (
        "生成后的图片张量，可继续接后处理、预览或保存节点。",
        "实际保存的 PNG 文件绝对路径。",
    )
    FUNCTION = "generate"
    OUTPUT_NODE = True
    CATEGORY = "Kongshan/API"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Always call the external image model again instead of reusing a
        # previous ComfyUI cache entry for identical inputs.
        return float("nan")

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    def generate(
        self,
        product_image,
        final_prompt,
        reference,
        output_prefix,
        provider,
        api_key,
        model,
    ):
        config = load_config()
        resolved_model, base_url, actual_api_key, provider_name, provider_data = resolve_provider(
            config, provider, api_key, model, "image_gen"
        )

        output_root = Path(folder_paths.get_output_directory()).resolve()
        prefix_path = Path(output_prefix.replace("\\", "/"))
        target_dir = (output_root / prefix_path.parent).resolve()
        if output_root not in target_dir.parents and target_dir != output_root:
            raise RuntimeError("output_prefix must stay inside the ComfyUI output directory")
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = target_dir / f"{prefix_path.name}_{stamp}.png"

        if provider_name == "gemini":
            # Use Gemini-specific generateContent API
            parts: list[dict[str, Any]] = [
                {
                    "text": (
                        "Generate exactly one NEW final image, not a retouch or upscale of the source. "
                        "Preserve the source product identity precisely, but replace the entire original "
                        "background, lighting, shadows, framing, and composition.\n\n"
                        + final_prompt
                    )
                },
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(tensor_to_png(product_image)).decode("ascii"),
                    }
                },
            ]
            if reference.get("image") is not None:
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64.b64encode(tensor_to_png(reference["image"])).decode("ascii"),
                        }
                    }
                )

            url = f"{base_url}/v1beta/models/{resolved_model}:generateContent"
            response = requests.post(
                url,
                headers={"x-goog-api-key": actual_api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                },
                timeout=600,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Gemini image generation failed ({response.status_code}): {response.text[:2000]}"
                )

            payload = response.json()
            candidates = payload.get("candidates") or []
            response_parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            image_data = None
            response_text: list[str] = []
            for part in response_parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    image_data = base64.b64decode(inline["data"])
                    break
                if part.get("text"):
                    response_text.append(part["text"])
            if image_data is None:
                detail = " ".join(response_text) or json.dumps(payload, ensure_ascii=False)[:2000]
                raise RuntimeError(f"Gemini returned no image: {detail}")

        else:
            # OpenAI-compatible images/generations API
            url = f"{base_url}/images/generations" if not base_url.endswith("/images/generations") else base_url

            headers = {
                "Authorization": f"Bearer {actual_api_key}",
                "HTTP-Referer": "https://github.com/kongshan4219/ComfyUI-Kongshan-Nodes",
                "X-Title": "Kongshan Nodes for ComfyUI",
                "Content-Type": "application/json",
            }
            response = requests.post(
                url,
                headers=headers,
                json={
                    "model": resolved_model,
                    "prompt": final_prompt,
                    "n": 1,
                    "response_format": "b64_json"
                },
                timeout=600,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Image generation failed ({response.status_code}): {response.text[:2000]}"
                )

            payload = response.json()
            data = payload.get("data") or []
            if not data:
                raise RuntimeError(f"Image generation returned no data: {json.dumps(payload)[:2000]}")

            b64_data = data[0].get("b64_json")
            if b64_data:
                image_data = base64.b64decode(b64_data)
            else:
                img_url = data[0].get("url")
                if not img_url:
                    raise RuntimeError("Neither b64_json nor url found in generation response.")
                img_res = requests.get(img_url, timeout=60)
                img_res.raise_for_status()
                image_data = img_res.content

        with Image.open(io.BytesIO(image_data)) as generated:
            generated.convert("RGB").save(output_path, format="PNG")
        return load_image(output_path), str(output_path)


NODE_CLASS_MAPPINGS = {
    "KSGeminiGenerate": KSGeminiGenerate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSGeminiGenerate": "KS API 生图",
}
