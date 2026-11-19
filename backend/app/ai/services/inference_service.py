from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np

from ..models.base_model_adapter import AIModelError
from ..registry.model_registry import ModelRegistry
from ..schemas.prediction_schemas import TilePrediction, TilePredictionMetadata
from .tiling_service import PreparedTile
from .enhanced_inference import INFERENCE_MODES, predict_mode


logger = logging.getLogger(__name__)
INTEGRATION_WARNING = (
    "Sentinel-2 10 m valide uniquement l'integration technique. "
    "Le ratio de pixels positifs ne mesure pas la qualite scientifique et ne constitue pas un nombre de batiments."
)


class InferenceService:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def iter_predictions(
        self,
        tiles: Iterable[PreparedTile],
        *,
        object_type: str = "building",
        probability_threshold: float = 0.50,
        inference_mode: str = "standard",
        model_id: str | None = None,
    ) -> Iterator[TilePrediction]:
        if not 0.0 <= probability_threshold <= 1.0:
            raise ValueError("probability_threshold doit etre compris entre 0 et 1.")
        adapter = self.registry.get_selected_model(object_type, model_id)
        if inference_mode not in INFERENCE_MODES:
            raise ValueError(f"Mode d'inference inconnu: {inference_mode}")
        # Resolve unavailable checkpoints before processing any tiles. It also
        # keeps skipped and processed tiles on one stable model identity.
        adapter.load()
        batch_size = (
            max(1, int(getattr(adapter, "preferred_batch_size", 1)))
            if inference_mode == "standard"
            else 1
        )
        pending: list[PreparedTile] = []
        processed_tiles = 0
        for tile in tiles:
            pending.append(tile)
            if len(pending) >= batch_size:
                for prediction in self._predict_batch(
                    adapter, pending, threshold=probability_threshold, inference_mode=inference_mode
                ):
                    processed_tiles += 1
                    if processed_tiles == 1 or processed_tiles % 25 == 0:
                        logger.info("[AI-INFERENCE] progress model=%s tiles=%s", getattr(adapter, "MODEL_ID", model_id or "default"), processed_tiles)
                    yield prediction
                pending = []
        if pending:
            for prediction in self._predict_batch(
                adapter, pending, threshold=probability_threshold, inference_mode=inference_mode
            ):
                processed_tiles += 1
                logger.info("[AI-INFERENCE] progress model=%s tiles=%s", getattr(adapter, "MODEL_ID", model_id or "default"), processed_tiles)
                yield prediction

    def _predict_batch(
        self,
        adapter: Any,
        tiles: list[PreparedTile],
        *,
        threshold: float,
        inference_mode: str,
    ) -> Iterator[TilePrediction]:
        model_info = adapter.get_model_info()
        valid_tiles = [tile for tile in tiles if not tile.metadata.skip_inference]
        if inference_mode == "standard":
            outputs = iter(adapter.predict_batch(valid_tiles)) if valid_tiles else iter(())
        else:
            outputs = iter(predict_mode(adapter, tile, inference_mode) for tile in valid_tiles)
        for tile in tiles:
            if tile.metadata.skip_inference:
                logger.info("[AI-INFERENCE] skipped tile=%s", tile.metadata.tile_id)
                yield self._skipped_prediction(tile, model_info, threshold)
                continue
            try:
                output = next(outputs)
            except StopIteration as exc:
                raise AIModelError("MODEL_OUTPUT_INVALID", "Le modele n'a pas renvoye toutes les tuiles.") from exc
            yield self._processed_prediction(tile, output, model_info, threshold)
        try:
            next(outputs)
        except StopIteration:
            return
        raise AIModelError("MODEL_OUTPUT_INVALID", "Le modele a renvoye trop de tuiles.")

    @staticmethod
    def _processed_prediction(
        tile: PreparedTile, output: Any, model_info: dict[str, Any], threshold: float
    ) -> TilePrediction:
        probability = output.probability_map
        if probability.shape != tile.valid_mask.shape:
            raise AIModelError(
                "MODEL_OUTPUT_INVALID",
                "La carte de probabilite ne correspond pas au valid_mask.",
            )
        probability[~tile.valid_mask] = np.float32(0.0)
        binary_mask = np.logical_and(
            probability >= np.float32(threshold),
            tile.valid_mask,
        ).astype(np.uint8)
        valid_pixel_count = int(tile.valid_mask.sum())
        positive_pixel_count = int(binary_mask.sum())
        positive_ratio = float(positive_pixel_count) / float(valid_pixel_count) if valid_pixel_count else 0.0
        metadata = TilePredictionMetadata(
            tile_id=tile.metadata.tile_id,
            raster_id=tile.metadata.source_raster_id,
            model_name=str(model_info["model_name"]),
            model_id=str(model_info.get("model_id") or "unet_resnet34"),
            model_version=str(model_info["model_version"]),
            model_architecture=InferenceService._model_architecture(model_info),
            model_checkpoint_hash=model_info.get("checkpoint_sha256"),
            preprocessing_profile=model_info.get("preprocessing_profile"),
            tile_size=tile.metadata.tile_size,
            checkpoint_id=model_info.get("checkpoint_id"),
            runtime=str(model_info["runtime"]),
            device=str(model_info["device"]),
            model_mode=str(model_info["model_mode"]),
            status="processed",
            threshold=threshold,
            valid_width=tile.metadata.valid_width,
            valid_height=tile.metadata.valid_height,
            valid_pixel_count=valid_pixel_count,
            valid_pixel_ratio=tile.metadata.valid_pixel_ratio,
            prediction_shape=list(probability.shape),
            positive_pixel_count=positive_pixel_count,
            positive_pixel_ratio=positive_ratio,
            inference_time_ms=output.inference_time_ms,
            source_type=InferenceService._source_type(tile),
            source_resolution=InferenceService._source_resolution(tile),
            model_details=dict(getattr(output, "details", {}) or {}),
        )
        logger.info("[AI-INFERENCE] completed tile=%s time_ms=%.3f", tile.metadata.tile_id, output.inference_time_ms)
        return TilePrediction(
            metadata=metadata,
            probability_map=probability,
            binary_mask=binary_mask,
            valid_mask=tile.valid_mask,
            tile_metadata=tile.metadata,
        )

    def summarize(
        self,
        tiles: Iterable[PreparedTile],
        *,
        object_type: str = "building",
        probability_threshold: float = 0.50,
        inference_mode: str = "standard",
        model_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        total = processed = skipped = positive_pixels = valid_pixels = 0
        total_inference_ms = 0.0
        min_inference_ms: float | None = None
        max_inference_ms: float | None = None
        for prediction in self.iter_predictions(
            tiles,
            object_type=object_type,
            probability_threshold=probability_threshold,
            inference_mode=inference_mode,
            model_id=model_id,
        ):
            total += 1
            if prediction.metadata.status == "skipped":
                skipped += 1
            else:
                processed += 1
                positive_pixels += prediction.metadata.positive_pixel_count
                valid_pixels += prediction.metadata.valid_pixel_count
                total_inference_ms += prediction.metadata.inference_time_ms
                min_inference_ms = (
                    prediction.metadata.inference_time_ms
                    if min_inference_ms is None
                    else min(min_inference_ms, prediction.metadata.inference_time_ms)
                )
                max_inference_ms = (
                    prediction.metadata.inference_time_ms
                    if max_inference_ms is None
                    else max(max_inference_ms, prediction.metadata.inference_time_ms)
                )
            # The in-memory maps intentionally leave scope before the next tile.
        pipeline_ms = (time.perf_counter() - started) * 1000.0
        adapter = self.registry.get_selected_model(object_type, model_id)
        info = adapter.get_model_info()
        positive_ratio = float(positive_pixels) / float(valid_pixels) if valid_pixels else 0.0
        return {
            "success": True,
            "object_type": object_type,
            "quality_mode": (
                "real_model_unvalidated"
                if info["model_mode"] in {"REAL", "EXPERIMENTAL"}
                else "integration_test"
            ),
            "warning": INTEGRATION_WARNING,
            "model": {
                "id": info.get("model_id") or "unet_resnet34",
                "name": info["model_name"],
                "version": info["model_version"],
                "architecture": self._model_architecture(info),
                "checkpoint_hash": info.get("checkpoint_sha256"),
                "preprocessing_profile": info.get("preprocessing_profile"),
                "input_size": info.get("preferred_tile_size") or info.get("input_size"),
                "checkpoint_id": info.get("checkpoint_id"),
                "runtime": info["runtime"],
                "device": info["device"],
                "loaded": info["loaded"],
                "model_mode": info["model_mode"],
                "threshold_status": info.get("threshold_status", "NOT_CALIBRATED"),
            },
            "tiles": {"total": total, "processed": processed, "skipped": skipped},
            "prediction": {
                "threshold": probability_threshold,
                "inference_mode": inference_mode,
                "positive_pixels": positive_pixels,
                "valid_pixels": valid_pixels,
                "positive_ratio": positive_ratio,
            },
            "performance": {
                "model_load_time_ms": float(info["model_load_time_ms"]),
                "total_inference_time_ms": total_inference_ms,
                "average_tile_inference_time_ms": total_inference_ms / processed if processed else 0.0,
                "min_inference_time_ms": min_inference_ms or 0.0,
                "max_inference_time_ms": max_inference_ms or 0.0,
                "total_pipeline_time_ms": pipeline_ms,
                "tiles_per_second": processed / (pipeline_ms / 1000.0) if processed and pipeline_ms > 0 else None,
            },
        }

    @staticmethod
    def _skipped_prediction(
        tile: PreparedTile,
        model_info: dict[str, Any],
        threshold: float,
    ) -> TilePrediction:
        metadata = TilePredictionMetadata(
            tile_id=tile.metadata.tile_id,
            raster_id=tile.metadata.source_raster_id,
            model_name=str(model_info["model_name"]),
            model_version=str(model_info["model_version"]),
            model_id=str(model_info.get("model_id") or "unet_resnet34"),
            model_architecture=InferenceService._model_architecture(model_info),
            model_checkpoint_hash=model_info.get("checkpoint_sha256"),
            preprocessing_profile=model_info.get("preprocessing_profile"),
            tile_size=tile.metadata.tile_size,
            checkpoint_id=model_info.get("checkpoint_id"),
            runtime=str(model_info["runtime"]),
            device=str(model_info["device"]),
            model_mode=str(model_info["model_mode"]),
            status="skipped",
            reason="insufficient_valid_pixels",
            threshold=threshold,
            valid_width=tile.metadata.valid_width,
            valid_height=tile.metadata.valid_height,
            valid_pixel_count=int(tile.valid_mask.sum()),
            valid_pixel_ratio=tile.metadata.valid_pixel_ratio,
            prediction_shape=list(tile.valid_mask.shape),
            positive_pixel_count=0,
            positive_pixel_ratio=0.0,
            inference_time_ms=0.0,
            source_type=InferenceService._source_type(tile),
            source_resolution=InferenceService._source_resolution(tile),
        )
        return TilePrediction(
            metadata=metadata,
            probability_map=None,
            binary_mask=None,
            valid_mask=tile.valid_mask,
            tile_metadata=tile.metadata,
        )

    @staticmethod
    def _source_type(tile: PreparedTile) -> str | None:
        profile = tile.metadata.source_profile
        if profile == "rgb_orthophoto_uint8_v1":
            return "orthophoto_local"
        if profile == "sentinel2_sr_v1":
            return "sentinel2_gee"
        return None

    @staticmethod
    def _model_architecture(model_info: dict[str, Any]) -> str | None:
        if model_info.get("model_id") == "spacenet2_deeplab":
            return "DeepLabV3 ResNet-50"
        architecture = model_info.get("model_architecture")
        return str(architecture) if architecture is not None else None

    @staticmethod
    def _source_resolution(tile: PreparedTile) -> float | None:
        try:
            a, b, _c, d, e, _f = tile.metadata.transform[:6]
            resolution_x = float((a * a + d * d) ** 0.5)
            resolution_y = float((b * b + e * e) ** 0.5)
            return (resolution_x + resolution_y) / 2.0
        except (TypeError, ValueError, IndexError):
            return None

