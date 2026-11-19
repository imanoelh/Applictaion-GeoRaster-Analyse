from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.api.ai_inference_routes import (
    get_inference_service,
    router as inference_router,
)
from app.ai.api.ai_raster_routes import get_ai_raster_service, get_tiling_service
from app.ai.models.base_model_adapter import AIModelError
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.registry.model_registry import ModelRegistry
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.inference_service import InferenceService
from app.ai.services.tiling_service import TilingService


EXPECTED_SHA256 = "6cd2467e063696e9d41d409bda7751a9ccdb057d5adba251ab5a765d8d415987"


def real_config_or_skip() -> BuildingModelConfig:
    config = BuildingModelConfig.from_env()
    if config.checkpoint_path is None or not config.checkpoint_path.is_file():
        pytest.skip("REAL_BUILDING_CHECKPOINT_NOT_AVAILABLE")
    return config


def write_rgb_orthophoto(path: Path) -> Path:
    height, width = 640, 700
    rows, cols = np.indices((height, width))
    data = np.stack(
        (
            ((cols * 3 + rows) % 256),
            ((rows * 2 + 40) % 256),
            (((rows // 32) * 45 + (cols // 32) * 20) % 256),
        )
    ).astype(np.uint8)
    data[:, :32, :32] = 0
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
        nodata=0,
    ) as dataset:
        dataset.write(data)
        dataset.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
        dataset.descriptions = ("R", "G", "B")
    return path


def test_real_checkpoint_identity_load_eval_and_contract() -> None:
    config = real_config_or_skip()
    assert config.checkpoint_sha256 == EXPECTED_SHA256
    checksum = hashlib.sha256()
    with config.checkpoint_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    digest = checksum.hexdigest()
    assert digest == EXPECTED_SHA256
    assert config.checkpoint_format == "state_dict"
    assert config.model_architecture == "unet_resnet34"
    assert config.weights_license == "CC-BY-4.0"
    assert config.model_input_size == 512
    assert config.model_normalization == "per_channel_zscore"

    adapter = BuildingModelAdapter(config)
    adapter.load()
    info = adapter.get_model_info()
    assert adapter.is_loaded() is True
    assert adapter._model.training is False
    assert info["model_mode"] == "REAL"
    assert info["device"] == "cpu"
    assert info["checkpoint_id"] == "sha256:6cd2467e0636"
    adapter.close()


def test_real_checkpoint_rejects_unverified_license() -> None:
    config = real_config_or_skip()
    adapter = BuildingModelAdapter(
        BuildingModelConfig(
            checkpoint_path=config.checkpoint_path,
            checkpoint_format="state_dict",
            model_architecture="unet_resnet34",
            enforce_provenance=True,
        )
    )
    with pytest.raises(AIModelError) as error:
        adapter.load()
    assert error.value.code == "MODEL_LICENSE_UNVERIFIED"


def test_synthetic_orthophoto_runs_through_real_checkpoint(tmp_path: Path) -> None:
    config = real_config_or_skip()
    source = write_rgb_orthophoto(tmp_path / "technical-orthophoto.tif")
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
    adapter = BuildingModelAdapter(config)
    registry = ModelRegistry()
    registry.register("building", lambda: adapter)
    predictions = list(
        InferenceService(registry).iter_predictions(
            tiles,
            probability_threshold=0.50,
        )
    )

    assert len(predictions) == 2
    assert sum(prediction.metadata.positive_pixel_count for prediction in predictions) == 0
    inference_times = [prediction.metadata.inference_time_ms for prediction in predictions]
    assert min(inference_times) > 0.0
    assert max(inference_times) >= min(inference_times)
    for prediction in predictions:
        assert prediction.metadata.model_mode == "REAL"
        assert prediction.metadata.model_architecture == "unet_resnet34"
        assert prediction.metadata.source_type == "orthophoto_local"
        assert prediction.metadata.source_resolution == pytest.approx(0.5)
        assert prediction.probability_map is not None
        assert prediction.binary_mask is not None
        assert prediction.probability_map.shape == (640, 640)
        assert prediction.probability_map.dtype == np.float32
        assert float(prediction.probability_map.min()) >= 0.0
        assert float(prediction.probability_map.max()) <= 1.0
        assert prediction.binary_mask.dtype == np.uint8
    assert adapter.get_model_info()["model_load_time_ms"] > 0.0
    last = predictions[-1]
    assert not last.probability_map[:, 188:].any()
    assert not last.binary_mask[:, 188:].any()
    adapter.close()


def test_real_checkpoint_api_returns_metadata_only(tmp_path: Path) -> None:
    config = real_config_or_skip()
    source = write_rgb_orthophoto(tmp_path / "api-technical-orthophoto.tif")
    raster_service = AIRasterService(tmp_path / "cache")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    adapter = BuildingModelAdapter(config)
    registry = ModelRegistry()
    registry.register("building", lambda: adapter)
    inference_service = InferenceService(registry)

    application = FastAPI()
    application.include_router(inference_router)
    application.dependency_overrides[get_ai_raster_service] = lambda: raster_service
    application.dependency_overrides[get_tiling_service] = lambda: TilingService()
    application.dependency_overrides[get_inference_service] = lambda: inference_service
    response = TestClient(application).post(
        "/api/ai/inference/building",
        json={"raster_id": prepared.raster_id, "model_id": "unet_resnet34"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quality_mode"] == "real_model_unvalidated"
    assert body["model"]["model_mode"] == "REAL"
    assert body["model"]["architecture"] == "unet_resnet34"
    assert body["model"]["threshold_status"] == "NOT_CALIBRATED"
    assert body["tiles"]["total"] == 2
    assert body["performance"]["min_inference_time_ms"] > 0.0
    assert body["performance"]["max_inference_time_ms"] >= body["performance"]["min_inference_time_ms"]
    assert "probability_map" not in body
    assert "binary_mask" not in body
    adapter.close()

