from __future__ import annotations

import asyncio
import os
import json
import requests
from pathlib import Path
from typing import Any
from aiohttp import web
from server import PromptServer

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "pipeline.config.json"

PROVIDER_FALLBACKS = {
    "gemini": {
        "vlm": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"],
        "embedding": ["text-embedding-004"],
        "image_gen": ["gemini-2.5-flash-image", "gemini-3.0-pro-image-preview"]
    },
    "openrouter": {
        "vlm": ["google/gemini-2.5-pro", "meta-llama/llama-3.3-70b-instruct"],
        "embedding": ["nvidia/llama-nemotron-embed-vl-1b-v2"],
        "image_gen": ["black-forest-labs/flux-1-schnell"]
    },
    "opencode": {
        "vlm": ["mimo-v2.5"],
        "embedding": [],
        "image_gen": []
    }
}


def _route_post(path: str):
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return lambda handler: handler
    return server.routes.post(path)


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


def resolve_key_value(provider_data: dict[str, Any], key_name: str) -> str:
    load_dotenv()
    key_val = provider_data.get("api_keys", {}).get(key_name, "")
    if not key_val:
        return ""
    if key_val.startswith("env:"):
        env_name = key_val[4:]
        return os.environ.get(env_name, "")
    if os.environ.get(key_val):
        return os.environ.get(key_val)
    return key_val


def fetch_models(provider_name: str, provider_data: dict[str, Any], api_key: str, category: str) -> list[str]:
    model_fetch = provider_data.get("model_fetch", {})
    if isinstance(model_fetch, dict) and "models" in model_fetch:
        return model_fetch["models"]
    if "models" in provider_data:
        return provider_data["models"]

    method = model_fetch.get("method") if isinstance(model_fetch, dict) else ""
    if not method or not api_key:
        return PROVIDER_FALLBACKS.get(provider_name, {}).get(category, [])

    base_url = provider_data.get("base_url", "")

    try:
        if method == "gemini":
            url = f"{base_url.rstrip('/')}/v1beta/models" if base_url else "https://generativelanguage.googleapis.com/v1beta/models"
            models = []
            page_token = ""
            while True:
                params = {"pageSize": 1000}
                if page_token:
                    params["pageToken"] = page_token
                response = requests.get(
                    url,
                    headers={"x-goog-api-key": api_key},
                    params=params,
                    timeout=15,
                )
                if not response.ok:
                    raise RuntimeError(f"Gemini listing failed ({response.status_code}): {response.text[:200]}")
                payload = response.json()
                for item in payload.get("models", []):
                    model = str(item.get("name", "")).removeprefix("models/")
                    methods = item.get("supportedGenerationMethods", [])

                    if category == "image_gen":
                        if "image" in model.lower() and "generateContent" in methods:
                            models.append(model)
                    elif category == "embedding":
                        if "embed" in model.lower():
                            models.append(model)
                    else:  # vlm
                        if "generateContent" in methods and "image" not in model.lower():
                            models.append(model)

                page_token = payload.get("nextPageToken", "")
                if not page_token:
                    break
            return list(dict.fromkeys(models))

        elif method in ("openai", "openrouter"):
            url = model_fetch.get("url") or f"{base_url.rstrip('/')}/models"
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            if not response.ok:
                raise RuntimeError(f"Model listing failed ({response.status_code}): {response.text[:200]}")
            payload = response.json()
            raw_models = [item.get("id") for item in payload.get("data", []) if item.get("id")]

            models = []
            for model in raw_models:
                if category == "image_gen":
                    if any(kw in model.lower() for kw in ("dall-e", "flux", "stable-diffusion", "sdxl", "midjourney", "playgrounds", "imagen")):
                        models.append(model)
                elif category == "embedding":
                    if "embed" in model.lower():
                        models.append(model)
                else:  # vlm
                    if "embed" not in model.lower() and not any(kw in model.lower() for kw in ("dall-e", "flux", "stable-diffusion", "sdxl")):
                        models.append(model)
            if not models:
                models = raw_models
            return list(dict.fromkeys(models))

    except Exception as e:
        print(f"[Kongshan Nodes] Error fetching models from provider {provider_name}: {e}")
        # Fallback to predefined lists
        return PROVIDER_FALLBACKS.get(provider_name, {}).get(category, [])

    return PROVIDER_FALLBACKS.get(provider_name, {}).get(category, [])


@_route_post("/ks-nodes/config-info")
async def ks_config_info(request):
    try:
        payload = await request.json()
        config_path = str(payload.get("config_path", ""))
        config = load_config(config_path)
    except Exception as e:
        return web.json_response({"error": f"Failed to load config: {str(e)}"}, status=400)

    providers_info = {}
    providers = config.get("providers", {})
    for p_name, p_data in providers.items():
        keys_list = []
        api_keys = p_data.get("api_keys", {})
        for key_name in api_keys.keys():
            val = resolve_key_value(p_data, key_name)
            keys_list.append({
                "name": key_name,
                "is_configured": bool(val)
            })
        providers_info[p_name] = {
            "api_keys": keys_list,
            "default_api_key": p_data.get("default_api_key", "")
        }

    defaults = config.get("defaults", {})
    return web.json_response({
        "providers": providers_info,
        "defaults": defaults
    })


@_route_post("/ks-nodes/models")
async def ks_models(request):
    try:
        payload = await request.json()
        config_path = str(payload.get("config_path", ""))
        provider_name = str(payload.get("provider", ""))
        api_key_name = str(payload.get("api_key", ""))
        category = str(payload.get("category", "vlm"))

        config = load_config(config_path)
    except Exception as e:
        return web.json_response({"error": f"Failed to load config: {str(e)}"}, status=400)

    providers = config.get("providers", {})
    
    # Resolve provider
    if provider_name == "default" or not provider_name or provider_name.startswith("default (") or provider_name.startswith("default("):
        provider_name = config.get("defaults", {}).get(category, {}).get("provider", "")
    
    provider_data = providers.get(provider_name)
    if not provider_data:
        return web.json_response({"error": f"Provider '{provider_name}' not found in config."}, status=404)

    # Resolve API Key
    if api_key_name == "default" or not api_key_name or api_key_name.startswith("default (") or api_key_name.startswith("default("):
        api_key_name = config.get("defaults", {}).get(category, {}).get("api_key", "")
        if api_key_name == "default" or not api_key_name or api_key_name.startswith("default (") or api_key_name.startswith("default("):
            api_key_name = provider_data.get("default_api_key", "")

    api_key = resolve_key_value(provider_data, api_key_name)
    
    try:
        models = await asyncio.to_thread(fetch_models, provider_name, provider_data, api_key, category)
    except Exception as error:
        return web.json_response({"error": str(error)}, status=502)

    return web.json_response({"models": models})


# Legacy route for backward compatibility with older/cached versions of the frontend
@_route_post("/ks-nodes/gemini-models")
async def ks_gemini_models(request):
    try:
        payload = await request.json()
        key_name = str(payload.get("gemini_api_key", ""))
        config = load_config("")
        gemini_provider = config.get("providers", {}).get("gemini", {})
        api_key = resolve_key_value(gemini_provider, key_name)
        if not api_key:
            return web.json_response({"error": f"API key {key_name} is not set."}, status=400)
        models = await asyncio.to_thread(fetch_models, "gemini", gemini_provider, api_key, "image_gen")
        return web.json_response({"models": models})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
