from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from app.ai.api.ai_raster_routes import get_ai_raster_service, router
from app.ai.schemas.ai_raster_schemas import AIRasterPrepareRequest
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.image_validator import ImageValidator, RasterValidationError
from app.ai.sources.base_raster_source import RasterSource
from app import gee_client


PROJECTED_BOUNDS = (500_000.0, 2_799_000.0, 501_000.0, 2_800_000.0)
AOI_WGS84 = transform_bounds("EPSG:32638", "EPSG:4326", *PROJECTED_BOUNDS)


def request_for_aoi(aoi: dict[str, Any] | None = None) -> AIRasterPrepareRequest:
    west, south, east, north = AOI_WGS84
    return AIRasterPrepareRequest(
        geometry=(aoi or {
            "type": "Polygon",
            "coordinates": [[
                [west, south], [east, south], [east, north], [west, north], [west, south]
            ]],
        }),
        start_date="2024-01-01",
        end_date="2024-01-31",
        sensor="sentinel-2",
        image_method="median_composite",
    )


class ValidFakeSource(RasterSource):
    SOURCE = "sentinel2"

    def __init__(self, payload: dict[str, Any], cache_dir: Path, raster_id: str) -> None:
        self.cache_dir = cache_dir
        self.raster_id = raster_id

    def get_raster(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{self.raster_id}.tif"
        data = np.ones((3, 100, 100), dtype=np.uint16)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=100,
            height=100,
            count=3,
            dtype="uint16",
            crs="EPSG:32638",
            transform=from_origin(500_000, 2_800_000, 10, 10),
            nodata=0,
        ) as dataset:
            dataset.write(data)
            dataset.descriptions = ("B4", "B3", "B2")
        return path

    def get_metadata(self) -> dict[str, Any]:
        return {"images_count": 4, "mosaic_method": "median_composite_mosaic"}

    def get_crs(self) -> str | None:
        return "EPSG:32638"

    def get_resolution(self) -> float | None:
        return 10.0

    def get_bounds(self) -> list[float] | None:
        return list(AOI_WGS84)


def valid_factory(payload: dict[str, Any], cache_dir: Path, raster_id: str) -> RasterSource:
    return ValidFakeSource(payload, cache_dir, raster_id)


def test_valid_aoi_produces_readable_rgb_geotiff_and_metadata(tmp_path: Path) -> None:
    service = AIRasterService(tmp_path, source_factory=valid_factory)
    result = service.prepare(request_for_aoi())

    assert result.success is True
    assert result.source == "sentinel2"
    assert result.quality_mode == "integration_test"
    assert result.validation.valid is True
    assert result.validation.band_names == ["B4", "B3", "B2"]
    assert result.validation.bands == 3
    assert result.validation.crs == "EPSG:32638"
    assert result.validation.resolution_x == pytest.approx(10)
    assert result.validation.resolution_y == pytest.approx(10)
    assert result.validation.aoi_match is True
    assert result.metadata["aoi_hash"] in result.raster_id

    path = tmp_path / f"{result.raster_id}.tif"
    with rasterio.open(path) as dataset:
        assert dataset.count == 3
        assert dataset.width == dataset.height == 100
        assert dataset.transform != rasterio.Affine.identity()
        assert dataset.bounds.left < dataset.bounds.right
        assert dataset.bounds.bottom < dataset.bounds.top
        assert dataset.read(1).shape == (100, 100)

    assert service.cleanup_raster(result.raster_id) is True
    assert list(tmp_path.iterdir()) == []


def test_invalid_aoi_is_controlled_and_does_not_create_files(tmp_path: Path) -> None:
    service = AIRasterService(tmp_path, source_factory=valid_factory)
    invalid = {"type": "Polygon", "coordinates": [[[46.0, 24.0], [46.0, 24.0]]]}
    with pytest.raises(ValueError, match="AOI invalide"):
        service.prepare(request_for_aoi(invalid))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda payload, directory, raster_id: FailingSource(directory, raster_id, "Aucune image Sentinel-2 trouvee."),
            "Aucune image",
        ),
        (
            lambda payload, directory, raster_id: FailingSource(directory, raster_id, "Echec GEE/telechargement", create_partial=True),
            "telechargement",
        ),
    ],
)
def test_source_failures_are_clear_and_clean_partial_files(
    tmp_path: Path,
    factory: Any,
    message: str,
) -> None:
    service = AIRasterService(tmp_path, source_factory=factory)
    with pytest.raises((ValueError, RuntimeError), match=message):
        service.prepare(request_for_aoi())
    assert list(tmp_path.iterdir()) == [] if tmp_path.exists() else True


class FailingSource(ValidFakeSource):
    def __init__(self, cache_dir: Path, raster_id: str, message: str, create_partial: bool = False) -> None:
        self.cache_dir = cache_dir
        self.raster_id = raster_id
        self.message = message
        self.create_partial = create_partial

    def get_raster(self) -> Path:
        if self.create_partial:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{self.raster_id}.tif.part").write_bytes(b"partial")
            raise RuntimeError(self.message)
        raise ValueError(self.message)


def test_validator_rejects_non_rgb_raster(tmp_path: Path) -> None:
    path = tmp_path / "single-band.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="uint16",
        crs="EPSG:32638",
        transform=from_origin(500_000, 2_800_000, 10, 10),
    ) as dataset:
        dataset.write(np.ones((1, 10, 10), dtype=np.uint16))
    with pytest.raises(RasterValidationError, match="au moins 3 bandes"):
        ImageValidator().validate(path, source="sentinel2")


def test_gee_adapter_reuses_mosaic_and_requests_b4_b3_b2_at_10m(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class FakeImage:
        def select(self, bands: list[str]) -> "FakeImage":
            calls["select"] = bands
            return self

        def rename(self, bands: list[str]) -> "FakeImage":
            calls["rename"] = bands
            return self

        def toUint16(self) -> "FakeImage":
            calls["uint16"] = True
            return self

        def clip(self, geom: object) -> "FakeImage":
            calls["clip"] = geom
            return self

        def getDownloadURL(self, parameters: dict[str, Any]) -> str:
            calls["download"] = parameters
            return "https://example.invalid/rgb.tif"

    geom = object()
    monkeypatch.setattr(
        gee_client,
        "_build_analysis_mosaic",
        lambda payload: {"image": FakeImage(), "geom": geom, "images_count": 3, "method": "median"},
    )
    payload = request_for_aoi().model_dump(mode="python", exclude_none=True)
    result = gee_client.create_ai_rgb_geotiff_download(payload)

    assert calls["select"] == ["B4", "B3", "B2"]
    assert calls["rename"] == ["B4", "B3", "B2"]
    assert calls["download"]["bands"] == ["B4", "B3", "B2"]
    assert calls["download"]["scale"] == 10
    assert calls["download"]["format"] == "GEO_TIFF"
    assert calls["download"]["filePerBand"] is False
    assert result["resolution_m"] == 10


def test_prepare_api_returns_metadata_only(tmp_path: Path) -> None:
    application = FastAPI()
    application.include_router(router)
    service = AIRasterService(tmp_path, source_factory=valid_factory)
    application.dependency_overrides[get_ai_raster_service] = lambda: service
    west, south, east, north = AOI_WGS84
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "sensor": "sentinel-2",
    }
    response = TestClient(application).post("/api/ai/raster/prepare", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["valid"] is True
    assert body["validation"]["band_names"] == ["B4", "B3", "B2"]
    assert "raster" not in body
    assert "path" not in body
