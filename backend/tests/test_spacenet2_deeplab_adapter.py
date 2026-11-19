from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.enums import ColorInterp

from app.ai.api.ai_vectorization_routes import build_building_vector_result
from app.ai.models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
from app.ai.registry.model_registry import ModelRegistry, create_default_model_registry
from app.ai.models.base_model_adapter import AIModelError
from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.schemas.vectorization_schemas import BuildingVectorPipelineRequest
from app.ai.schemas.prediction_schemas import BuildingInferenceRequest
from app.ai.schemas.postprocessing_schemas import BuildingPostProcessRequest
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.building_polygonization_service import BuildingPolygonizationService
from app.ai.services.building_results_service import BuildingResultsService
from app.ai.services.inference_service import InferenceService
from app.ai.services.postprocessing_service import PostProcessingService
from app.ai.services.tiling_service import TilingService
from app.ai.schemas.tile_schemas import TileBounds, TileMetadata
from app.ai.services.tiling_service import PreparedTile


EXPECTED_SHA256 = "170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555"
CHECKPOINT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "models"
    / "building"
    / "experimental"
    / "spacenet2-deeplab"
    / "best_deeplab.pth"
)


@pytest.fixture(scope="module")
def model_c_adapter() -> SpaceNet2DeepLabAdapter:
    if not CHECKPOINT.is_file():
        pytest.skip("MODEL_C_CHECKPOINT_NOT_AVAILABLE")
    try:
        import torch
    except ImportError:
        pytest.skip("PYTORCH_NOT_AVAILABLE")
    torch.set_num_threads(2)
    adapter = SpaceNet2DeepLabAdapter(CHECKPOINT, expected_sha256=EXPECTED_SHA256, engine="pytorch")
    adapter.load()
    yield adapter
    adapter.close()


def make_tile() -> PreparedTile:
    image = np.full((3, 512, 512), 0.5, dtype=np.float32)
    valid = np.ones((512, 512), dtype=np.bool_)
    valid[:20, :] = False
    valid[:, 490:] = False
    valid[140:210, 190:290] = False
    image[:, ~valid] = 0.0
    metadata = TileMetadata(
        tile_id="model-c-test-tile",
        row_index=0,
        col_index=0,
        row_offset=0,
        col_offset=0,
        width=512,
        height=512,
        valid_width=512,
        valid_height=512,
        tile_size=512,
        overlap_pixels=102,
        stride=410,
        padding_top=0,
        padding_bottom=0,
        padding_left=0,
        padding_right=0,
        valid_pixel_ratio=float(valid.mean()),
        skip_inference=False,
        transform=[0.5, 0.0, 400000.0, 0.0, -0.5, 3760000.0, 0.0, 0.0, 1.0],
        bounds=TileBounds(left=400000, bottom=3759744, right=400256, top=3760000),
        crs="EPSG:32638",
        source_raster_id="model-c-test-raster",
        source_profile="rgb_orthophoto_uint8_v1",
    )
    return PreparedTile(
        image=image,
        source_rgb=np.full((3, 512, 512), 127, dtype=np.uint8),
        valid_mask=valid,
        metadata=metadata,
    )


def test_model_c_strict_load_and_torchvision_runtime_output(model_c_adapter: SpaceNet2DeepLabAdapter) -> None:
    import torch
    from torchvision.models.segmentation.deeplabv3 import DeepLabHead, FCNHead
    from torchvision.models._utils import IntermediateLayerGetter

    model = model_c_adapter._model
    assert model is not None
    assert isinstance(model.backbone, IntermediateLayerGetter)
    assert model.backbone.conv1.in_channels == 3
    assert tuple(len(getattr(model.backbone, f"layer{index}")) for index in range(1, 5)) == (3, 4, 6, 3)
    assert model.backbone.layer4[-1].conv3.out_channels == 2048
    assert isinstance(model.classifier, DeepLabHead)
    assert isinstance(model.aux_classifier, FCNHead)
    assert model_c_adapter.get_model_info()["model_architecture"] == "torchvision_deeplabv3"
    assert model_c_adapter.get_model_info()["experimental_only"] is False

    with torch.inference_mode():
        output = model(torch.zeros((1, 3, 512, 512), dtype=torch.float32))

    assert type(output).__name__ == "OrderedDict"
    assert set(output) == {"out", "aux"}
    assert tuple(output["out"].shape) == (1, 1, 512, 512)
    assert tuple(output["aux"].shape) == (1, 21, 512, 512)
    assert torch.isfinite(output["out"]).all()
    assert torch.isfinite(output["aux"]).all()


def test_building_registry_exposes_deeplab_default_and_lazy_legacy_choice() -> None:
    registry = create_default_model_registry()
    models = {model["id"]: model for model in registry.list_models("building")}
    assert models["unet_resnet34"]["default"] is False
    assert models["unet_resnet34"]["status"] == "LEGACY"
    assert models["spacenet2_deeplab"]["name"] == "Standard Building Detection"
    assert models["spacenet2_deeplab"]["architecture"] == "DeepLabV3 / ResNet-50"
    assert models["spacenet2_deeplab"]["status"] == "PRODUCTION"
    assert models["spacenet2_deeplab"]["default"] is True
    assert registry.get_selected_model("building") is registry.get_selected_model("building", "spacenet2_deeplab")
    assert registry.get_selected_model("building", "unet_resnet34") is not registry.get_selected_model("building")
    candidate = registry.get_selected_model("building", "spacenet2_deeplab")
    assert isinstance(candidate, SpaceNet2DeepLabAdapter)
    assert candidate.preferred_tile_size == 512
    assert candidate.is_loaded() is False


def test_building_requests_without_model_id_select_deeplab() -> None:
    assert BuildingInferenceRequest(raster_id="raster").model_id == "spacenet2_deeplab"
    assert BuildingPostProcessRequest(raster_id="raster").model_id == "spacenet2_deeplab"
    assert BuildingVectorPipelineRequest(raster_id="raster").model_id == "spacenet2_deeplab"


def test_unknown_and_missing_selected_models_fail_without_default_fallback(tmp_path: Path) -> None:
    registry = ModelRegistry()
    production = BuildingModelAdapter(BuildingModelConfig(checkpoint_path=None, test_only=True))
    registry.register("building", lambda: production)
    registry.register_model(
        "building",
        "spacenet2_deeplab",
        lambda: SpaceNet2DeepLabAdapter(tmp_path / "missing.pth", expected_sha256=EXPECTED_SHA256),
        metadata={"id": "spacenet2_deeplab", "name": "DeepLabV3 ResNet-50"},
    )

    with pytest.raises(AIModelError) as unknown:
        registry.get_selected_model("building", "unknown_model")
    assert unknown.value.code == "MODEL_NOT_FOUND"

    selected = registry.get_selected_model("building", "spacenet2_deeplab")
    assert selected is not production
    with pytest.raises(AIModelError) as missing:
        selected.load()
    assert missing.value.code == "MODEL_FILE_NOT_FOUND"
    assert registry.get_model("building") is production


def test_model_c_adapter_masks_invalid_pixels_and_reports_training_preprocessing(
    model_c_adapter: SpaceNet2DeepLabAdapter,
) -> None:
    tile = make_tile()
    normalized_tile = model_c_adapter.normalize_tile(tile, image_min=0.0, image_max=255.0)
    output = model_c_adapter.predict(normalized_tile)
    info = model_c_adapter.get_model_info()

    assert output.probability_map.shape == (512, 512)
    assert output.probability_map.dtype == np.float32
    assert np.isfinite(output.probability_map).all()
    assert float(output.probability_map.min()) >= 0.0
    assert float(output.probability_map.max()) <= 1.0
    assert np.all(output.probability_map[~tile.valid_mask] == 0.0)
    assert output.inference_time_ms > 0.0
    assert info["training_normalization"] == "full_image_global_rgb_minmax_to_0_1"
    assert info["training_mean"] is None
    assert info["training_std"] is None
    assert info["preprocessing_status"].startswith("CONFIRMED_MINMAX")


def test_model_c_batch_inference_matches_single_tile_outputs(
    model_c_adapter: SpaceNet2DeepLabAdapter,
) -> None:
    tile = make_tile()
    load_count = model_c_adapter.get_model_info()["load_count"]
    model_c_adapter.load()
    assert model_c_adapter.get_model_info()["load_count"] == load_count
    single = model_c_adapter.predict(tile)
    batched = model_c_adapter.predict_batch([tile, tile, tile, tile])
    assert len(batched) == 4
    for output in batched:
        np.testing.assert_allclose(output.probability_map, single.probability_map, rtol=0.0, atol=2e-6)
        np.testing.assert_array_equal(output.probability_map >= 0.50, single.probability_map >= 0.50)
        assert output.inference_time_ms > 0.0


def test_model_c_onnx_runtime_engine_produces_masked_probabilities() -> None:
    adapter = SpaceNet2DeepLabAdapter(CHECKPOINT, expected_sha256=EXPECTED_SHA256, engine="onnxruntime")
    tile = make_tile()
    try:
        output = adapter.predict(tile)
        info = adapter.get_model_info()
        assert info["runtime"] == "onnxruntime"
        assert info["experimental_only"] is False
        assert output.probability_map.shape == (512, 512)
        assert output.probability_map.dtype == np.float32
        assert np.isfinite(output.probability_map).all()
        assert float(output.probability_map.min()) >= 0.0
        assert float(output.probability_map.max()) <= 1.0
        assert np.all(output.probability_map[~tile.valid_mask] == 0.0)
        assert output.inference_time_ms > 0.0
    finally:
        adapter.close()


def test_model_c_minmax_is_global_across_rgb_and_masks_invalid_pixels(
    model_c_adapter: SpaceNet2DeepLabAdapter,
) -> None:
    tile = make_tile()
    source = np.zeros((3, 512, 512), dtype=np.uint8)
    source[0, :, :] = 20
    source[1, :, :] = 120
    source[2, :, :] = 220
    source[0, 0, 0] = 0
    source[2, 0, 1] = 255
    valid = tile.valid_mask.copy()
    valid[0, 0:2] = True
    tile = tile.__class__(image=tile.image, source_rgb=source, valid_mask=valid, metadata=tile.metadata)

    normalized = model_c_adapter.normalize_tile(tile, image_min=0.0, image_max=255.0)
    np.testing.assert_allclose(normalized.image[:, 30, 30], [20 / 255, 120 / 255, 220 / 255])
    np.testing.assert_allclose(
        normalized.image[:, 30, 30], np.asarray([20, 120, 220], dtype=np.float32) / 255.0
    )
    assert normalized.image[0, 0, 0] == 0.0
    assert normalized.image[2, 0, 1] == 1.0
    assert np.all(normalized.image[:, ~valid] == 0.0)

    shifted = model_c_adapter.normalize_tile(tile, image_min=20.0, image_max=220.0)
    np.testing.assert_allclose(shifted.image[:, 30, 30], [0.0, 0.5, 1.0])
    assert not np.allclose(shifted.image[:, 30, 30], np.asarray([20, 120, 220]) / 255.0)


def test_model_c_windowed_image_stats_ignore_nodata_and_cache_by_raster_id(
    model_c_adapter: SpaceNet2DeepLabAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "stats.tif"
    data = np.full((3, 1030, 1030), 50, dtype=np.uint8)
    data[:, 0, 0] = 255
    data[:, 1029, 1029] = 5
    data[:, 20, 20] = 0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=1030,
        height=1030,
        count=3,
        dtype="uint8",
        nodata=0,
        crs="EPSG:32638",
        transform=from_origin(400000, 3760000, 0.5, 0.5),
    ) as dataset:
        dataset.write(data)

    assert model_c_adapter._image_minmax(path, raster_id="raster-one", band_indexes=(1, 2, 3)) == (5.0, 255.0)

    def fail_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("cached raster statistics should be reused")

    monkeypatch.setattr(rasterio, "open", fail_open)
    assert model_c_adapter._image_minmax(path, raster_id="raster-one", band_indexes=(1, 2, 3)) == (5.0, 255.0)


def test_model_c_small_local_raster_runs_through_results(
    model_c_adapter: SpaceNet2DeepLabAdapter, tmp_path: Path
) -> None:
    source = tmp_path / "small-rgb.tif"
    rows, cols = np.indices((512, 512))
    data = np.stack(
        ((cols % 256), (rows % 256), ((rows + cols) % 256)), axis=0
    ).astype(np.uint8)
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        width=512,
        height=512,
        count=3,
        dtype="uint8",
        nodata=0,
        crs="EPSG:32638",
        transform=from_origin(400000, 3760000, 0.5, 0.5),
    ) as dataset:
        dataset.write(data)
        dataset.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
        dataset.descriptions = ("R", "G", "B")

    raster_service = AIRasterService(tmp_path / "cache")
    prepared = raster_service.prepare_local(source, original_filename=source.name)
    registry = ModelRegistry()
    registry.register("building", lambda: BuildingModelAdapter(BuildingModelConfig(checkpoint_path=None, test_only=True)))
    registry.register_model(
        "building",
        "spacenet2_deeplab",
        lambda: model_c_adapter,
        metadata={"id": "spacenet2_deeplab", "name": "DeepLabV3 ResNet-50"},
    )
    inference = InferenceService(registry)
    class RecordingTilingService(TilingService):
        requested_tile_sizes: list[int]

        def __init__(self) -> None:
            super().__init__()
            self.requested_tile_sizes = []

        def iter_tiles(self, raster_path: Path, **kwargs: object):
            self.requested_tile_sizes.append(int(kwargs["tile_size"]))
            return super().iter_tiles(raster_path, **kwargs)

    tiling = RecordingTilingService()
    vector_result = build_building_vector_result(
        BuildingVectorPipelineRequest(raster_id=prepared.raster_id, model_id="spacenet2_deeplab"),
        raster_service=raster_service,
        tiling_service=tiling,
        inference_service=inference,
        postprocessing_service=PostProcessingService(),
        polygonization_service=BuildingPolygonizationService(),
    )
    result = BuildingResultsService().build(vector_result)

    assert tiling.requested_tile_sizes == [512]
    assert result.raster_id == prepared.raster_id
    assert result.feature_collection.type == "FeatureCollection"
    assert result.model_mode == "PRODUCTION"
    assert result.model_id == "spacenet2_deeplab"
    assert result.model_architecture == "DeepLabV3 ResNet-50"
    assert result.model_checkpoint_hash == EXPECTED_SHA256
    assert result.tile_size == 512
    assert result.preprocessing_profile == "full_raster_global_rgb_minmax_v1"
