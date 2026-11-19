from __future__ import annotations

import time
from typing import Any, Iterable

import numpy as np

from ..models.base_model_adapter import BaseModelAdapter, ModelOutput
from .tiling_service import PreparedTile

INFERENCE_MODES = {"standard", "tta", "multi_scale", "enhanced"}
TTA_TRANSFORMS = ("original", "hflip", "vflip", "rot90")
MULTI_SCALE_FACTORS = (0.75, 1.0, 1.25)


def _transform(image: np.ndarray, mask: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    if name == "original":
        return image.copy(), mask.copy()
    if name == "hflip":
        return image[:, :, ::-1].copy(), mask[:, ::-1].copy()
    if name == "vflip":
        return image[:, ::-1, :].copy(), mask[::-1, :].copy()
    if name == "rot90":
        return np.rot90(image, 1, axes=(1, 2)).copy(), np.rot90(mask, 1).copy()
    raise ValueError(f"Transformation inconnue: {name}")


def _inverse(probability: np.ndarray, name: str) -> np.ndarray:
    if name == "original":
        return probability
    if name == "hflip":
        return probability[:, ::-1]
    if name == "vflip":
        return probability[::-1, :]
    if name == "rot90":
        return np.rot90(probability, -1)
    raise ValueError(f"Transformation inconnue: {name}")


def _resize_chw(image: np.ndarray, height: int, width: int) -> np.ndarray:
    import torch
    import torch.nn.functional as functional

    tensor = torch.from_numpy(np.ascontiguousarray(image))[None]
    resized = functional.interpolate(tensor, size=(height, width), mode="bilinear", align_corners=False)
    return resized[0].numpy().astype(np.float32, copy=False)


def _scaled_canvas(image: np.ndarray, mask: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    height, width = mask.shape
    if scale == 1.0:
        return image.copy(), mask.copy()
    target_height = max(1, int(round(height * scale)))
    target_width = max(1, int(round(width * scale)))
    resized = _resize_chw(image, target_height, target_width)
    resized_mask = _resize_chw(mask.astype(np.float32)[None], target_height, target_width)[0] > 0.5
    canvas = np.zeros_like(image, dtype=np.float32)
    canvas_mask = np.zeros_like(mask, dtype=np.bool_)
    src_row = max(0, (target_height - height) // 2)
    src_col = max(0, (target_width - width) // 2)
    dst_row = max(0, (height - target_height) // 2)
    dst_col = max(0, (width - target_width) // 2)
    copy_height = min(height, target_height)
    copy_width = min(width, target_width)
    canvas[:, dst_row : dst_row + copy_height, dst_col : dst_col + copy_width] = resized[:, src_row : src_row + copy_height, src_col : src_col + copy_width]
    canvas_mask[dst_row : dst_row + copy_height, dst_col : dst_col + copy_width] = resized_mask[src_row : src_row + copy_height, src_col : src_col + copy_width]
    return canvas, canvas_mask


def _predict_one(adapter: BaseModelAdapter, tile: PreparedTile, image: np.ndarray, mask: np.ndarray) -> ModelOutput:
    transformed = PreparedTile(image=image, source_rgb=tile.source_rgb, valid_mask=mask, metadata=tile.metadata)
    return adapter.predict(transformed)


def predict_mode(adapter: BaseModelAdapter, tile: PreparedTile, mode: str) -> ModelOutput:
    """Predict one tile with reversible TTA/multi-scale probability fusion."""
    if mode not in INFERENCE_MODES:
        raise ValueError(f"Mode d'inference inconnu: {mode}")
    if mode == "standard":
        return adapter.predict(tile)
    started = time.perf_counter()
    predictions: list[np.ndarray] = []
    if mode in {"tta", "enhanced"}:
        for transform_name in TTA_TRANSFORMS:
            image, mask = _transform(tile.image, tile.valid_mask, transform_name)
            output = _predict_one(adapter, tile, image, mask)
            predictions.append(_inverse(output.probability_map, transform_name))
    if mode in {"multi_scale", "enhanced"}:
        scales: Iterable[float] = MULTI_SCALE_FACTORS
        if mode == "enhanced":
            scales = (0.75, 1.25)
        for scale in scales:
            image, mask = _scaled_canvas(tile.image, tile.valid_mask, scale)
            output = _predict_one(adapter, tile, image, mask)
            predictions.append(output.probability_map)
    fused = np.mean(np.stack(predictions, axis=0), axis=0, dtype=np.float32)
    fused[~tile.valid_mask] = np.float32(0.0)
    if not np.isfinite(fused).all() or fused.shape != tile.valid_mask.shape:
        raise ValueError("La fusion enhanced a produit une carte invalide.")
    return ModelOutput(probability_map=fused.astype(np.float32, copy=False), inference_time_ms=(time.perf_counter() - started) * 1000.0)
