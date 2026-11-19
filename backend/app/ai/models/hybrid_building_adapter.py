from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from ..config.building_model_catalog import model_identity
from ..services.tiling_service import PreparedTile
from .base_model_adapter import AIModelError, BaseModelAdapter, ModelOutput


class HybridBuildingModelAdapter(BaseModelAdapter):
    """Experimental C + D adapter. Raster result routes fuse global binary masks."""

    MODEL_ID = "hybrid_model_c_model_d"
    MODEL_NAME = "Hybrid DeepLabV3 + WHU"
    MODEL_VERSION = "hybrid-union-v1"
    MODEL_ARCHITECTURE = "DeepLabV3 ResNet-50 + WHU U-Net++ EfficientNet-B4"
    STATUS = model_identity(MODEL_ID)["status"]
    preferred_tile_size = 512
    preferred_overlap_ratio = 0.5
    preferred_batch_size = 1

    def __init__(self, model_c: BaseModelAdapter, model_d: BaseModelAdapter) -> None:
        self.model_c = model_c
        self.model_d = model_d
        self._prepared: dict[tuple[str | None, str], tuple[PreparedTile, PreparedTile]] = {}
        self._cache_lock = threading.RLock()
        self._fusion_time_ms = 0.0

    def load(self) -> None:
        # Both component models are required. Any failure aborts Model E.
        self.model_c.load()
        self.model_d.load()

    def is_loaded(self) -> bool:
        return self.model_c.is_loaded() and self.model_d.is_loaded()

    def prepare_inference_tiles(
        self,
        tiles: Iterable[PreparedTile],
        raster_path: Path,
        *,
        raster_id: str,
        band_indexes: tuple[int, int, int],
    ) -> Iterator[PreparedTile]:
        image_min, image_max = self.model_c._image_minmax(  # type: ignore[attr-defined]
            Path(raster_path), raster_id=raster_id, band_indexes=band_indexes
        )
        for tile in tiles:
            if tile.metadata.skip_inference:
                yield tile
                continue
            c_tile = self.model_c.normalize_tile(  # type: ignore[attr-defined]
                tile, image_min=image_min, image_max=image_max
            )
            key = (tile.metadata.source_raster_id, tile.metadata.tile_id)
            with self._cache_lock:
                self._prepared[key] = (c_tile, tile)
            yield tile

    def predict(self, tile: PreparedTile) -> ModelOutput:
        key = (tile.metadata.source_raster_id, tile.metadata.tile_id)
        with self._cache_lock:
            pair = self._prepared.pop(key, None)
        if pair is None:
            raise AIModelError(
                "HYBRID_INPUT_NOT_PREPARED",
                "Les deux entrées du modèle hybride n’ont pas été préparées pour cette tuile.",
            )
        c_tile, d_tile = pair
        # Propagate C or D failures; never silently continue with a single model.
        c_output = self.model_c.predict(c_tile)
        d_output = self.model_d.predict(d_tile)
        if c_output.probability_map.shape != d_output.probability_map.shape:
            raise AIModelError("HYBRID_ALIGNMENT_ERROR", "Les masques MODEL_C et MODEL_D n’ont pas la même forme.")
        if not np.array_equal(c_tile.valid_mask, d_tile.valid_mask):
            raise AIModelError("HYBRID_ALIGNMENT_ERROR", "Les valid_mask MODEL_C et MODEL_D diffèrent.")
        fusion_started = time.perf_counter()
        # For a common threshold, max(pC, pD) is equivalent to binary C OR D.
        probability = np.maximum(c_output.probability_map, d_output.probability_map).astype(np.float32, copy=False)
        probability[~tile.valid_mask] = np.float32(0.0)
        fusion_ms = (time.perf_counter() - fusion_started) * 1000.0
        self._fusion_time_ms += fusion_ms
        details = {
            "status": self.STATUS,
            "fusion_method": "UNION",
            "model_c_inference_time_ms": float(c_output.inference_time_ms),
            "model_d_inference_time_ms": float(d_output.inference_time_ms),
            "fusion_time_ms": float(fusion_ms),
        }
        return ModelOutput(
            probability,
            float(c_output.inference_time_ms + d_output.inference_time_ms + fusion_ms),
            details,
        )

    def get_model_info(self) -> dict[str, Any]:
        c_info = self.model_c.get_model_info()
        d_info = self.model_d.get_model_info()
        return {
            "model_id": self.MODEL_ID,
            "model_name": self.MODEL_NAME,
            "display_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "model_architecture": self.MODEL_ARCHITECTURE,
            "preferred_tile_size": self.preferred_tile_size,
            "preferred_overlap_ratio": self.preferred_overlap_ratio,
            "preprocessing_profile": "component_specific:C_full_raster_minmax;D_rgb_0_1",
            "runtime": "composite",
            "device": "cpu",
            "loaded": self.is_loaded(),
            "model_mode": self.STATUS,
            "experimental_only": True,
            "threshold_status": "NOT_CALIBRATED",
            "component_models": [
                {
                    "role": "MODEL_C",
                    "model_id": c_info.get("model_id"),
                    "identifier": c_info.get("model_version"),
                    "engine": c_info.get("runtime"),
                    "checkpoint_sha256": c_info.get("checkpoint_sha256"),
                    "loaded": c_info.get("loaded", False),
                    "model_load_time_ms": c_info.get("model_load_time_ms", 0.0),
                },
                {
                    "role": "MODEL_D",
                    "model_id": d_info.get("model_id"),
                    "identifier": d_info.get("model_version"),
                    "engine": d_info.get("runtime"),
                    "checkpoint_sha256": d_info.get("checkpoint_sha256"),
                    "loaded": d_info.get("loaded", False),
                    "model_load_time_ms": d_info.get("model_load_time_ms", 0.0),
                },
            ],
            "fusion_method": "UNION",
            "fusion_time_ms": float(self._fusion_time_ms),
            **model_identity("hybrid_model_c_model_d", "composite"),
        }

    def close(self) -> None:
        with self._cache_lock:
            self._prepared.clear()
        self.model_c.close()
        self.model_d.close()

