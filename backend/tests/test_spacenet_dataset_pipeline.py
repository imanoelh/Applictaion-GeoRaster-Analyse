from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from backend.scripts.building_dataset.prepare_spacenet_building_dataset import (
    discover_pairs,
    extract_spacenet_sample_id,
    prepare_dataset,
    uint16_to_uint8_percentile,
)


def test_uint16_percentile_conversion_clips_and_returns_uint8() -> None:
    rgb = np.array(
        [[[0, 100, 200, 1000]], [[10, 110, 210, 1010]], [[20, 120, 220, 1020]]],
        dtype=np.uint16,
    )
    converted = uint16_to_uint8_percentile(rgb, low_percentile=0, high_percentile=100)
    assert converted.dtype == np.uint8
    assert converted.shape == rgb.shape
    assert converted[:, :, 0].tolist() == [[0], [0], [0]]
    assert converted[:, :, -1].tolist() == [[255], [255], [255]]


def test_uint16_percentile_constant_band_is_safe() -> None:
    rgb = np.full((3, 4, 4), 512, dtype=np.uint16)
    converted = uint16_to_uint8_percentile(rgb)
    assert converted.dtype == np.uint8
    assert set(np.unique(converted).tolist()) == {255}


def test_spacenet_canonical_ids_cover_real_names_and_extensions() -> None:
    assert extract_spacenet_sample_id("RGB-PanSharpen_AOI_5_Khartoum_img1.tif") == "AOI_5_Khartoum_img1"
    assert extract_spacenet_sample_id("buildings_AOI_5_Khartoum_img1.geojson") == "AOI_5_Khartoum_img1"
    assert extract_spacenet_sample_id("MUL_AOI_5_Khartoum_img1001.tiff") == "AOI_5_Khartoum_img1001"
    assert extract_spacenet_sample_id(r"D:\SpaceNet\PAN_AOI_5_Khartoum_img10.tif") == "AOI_5_Khartoum_img10"


def test_spacenet_img_numbers_and_aoi_never_collide() -> None:
    values = [
        extract_spacenet_sample_id("RGB-PanSharpen_AOI_5_Khartoum_img1.tif"),
        extract_spacenet_sample_id("RGB-PanSharpen_AOI_5_Khartoum_img10.tif"),
        extract_spacenet_sample_id("RGB-PanSharpen_AOI_5_Khartoum_img100.tif"),
        extract_spacenet_sample_id("RGB-PanSharpen_AOI_2_Vegas_img1.tif"),
    ]
    assert len(set(values)) == 4


def test_pairing_reports_missing_and_duplicate_ids_without_silent_choice(tmp_path: Path) -> None:
    imagery = tmp_path / "images"; labels = tmp_path / "labels"
    imagery.mkdir(); labels.mkdir()
    for name in ("RGB-PanSharpen_AOI_5_Khartoum_img1.tif", "RGB-PanSharpen_AOI_5_Khartoum_img10.tif", "RGB-PanSharpen_AOI_5_Khartoum_img99.tif"):
        (imagery / name).touch()
    (labels / "buildings_AOI_5_Khartoum_img1.geojson").touch()
    (labels / "buildings_AOI_5_Khartoum_img10.geojson").touch()
    (labels / "duplicate_AOI_5_Khartoum_img10.geojson").touch()
    pairs, rejected = discover_pairs(imagery, labels)
    assert [pair.source_id for pair in pairs] == ["AOI_5_Khartoum_img1"]
    reasons = {(item["canonical_sample_id"], item["reason"]) for item in rejected}
    assert ("AOI_5_Khartoum_img10", "DUPLICATE_LABEL_CANONICAL_ID") in reasons
    assert ("AOI_5_Khartoum_img99", "NO_MATCHING_LABEL") in reasons


def _fixture(root: Path) -> tuple[Path, Path]:
    imagery = root / "images"; labels = root / "labels"
    imagery.mkdir(); labels.mkdir()
    path = imagery / "scene_01_RGB.tif"
    # A PROJ installation on the validation host points to an incompatible
    # PostgreSQL proj.db; use an explicit CRS string so the fixture remains
    # runnable without consulting the EPSG database.
    profile = {"driver": "GTiff", "width": 512, "height": 512, "count": 3, "dtype": "uint8", "crs": "+proj=utm +zone=37 +datum=WGS84 +units=m +no_defs", "transform": from_origin(500000, 2800512, 1, 1)}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((3, 512, 512), 120, dtype=np.uint8))
    payload = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[500010, 2800500], [500030, 2800500], [500030, 2800480], [500010, 2800480], [500010, 2800500]]]}}]}
    (labels / "scene_01_buildings.geojson").write_text(json.dumps(payload), encoding="utf-8")
    return imagery, labels


def test_prepare_rasterizes_aligned_512_tile_and_manifest(tmp_path: Path) -> None:
    imagery, labels = _fixture(tmp_path)
    out = tmp_path / "dataset"
    result = prepare_dataset(imagery=imagery, labels=labels, output=out, test_ratio=0.0, val_ratio=0.0, train_ratio=1.0, max_empty_tile_ratio=0.35)
    assert result["total_tiles"] == 1
    manifest = json.loads((out / "metadata/dataset_manifest.json").read_text())
    item = manifest["records"][0]
    with rasterio.open(out / item["image_path"]) as image, rasterio.open(out / item["mask_path"]) as mask:
        assert image.width == image.height == mask.width == mask.height == 512
        assert image.transform == mask.transform
        values = set(np.unique(mask.read(1)).tolist())
        assert values <= {0, 255} and 255 in values


def test_dry_run_and_split_reproducible(tmp_path: Path) -> None:
    imagery, labels = _fixture(tmp_path)
    first = prepare_dataset(imagery=imagery, labels=labels, output=tmp_path / "a", dry_run=True, limit=5)
    second = prepare_dataset(imagery=imagery, labels=labels, output=tmp_path / "b", dry_run=True, limit=5)
    assert first == second
    assert first["pairs"] == 1


def test_nodata_window_is_rejected(tmp_path: Path) -> None:
    imagery, labels = _fixture(tmp_path)
    with rasterio.open(imagery / "scene_01_RGB.tif", "r+") as dst:
        dst.nodata = 0
        dst.write(np.zeros((3, 512, 512), dtype=np.uint8))
    result = prepare_dataset(imagery=imagery, labels=labels, output=tmp_path / "dataset", test_ratio=0.0, val_ratio=0.0, train_ratio=1.0, nodata_threshold=0.1)
    assert result["total_tiles"] == 0
    assert result["rejected_tiles"] >= 1
