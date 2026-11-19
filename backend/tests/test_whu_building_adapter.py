from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from app.ai.models.whu_building_adapter import WHUBuildingModelAdapter
from app.ai.registry.model_registry import create_default_model_registry
from app.ai.schemas.tile_schemas import TileBounds, TileMetadata
from app.ai.services.tiling_service import PreparedTile


EXPECTED_SHA256 = "922af7c96c0dc44256ab8b4d1a071f2151e0a921c997af80b55bb766bcc30dc6"


def test_whu_checkpoint_strict_load_and_probability_contract() -> None:
    backend = Path(__file__).resolve().parents[1]
    checkpoint = backend / "data/models/building/experimental/whu_unetplusplus_effb4/model.pth"
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert digest == EXPECTED_SHA256

    adapter = WHUBuildingModelAdapter(checkpoint)
    metadata = TileMetadata(
        tile_id="whu-smoke",
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
        source_raster_id="whu-smoke",
        source_profile="rgb_orthophoto_uint8_v1",
    )
    tile = PreparedTile(
        image=np.full((3, 512, 512), 0.5, dtype=np.float32),
        source_rgb=np.full((512, 512, 3), 127, dtype=np.uint8),
        valid_mask=np.ones((512, 512), dtype=np.bool_),
        metadata=metadata,
    )
    try:
        prediction = adapter.predict(tile)
        info = adapter.get_model_info()
        assert adapter.is_loaded()
        assert info["model_mode"] == "EXPERIMENTAL"
        assert info["runtime"] == "pytorch"
        assert info["input_size"] == 512
        assert info["class_count"] == 2
        assert prediction.probability_map.shape == (512, 512)
        assert prediction.probability_map.dtype == np.float32
        assert np.isfinite(prediction.probability_map).all()
        assert float(prediction.probability_map.min()) >= 0
        assert float(prediction.probability_map.max()) <= 1
    finally:
        adapter.close()


def test_whu_is_experimental_and_spacenet_remains_default() -> None:
    registry = create_default_model_registry()
    models = {item["id"]: item for item in registry.list_models("building")}
    assert models["spacenet2_deeplab"]["default"] is True
    assert models["whu_unetplusplus_effb4"]["default"] is False
    assert models["whu_unetplusplus_effb4"]["status"] == "EXPERIMENTAL"
    assert type(registry.get_selected_model("building", "whu_unetplusplus_effb4")) is WHUBuildingModelAdapter
    assert registry.get_selected_model("building").get_model_info()["model_id"] == "spacenet2_deeplab"
    registry.close_all()
