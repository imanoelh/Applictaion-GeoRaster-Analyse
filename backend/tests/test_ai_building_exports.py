from __future__ import annotations

import csv
import io
import json
import math
import time
import zipfile

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.api.ai_results_routes import router as results_router
from app.ai.services.building_export_service import BuildingExportService
from app.ai.services.building_results_service import BuildingResultsService
from tests.test_ai_building_results import vector_result


def building_result(candidate_count: int = 2):
    columns = max(1, math.ceil(math.sqrt(candidate_count)))
    rows = max(1, math.ceil(candidate_count / columns))
    mask = np.zeros((rows * 7 + 4, columns * 7 + 4), dtype=np.uint8)
    for index in range(candidate_count):
        row = 2 + (index // columns) * 7
        column = 2 + (index % columns) * 7
        mask[row : row + 4, column : column + 5] = 1
    return BuildingResultsService().build(vector_result(mask))


def test_geojson_export_is_valid_safe_and_limited_to_public_properties() -> None:
    result = building_result()
    artifact = BuildingExportService().export(result, "geojson")
    payload = json.loads(artifact.content)
    assert artifact.media_type.startswith("application/geo+json")
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 2
    properties = payload["features"][0]["properties"]
    assert set(properties) == {
        "object_id",
        "object_type",
        "area_m2",
        "perimeter_m",
        "pixel_count",
        "centroid_lon",
        "centroid_lat",
        "model_name",
        "model_id",
        "model_architecture",
        "preprocessing_profile",
        "tile_size",
        "model_version",
        "threshold",
        "scientific_accuracy_status",
        "model_status",
        "component_models",
        "fusion_method",
    }
    assert properties["scientific_accuracy_status"] == "NOT_VALIDATED"
    encoded = artifact.content.decode("utf-8").lower()
    assert "checkpoint" not in encoded
    assert "cache_path" not in encoded


def test_csv_export_has_one_global_statistics_row_and_handles_nulls() -> None:
    result = building_result(0)
    artifact = BuildingExportService().export(result, "csv")
    rows = list(csv.DictReader(io.StringIO(artifact.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["analysis_id"] == result.analysis_id
    assert rows[0]["candidate_count"] == "0"
    assert rows[0]["total_area_m2"] == ""
    assert rows[0]["mean_area_m2"] == ""
    assert rows[0]["quality_mode"] == "real_model_unvalidated"
    assert rows[0]["scientific_accuracy_status"] == "NOT_VALIDATED"


def test_metadata_export_is_strict_json_and_removes_sensitive_config_keys() -> None:
    result = building_result(1).model_copy(deep=True)
    result.processing_metadata.postprocessing_config["checkpoint_path"] = "C:/secret/model.pt"
    result.processing_metadata.postprocessing_config["nested"] = {"api_token": "secret", "keep": 4}
    result.processing_metadata.postprocessing_config["innocent_name"] = "C:/secret/other.bin"
    artifact = BuildingExportService().export(result, "metadata")
    metadata = json.loads(artifact.content)
    assert metadata["analysis_id"] == result.analysis_id
    assert metadata["model_id"] == "unet_resnet34"
    assert "model_architecture" in metadata
    assert "model_checkpoint_hash" in metadata
    assert metadata["result_schema_version"] == "1.0"
    assert metadata["scientific_accuracy_status"] == "NOT_VALIDATED"
    assert "created_at" in metadata
    assert "checkpoint_path" not in metadata["postprocessing_config"]
    assert metadata["postprocessing_config"]["nested"] == {"keep": 4}
    assert metadata["postprocessing_config"]["innocent_name"] is None
    json.dumps(metadata, allow_nan=False)


def test_zip_export_contains_exactly_geojson_csv_and_metadata() -> None:
    result = building_result(3)
    artifact = BuildingExportService().export(result, "zip")
    assert artifact.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        assert set(archive.namelist()) == {
            "building_candidates.geojson",
            "building_statistics.csv",
            "building_metadata.json",
        }
        assert len(json.loads(archive.read("building_candidates.geojson"))["features"]) == 3
        assert json.loads(archive.read("building_metadata.json"))["analysis_id"] == result.analysis_id


def test_export_api_downloads_each_supported_format_without_persistence() -> None:
    application = FastAPI()
    application.include_router(results_router)
    client = TestClient(application)
    result = building_result(2).model_dump(mode="json")
    expected_types = {
        "geojson": "application/geo+json",
        "csv": "text/csv",
        "metadata": "application/json",
        "zip": "application/zip",
    }
    for export_format, media_type in expected_types.items():
        response = client.post(
            "/api/ai/results/building/export",
            json={"format": export_format, "result": result},
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(media_type)
        assert "attachment" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "no-store"


def test_export_api_rejects_unknown_format_and_invalid_analysis_id() -> None:
    application = FastAPI()
    application.include_router(results_router)
    client = TestClient(application)
    result = building_result(1).model_dump(mode="json")
    invalid_format = client.post(
        "/api/ai/results/building/export",
        json={"format": "shp", "result": result},
    )
    assert invalid_format.status_code == 422
    result["analysis_id"] = "../../invalid"
    invalid_id = client.post(
        "/api/ai/results/building/export",
        json={"format": "geojson", "result": result},
    )
    assert invalid_id.status_code == 422


def test_zip_export_handles_2500_features_without_persistent_copy() -> None:
    result = building_result(2500)
    started = time.perf_counter()
    artifact = BuildingExportService().export(result, "zip")
    elapsed = time.perf_counter() - started
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        payload = json.loads(archive.read("building_candidates.geojson"))
    assert len(payload["features"]) == 2500
    assert elapsed < 10.0
