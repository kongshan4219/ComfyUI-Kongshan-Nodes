from __future__ import annotations

import json
from pathlib import Path
from ._gemini_product_utils import (
    IMAGE_EXTENSIONS,
    load_config,
    load_image,
    tensor_to_png,
    embedding,
    cosine,
)


class KSSelectReference:
    DESCRIPTION = "根据商品特征选择参考图，或把外部参考图包装成 KS_REFERENCE 供策略和生图节点使用。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "product_image": ("IMAGE", {"tooltip": "商品图片，用于和参考图库计算视觉相似度。"}),
                "product_profile": ("STRING", {"forceInput": True, "tooltip": "商品分析 JSON。reference 模式会读取其中的颜色和风格标签辅助匹配。"}),
                "mode": (["ai_design", "reference", "background"], {"tooltip": "参考选择模式：ai_design 不使用参考图；reference 从目录或输入图中选择风格参考；background 取目录第一张作为背景参考。"}),
                "reference_directory": ("STRING", {"default": "", "tooltip": "参考图库目录。reference/background 模式未连接 reference_image 时会从这里读取 png/jpg/jpeg/webp 图片。"}),
                "provider": (["default"], {"default": "default", "tooltip": "Embedding 供应商。default 使用配置文件 embedding.defaults.provider。"}),
                "api_key": (["default"], {"default": "default", "tooltip": "Embedding API 密钥名称。default 使用配置文件默认密钥。"}),
                "model": (["default"], {"default": "default", "tooltip": "Embedding 模型。不同模型会影响相似度匹配质量、速度和费用。"}),
            },
            "optional": {"reference_image": ("IMAGE", {"tooltip": "手动连接的参考图。连接后优先使用它，match_score 固定为 1.0。"})},
        }

    RETURN_TYPES = ("KS_REFERENCE", "STRING", "FLOAT")
    RETURN_NAMES = ("reference", "reference_name", "match_score")
    RETURN_DESCRIPTIONS = (
        "参考图对象，包含 image 和 path，可传给设计策略或生图节点。",
        "被选中的参考图名称；ai_design 模式为空，手动参考图为 connected reference。",
        "匹配分数。ai_design 为 0，手动参考图或 background 为 1，reference 模式为相似度评分。",
    )
    FUNCTION = "select"
    CATEGORY = "Kongshan/API"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    def select(self, product_image, product_profile, mode, reference_directory, provider, api_key, model, reference_image=None):
        if mode == "ai_design":
            return {"image": None, "path": ""}, "", 0.0
        if reference_image is not None:
            return {"image": reference_image, "path": "connected reference"}, "connected reference", 1.0
        directory = Path(reference_directory).expanduser()
        if not directory.is_dir():
            raise RuntimeError(f"Reference directory not found: {directory}")
        candidates = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
        if not candidates:
            raise RuntimeError(f"No reference images found in: {directory}")
        if mode == "background":
            path = candidates[0]
            return {"image": load_image(path), "path": str(path)}, path.name, 1.0

        config = load_config()
        cache_path = directory / "reference_embeddings.json"
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        product_vec = embedding(config, provider, api_key, model, tensor_to_png(product_image))
        tags = set()
        try:
            profile = json.loads(product_profile)
            tags.update(profile.get("style_tags", []))
            tags.update(profile.get("main_colors", []))
        except json.JSONDecodeError:
            pass
        best_path, best_score, changed = None, -1.0, False
        for path in candidates:
            item = cache.get(path.name)
            if not isinstance(item, dict) or not item.get("dense_vector"):
                item = {"dense_vector": embedding(config, provider, api_key, model, path.read_bytes()), "tags": []}
                cache[path.name] = item
                changed = True
            visual_score = cosine(product_vec, item.get("dense_vector", []))
            ref_tags = set(item.get("tags", []))
            tag_score = len(tags & ref_tags) / len(tags) if tags and ref_tags else 0.0
            score = 0.8 * visual_score + 0.2 * tag_score
            if score > best_score:
                best_path, best_score = path, score
        if changed:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        if best_path is None:
            raise RuntimeError("Reference matching produced no result")
        return {"image": load_image(best_path), "path": str(best_path)}, best_path.name, float(best_score)


NODE_CLASS_MAPPINGS = {
    "KSSelectReference": KSSelectReference,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSSelectReference": "选择参考图",
}
