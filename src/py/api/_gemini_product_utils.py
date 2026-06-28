from __future__ import annotations

import base64
import io
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import requests
import torch
from PIL import Image

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "pipeline.config.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def load_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path).expanduser() if config_path.strip() else DEFAULT_CONFIG
    if not path.is_absolute():
        path = PACKAGE_ROOT / path
    if not path.exists():
        raise RuntimeError(f"Kongshan node config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_dotenv() -> None:
    path = PACKAGE_ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def list_gemini_image_models(api_key: str) -> list[str]:
    models: list[str] = []
    page_token = ""
    while True:
        params: dict[str, str | int] = {"pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": api_key},
            params=params,
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(
                f"Gemini model loading failed ({response.status_code}): "
                f"{response.text[:1000]}"
            )
        payload = response.json()
        for item in payload.get("models", []):
            model = str(item.get("name", "")).removeprefix("models/")
            methods = item.get("supportedGenerationMethods", [])
            if model and "image" in model.lower() and "generateContent" in methods:
                models.append(model)
        page_token = str(payload.get("nextPageToken", ""))
        if not page_token:
            break
    return list(dict.fromkeys(models))


def resolve_provider(config: dict[str, Any], provider: str, api_key_name: str, model: str, category: str) -> tuple[str, str, str, str, dict[str, Any]]:
    load_dotenv()

    # 1. Resolve Provider
    provider_name = provider.strip() if provider else "default"
    if provider_name == "default" or provider_name.startswith("default (") or provider_name.startswith("default("):
        provider_name = config.get("defaults", {}).get(category, {}).get("provider", "")

    provider_data = config.get("providers", {}).get(provider_name)
    if not provider_data:
        raise RuntimeError(f"Provider '{provider_name}' not found in configuration.")

    # 2. Resolve Model
    resolved_model = model.strip() if model else "default"
    if resolved_model == "default" or resolved_model.startswith("default (") or resolved_model.startswith("default("):
        resolved_model = config.get("defaults", {}).get(category, {}).get("model", "")
    if not resolved_model:
        raise RuntimeError(f"No default model configured for category: {category}")

    # 3. Resolve API Key Name
    resolved_key_name = api_key_name.strip() if api_key_name else "default"
    if resolved_key_name == "default" or resolved_key_name.startswith("default (") or resolved_key_name.startswith("default("):
        resolved_key_name = config.get("defaults", {}).get(category, {}).get("api_key", "default")
        if resolved_key_name == "default" or resolved_key_name.startswith("default (") or resolved_key_name.startswith("default("):
            resolved_key_name = provider_data.get("default_api_key", "")

    # 4. Resolve API Key Value
    api_key_val = provider_data.get("api_keys", {}).get(resolved_key_name, "")
    if not api_key_val:
        api_keys = provider_data.get("api_keys", {})
        if len(api_keys) == 1:
            api_key_val = list(api_keys.values())[0]
            resolved_key_name = list(api_keys.keys())[0]

    if not api_key_val:
        raise RuntimeError(f"API key name '{resolved_key_name}' not found for provider '{provider_name}'.")

    if api_key_val.startswith("env:"):
        env_name = api_key_val[4:]
        api_key = os.environ.get(env_name, "")
    elif os.environ.get(api_key_val):
        api_key = os.environ.get(api_key_val, "")
    else:
        api_key = api_key_val

    if not api_key:
        raise RuntimeError(f"API key '{resolved_key_name}' for provider '{provider_name}' is not set in environment or config.")

    base_url = provider_data.get("base_url", "")
    return resolved_model, base_url.rstrip("/"), api_key, provider_name, provider_data


def headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/kongshan4219/ComfyUI-Kongshan-Nodes",
        "X-Title": "Kongshan Nodes for ComfyUI",
        "Content-Type": "application/json",
    }


def tensor_to_png(image: torch.Tensor) -> bytes:
    array = image[0].detach().cpu().numpy()
    array = np.clip(array * 255.0, 0, 255).astype(np.uint8)
    output = io.BytesIO()
    Image.fromarray(array).save(output, format="PNG")
    return output.getvalue()


def data_url(image: torch.Tensor) -> str:
    return "data:image/png;base64," + base64.b64encode(tensor_to_png(image)).decode("ascii")


def pil_to_tensor(image: Image.Image) -> torch.Tensor:
    array = np.asarray(image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(array)[None,]


def load_image(path: Path) -> torch.Tensor:
    with Image.open(path) as image:
        return pil_to_tensor(image)


def chat_json(config: dict[str, Any], provider: str, api_key_name: str, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    resolved_model, base_url, api_key, provider_name, _ = resolve_provider(config, provider, api_key_name, model, "vlm")

    if provider_name == "gemini":
        url = f"{base_url}/v1beta/openai/chat/completions" if base_url else "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        auth_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        url = base_url if base_url.endswith(("/chat/completions", "/messages")) else f"{base_url}/chat/completions"
        auth_headers = headers(api_key)

    response = requests.post(
        url,
        headers=auth_headers,
        json={"model": resolved_model, "messages": messages, "response_format": {"type": "json_object"}},
        timeout=180,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return content if isinstance(content, dict) else json.loads(content)


def embedding(config: dict[str, Any], provider: str, api_key_name: str, model: str, image_bytes: bytes) -> list[float]:
    resolved_model, base_url, api_key, provider_name, _ = resolve_provider(config, provider, api_key_name, model, "embedding")

    if provider_name == "gemini":
        url = f"{base_url}/v1beta/openai/embeddings" if base_url else "https://generativelanguage.googleapis.com/v1beta/openai/embeddings"
        auth_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        url = base_url if base_url.endswith("/embeddings") else f"{base_url}/embeddings"
        auth_headers = headers(api_key)

    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": resolved_model,
        "input": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]}],
    }
    response = requests.post(url, headers=auth_headers, json=payload, timeout=180)
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a))
    mb = math.sqrt(sum(y * y for y in b))
    return dot / (ma * mb) if ma and mb else 0.0
