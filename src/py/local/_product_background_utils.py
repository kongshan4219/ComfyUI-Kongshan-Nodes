from __future__ import annotations

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage


def _fill_mask_holes(mask: Image.Image) -> Image.Image:
    """Fill background islands that are fully enclosed by the foreground mask."""
    padded = Image.new("L", (mask.width + 2, mask.height + 2), 0)
    padded.paste(mask, (1, 1))
    inverted = Image.eval(padded, lambda value: 255 - value)
    ImageDraw.floodfill(inverted, (0, 0), 128)

    padded_array = np.asarray(padded).copy()
    enclosed_background = np.asarray(inverted) == 255
    padded_array[enclosed_background] = 255
    return Image.fromarray(padded_array[1:-1, 1:-1], mode="L")


def _prepare_mask(
    mask_tensor: torch.Tensor,
    threshold: float,
    min_component_area: int,
    close_radius: int,
    expand_pixels: int,
    fill_holes: bool,
) -> Image.Image:
    mask_array = mask_tensor.detach().cpu().numpy()
    if mask_array.ndim == 3:
        mask_array = np.squeeze(mask_array)
    binary = mask_array >= float(threshold)

    min_component_area = max(0, int(min_component_area))
    if min_component_area:
        labels, component_count = ndimage.label(binary)
        if component_count:
            areas = np.bincount(labels.ravel())
            keep = areas >= min_component_area
            keep[0] = False
            binary = keep[labels]

    binary = binary.astype(np.uint8) * 255
    mask = Image.fromarray(binary, mode="L")

    close_radius = max(0, int(close_radius))
    if close_radius:
        kernel_size = close_radius * 2 + 1
        mask = mask.filter(ImageFilter.MaxFilter(kernel_size))
        mask = mask.filter(ImageFilter.MinFilter(kernel_size))
    if fill_holes:
        mask = _fill_mask_holes(mask)

    expand_pixels = max(0, int(expand_pixels))
    if expand_pixels:
        mask = mask.filter(ImageFilter.MaxFilter(expand_pixels * 2 + 1))
    return mask


def _prepare_masks(
    masks: torch.Tensor,
    threshold: float,
    min_component_area: int,
    close_radius: int,
    expand_pixels: int,
    fill_holes: bool,
) -> list[Image.Image]:
    return [
        _prepare_mask(
            masks[index],
            threshold,
            min_component_area,
            close_radius,
            expand_pixels,
            fill_holes,
        )
        for index in range(masks.shape[0])
    ]


def _image_tensor_to_uint8_rgb(image_tensor: torch.Tensor) -> np.ndarray:
    array = np.clip(image_tensor.detach().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
    if array.ndim == 2:
        array = np.stack([array, array, array], axis=-1)
    return array[..., :3]


def _resize_mask_to_shape(mask: Image.Image | np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    mask_array = np.asarray(mask)
    if mask_array.shape == shape:
        return mask_array
    return np.asarray(
        Image.fromarray(mask_array, mode="L").resize(
            (shape[1], shape[0]),
            Image.Resampling.NEAREST,
        )
    )


def _union_masks(masks: list[Image.Image], shape: tuple[int, int]) -> np.ndarray:
    union_mask = np.zeros(shape, dtype=np.uint8)
    for mask in masks:
        union_mask = np.maximum(union_mask, _resize_mask_to_shape(mask, shape))
    return union_mask


def _feather_mask(mask: Image.Image, edge_feather: float) -> Image.Image:
    if edge_feather > 0:
        return mask.filter(ImageFilter.GaussianBlur(float(edge_feather)))
    return mask


def _apply_background(
    source_array: np.ndarray,
    mask: Image.Image | np.ndarray,
    background_mode: str,
    edge_feather: float = 0.0,
) -> Image.Image:
    source_rgb = source_array[..., :3]
    full_mask = Image.fromarray(np.asarray(mask), mode="L")
    full_mask = _feather_mask(full_mask, edge_feather)

    if background_mode == "transparent":
        result = Image.fromarray(source_rgb, mode="RGB").convert("RGBA")
        result.putalpha(full_mask)
        return result

    canvas = Image.new("RGB", (source_rgb.shape[1], source_rgb.shape[0]), "white")
    canvas.paste(Image.fromarray(source_rgb, mode="RGB"), (0, 0), full_mask)
    return canvas


def _pil_to_tensor(image: Image.Image) -> torch.Tensor:
    return torch.from_numpy(np.asarray(image).astype(np.float32) / 255.0)[None,]


def _collect_mask_instances(
    processed_masks: list[Image.Image],
    prefer_grouped_product_masks: bool,
) -> list[dict[str, int]]:
    redundant_mask_indices = (
        _find_redundant_component_masks(processed_masks)
        if prefer_grouped_product_masks
        else set()
    )

    instances: list[dict[str, int]] = []
    for index, processed_mask in enumerate(processed_masks):
        if index in redundant_mask_indices:
            continue
        mask = np.asarray(processed_mask)
        ys, xs = np.where(mask > 0)
        if len(xs) == 0:
            continue
        instances.append(
            {
                "source_index": index,
                "x1": int(xs.min()),
                "y1": int(ys.min()),
                "x2": int(xs.max()) + 1,
                "y2": int(ys.max()) + 1,
            }
        )
    return instances


def _find_redundant_component_masks(masks: list[Image.Image]) -> set[int]:
    """Prefer a complete product mask over its separately detected components."""
    arrays = [np.asarray(mask) > 0 for mask in masks]
    areas = [int(array.sum()) for array in arrays]
    redundant_components = set()

    for candidate_index, candidate in enumerate(arrays):
        candidate_area = areas[candidate_index]
        if candidate_area == 0:
            continue

        children = []
        for child_index, child in enumerate(arrays):
            child_area = areas[child_index]
            if (
                child_index == candidate_index
                or child_area == 0
                or child_area >= candidate_area * 0.8
            ):
                continue
            child_coverage = np.logical_and(candidate, child).sum() / child_area
            if child_coverage >= 0.97:
                children.append((child_index, child))

        if len(children) < 2:
            continue

        child_union = np.logical_or.reduce([child for _, child in children])
        candidate_coverage = np.logical_and(candidate, child_union).sum() / candidate_area
        if candidate_coverage >= 0.9:
            redundant_components.update(child_index for child_index, _ in children)

    return redundant_components
