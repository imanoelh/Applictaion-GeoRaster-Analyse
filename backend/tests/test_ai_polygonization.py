from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from app.ai.api.ai_inference_routes import get_inference_service
from app.ai.api.ai_postprocessing_routes import get_postprocessing_service
from app.ai.api.ai_raster_routes import get_ai_raster_service, get_tiling_service
from app.ai.api.ai_vectorization_routes import (
    get_polygonization_service,
    router as vectorization_router,
)
from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.registry.model_registry import ModelRegistry
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.building_polygonization_service import (
    BuildingPolygonizationService,
    PolygonizationConfig,
)
from app.ai.services.inference_service import InferenceService
from app.ai.services.postprocessing_service import (
    BuildingMaskResult,
    PostProcessingConfig,
    PostProcessingService,
    RasterGrid,
)
from app.ai.services.tiling_service import TilingService
from tests.test_ai_postprocessing import ConstantAdapter, write_orthophoto


def mask_result(
    mask: np.ndarray,
    *,
    valid: np.ndarray | None = None,
    transform: tuple[float, ...] | None = None,
    crs: str = "EPSG:32638",
) -> BuildingMaskResult:
    height, width = mask.shape
    affine = from_origin(100.0, 200.0, 0.25, 0.25) if transform is None else Affine(*transform[:6])
    transform_values = tuple(float(value) for value in tuple(affine))
    valid_mask = np.ones(mask.shape, dtype=np.bool_) if valid is None else valid.astype(np.bool_)
    binary = mask.astype(np.uint8)
    binary[~valid_mask] = 0
    left, top = affine * (0, 0)
    right, bottom = affine * (width, height)
    return BuildingMaskResult(
        raster_id="polygon-test",
        source_type="orthophoto_local",
        model_name="test-building",
        model_version="test-v1",
        model_mode="TEST_ONLY",
        threshold=0.5,
        width=width,
        height=height,
        crs=crs,
        transform=transform_values,
        bounds={
            "left": min(left, right),
            "bottom": min(bottom, top),
            "right": max(left, right),
            "top": max(bottom, top),
        },
        resolution=(0.25, 0.25),
        pixel_area=0.0625,
        positive_pixel_count=int(binary.sum()),
        positive_pixel_ratio=float(binary.sum() / valid_mask.sum()) if valid_mask.any() else 0.0,
        valid_pixel_count=int(valid_mask.sum()),
        tiles_total=1,
        tiles_processed=1,
        tiles_skipped=0,
        postprocessing_config={"probability_threshold": 0.5},
        processing_time_ms=1.0,
        estimated_global_memory_bytes=height * width * 16,
        global_probability_map=binary.astype(np.float32),
        global_binary_mask=binary,
        global_valid_mask=valid_mask,
        components=(),
    )


def test_rectangle_georeferencing_area_centroid_bbox_and_perimeter() -> None:
    mask = np.zeros((30, 40), dtype=np.uint8)
    mask[5:15, 10:30] = 1
    result = BuildingPolygonizationService().polygonize(mask_result(mask))
    assert result.feature_count == 1
    feature = result.building_features[0]
    assert feature.building_id == "building_000001"
    assert feature.geometry_type == "Polygon"
    assert feature.pixel_count == 200
    assert feature.area_map_units == pytest.approx(12.5)
    assert feature.area_m2 == pytest.approx(12.5)
    assert feature.perimeter_map_units == pytest.approx(15.0)
    assert feature.centroid_x == pytest.approx(105.0)
    assert feature.centroid_y == pytest.approx(197.5)
    assert feature.bbox == pytest.approx((102.5, 196.25, 107.5, 198.75))
    assert result.crs == "EPSG:32638"


def test_two_buildings_are_not_merged_and_ids_are_spatially_stable() -> None:
    mask = np.zeros((20, 30), dtype=np.uint8)
    mask[2:6, 3:8] = 1
    mask[12:18, 20:27] = 1
    result = BuildingPolygonizationService().polygonize(mask_result(mask))
    assert result.feature_count == 2
    assert [item.building_id for item in result.building_features] == [
        "building_000001",
        "building_000002",
    ]
    assert [item.pixel_count for item in result.building_features] == [20, 42]
    assert result.building_features[0].centroid_y > result.building_features[1].centroid_y


def test_object_crossing_old_tile_boundary_is_one_geometry() -> None:
    mask = np.zeros((24, 700), dtype=np.uint8)
    mask[6:18, 500:525] = 1
    result = BuildingPolygonizationService().polygonize(mask_result(mask))
    assert result.feature_count == 1
    assert result.building_features[0].pixel_count == 300


def test_significant_hole_is_preserved() -> None:
    mask = np.zeros((24, 24), dtype=np.uint8)
    mask[2:22, 2:22] = 1
    mask[8:14, 8:14] = 0
    result = BuildingPolygonizationService().polygonize(mask_result(mask))
    feature = result.building_features[0]
    assert feature.geometry_type == "Polygon"
    assert len(feature.geometry.interiors) == 1
    assert feature.pixel_count == 364
    assert feature.area_map_units == pytest.approx(22.75)


def test_raster_edge_and_defensive_valid_mask_are_respected() -> None:
    mask = np.zeros((12, 14), dtype=np.uint8)
    mask[0:4, 0:5] = 1
    mask[7:10, 8:12] = 1
    valid = np.ones(mask.shape, dtype=np.bool_)
    valid[7:10, 8:12] = False
    source = mask_result(mask, valid=valid)
    # Simulate an upstream internal mistake after construction: polygonization
    # must still intersect the binary mask with global_valid_mask.
    source.global_binary_mask[7:10, 8:12] = 1
    result = BuildingPolygonizationService().polygonize(source)
    assert result.feature_count == 1
    assert result.building_features[0].bbox == pytest.approx((100.0, 199.0, 101.25, 200.0))
    bounds = result.building_features[0].bbox
    assert source.bounds["left"] <= bounds[0] <= bounds[2] <= source.bounds["right"]
    assert source.bounds["bottom"] <= bounds[1] <= bounds[3] <= source.bounds["top"]


def test_connectivity_is_explicit_and_configurable() -> None:
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[1, 1] = 1
    mask[2, 2] = 1
    service = BuildingPolygonizationService()
    four = service.polygonize(mask_result(mask), config=PolygonizationConfig(polygon_connectivity=4))
    eight = service.polygonize(mask_result(mask), config=PolygonizationConfig(polygon_connectivity=8))
    assert four.feature_count == 2
    assert eight.feature_count == 1
    assert eight.building_features[0].geometry_type == "MultiPolygon"


def test_invalid_geometry_is_repaired_without_uncontrolled_failure() -> None:
    bow_tie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])
    assert not bow_tie.is_valid
    repaired = BuildingPolygonizationService._validated_polygonal_geometry(bow_tie)
    assert repaired is not None
    assert repaired.is_valid
    assert repaired.geom_type == "MultiPolygon"


def test_polygonization_is_deterministic() -> None:
    mask = np.zeros((18, 22), dtype=np.uint8)
    mask[1:5, 14:19] = 1
    mask[9:16, 2:8] = 1
    service = BuildingPolygonizationService()
    first = service.polygonize(mask_result(mask))
    second = service.polygonize(mask_result(mask))
    assert [item.building_id for item in first.building_features] == [
        item.building_id for item in second.building_features
    ]
    assert [item.geometry.wkb_hex for item in first.building_features] == [
        item.geometry.wkb_hex for item in second.building_features
    ]


def test_geographic_crs_gets_local_metric_measurements_without_mutating_native_geometry() -> None:
    mask = np.ones((2, 3), dtype=np.uint8)
    geographic_transform = tuple(from_origin(-7.0, 34.0, 0.0001, 0.0001))
    result = BuildingPolygonizationService().polygonize(
        mask_result(mask, transform=geographic_transform, crs="EPSG:4326")
    )
    assert result.total_area_m2 is not None and result.total_area_m2 > 0
    assert result.building_features[0].area_m2 is not None
    assert result.building_features[0].perimeter_m is not None


def test_vectorization_api_is_thin_and_geojson_is_opt_in(tmp_path: Path) -> None:
    raster_service = AIRasterService(tmp_path / "cache")
    source = write_orthophoto(tmp_path / "api-vector-ortho.tif")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    registry = ModelRegistry()
    registry.register("building", ConstantAdapter)
    application = FastAPI()
    application.include_router(vectorization_router)
    application.dependency_overrides[get_ai_raster_service] = lambda: raster_service
    application.dependency_overrides[get_tiling_service] = TilingService
    application.dependency_overrides[get_inference_service] = lambda: InferenceService(registry)
    application.dependency_overrides[get_postprocessing_service] = PostProcessingService
    application.dependency_overrides[get_polygonization_service] = BuildingPolygonizationService
    client = TestClient(application)

    response = client.post(
        "/api/ai/vectorize/building",
        json={"raster_id": prepared.raster_id, "model_id": "unet_resnet34", "min_object_pixels": 0},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_type"] == "building_vector_candidates"
    assert body["scientific_accuracy"] == "NOT_VALIDATED"
    assert body["vectorization"]["feature_count"] == 1
    assert body["geojson"] is None
    assert '"features"' not in json.dumps(body)

    with_geojson = client.post(
        "/api/ai/vectorize/building",
        json={"raster_id": prepared.raster_id, "model_id": "unet_resnet34", "min_object_pixels": 0, "include_geojson": True},
    )
    assert with_geojson.status_code == 200
    assert with_geojson.json()["geojson"]["type"] == "FeatureCollection"


def test_real_model_to_mask_to_polygonization_smoke(tmp_path: Path) -> None:
    model_config = BuildingModelConfig.from_env()
    if model_config.checkpoint_path is None or not model_config.checkpoint_path.is_file():
        pytest.skip("REAL_BUILDING_CHECKPOINT_NOT_AVAILABLE")
    source = write_orthophoto(tmp_path / "real-vector-ortho.tif", width=700, height=640)
    raster_service = AIRasterService(tmp_path / "cache")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    raster_path, sidecar = raster_service.get_validated_artifact(prepared.raster_id)
    profile, indexes = raster_service.get_preprocessing_context(sidecar)
    adapter = BuildingModelAdapter(model_config)
    registry = ModelRegistry()
    registry.register("building", lambda: adapter)
    predictions = InferenceService(registry).iter_predictions(
        TilingService().iter_tiles(
            raster_path,
            raster_id=prepared.raster_id,
            preprocessing_profile=profile,
            band_indexes=indexes,
        ),
        probability_threshold=0.5,
    )
    with rasterio.open(raster_path) as dataset:
        bounds = dataset.bounds
        grid = RasterGrid(
            raster_id=prepared.raster_id,
            width=dataset.width,
            height=dataset.height,
            crs=dataset.crs.to_string(),
            transform=tuple(dataset.transform),
            bounds={"left": bounds.left, "bottom": bounds.bottom, "right": bounds.right, "top": bounds.top},
        )
    raster_result = PostProcessingService().process(
        predictions,
        grid=grid,
        config=PostProcessingConfig(),
    )
    vector_result = BuildingPolygonizationService().polygonize(raster_result)
    assert raster_result.model_mode == "REAL"
    assert vector_result.raster_id == prepared.raster_id
    assert vector_result.crs == "EPSG:32638"
    assert all(feature.geometry.is_valid for feature in vector_result.building_features)
    adapter.close()
