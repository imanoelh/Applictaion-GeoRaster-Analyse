from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin
from rasterio.warp import transform
from shapely.geometry import shape

from app.ai.api.ai_inference_routes import get_inference_service
from app.ai.api.ai_postprocessing_routes import get_postprocessing_service
from app.ai.api.ai_raster_routes import get_ai_raster_service, get_tiling_service
from app.ai.api.ai_results_routes import get_results_service, router as results_router
from app.ai.api.ai_vectorization_routes import get_polygonization_service
from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.registry.model_registry import ModelRegistry
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.building_polygonization_service import (
    BuildingPolygonizationService,
    BuildingVectorResult,
)
from app.ai.services.building_results_service import BuildingResultsService
from app.ai.services.inference_service import InferenceService
from app.ai.services.postprocessing_service import PostProcessingConfig, PostProcessingService, RasterGrid
from app.ai.services.tiling_service import TilingService
from tests.test_ai_polygonization import mask_result
from tests.test_ai_postprocessing import ConstantAdapter, write_orthophoto


def vector_result(mask: np.ndarray) -> BuildingVectorResult:
    return BuildingPolygonizationService().polygonize(mask_result(mask))


def test_feature_collection_has_two_ordered_wgs84_features_and_safe_properties() -> None:
    mask = np.zeros((20, 30), dtype=np.uint8)
    mask[2:6, 3:8] = 1
    mask[12:18, 20:27] = 1
    native = vector_result(mask)
    native_wkb = [feature.geometry.wkb for feature in native.building_features]
    result = BuildingResultsService().build(native)
    assert result.candidate_count == 2
    assert result.feature_collection.type == "FeatureCollection"
    assert [feature.id for feature in result.feature_collection.features] == [
        "building_000001",
        "building_000002",
    ]
    assert [feature.properties["object_id"] for feature in result.feature_collection.features] == [
        "building_000001",
        "building_000002",
    ]
    assert all(feature.properties["object_type"] == "building_candidate" for feature in result.feature_collection.features)
    assert all(shape(feature.geometry).is_valid for feature in result.feature_collection.features)
    assert [feature.geometry.wkb for feature in native.building_features] == native_wkb
    serialized = json.dumps(result.model_dump(mode="json"))
    for forbidden in ("probability_map", "binary_mask", "checkpoint_path", "Tensor", "numpy"):
        assert forbidden not in serialized


def test_statistics_are_exact_for_multiple_and_single_candidates() -> None:
    mask = np.zeros((14, 16), dtype=np.uint8)
    mask[1:3, 1:3] = 1  # 4 pixels = 0.25 m2, perimeter 2 m
    mask[7:9, 8:12] = 1  # 8 pixels = 0.5 m2, perimeter 3 m
    result = BuildingResultsService().build(vector_result(mask))
    stats = result.statistics
    assert stats.candidate_count == 2
    assert stats.total_area_map_units == pytest.approx(0.75)
    assert stats.mean_area_map_units == pytest.approx(0.375)
    assert stats.median_area_map_units == pytest.approx(0.375)
    assert stats.min_area_map_units == pytest.approx(0.25)
    assert stats.max_area_map_units == pytest.approx(0.5)
    assert stats.total_perimeter_map_units == pytest.approx(5.0)
    assert stats.mean_perimeter_map_units == pytest.approx(2.5)
    assert stats.total_area_m2 == pytest.approx(0.75)

    single_mask = np.zeros((5, 5), dtype=np.uint8)
    single_mask[1:3, 1:3] = 1
    single = BuildingResultsService().build(vector_result(single_mask)).statistics
    assert single.candidate_count == 1
    assert single.mean_area_map_units == single.median_area_map_units == 0.25


def test_empty_result_is_successful_and_has_coherent_statistics() -> None:
    result = BuildingResultsService().build(vector_result(np.zeros((10, 12), dtype=np.uint8)))
    assert result.success
    assert result.candidate_count == 0
    assert result.feature_collection.features == []
    assert result.statistics.total_area_map_units == 0.0
    assert result.statistics.total_perimeter_map_units == 0.0
    assert result.statistics.mean_area_map_units is None
    assert result.statistics.median_area_m2 is None


def test_wgs84_reprojection_round_trip_centroid_and_bounds() -> None:
    mask = np.zeros((12, 12), dtype=np.uint8)
    mask[3:8, 4:10] = 1
    native = BuildingPolygonizationService().polygonize(
        mask_result(mask, transform=tuple(from_origin(500_000.0, 2_800_000.0, 0.25, 0.25)))
    )
    feature = native.building_features[0]
    result = BuildingResultsService().build(native)
    api_feature = result.feature_collection.features[0]
    lon = api_feature.properties["centroid_lon"]
    lat = api_feature.properties["centroid_lat"]
    assert 40.0 < lon < 50.0
    assert 20.0 < lat < 30.0
    xs, ys = transform("EPSG:4326", native.crs, [lon], [lat])
    assert xs[0] == pytest.approx(feature.centroid_x, abs=1e-5)
    assert ys[0] == pytest.approx(feature.centroid_y, abs=1e-5)
    assert shape(api_feature.geometry).is_valid
    assert result.source_crs == "EPSG:32638"
    assert result.feature_collection_crs == "EPSG:4326"
    assert result.native_bounds == native.bounds
    assert -180 <= result.wgs84_bounds["left"] <= result.wgs84_bounds["right"] <= 180
    assert -90 <= result.wgs84_bounds["bottom"] <= result.wgs84_bounds["top"] <= 90


def test_deterministic_payload_except_unique_analysis_and_timing_metadata() -> None:
    mask = np.zeros((15, 20), dtype=np.uint8)
    mask[2:6, 2:7] = 1
    mask[9:13, 12:18] = 1
    service = BuildingResultsService()
    native = vector_result(mask)
    first = service.build(native)
    second = service.build(native)
    assert first.analysis_id != second.analysis_id
    assert first.feature_collection == second.feature_collection
    assert first.statistics == second.statistics
    assert first.candidate_count == second.candidate_count


def test_source_quality_modes_and_scientific_status_are_explicit() -> None:
    mask = np.ones((3, 3), dtype=np.uint8)
    native = vector_result(mask)
    orthophoto = BuildingResultsService().build(native)
    sentinel = BuildingResultsService().build(replace(native, source_type="gee_sentinel2"))
    assert orthophoto.quality_mode == "real_model_unvalidated"
    assert sentinel.quality_mode == "integration_test"
    assert orthophoto.scientific_accuracy_status == "NOT_VALIDATED"
    assert "not yet been validated" in orthophoto.quality_note


def test_result_is_strictly_json_serializable_and_schema_is_versioned() -> None:
    mask = np.ones((4, 6), dtype=np.uint8)
    result = BuildingResultsService().build(vector_result(mask))
    payload = result.model_dump(mode="json")
    encoded = json.dumps(payload, allow_nan=False)
    assert json.loads(encoded)["result_schema_version"] == "1.0"
    assert result.analysis_type == "ai_object_detection"
    assert result.object_type == "building"


def test_results_api_returns_complete_feature_collection_without_sensitive_paths(tmp_path: Path) -> None:
    raster_service = AIRasterService(tmp_path / "cache")
    source = write_orthophoto(tmp_path / "api-results-ortho.tif")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    registry = ModelRegistry()
    registry.register("building", ConstantAdapter)
    application = FastAPI()
    application.include_router(results_router)
    application.dependency_overrides[get_ai_raster_service] = lambda: raster_service
    application.dependency_overrides[get_tiling_service] = TilingService
    application.dependency_overrides[get_inference_service] = lambda: InferenceService(registry)
    application.dependency_overrides[get_postprocessing_service] = PostProcessingService
    application.dependency_overrides[get_polygonization_service] = BuildingPolygonizationService
    application.dependency_overrides[get_results_service] = BuildingResultsService
    response = TestClient(application).post(
        "/api/ai/results/building",
        json={"raster_id": prepared.raster_id, "model_id": "unet_resnet34", "min_object_pixels": 0},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_count"] == 1
    assert body["feature_collection"]["type"] == "FeatureCollection"
    assert body["feature_collection_crs"] == "EPSG:4326"
    assert body["scientific_accuracy_status"] == "NOT_VALIDATED"
    serialized = json.dumps(body)
    assert str(tmp_path) not in serialized
    assert "checkpoint_path" not in serialized.lower()
    assert "building_count" not in serialized


def test_real_model_complete_results_pipeline_smoke(tmp_path: Path) -> None:
    model_config = BuildingModelConfig.from_env()
    if model_config.checkpoint_path is None or not model_config.checkpoint_path.is_file():
        pytest.skip("REAL_BUILDING_CHECKPOINT_NOT_AVAILABLE")
    source = write_orthophoto(tmp_path / "real-results-ortho.tif", width=700, height=640)
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
    mask_output = PostProcessingService().process(predictions, grid=grid, config=PostProcessingConfig())
    vector_output = BuildingPolygonizationService().polygonize(mask_output)
    result = BuildingResultsService().build(vector_output)
    assert result.model_mode == "REAL"
    assert result.scientific_accuracy_status == "NOT_VALIDATED"
    assert result.feature_collection_crs == "EPSG:4326"
    json.dumps(result.model_dump(mode="json"), allow_nan=False)
    adapter.close()


def test_results_build_handles_hundreds_of_candidates() -> None:
    mask = np.zeros((400, 400), dtype=np.uint8)
    for row in range(5, 395, 20):
        for col in range(5, 395, 20):
            mask[row : row + 5, col : col + 6] = 1
    native = vector_result(mask)
    result = BuildingResultsService().build(native)
    assert result.candidate_count == 400
    assert len(result.feature_collection.features) == 400
    assert result.processing_metadata.results_build_time_ms > 0
    assert result.processing_metadata.geojson_serialization_time_ms > 0
