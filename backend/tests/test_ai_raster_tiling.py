from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import numpy as np
import pytest
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin, xy

from app.ai.api.ai_raster_routes import (
    get_ai_raster_service,
    get_tiling_service,
    router,
)
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.preprocessing_service import PreprocessingService
from app.ai.services.tiling_service import PreparedTile, TilingService


TRANSFORM = from_origin(500_000, 2_800_000, 10, 10)
CRS = "EPSG:32638"


def write_rgb_raster(
    path: Path,
    *,
    width: int,
    height: int,
    data: np.ndarray | None = None,
    nodata: int | None = 0,
) -> Path:
    values = data if data is not None else np.full((3, height, width), 2_500, dtype=np.uint16)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=3,
        dtype="uint16",
        crs=CRS,
        transform=TRANSFORM,
        nodata=nodata,
    ) as dataset:
        dataset.write(values)
        dataset.descriptions = ("B4", "B3", "B2")
    return path


def collect_tiles(path: Path, **kwargs: object) -> list[PreparedTile]:
    return list(TilingService().iter_tiles(path, raster_id="synthetic", **kwargs))


def test_small_52x57_raster_is_one_padded_georeferenced_tile(tmp_path: Path) -> None:
    path = write_rgb_raster(tmp_path / "small.tif", width=52, height=57)
    tiles = collect_tiles(path)

    assert len(tiles) == 1
    tile = tiles[0]
    assert tile.image.shape == (3, 640, 640)
    assert tile.image.dtype == np.float32
    assert tile.source_rgb.shape == (3, 640, 640)
    assert tile.metadata.valid_width == 52
    assert tile.metadata.valid_height == 57
    assert tile.metadata.padding_right == 588
    assert tile.metadata.padding_bottom == 583
    assert tile.metadata.padding_top == tile.metadata.padding_left == 0
    assert tile.valid_mask[:57, :52].all()
    assert not tile.valid_mask[57:, :].any()
    assert not tile.valid_mask[:, 52:].any()
    assert tile.metadata.valid_pixel_ratio == pytest.approx(1.0)
    assert tile.metadata.bounds.left == pytest.approx(500_000)
    assert tile.metadata.bounds.right == pytest.approx(500_520)
    assert tile.metadata.bounds.top == pytest.approx(2_800_000)
    assert tile.metadata.bounds.bottom == pytest.approx(2_799_430)


def test_1500x1300_multitile_offsets_overlap_coverage_and_edges(tmp_path: Path) -> None:
    width, height = 1500, 1300
    path = write_rgb_raster(tmp_path / "large.tif", width=width, height=height)
    tiles = collect_tiles(path, tile_size=640, overlap_ratio=0.20)

    assert len(tiles) == 9
    assert sorted({tile.metadata.col_offset for tile in tiles}) == [0, 512, 1024]
    assert sorted({tile.metadata.row_offset for tile in tiles}) == [0, 512, 1024]
    assert all(tile.metadata.overlap_pixels == 128 for tile in tiles)
    assert all(tile.metadata.stride == 512 for tile in tiles)

    coverage = np.zeros((height, width), dtype=np.uint8)
    for tile in tiles:
        meta = tile.metadata
        coverage[
            meta.row_offset : meta.row_offset + meta.valid_height,
            meta.col_offset : meta.col_offset + meta.valid_width,
        ] += 1
    assert np.all(coverage >= 1)
    assert np.any(coverage > 1)

    right = next(tile for tile in tiles if tile.metadata.row_index == 0 and tile.metadata.col_index == 2)
    bottom = next(tile for tile in tiles if tile.metadata.row_index == 2 and tile.metadata.col_index == 0)
    corner = next(tile for tile in tiles if tile.metadata.row_index == 2 and tile.metadata.col_index == 2)
    assert (right.metadata.valid_width, right.metadata.padding_right) == (476, 164)
    assert (bottom.metadata.valid_height, bottom.metadata.padding_bottom) == (276, 364)
    assert (corner.metadata.valid_width, corner.metadata.valid_height) == (476, 276)
    assert (corner.metadata.padding_right, corner.metadata.padding_bottom) == (164, 364)


def test_tile_local_to_global_and_map_coordinates_match_source(tmp_path: Path) -> None:
    path = write_rgb_raster(tmp_path / "georef.tif", width=1500, height=1300)
    tiles = collect_tiles(path)
    service = TilingService()
    selected = [tiles[0], tiles[4], tiles[8]]

    for tile in selected:
        local_x = min(100, tile.metadata.valid_width - 1)
        local_y = min(120, tile.metadata.valid_height - 1)
        global_col, global_row = service.tile_pixel_to_raster_pixel(
            tile.metadata, local_x, local_y
        )
        assert global_col == tile.metadata.col_offset + local_x
        assert global_row == tile.metadata.row_offset + local_y
        expected_x, expected_y = xy(TRANSFORM, global_row, global_col, offset="center")
        actual_x, actual_y = service.tile_pixel_to_map_coordinates(
            tile.metadata, local_x, local_y
        )
        assert actual_x == pytest.approx(expected_x, abs=1e-9)
        assert actual_y == pytest.approx(expected_y, abs=1e-9)


def test_padding_pixel_cannot_be_converted_to_real_coordinates(tmp_path: Path) -> None:
    path = write_rgb_raster(tmp_path / "padding.tif", width=52, height=57)
    tile = collect_tiles(path)[0]
    with pytest.raises(ValueError, match="padding"):
        TilingService.tile_pixel_to_raster_pixel(tile.metadata, 52, 10)
    with pytest.raises(ValueError, match="padding"):
        TilingService.tile_pixel_to_map_coordinates(tile.metadata, 10, 57)


def test_nodata_mask_ratios_and_skip_inference(tmp_path: Path) -> None:
    data = np.full((3, 640, 1280), 2_000, dtype=np.uint16)
    data[:, :, :320] = 0
    data[:, :, 640:] = 0
    path = write_rgb_raster(tmp_path / "nodata.tif", width=1280, height=640, data=data)
    tiles = collect_tiles(
        path,
        tile_size=640,
        overlap_ratio=0,
        min_valid_pixel_ratio=0.05,
    )

    assert len(tiles) == 2
    partial, empty = tiles
    assert partial.metadata.valid_pixel_ratio == pytest.approx(0.5)
    assert partial.metadata.skip_inference is False
    assert partial.valid_mask[:, :320].sum() == 0
    assert partial.valid_mask[:, 320:].all()
    assert empty.metadata.valid_pixel_ratio == pytest.approx(0.0)
    assert empty.metadata.skip_inference is True
    assert not empty.valid_mask.any()
    assert np.all(empty.image == 0)


def test_fixed_normalization_is_identical_across_tiles_and_clips() -> None:
    service = PreprocessingService()
    first = np.array([[[0, 5_000, 12_000]], [[0, 5_000, 12_000]], [[0, 5_000, 12_000]]], dtype=np.uint16)
    second = np.array([[[5_000, 1_000, 5_000]], [[5_000, 1_000, 5_000]], [[5_000, 1_000, 5_000]]], dtype=np.uint16)
    first_mask = np.array([[True, True, True]])
    second_mask = np.array([[True, False, True]])

    normalized_first = service.normalize(first, first_mask)
    normalized_second = service.normalize(second, second_mask)
    assert normalized_first.dtype == np.float32
    assert normalized_first[:, 0, 0].tolist() == pytest.approx([0.0, 0.0, 0.0])
    assert normalized_first[:, 0, 1].tolist() == pytest.approx([0.5, 0.5, 0.5])
    assert normalized_first[:, 0, 2].tolist() == pytest.approx([1.0, 1.0, 1.0])
    assert normalized_second[:, 0, 0].tolist() == pytest.approx(normalized_first[:, 0, 1].tolist())
    assert normalized_second[:, 0, 2].tolist() == pytest.approx(normalized_first[:, 0, 1].tolist())
    assert np.all(normalized_second[:, 0, 1] == 0)


@pytest.mark.parametrize(
    ("tile_size", "overlap"),
    [(0, 0.2), (640, -0.1), (640, 1.0)],
)
def test_invalid_tiling_configuration_is_rejected(tile_size: int, overlap: float) -> None:
    with pytest.raises(ValueError):
        TilingService.configuration(tile_size, overlap)


def test_tiling_is_a_lazy_generator(tmp_path: Path) -> None:
    path = write_rgb_raster(tmp_path / "lazy.tif", width=1500, height=1300)
    iterator = TilingService().iter_tiles(path)
    assert isinstance(iterator, Iterator)
    first = next(iterator)
    assert first.metadata.tile_id == "tile_0001"
    iterator.close()


def test_tiling_api_returns_only_limited_metadata(tmp_path: Path) -> None:
    raster_id = "ai-s2-20240101-0123456789ab-abcdef012345"
    raster_path = write_rgb_raster(tmp_path / f"{raster_id}.tif", width=1500, height=1300)
    validation = {"valid": True, "width": 1500, "height": 1300}
    (tmp_path / f"{raster_id}.json").write_text(
        json.dumps({"raster_id": raster_id, "validation": validation, "metadata": {}}),
        encoding="utf-8",
    )
    assert raster_path.is_file()

    application = FastAPI()
    application.include_router(router)
    raster_service = AIRasterService(tmp_path)
    tiling_service = TilingService()
    application.dependency_overrides[get_ai_raster_service] = lambda: raster_service
    application.dependency_overrides[get_tiling_service] = lambda: tiling_service
    response = TestClient(application).post(
        "/api/ai/raster/tile",
        json={
            "raster_id": raster_id,
            "tile_size": 640,
            "overlap_ratio": 0.2,
            "min_valid_pixel_ratio": 0.05,
            "max_tiles_metadata": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preprocessing"]["input_dtype"] == "uint16"
    assert body["preprocessing"]["output_dtype"] == "float32"
    assert body["tiling"]["tiles_count"] == 9
    assert body["tiling"]["metadata_returned"] == 2
    assert len(body["tiles"]) == 2
    assert "image" not in body["tiles"][0]
    assert "source_rgb" not in body["tiles"][0]
    assert "valid_mask" not in body["tiles"][0]

