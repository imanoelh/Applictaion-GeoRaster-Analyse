from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from app.ai.api.ai_inference_routes import get_inference_service
from app.ai.api.ai_postprocessing_routes import (
    get_postprocessing_service,
    router as postprocessing_router,
)
from app.ai.api.ai_raster_routes import get_ai_raster_service, get_tiling_service
from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.models.base_model_adapter import BaseModelAdapter, ModelOutput
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.registry.model_registry import ModelRegistry
from app.ai.schemas.prediction_schemas import TilePrediction, TilePredictionMetadata
from app.ai.schemas.tile_schemas import TileMetadata
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.inference_service import InferenceService
from app.ai.services.postprocessing_service import (
    PostProcessingConfig,
    PostProcessingService,
    RasterGrid,
)
from app.ai.services.tiling_service import PreparedTile, TilingService


def grid(width: int, height: int, *, raster_id: str = "test-raster") -> RasterGrid:
    return RasterGrid(
        raster_id=raster_id,
        width=width,
        height=height,
        crs="EPSG:32638",
        transform=(0.5, 0.0, 500_000.0, 0.0, -0.5, 2_800_000.0, 0.0, 0.0, 1.0),
        bounds={
            "left": 500_000.0,
            "bottom": 2_800_000.0 - height * 0.5,
            "right": 500_000.0 + width * 0.5,
            "top": 2_800_000.0,
        },
    )


def prediction(
    probability: np.ndarray | None,
    *,
    row_offset: int,
    col_offset: int,
    valid_height: int,
    valid_width: int,
    valid_mask: np.ndarray | None = None,
    tile_id: str = "tile_0001",
) -> TilePrediction:
    tile_size = 640 if probability is None else int(probability.shape[0])
    if valid_mask is None:
        valid_mask = np.zeros((tile_size, tile_size), dtype=np.bool_)
        valid_mask[:valid_height, :valid_width] = True
    status = "skipped" if probability is None else "processed"
    binary = None if probability is None else np.logical_and(probability >= 0.5, valid_mask).astype(np.uint8)
    tile_metadata = TileMetadata(
        tile_id=tile_id,
        row_index=0,
        col_index=0,
        row_offset=row_offset,
        col_offset=col_offset,
        width=tile_size,
        height=tile_size,
        valid_width=valid_width,
        valid_height=valid_height,
        tile_size=tile_size,
        overlap_pixels=128 if tile_size == 640 else 2,
        stride=512 if tile_size == 640 else max(1, tile_size - 2),
        padding_top=0,
        padding_bottom=tile_size - valid_height,
        padding_left=0,
        padding_right=tile_size - valid_width,
        valid_pixel_ratio=float(valid_mask[:valid_height, :valid_width].mean()),
        skip_inference=status == "skipped",
        transform=[0.5, 0.0, 500_000.0 + col_offset * 0.5, 0.0, -0.5, 2_800_000.0 - row_offset * 0.5, 0.0, 0.0, 1.0],
        bounds={
            "left": 500_000.0 + col_offset * 0.5,
            "bottom": 2_800_000.0 - (row_offset + valid_height) * 0.5,
            "right": 500_000.0 + (col_offset + valid_width) * 0.5,
            "top": 2_800_000.0 - row_offset * 0.5,
        },
        crs="EPSG:32638",
        source_raster_id="test-raster",
        source_profile="rgb_orthophoto_uint8_v1",
    )
    metadata = TilePredictionMetadata(
        tile_id=tile_id,
        raster_id="test-raster",
        model_name="test-building",
        model_version="test-v1",
        model_architecture="test",
        checkpoint_id=None,
        runtime="test",
        device="cpu",
        model_mode="TEST_ONLY",
        status=status,
        threshold=0.5,
        valid_width=valid_width,
        valid_height=valid_height,
        valid_pixel_count=int(valid_mask.sum()),
        valid_pixel_ratio=tile_metadata.valid_pixel_ratio,
        prediction_shape=[tile_size, tile_size],
        positive_pixel_count=int(binary.sum()) if binary is not None else 0,
        positive_pixel_ratio=0.0,
        inference_time_ms=1.0 if probability is not None else 0.0,
        source_type="orthophoto_local",
        source_resolution=0.5,
    )
    return TilePrediction(
        metadata=metadata,
        probability_map=probability,
        binary_mask=binary,
        valid_mask=valid_mask,
        tile_metadata=tile_metadata,
    )


def config(**overrides: object) -> PostProcessingConfig:
    values: dict[str, object] = {
        "probability_threshold": 0.5,
        "min_object_pixels": 0,
        "max_hole_pixels": 0,
    }
    values.update(overrides)
    return PostProcessingConfig(**values)  # type: ignore[arg-type]


def test_overlap_probability_mean_conflict_is_deterministic() -> None:
    first = np.full((8, 8), 0.8, dtype=np.float32)
    second = np.full((8, 8), 0.6, dtype=np.float32)
    result = PostProcessingService().process(
        [
            prediction(first, row_offset=0, col_offset=0, valid_height=8, valid_width=8),
            prediction(second, row_offset=0, col_offset=6, valid_height=8, valid_width=8, tile_id="tile_0002"),
        ],
        grid=grid(14, 8),
        config=config(probability_threshold=0.65),
    )
    assert result.global_probability_map[3, 6] == pytest.approx(0.7)
    assert result.global_probability_map[3, 7] == pytest.approx(0.7)
    assert result.global_binary_mask[3, 6] == 1
    assert result.postprocessing_config["merge_strategy"] == "uniform_probability_mean"


def test_object_crossing_overlap_is_one_continuous_component() -> None:
    first = np.zeros((8, 8), dtype=np.float32)
    second = np.zeros((8, 8), dtype=np.float32)
    first[2:6, 5:8] = 0.9
    second[2:6, 0:3] = 0.9
    result = PostProcessingService().process(
        [
            prediction(first, row_offset=0, col_offset=0, valid_height=8, valid_width=8),
            prediction(second, row_offset=0, col_offset=6, valid_height=8, valid_width=8, tile_id="tile_0002"),
        ],
        grid=grid(14, 8),
        config=config(),
    )
    assert len(result.components) == 1
    assert result.components[0].bbox == (5, 2, 9, 6)
    assert result.components[0].pixel_count == 16


def test_padding_and_nodata_probabilities_never_survive() -> None:
    probability = np.ones((8, 8), dtype=np.float32)
    valid = np.zeros((8, 8), dtype=np.bool_)
    valid[:5, :6] = True
    valid[2, 3] = False
    result = PostProcessingService().process(
        [
            prediction(
                probability,
                row_offset=0,
                col_offset=0,
                valid_height=5,
                valid_width=6,
                valid_mask=valid,
            )
        ],
        grid=grid(6, 5),
        config=config(),
    )
    assert result.global_binary_mask.shape == (5, 6)
    assert result.global_binary_mask[2, 3] == 0
    assert result.global_probability_map[2, 3] == 0.0
    assert result.positive_pixel_count == 29


def test_small_object_removed_and_sufficient_object_preserved() -> None:
    probability = np.zeros((12, 12), dtype=np.float32)
    probability[2:6, 2:6] = 0.9
    probability[9, 9] = 0.9
    result = PostProcessingService().process(
        [prediction(probability, row_offset=0, col_offset=0, valid_height=12, valid_width=12)],
        grid=grid(12, 12),
        config=config(min_object_pixels=4),
    )
    assert result.global_binary_mask[3, 3] == 1
    assert result.global_binary_mask[9, 9] == 0
    assert result.positive_pixel_count == 16
    assert result.postprocessing_config["small_object_status"] == "NOT_CALIBRATED"


def test_small_hole_filled_but_large_hole_remains() -> None:
    probability = np.zeros((16, 16), dtype=np.float32)
    probability[1:15, 1:15] = 0.9
    probability[4, 4] = 0.0
    probability[8:11, 8:11] = 0.0
    result = PostProcessingService().process(
        [prediction(probability, row_offset=0, col_offset=0, valid_height=16, valid_width=16)],
        grid=grid(16, 16),
        config=config(max_hole_pixels=2),
    )
    assert result.global_binary_mask[4, 4] == 1
    assert not result.global_binary_mask[8:11, 8:11].any()


def test_optional_morphology_is_disabled_by_default_and_respects_valid_mask() -> None:
    mask = np.zeros((9, 9), dtype=np.bool_)
    mask[2:7, 2:7] = True
    mask[4, 4] = False
    mask[0, 0] = True
    valid = np.ones((9, 9), dtype=np.bool_)
    valid[4, 5] = False
    unchanged = PostProcessingService.apply_morphology(mask, valid_mask=valid, config=config())
    assert unchanged[4, 4] == 0
    closed = PostProcessingService.apply_morphology(
        mask,
        valid_mask=valid,
        config=config(closing_enabled=True, morphology_kernel_size=3),
    )
    assert closed[4, 4] == 1
    assert closed[4, 5] == 0


def test_multitile_640_result_matches_original_grid_and_georeferencing() -> None:
    raster_width, raster_height = 900, 700
    probabilities: list[TilePrediction] = []
    for row_offset in (0, 512):
        for col_offset in (0, 512):
            valid_height = min(640, raster_height - row_offset)
            valid_width = min(640, raster_width - col_offset)
            array = np.full((640, 640), 0.75, dtype=np.float32)
            probabilities.append(
                prediction(
                    array,
                    row_offset=row_offset,
                    col_offset=col_offset,
                    valid_height=valid_height,
                    valid_width=valid_width,
                    tile_id=f"tile_{len(probabilities) + 1:04d}",
                )
            )
    source_grid = grid(raster_width, raster_height)
    result = PostProcessingService().process(probabilities, grid=source_grid, config=config())
    assert result.global_probability_map.shape == (raster_height, raster_width)
    assert result.global_binary_mask.shape == (raster_height, raster_width)
    assert result.global_valid_mask.all()
    assert np.allclose(result.global_probability_map, 0.75)
    assert result.crs == source_grid.crs
    assert result.transform == source_grid.transform
    assert result.bounds == source_grid.bounds
    assert result.resolution == pytest.approx((0.5, 0.5))
    assert result.pixel_area == pytest.approx(0.25)


def test_pixel_area_helper_never_assumes_one_pixel_is_one_square_metre() -> None:
    assert PostProcessingService.pixels_to_area(10, resolution_x=0.5, resolution_y=0.25) == pytest.approx(1.25)


class ConstantAdapter(BaseModelAdapter):
    def load(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return True

    def predict(self, tile: PreparedTile) -> ModelOutput:
        probability = np.zeros(tile.valid_mask.shape, dtype=np.float32)
        probability[2:8, 2:8] = 0.9
        probability[~tile.valid_mask] = 0.0
        return ModelOutput(probability_map=probability, inference_time_ms=1.0)

    def get_model_info(self) -> dict[str, object]:
        return {
            "model_name": "constant-test",
            "model_version": "v1",
            "model_architecture": "test",
            "checkpoint_id": None,
            "runtime": "test",
            "device": "cpu",
            "loaded": True,
            "model_mode": "TEST_ONLY",
            "model_load_time_ms": 0.0,
            "load_count": 1,
            "threshold_status": "NOT_CALIBRATED",
        }

    def close(self) -> None:
        return None


def write_orthophoto(path: Path, *, width: int = 20, height: int = 18) -> Path:
    rows, cols = np.indices((height, width))
    data = np.stack(((cols * 5) % 256, (rows * 7) % 256, ((rows + cols) * 3) % 256)).astype(np.uint8)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=3,
        dtype="uint8",
        crs="EPSG:32638",
        transform=from_origin(500_000.0, 2_800_000.0, 0.5, 0.5),
    ) as dataset:
        dataset.write(data)
        dataset.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
        dataset.descriptions = ("R", "G", "B")
    return path


def test_postprocessing_api_is_thin_and_never_serializes_mask_arrays(tmp_path: Path) -> None:
    raster_service = AIRasterService(tmp_path / "cache")
    source = write_orthophoto(tmp_path / "api-ortho.tif")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    registry = ModelRegistry()
    registry.register("building", ConstantAdapter)

    application = FastAPI()
    application.include_router(postprocessing_router)
    application.dependency_overrides[get_ai_raster_service] = lambda: raster_service
    application.dependency_overrides[get_tiling_service] = TilingService
    application.dependency_overrides[get_inference_service] = lambda: InferenceService(registry)
    application.dependency_overrides[get_postprocessing_service] = PostProcessingService
    response = TestClient(application).post(
        "/api/ai/postprocess/building",
        json={"raster_id": prepared.raster_id, "model_id": "unet_resnet34", "min_object_pixels": 0},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_type"] == "building_raster_mask"
    assert body["grid"]["width"] == 20
    assert body["grid"]["height"] == 18
    assert body["grid"]["crs"] == "EPSG:32638"
    serialized = json.dumps(body)
    assert "global_probability_map" not in serialized
    assert "global_binary_mask" not in serialized
    assert "buildings_detected" not in serialized


def test_real_model_probability_maps_reach_global_postprocessing(tmp_path: Path) -> None:
    model_config = BuildingModelConfig.from_env()
    if model_config.checkpoint_path is None or not model_config.checkpoint_path.is_file():
        pytest.skip("REAL_BUILDING_CHECKPOINT_NOT_AVAILABLE")
    source = write_orthophoto(tmp_path / "real-model-ortho.tif", width=700, height=640)
    raster_service = AIRasterService(tmp_path / "cache")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    raster_path, sidecar = raster_service.get_validated_artifact(prepared.raster_id)
    profile, indexes = raster_service.get_preprocessing_context(sidecar)
    tiles = TilingService().iter_tiles(
        raster_path,
        raster_id=prepared.raster_id,
        preprocessing_profile=profile,
        band_indexes=indexes,
    )
    adapter = BuildingModelAdapter(model_config)
    registry = ModelRegistry()
    registry.register("building", lambda: adapter)
    predictions = InferenceService(registry).iter_predictions(tiles, probability_threshold=0.5)
    with rasterio.open(raster_path) as dataset:
        bounds = dataset.bounds
        source_grid = RasterGrid(
            raster_id=prepared.raster_id,
            width=dataset.width,
            height=dataset.height,
            crs=dataset.crs.to_string(),
            transform=tuple(dataset.transform),
            bounds={"left": bounds.left, "bottom": bounds.bottom, "right": bounds.right, "top": bounds.top},
        )
    result = PostProcessingService().process(predictions, grid=source_grid, config=config(min_object_pixels=4))
    assert result.model_mode == "REAL"
    assert result.global_probability_map.shape == (640, 700)
    assert result.global_probability_map.dtype == np.float32
    assert np.isfinite(result.global_probability_map).all()
    assert 0.0 <= float(result.global_probability_map.min()) <= float(result.global_probability_map.max()) <= 1.0
    assert result.global_binary_mask.shape == (640, 700)
    assert result.global_binary_mask.dtype == np.uint8
    assert result.crs == "EPSG:32638"
    adapter.close()


def test_large_raster_uses_disk_backed_global_arrays_and_cleans_up() -> None:
    raster_grid = grid(5001, 5001, raster_id="large-raster")
    tile_probability = np.ones((640, 640), dtype=np.float32)
    result = PostProcessingService(max_global_pixels=25_000_000).process(
        [prediction(tile_probability, row_offset=0, col_offset=0, valid_height=640, valid_width=640)],
        grid=raster_grid,
        config=PostProcessingConfig(min_object_pixels=1),
    )
    assert result.storage_dir is not None
    assert result.global_probability_map.shape == (5001, 5001)
    assert result.global_probability_map[0, 0] == 1.0
    storage_dir = result.storage_dir
    result.cleanup()
    assert storage_dir is not None
    assert not Path(storage_dir).exists()


def test_disk_backed_and_in_memory_fusion_are_equivalent() -> None:
    raster_grid = grid(32, 32, raster_id="equivalence")
    tile_probability = np.full((16, 16), 0.75, dtype=np.float32)
    predictions = [prediction(tile_probability, row_offset=0, col_offset=0, valid_height=16, valid_width=16)]
    in_memory = PostProcessingService(max_global_pixels=10_000).process(
        predictions, grid=raster_grid, config=PostProcessingConfig(min_object_pixels=1)
    )
    disk_backed = PostProcessingService(max_global_pixels=1).process(
        [prediction(tile_probability, row_offset=0, col_offset=0, valid_height=16, valid_width=16)],
        grid=raster_grid,
        config=PostProcessingConfig(min_object_pixels=1),
    )
    np.testing.assert_array_equal(in_memory.global_probability_map, disk_backed.global_probability_map)
    np.testing.assert_array_equal(in_memory.global_binary_mask, disk_backed.global_binary_mask)
    disk_backed.cleanup()
