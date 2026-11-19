from __future__ import annotations

import numpy as np
import pytest

from app.ai.models.base_model_adapter import AIModelError, ModelOutput
from app.ai.models.hybrid_building_adapter import HybridBuildingModelAdapter
from app.ai.registry.model_registry import create_default_model_registry
from app.ai.schemas.prediction_schemas import TilePrediction, TilePredictionMetadata
from app.ai.schemas.tile_schemas import TileBounds, TileMetadata
from app.ai.services.postprocessing_service import (
    PostProcessingConfig,
    PostProcessingService,
    RasterGrid,
)
from app.ai.services.tiling_service import PreparedTile


class FakeAdapter:
    def __init__(self, model_id: str, probability: np.ndarray, *, fail: bool = False) -> None:
        self.model_id = model_id
        self.probability = probability
        self.fail = fail
        self.calls = 0

    def load(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return True

    def predict(self, tile: PreparedTile) -> ModelOutput:
        self.calls += 1
        if self.fail:
            raise AIModelError("INFERENCE_FAILED", f"{self.model_id} failed")
        return ModelOutput(self.probability.copy(), 12.0)

    def get_model_info(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_version": "test-v1",
            "model_name": self.model_id,
            "model_architecture": self.model_id,
            "runtime": "test",
            "checkpoint_sha256": f"hash-{self.model_id}",
            "loaded": True,
        }

    def close(self) -> None:
        return None


def make_tile(tile_size: int = 4) -> PreparedTile:
    bounds = TileBounds(left=0, bottom=0, right=tile_size, top=tile_size)
    metadata = TileMetadata(
        tile_id="hybrid-test-tile",
        row_index=0,
        col_index=0,
        row_offset=0,
        col_offset=0,
        width=tile_size,
        height=tile_size,
        valid_width=tile_size,
        valid_height=tile_size,
        tile_size=tile_size,
        overlap_pixels=0,
        stride=tile_size,
        padding_top=0,
        padding_bottom=0,
        padding_left=0,
        padding_right=0,
        valid_pixel_ratio=1.0,
        skip_inference=False,
        transform=[1, 0, 0, 0, -1, tile_size, 0, 0, 1],
        bounds=bounds,
        crs="EPSG:32637",
        source_raster_id="hybrid-test-raster",
        source_profile="rgb_orthophoto_uint8_v1",
    )
    return PreparedTile(
        image=np.full((3, tile_size, tile_size), 0.5, dtype=np.float32),
        source_rgb=np.full((3, tile_size, tile_size), 128, dtype=np.uint8),
        valid_mask=np.ones((tile_size, tile_size), dtype=np.bool_),
        metadata=metadata,
    )


def make_prediction(model_id: str, probability: np.ndarray) -> TilePrediction:
    tile = make_tile(probability.shape[0])
    binary = probability >= 0.5
    metadata = TilePredictionMetadata(
        tile_id=tile.metadata.tile_id,
        raster_id="hybrid-test-raster",
        model_name=model_id,
        model_version="test-v1",
        model_id=model_id,
        model_architecture=model_id,
        runtime="test",
        device="cpu",
        model_mode="EXPERIMENTAL",
        status="processed",
        threshold=0.5,
        valid_width=probability.shape[1],
        valid_height=probability.shape[0],
        valid_pixel_count=int(tile.valid_mask.sum()),
        valid_pixel_ratio=1.0,
        prediction_shape=list(probability.shape),
        positive_pixel_count=int(binary.sum()),
        positive_pixel_ratio=float(binary.mean()),
        inference_time_ms=12.0,
        source_type="orthophoto_local",
        source_resolution=1.0,
        preprocessing_profile="test",
        tile_size=probability.shape[0],
    )
    return TilePrediction(metadata, probability, binary.astype(np.uint8), tile.valid_mask, tile.metadata)


def test_model_e_requires_both_models_and_fuses_component_probabilities() -> None:
    c_probability = np.zeros((4, 4), dtype=np.float32)
    d_probability = np.zeros((4, 4), dtype=np.float32)
    c_probability[:2, :2] = 0.7
    d_probability[2:, 2:] = 0.8
    c = FakeAdapter("spacenet2_deeplab", c_probability)
    d = FakeAdapter("whu_unetplusplus_effb4", d_probability)
    hybrid = HybridBuildingModelAdapter(c, d)
    tile = make_tile()
    hybrid._prepared[(tile.metadata.source_raster_id, tile.metadata.tile_id)] = (tile, tile)

    output = hybrid.predict(tile)

    expected_union = np.logical_or(c_probability >= 0.5, d_probability >= 0.5)
    assert np.array_equal(output.probability_map >= 0.5, expected_union)
    assert c.calls == d.calls == 1
    assert output.details["fusion_method"] == "UNION"


def test_model_e_propagates_component_failure_without_fallback() -> None:
    c = FakeAdapter("spacenet2_deeplab", np.zeros((4, 4), dtype=np.float32))
    d = FakeAdapter("whu_unetplusplus_effb4", np.zeros((4, 4), dtype=np.float32), fail=True)
    hybrid = HybridBuildingModelAdapter(c, d)
    tile = make_tile()
    hybrid._prepared[(tile.metadata.source_raster_id, tile.metadata.tile_id)] = (tile, tile)

    with pytest.raises(AIModelError, match="WHU|whu_unetplusplus_effb4"):
        hybrid.predict(tile)
    assert c.calls == d.calls == 1


def test_raster_level_mask_union_is_passed_to_one_cleanup_stage() -> None:
    c_probability = np.zeros((4, 4), dtype=np.float32)
    d_probability = np.zeros((4, 4), dtype=np.float32)
    c_probability[0:2, 0:2] = 0.9
    d_probability[2:4, 2:4] = 0.9
    service = PostProcessingService()
    grid = RasterGrid(
        raster_id="hybrid-test-raster",
        width=4,
        height=4,
        crs="EPSG:32637",
        transform=(1, 0, 0, 0, -1, 4, 0, 0, 1),
        bounds={"left": 0, "bottom": 0, "right": 4, "top": 4},
    )
    mask_c = service.threshold_model_mask([make_prediction("spacenet2_deeplab", c_probability)], grid=grid, threshold=0.5)
    mask_d = service.threshold_model_mask([make_prediction("whu_unetplusplus_effb4", d_probability)], grid=grid, threshold=0.5)
    union = np.logical_or(mask_c.global_binary_mask, mask_d.global_binary_mask)
    result = service.process_binary_mask(
        union,
        mask_c.global_valid_mask,
        grid=grid,
        config=PostProcessingConfig(min_object_pixels=0),
        model_name="Hybrid DeepLabV3 + WHU",
        model_version="test-v1",
        model_id="hybrid_model_c_model_d",
        model_architecture="DeepLabV3 + WHU U-Net++",
        model_metadata={"status": "HYBRID_EXPERIMENTAL", "fusion_method": "UNION"},
        source_type="orthophoto_local",
        tiles_total=1,
        tiles_processed=1,
        tiles_skipped=0,
    )
    try:
        assert np.array_equal(result.global_binary_mask, union.astype(np.uint8))
        assert result.model_metadata["fusion_method"] == "UNION"
        assert result.width == result.height == 4
    finally:
        mask_c.cleanup()
        mask_d.cleanup()
        result.cleanup()


def test_model_registry_keeps_model_c_default_and_model_e_experimental() -> None:
    registry = create_default_model_registry()
    try:
        models = {entry["id"]: entry for entry in registry.list_models("building")}
        assert registry._default_model_ids["building"] == "spacenet2_deeplab"
        assert models["spacenet2_deeplab"]["default"] is True
        assert models["hybrid_model_c_model_d"]["default"] is False
        assert models["hybrid_model_c_model_d"]["status"] == "BENCHMARK_ONLY"
        assert models["whu_unetplusplus_effb4"]["status"] == "EXPERIMENTAL"
    finally:
        registry.close_all()
