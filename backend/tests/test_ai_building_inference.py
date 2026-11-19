from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pytest
import rasterio
import torch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from app.ai.api.ai_inference_routes import get_inference_service, router as inference_router
from app.ai.api.ai_raster_routes import get_ai_raster_service, get_tiling_service
from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.models.base_model_adapter import AIModelError, BaseModelAdapter, ModelOutput
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.registry.model_registry import ModelRegistry
from app.ai.schemas.ai_raster_schemas import AIRasterPrepareRequest
from app.ai.schemas.tile_schemas import TileMetadata
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.inference_service import InferenceService
from app.ai.services.tiling_service import PreparedTile, TilingService
from app.ai.sources.base_raster_source import RasterSource


class DeterministicSegmentationModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.grad_enabled_during_forward: bool | None = None

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        self.grad_enabled_during_forward = torch.is_grad_enabled()
        # Only channel 0 is used, which also verifies CHW order in tests.
        return (value[:, 0:1] - 0.5) * 10.0


class TorchScriptSegmentationModel(torch.nn.Module):
    """Minimal test-only module used to validate the real TorchScript loader."""

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return (value[:, 0:1] - 0.5) * 10.0


def tile_metadata(
    *,
    tile_id: str = "tile_0001",
    valid_width: int = 640,
    valid_height: int = 640,
    skip: bool = False,
    ratio: float = 1.0,
) -> TileMetadata:
    return TileMetadata(
        tile_id=tile_id,
        row_index=0,
        col_index=0,
        row_offset=0,
        col_offset=0,
        width=640,
        height=640,
        valid_width=valid_width,
        valid_height=valid_height,
        tile_size=640,
        overlap_pixels=128,
        stride=512,
        padding_top=0,
        padding_bottom=640 - valid_height,
        padding_left=0,
        padding_right=640 - valid_width,
        valid_pixel_ratio=ratio,
        skip_inference=skip,
        transform=[10.0, 0.0, 500_000.0, 0.0, -10.0, 2_800_000.0, 0.0, 0.0, 1.0],
        bounds={"left": 500_000, "bottom": 2_793_600, "right": 506_400, "top": 2_800_000},
        crs="EPSG:32638",
        source_raster_id="ai-s2-20240101-0123456789ab-abcdef012345",
    )


def prepared_tile(
    *,
    value: float = 0.6,
    tile_id: str = "tile_0001",
    valid_width: int = 640,
    valid_height: int = 640,
    skip: bool = False,
    ratio: float = 1.0,
) -> PreparedTile:
    image = np.full((3, 640, 640), value, dtype=np.float32)
    mask = np.zeros((640, 640), dtype=np.bool_)
    mask[:valid_height, :valid_width] = True
    return PreparedTile(
        image=image,
        source_rgb=np.zeros((3, 640, 640), dtype=np.uint16),
        valid_mask=mask,
        metadata=tile_metadata(
            tile_id=tile_id,
            valid_width=valid_width,
            valid_height=valid_height,
            skip=skip,
            ratio=ratio,
        ),
    )


def make_test_config(tmp_path: Path, *, output_kind: str = "logits") -> BuildingModelConfig:
    checkpoint = tmp_path / "test-only-checkpoint.placeholder"
    checkpoint.write_bytes(b"test-only")
    return BuildingModelConfig(
        checkpoint_path=checkpoint,
        model_name="deterministic-test-segmentation",
        model_version="test-v1",
        output_kind=output_kind,
        test_only=True,
    )


def deterministic_adapter(
    tmp_path: Path,
    *,
    model: DeterministicSegmentationModel | None = None,
) -> tuple[BuildingModelAdapter, DeterministicSegmentationModel, dict[str, int]]:
    selected_model = model or DeterministicSegmentationModel()
    calls = {"loads": 0}

    def loader(path: Path, device: str) -> DeterministicSegmentationModel:
        assert path.is_file()
        assert device == "cpu"
        calls["loads"] += 1
        return selected_model

    adapter = BuildingModelAdapter(make_test_config(tmp_path), model_loader=loader)
    return adapter, selected_model, calls


def registry_for(adapter: BaseModelAdapter) -> ModelRegistry:
    registry = ModelRegistry()
    registry.register("building", lambda: adapter)
    return registry


def test_model_adapter_contract_and_eval_mode(tmp_path: Path) -> None:
    adapter, model, calls = deterministic_adapter(tmp_path)
    assert adapter.is_loaded() is False
    adapter.load()
    assert adapter.is_loaded() is True
    assert calls["loads"] == 1
    assert model.training is False
    output = adapter.predict(prepared_tile())
    assert isinstance(output, ModelOutput)
    info = adapter.get_model_info()
    assert info["runtime"] == "pytorch"
    assert info["device"] == "cpu"
    assert info["model_mode"] == "TEST_ONLY"
    adapter.close()
    assert adapter.is_loaded() is False


def test_torchscript_checkpoint_loads_and_predicts_on_cpu(tmp_path: Path) -> None:
    checkpoint = tmp_path / "deterministic-test-only.pt"
    example = torch.zeros((1, 3, 640, 640), dtype=torch.float32)
    traced = torch.jit.trace(TorchScriptSegmentationModel().eval(), example)
    torch.jit.save(traced, str(checkpoint))

    adapter = BuildingModelAdapter(
        BuildingModelConfig(
            checkpoint_path=checkpoint,
            model_name="torchscript-test-segmentation",
            model_version="test-v1",
            test_only=True,
        )
    )
    output = adapter.predict(prepared_tile(value=0.6))

    assert adapter.is_loaded() is True
    assert adapter.get_model_info()["device"] == "cpu"
    assert adapter.get_model_info()["load_count"] == 1
    assert output.probability_map.shape == (640, 640)
    assert output.probability_map.dtype == np.float32
    assert float(output.probability_map[0, 0]) == pytest.approx(0.7310586)


def test_model_is_loaded_once_for_multiple_tiles(tmp_path: Path) -> None:
    adapter, _model, calls = deterministic_adapter(tmp_path)
    service = InferenceService(registry_for(adapter))
    results = list(service.iter_predictions((prepared_tile(tile_id=f"tile_{i:04d}") for i in range(3))))
    assert len(results) == 3
    assert calls["loads"] == 1
    assert adapter.get_model_info()["load_count"] == 1


def test_numpy_to_tensor_shape_dtype_and_band_order(tmp_path: Path) -> None:
    adapter, _model, _calls = deterministic_adapter(tmp_path)
    tile = prepared_tile(value=0.0)
    tile.image[0, :, :] = 0.1
    tile.image[1, :, :] = 0.2
    tile.image[2, :, :] = 0.3
    tensor = adapter.tile_to_tensor(tile)
    assert tuple(tensor.shape) == (1, 3, 640, 640)
    assert tensor.dtype == torch.float32
    assert tensor.device.type == "cpu"
    assert tensor[0, :, 10, 10].tolist() == pytest.approx([0.1, 0.2, 0.3])


def test_probability_output_shape_dtype_range_and_inference_mode(tmp_path: Path) -> None:
    adapter, model, _calls = deterministic_adapter(tmp_path)
    result = adapter.predict(prepared_tile(value=0.6))
    assert result.probability_map.shape == (640, 640)
    assert result.probability_map.dtype == np.float32
    assert float(result.probability_map.min()) >= 0.0
    assert float(result.probability_map.max()) <= 1.0
    assert model.grad_enabled_during_forward is False


def test_threshold_049_050_090() -> None:
    probability = np.zeros((640, 640), dtype=np.float32)
    probability[0, 0:3] = [0.49, 0.50, 0.90]
    adapter = StaticProbabilityAdapter(probability)
    prediction = next(
        InferenceService(registry_for(adapter)).iter_predictions(
            [prepared_tile(value=0.0)], probability_threshold=0.50
        )
    )
    assert prediction.binary_mask is not None
    assert prediction.binary_mask[0, 0:3].tolist() == [0, 1, 1]


def test_nodata_and_padding_are_zeroed_after_prediction() -> None:
    probability = np.ones((640, 640), dtype=np.float32)
    adapter = StaticProbabilityAdapter(probability)
    tile = prepared_tile(valid_width=52, valid_height=57, ratio=1.0)
    tile.valid_mask[10, 10] = False  # NoData inside the real window.
    prediction = next(InferenceService(registry_for(adapter)).iter_predictions([tile]))
    assert prediction.probability_map is not None
    assert prediction.binary_mask is not None
    assert prediction.probability_map[10, 10] == 0
    assert prediction.binary_mask[10, 10] == 0
    assert not prediction.probability_map[57:, :].any()
    assert not prediction.probability_map[:, 52:].any()
    assert not prediction.binary_mask[57:, :].any()
    assert not prediction.binary_mask[:, 52:].any()
    assert prediction.metadata.valid_width == 52
    assert prediction.metadata.valid_height == 57


def test_skip_inference_never_calls_model() -> None:
    adapter = StaticProbabilityAdapter(np.ones((640, 640), dtype=np.float32))
    result = next(
        InferenceService(registry_for(adapter)).iter_predictions(
            [prepared_tile(skip=True, ratio=0.0)]
        )
    )
    assert adapter.predict_calls == 0
    assert result.metadata.status == "skipped"
    assert result.metadata.reason == "insufficient_valid_pixels"
    assert result.probability_map is None
    assert result.binary_mask is None


def test_streaming_does_not_eagerly_consume_tiles() -> None:
    adapter = StaticProbabilityAdapter(np.ones((640, 640), dtype=np.float32))
    consumed: list[int] = []

    def source() -> Iterator[PreparedTile]:
        for index in range(3):
            consumed.append(index)
            yield prepared_tile(tile_id=f"tile_{index + 1:04d}")

    predictions = InferenceService(registry_for(adapter)).iter_predictions(source())
    assert consumed == []
    first = next(predictions)
    assert first.metadata.tile_id == "tile_0001"
    assert consumed == [0]
    second = next(predictions)
    assert second.metadata.tile_id == "tile_0002"
    assert consumed == [0, 1]


def test_model_not_configured_has_business_error() -> None:
    adapter = BuildingModelAdapter(BuildingModelConfig(checkpoint_path=None))
    with pytest.raises(AIModelError) as error:
        adapter.predict(prepared_tile())
    assert error.value.code == "MODEL_NOT_CONFIGURED"


def test_model_file_not_found_has_business_error(tmp_path: Path) -> None:
    adapter = BuildingModelAdapter(
        BuildingModelConfig(checkpoint_path=tmp_path / "missing-model.pt")
    )
    with pytest.raises(AIModelError) as error:
        adapter.load()
    assert error.value.code == "MODEL_FILE_NOT_FOUND"


def test_invalid_checkpoint_has_model_load_failed(tmp_path: Path) -> None:
    checkpoint = tmp_path / "invalid.pt"
    checkpoint.write_bytes(b"not-a-torchscript-model")
    adapter = BuildingModelAdapter(BuildingModelConfig(checkpoint_path=checkpoint))
    with pytest.raises(AIModelError) as error:
        adapter.load()
    assert error.value.code == "MODEL_LOAD_FAILED"


def test_invalid_input_and_output_have_business_errors(tmp_path: Path) -> None:
    adapter, _model, _calls = deterministic_adapter(tmp_path)
    invalid = prepared_tile()
    invalid.image[0, 0, 0] = np.nan
    with pytest.raises(AIModelError) as input_error:
        adapter.predict(invalid)
    assert input_error.value.code == "MODEL_INPUT_INVALID"

    wrong_output = WrongShapeModel()
    wrong_adapter, _unused, _calls = deterministic_adapter(tmp_path, model=wrong_output)  # type: ignore[arg-type]
    with pytest.raises(AIModelError) as output_error:
        wrong_adapter.predict(prepared_tile())
    assert output_error.value.code == "MODEL_OUTPUT_INVALID"


def test_registry_returns_single_instance_and_controlled_reload() -> None:
    created: list[StaticProbabilityAdapter] = []
    registry = ModelRegistry()

    def factory() -> StaticProbabilityAdapter:
        adapter = StaticProbabilityAdapter(np.zeros((640, 640), dtype=np.float32))
        created.append(adapter)
        return adapter

    registry.register("building", factory)
    first = registry.get_model("building")
    assert registry.get_model("building") is first
    replacement = registry.reload("building")
    assert replacement is not first
    assert registry.get_model("building") is replacement
    assert len(created) == 2


def test_registry_selection_is_explicit_and_separated_by_model_id() -> None:
    registry = ModelRegistry()
    production = StaticProbabilityAdapter(np.zeros((640, 640), dtype=np.float32))
    candidate = StaticProbabilityAdapter(np.ones((640, 640), dtype=np.float32))
    registry.register("building", lambda: production)
    registry.register_model(
        "building",
        "spacenet2_deeplab",
        lambda: candidate,
        metadata={"id": "spacenet2_deeplab", "name": "DeepLabV3 ResNet-50"},
    )

    assert registry.get_selected_model("building") is production
    assert registry.get_selected_model("building", "unet_resnet34") is production
    assert registry.get_selected_model("building", "spacenet2_deeplab") is candidate
    assert candidate is not production


def test_building_model_options_endpoint_reports_production_default_and_candidate() -> None:
    from app.ai.api.ai_inference_routes import router as inference_router

    application = FastAPI()
    application.include_router(inference_router)
    response = TestClient(application).get("/api/ai/inference/models/building")
    assert response.status_code == 200
    models = {item["id"]: item for item in response.json()["models"]}
    assert models["unet_resnet34"]["default"] is False
    assert models["unet_resnet34"]["status"] == "LEGACY"
    assert models["spacenet2_deeplab"]["default"] is True
    assert models["spacenet2_deeplab"]["status"] == "PRODUCTION"
    assert models["spacenet2_deeplab"]["input_size"] == 512


def write_validated_raster(cache_dir: Path, raster_id: str) -> Path:
    path = cache_dir / f"{raster_id}.tif"
    data = np.full((3, 57, 52), 6_000, dtype=np.uint16)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=52,
        height=57,
        count=3,
        dtype="uint16",
        crs="EPSG:32638",
        transform=from_origin(500_000, 2_800_000, 10, 10),
        nodata=0,
    ) as dataset:
        dataset.write(data)
        dataset.descriptions = ("B4", "B3", "B2")
    (cache_dir / f"{raster_id}.json").write_text(
        json.dumps({"raster_id": raster_id, "validation": {"valid": True}, "metadata": {}}),
        encoding="utf-8",
    )
    return path


class DeterministicSentinelSource(RasterSource):
    """Test-only GEE boundary double producing the stage-1 GeoTIFF contract."""

    SOURCE = "sentinel2"

    def __init__(self, payload: dict[str, Any], cache_dir: Path, raster_id: str) -> None:
        self.payload = payload
        self.cache_dir = cache_dir
        self.raster_id = raster_id

    def get_raster(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return write_validated_raster(self.cache_dir, self.raster_id)

    def get_metadata(self) -> dict[str, Any]:
        return {"images_count": 2, "mosaic_method": "median_composite_mosaic"}

    def get_crs(self) -> str | None:
        return "EPSG:32638"

    def get_resolution(self) -> float | None:
        return 10.0

    def get_bounds(self) -> list[float] | None:
        return list(transform_bounds("EPSG:32638", "EPSG:4326", 500_000, 2_799_430, 500_520, 2_800_000))


def test_stage1_to_stage3_integration_and_api_summary_only(tmp_path: Path) -> None:
    west, south, east, north = transform_bounds(
        "EPSG:32638", "EPSG:4326", 500_000, 2_799_430, 500_520, 2_800_000
    )
    raster_service = AIRasterService(
        tmp_path,
        source_factory=lambda payload, cache_dir, raster_id: DeterministicSentinelSource(
            payload, cache_dir, raster_id
        ),
    )
    prepared = raster_service.prepare(
        AIRasterPrepareRequest(
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]],
            },
            start_date="2024-01-01",
            end_date="2024-01-31",
            sensor="sentinel-2",
            image_method="median_composite",
        )
    )
    raster_id = prepared.raster_id
    assert prepared.validation.valid is True
    assert prepared.validation.band_names == ["B4", "B3", "B2"]
    assert prepared.validation.resolution_x == pytest.approx(10.0)
    assert prepared.validation.resolution_y == pytest.approx(10.0)

    adapter, _model, _calls = deterministic_adapter(tmp_path)
    inference = InferenceService(registry_for(adapter))

    application = FastAPI()
    application.include_router(inference_router)
    application.dependency_overrides[get_ai_raster_service] = lambda: raster_service
    application.dependency_overrides[get_tiling_service] = lambda: TilingService()
    application.dependency_overrides[get_inference_service] = lambda: inference
    response = TestClient(application).post(
        "/api/ai/inference/building",
        json={
            "raster_id": raster_id,
            "model_id": "unet_resnet34",
            "tile_size": 640,
            "overlap_ratio": 0.2,
            "probability_threshold": 0.5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["quality_mode"] == "integration_test"
    assert body["model"]["model_mode"] == "TEST_ONLY"
    assert body["tiles"] == {"total": 1, "processed": 1, "skipped": 0}
    assert body["model"]["runtime"] == "pytorch"
    assert "probability_map" not in json.dumps(body)
    assert "binary_mask" not in json.dumps(body)
    assert body["performance"]["model_load_time_ms"] >= 0
    assert body["performance"]["total_inference_time_ms"] >= 0
    assert body["performance"]["average_tile_inference_time_ms"] >= 0
    assert body["performance"]["tiles_per_second"] is not None


def test_production_api_without_checkpoint_returns_model_not_configured(tmp_path: Path) -> None:
    raster_id = "ai-s2-20240101-0123456789ab-abcdef012345"
    write_validated_raster(tmp_path, raster_id)
    adapter = BuildingModelAdapter(BuildingModelConfig(checkpoint_path=None))
    inference = InferenceService(registry_for(adapter))
    application = FastAPI()
    application.include_router(inference_router)
    application.dependency_overrides[get_ai_raster_service] = lambda: AIRasterService(tmp_path)
    application.dependency_overrides[get_tiling_service] = lambda: TilingService()
    application.dependency_overrides[get_inference_service] = lambda: inference
    response = TestClient(application).post(
        "/api/ai/inference/building",
        json={"raster_id": raster_id, "model_id": "unet_resnet34"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_NOT_CONFIGURED"


class StaticProbabilityAdapter(BaseModelAdapter):
    def __init__(self, probability: np.ndarray) -> None:
        self.probability = probability
        self.predict_calls = 0

    def load(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return True

    def predict(self, tile: PreparedTile) -> ModelOutput:
        self.predict_calls += 1
        return ModelOutput(self.probability.copy(), 0.1)

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_name": "static-test",
            "model_version": "test-v1",
            "runtime": "test",
            "device": "cpu",
            "loaded": True,
            "model_mode": "TEST_ONLY",
            "model_load_time_ms": 0.0,
            "load_count": 1,
        }

    def close(self) -> None:
        return None


class WrongShapeModel(DeterministicSegmentationModel):
    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return torch.zeros((1, 1, 10, 10), dtype=torch.float32)
