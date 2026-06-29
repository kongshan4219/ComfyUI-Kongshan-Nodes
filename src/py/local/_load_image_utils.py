from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence


def resolve_image_path(path_text: str) -> Path:
    path = Path(str(path_text).strip()).expanduser()
    if path.is_file():
        return path

    try:
        import folder_paths

        if folder_paths.exists_annotated_filepath(str(path_text)):
            return Path(folder_paths.get_annotated_filepath(str(path_text)))
    except Exception:
        pass

    return path


def load_image_like_comfy(path: Path):
    import comfy.model_management
    from comfy_api.latest import InputImpl
    import node_helpers

    image_path = str(path)

    dtype = comfy.model_management.intermediate_dtype()
    device = comfy.model_management.intermediate_device()

    components = InputImpl.VideoFromFile(image_path).get_components()
    if components.images.shape[0] > 0:
        images = components.images.to(device=device, dtype=dtype)
        if components.alpha is not None:
            mask = (1.0 - components.alpha[..., -1]).to(device=device, dtype=dtype)
        else:
            mask = torch.zeros((components.images.shape[0], 64, 64), dtype=dtype, device=device)
        return images, mask

    img = node_helpers.pillow(Image.open, image_path)

    output_images = []
    output_masks = []
    w, h = None, None

    for frame in ImageSequence.Iterator(img):
        frame = node_helpers.pillow(ImageOps.exif_transpose, frame)
        image = frame.convert("RGB")

        if len(output_images) == 0:
            w, h = image.size

        if image.size[0] != w or image.size[1] != h:
            continue

        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        if "A" in frame.getbands():
            mask = np.array(frame.getchannel("A")).astype(np.float32) / 255.0
            mask = 1.0 - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
        output_images.append(image.to(dtype=dtype))
        output_masks.append(mask.unsqueeze(0).to(dtype=dtype))

    output_image = torch.cat(output_images, dim=0)
    output_mask = torch.cat(output_masks, dim=0)

    return output_image.to(device=device, dtype=dtype), output_mask.to(device=device, dtype=dtype)


def image_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        digest.update(file.read())
    return digest.digest().hex()
