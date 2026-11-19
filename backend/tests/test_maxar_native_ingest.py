from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin
from fastapi.testclient import TestClient

from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.maxar_multispectral_profile import MaxarMultispectralProfile
from app.main import app


def _make_maxar(path: Path) -> None:
    profile = {
        "driver": "GTiff", "width": 64, "height": 64, "count": 8,
        "dtype": "uint16", "crs": "EPSG:32637", "transform": from_origin(500000, 4000000, 0.35, 0.35),
        "tiled": True, "blockxsize": 32, "blockysize": 32, "compress": "DEFLATE",
    }
    with rasterio.open(path, "w", **profile) as dst:
        for band in range(1, 9):
            dst.write((band * 1000 + np.arange(64 * 64, dtype=np.uint16).reshape(64, 64)), band)
        dst.colorinterp = (ColorInterp.undefined,) * 8
        dst.update_tags(PRODUCT="Maxar SkyWatch COG", AREA_OR_POINT="Area")


def test_maxar_profile_identifies_and_converts_windowed(tmp_path: Path) -> None:
    source = tmp_path / "25JUL28115945-S3DS-maxar_COG.tif"
    output = tmp_path / "rgb.tif"
    _make_maxar(source)

    identity = MaxarMultispectralProfile.identify(source)
    assert identity is not None
    assert identity["rgb_bands"] == {"R": 5, "G": 3, "B": 2}
    result = MaxarMultispectralProfile.convert_to_rgb(source, output)
    assert result["profile"] == MaxarMultispectralProfile.name
    with rasterio.open(output) as dataset:
        assert dataset.count == 3
        assert tuple(dataset.dtypes) == ("uint8",) * 3
        assert tuple(dataset.colorinterp) == (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
        assert dataset.tags()["STRETCH_STRATEGY"] == "p2-p98_per_channel"
        assert dataset.transform == from_origin(500000, 4000000, 0.35, 0.35)


def test_large_upload_state_is_ordered_and_cleaned(tmp_path: Path) -> None:
    service = AIRasterService(cache_dir=tmp_path)
    created = service.create_large_upload("maxar.tif", 6)
    assert created["chunk_size"] >= 1024 * 1024
    state = service.get_large_upload(created["upload_id"])
    assert state["next_chunk"] == 0
    path = service.large_upload_path(created["upload_id"])
    path.write_bytes(b"abc")
    state.update({"received_bytes": 3, "next_chunk": 1})
    service.save_large_upload_state(state)
    assert service.get_large_upload(created["upload_id"])["received_bytes"] == 3
    assert service.cleanup_large_upload(created["upload_id"])
    assert not path.exists()


def test_maxar_chunk_api_prepares_rgb_and_reuses_contract(tmp_path: Path) -> None:
    source = tmp_path / "25JUL28115945-S3DS-maxar_COG.tif"
    _make_maxar(source)
    payload = source.read_bytes()
    client = TestClient(app)
    init = client.post("/api/ai/raster/local/maxar/init", params={"filename": source.name, "size_bytes": len(payload)})
    assert init.status_code == 200, init.text
    info = init.json()
    half = len(payload) // 2
    for index, chunk in enumerate((payload[:half], payload[half:])):
        response = client.post(
            f"/api/ai/raster/local/maxar/{info['upload_id']}/chunk",
            params={"index": index, "total_chunks": 2},
            content=chunk,
        )
        assert response.status_code == 200, response.text
    complete = client.post(f"/api/ai/raster/local/maxar/{info['upload_id']}/complete")
    assert complete.status_code == 200, complete.text
    result = complete.json()
    assert result["validation"]["bands"] == 3
    assert result["metadata"]["maxar_rgb_bands"] == {"R": 5, "G": 3, "B": 2}
