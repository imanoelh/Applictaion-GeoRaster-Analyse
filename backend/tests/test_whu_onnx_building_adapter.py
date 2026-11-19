from __future__ import annotations

import numpy as np

from app.ai.models.whu_onnx_building_adapter import WHUOnnxBuildingModelAdapter
from app.ai.registry.model_registry import create_default_model_registry
from app.ai.schemas.tile_schemas import TileBounds, TileMetadata
from app.ai.services.tiling_service import PreparedTile


def make_tile() -> PreparedTile:
    metadata = TileMetadata(
        tile_id="whu-onnx-smoke",
        row_index=0,
        col_index=0,
        row_offset=0,
        col_offset=0,
        width=512,
        height=512,
        valid_width=512,
        valid_height=512,
        tile_size=512,
        overlap_pixels=256,
        stride=256,
        padding_top=0,
        padding_bottom=0,
        padding_left=0,
        padding_right=0,
        valid_pixel_ratio=1.0,
        skip_inference=False,
        transform=[0.35, 0, 582091.89, 0, -0.35, 2368180.84, 0, 0, 1],
        bounds=TileBounds(left=582091.89, bottom=2368001.64, right=582271.09, top=2368180.84),
        crs="EPSG:32637",
        source_raster_id="whu-onnx-smoke",
        source_profile="rgb_orthophoto_uint8_v1",
    )
    return PreparedTile(
        image=np.full((3, 512, 512), 0.5, dtype=np.float32),
        source_rgb=np.full((512, 512, 3), 127, dtype=np.uint8),
        valid_mask=np.ones((512, 512), dtype=np.bool_),
        metadata=metadata,
    )


def test_whu_onnx_strict_artifact_load_and_probability_contract() -> None:
    adapter = WHUOnnxBuildingModelAdapter()
    try:
        prediction = adapter.predict(make_tile())
        info = adapter.get_model_info()
        assert adapter.is_loaded()
        assert info["runtime"] == "onnxruntime"
        assert info["model_mode"] == "EXPERIMENTAL"
        assert info["intra_op_threads"] == 4
        assert prediction.probability_map.shape == (512, 512)
        assert prediction.probability_map.dtype == np.float32
        assert np.isfinite(prediction.probability_map).all()
        assert float(prediction.probability_map.min()) >= 0.0
        assert float(prediction.probability_map.max()) <= 1.0
    finally:
        adapter.close()


def test_whu_onnx_remains_experimental_and_model_c_stays_default() -> None:
    registry = create_default_model_registry()
    try:
        models = {item["id"]: item for item in registry.list_models("building")}
        assert models["spacenet2_deeplab"]["default"] is True
        assert models["whu_unetplusplus_effb4"]["default"] is False
        assert models[WHUOnnxBuildingModelAdapter.MODEL_ID]["default"] is False
        assert models[WHUOnnxBuildingModelAdapter.MODEL_ID]["status"] == "EXPERIMENTAL"
        assert isinstance(
            registry.get_selected_model("building", WHUOnnxBuildingModelAdapter.MODEL_ID),
            WHUOnnxBuildingModelAdapter,
        )
    finally:
        registry.close_all()
