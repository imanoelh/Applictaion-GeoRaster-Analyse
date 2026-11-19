from __future__ import annotations

import numpy as np

from app.ai.models.base_model_adapter import BaseModelAdapter, ModelOutput
from app.ai.schemas.tile_schemas import TileMetadata
from app.ai.services.enhanced_inference import predict_mode
from app.ai.services.tiling_service import PreparedTile


class EchoAdapter(BaseModelAdapter):
    def load(self) -> None: pass
    def is_loaded(self) -> bool: return True
    def close(self) -> None: pass
    def get_model_info(self): return {"model_name": "echo", "model_version": "1", "runtime": "test", "device": "cpu", "model_mode": "TEST_ONLY"}
    def predict(self, tile: PreparedTile) -> ModelOutput:
        probability = tile.image[0].copy()
        probability[~tile.valid_mask] = 0
        return ModelOutput(probability_map=probability, inference_time_ms=1.0)


def _tile() -> PreparedTile:
    image = np.zeros((3, 640, 640), dtype=np.float32)
    image[0] = np.linspace(0.0, 1.0, 640, dtype=np.float32)[None, :]
    mask = np.ones((640, 640), dtype=np.bool_)
    mask[-1, -1] = False
    metadata = TileMetadata(
        tile_id="tile", row_index=0, col_index=0, row_offset=0, col_offset=0,
        width=640, height=640, valid_width=640, valid_height=640, tile_size=640,
        overlap_pixels=128, stride=512, padding_top=0, padding_bottom=0, padding_left=0,
        padding_right=0, valid_pixel_ratio=1.0, skip_inference=False,
        transform=[1, 0, 0, 0, -1, 0, 0, 0, 1],
        bounds={"left": 0, "bottom": 0, "right": 640, "top": 640}, crs="EPSG:32637",
        source_raster_id="test-raster",
    )
    return PreparedTile(image=image, source_rgb=image.copy(), valid_mask=mask, metadata=metadata)


def test_tta_inverts_flips_and_rotation_before_mean() -> None:
    tile = _tile()
    output = predict_mode(EchoAdapter(), tile, "tta")
    np.testing.assert_allclose(output.probability_map[tile.valid_mask], tile.image[0][tile.valid_mask], atol=1e-6)
    assert output.probability_map.shape == tile.valid_mask.shape
    assert np.isfinite(output.probability_map).all()


def test_multiscale_and_enhanced_keep_exact_grid_and_mask() -> None:
    tile = _tile()
    for mode in ("multi_scale", "enhanced"):
        output = predict_mode(EchoAdapter(), tile, mode)
        assert output.probability_map.shape == (640, 640)
        assert np.isfinite(output.probability_map).all()
        assert float(output.probability_map[~tile.valid_mask].max(initial=0.0)) == 0.0
