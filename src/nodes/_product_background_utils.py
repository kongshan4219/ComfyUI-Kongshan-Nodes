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
