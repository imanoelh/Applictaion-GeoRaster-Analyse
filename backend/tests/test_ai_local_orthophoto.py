from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from app.ai.api.ai_raster_routes import get_ai_raster_service, router
from app.ai.errors import AIRasterError
from app.ai.models.base_model_adapter import BaseModelAdapter, ModelOutput
from app.ai.registry.model_registry import ModelRegistry
from app.ai.services.ai_raster_service import AIRasterService
from app.ai.services.image_validator import ImageValidator, RasterValidationError
from app.ai.services.inference_service import InferenceService
from app.ai.services.preprocessing_profiles import RGBOrthophotoProfile
from app.ai.services.tiling_service import TilingService
from app.ai.sources.local_raster_source import LocalRasterSource


ORTHO_PROFILE = "rgb_orthophoto_uint8_v1"


def write_orthophoto(
    path: Path,
    *,
    width: int = 1500,
    height: int = 1300,
    dtype: str = "uint8",
    nodata: int | None = None,
    colorinterp: tuple[ColorInterp, ColorInterp, ColorInterp] | None = (
        ColorInterp.red,
        ColorInterp.green,
        ColorInterp.blue,
    ),
    descriptions: tuple[str, str, str] | None = ("R", "G", "B"),
    crs: str | None = "EPSG:32638",
) -> Path:
    rows, cols = np.indices((height, width))
    maximum = 255 if dtype == "uint8" else 65_535
    data = np.stack(
        (
            (cols % (maximum + 1)),
            (rows % (maximum + 1)),
            ((rows + cols) % (maximum + 1)),
        )
    ).astype(dtype)
    if nodata is not None:
        data[:, :100, :100] = nodata
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=3,
        dtype=dtype,
        crs=crs,
        transform=from_origin(500_000.0, 2_800_000.0, 0.25, 0.25),
        nodata=nodata,
    ) as dataset:
        dataset.write(data)
        if colorinterp is not None:
            dataset.colorinterp = colorinterp
        if descriptions is not None:
            dataset.descriptions = descriptions
    return path


def prepare(path: Path, cache: Path, *, mapping: dict[str, int] | None = None):
    return AIRasterService(cache).prepare_local(
        path,
        original_filename=path.name,
        band_mapping=mapping,
    )


class DeterministicAdapter(BaseModelAdapter):
    def __init__(self) -> None:
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def is_loaded(self) -> bool:
        return self.loaded

    def predict(self, tile):
        self.load()
        return ModelOutput(tile.image[0].astype(np.float32, copy=True), 0.01)

    def get_model_info(self):
        return {
            "model_name": "orthophoto-contract-test",
            "model_version": "test-v1",
            "runtime": "numpy-test-double",
            "device": "cpu",
            "loaded": self.loaded,
            "model_mode": "TEST_ONLY",
            "model_load_time_ms": 0.0,
        }

    def close(self) -> None:
        self.loaded = False


def test_local_source_validation_metadata_and_cache_isolation(tmp_path: Path) -> None:
    source_path = write_orthophoto(tmp_path / "ortho.tif")
    cache = tmp_path / "cache"
    result = prepare(source_path, cache)

    assert result.source == "orthophoto_local"
    assert result.validation.source_type == "orthophoto_local"
    assert result.validation.source_profile == ORTHO_PROFILE
    assert result.validation.band_indexes == [1, 2, 3]
    assert result.validation.dtype == "uint8"
    assert result.validation.resolution_x == pytest.approx(0.25)
    assert result.validation.resolution_y == pytest.approx(0.25)
    assert result.validation.resolution_class == "VERY_HIGH_RESOLUTION"
    assert result.metadata["content_sha256"]
    assert result.metadata["preprocessing_profile"] == ORTHO_PROFILE

    path, sidecar = AIRasterService(cache).get_validated_artifact(result.raster_id)
    local = LocalRasterSource(source_path, cache, "unused", original_filename="ortho.tif")
    assert path.is_file()
    assert sidecar["metadata"]["source_type"] == "orthophoto_local"
    assert local.SOURCE == "orthophoto_local"

    changed = write_orthophoto(tmp_path / "ortho-changed.tif", width=1499)
    second = prepare(changed, cache)
    assert second.raster_id != result.raster_id
    assert result.raster_id.startswith("ai-ortho-")
    assert not result.raster_id.startswith("ai-s2-")


def test_rgb_normalization_is_fixed_and_tile_independent(tmp_path: Path) -> None:
    profile = RGBOrthophotoProfile()
    values = np.array([[[0, 127, 255]], [[0, 127, 255]], [[0, 127, 255]]], dtype=np.uint8)
    mask = np.ones((1, 3), dtype=np.bool_)
    output = profile.normalize(values, mask)
    assert output.dtype == np.float32
    assert output[0, 0].tolist() == pytest.approx([0.0, 127.0 / 255.0, 1.0])

    path = write_orthophoto(tmp_path / "constant.tif", width=900, height=640)
    with rasterio.open(path, "r+") as dataset:
        dataset.write(np.full((3, 640, 900), 127, dtype=np.uint8))
    tiles = list(
        TilingService().iter_tiles(
            path,
            tile_size=640,
            overlap_ratio=0.20,
            preprocessing_profile=ORTHO_PROFILE,
            band_indexes=(1, 2, 3),
        )
    )
    assert len(tiles) == 2
    assert tiles[0].image[0, 10, 10] == pytest.approx(127.0 / 255.0)
    assert tiles[1].image[0, 10, 10] == pytest.approx(127.0 / 255.0)


def test_band_order_uses_colorinterp_and_rejects_ambiguity(tmp_path: Path) -> None:
    path = write_orthophoto(
        tmp_path / "bgr.tif",
        width=10,
        height=10,
        colorinterp=(ColorInterp.blue, ColorInterp.green, ColorInterp.red),
        descriptions=None,
    )
    with rasterio.open(path, "r+") as dataset:
        dataset.write(np.full((10, 10), 10, dtype=np.uint8), 1)
        dataset.write(np.full((10, 10), 20, dtype=np.uint8), 2)
        dataset.write(np.full((10, 10), 30, dtype=np.uint8), 3)
    validation = ImageValidator().validate(path, source="orthophoto_local")
    assert validation["band_indexes"] == [3, 2, 1]
    tile = next(
        TilingService().iter_tiles(
            path,
            tile_size=10,
            overlap_ratio=0,
            preprocessing_profile=ORTHO_PROFILE,
            band_indexes=(3, 2, 1),
        )
    )
    assert tile.source_rgb[:, 0, 0].tolist() == [30, 20, 10]

    ambiguous = write_orthophoto(
        tmp_path / "ambiguous.tif",
        width=10,
        height=10,
        colorinterp=(ColorInterp.undefined,) * 3,
        descriptions=None,
    )
    with pytest.raises(RasterValidationError) as error:
        ImageValidator().validate(ambiguous, source="orthophoto_local")
    assert error.value.code == "UNSUPPORTED_BAND_CONFIGURATION"
    configured = ImageValidator().validate(
        ambiguous,
        source="orthophoto_local",
        band_mapping={"R": 1, "G": 2, "B": 3},
    )
    assert configured["band_indexes"] == [1, 2, 3]


def test_unsupported_dtype_and_missing_crs_are_business_errors(tmp_path: Path) -> None:
    uint16 = write_orthophoto(tmp_path / "uint16.tif", dtype="uint16")
    with pytest.raises(RasterValidationError) as dtype_error:
        ImageValidator().validate(uint16, source="orthophoto_local")
    assert dtype_error.value.code == "UNSUPPORTED_RASTER_DTYPE"

    no_crs = write_orthophoto(tmp_path / "no-crs.tif", crs=None)
    with pytest.raises(RasterValidationError) as crs_error:
        ImageValidator().validate(no_crs, source="orthophoto_local")
    assert crs_error.value.code == "RASTER_CRS_MISSING"


def test_multitile_nodata_padding_and_georeferencing(tmp_path: Path) -> None:
    path = write_orthophoto(tmp_path / "large-nodata.tif", nodata=0)
    tiles = list(
        TilingService().iter_tiles(
            path,
            raster_id="orthophoto-contract",
            preprocessing_profile=ORTHO_PROFILE,
            band_indexes=(1, 2, 3),
        )
    )
    assert len(tiles) == 9
    assert sorted({tile.metadata.row_offset for tile in tiles}) == [0, 512, 1024]
    assert sorted({tile.metadata.col_offset for tile in tiles}) == [0, 512, 1024]
    assert tiles[-1].metadata.valid_width == 476
    assert tiles[-1].metadata.valid_height == 276
    assert tiles[-1].metadata.padding_right == 164
    assert tiles[-1].metadata.padding_bottom == 364
    assert tiles[0].valid_mask[:100, :100].sum() == 0
    assert tiles[0].metadata.valid_pixel_ratio < 1.0
    assert np.all(tiles[0].image[:, :100, :100] == 0)
    assert tiles[0].metadata.source_profile == ORTHO_PROFILE
    map_x, map_y = TilingService.tile_pixel_to_map_coordinates(tiles[4].metadata, 0, 0)
    assert map_x == pytest.approx(500_000.0 + (512.5 * 0.25))
    assert map_y == pytest.approx(2_800_000.0 - (512.5 * 0.25))


def test_nodata_tile_can_be_skipped(tmp_path: Path) -> None:
    path = write_orthophoto(tmp_path / "mostly-empty.tif", width=640, height=640, nodata=0)
    with rasterio.open(path, "r+") as dataset:
        dataset.write(np.zeros((3, 640, 640), dtype=np.uint8))
        dataset.write(np.ones((3, 10, 10), dtype=np.uint8), window=((0, 10), (0, 10)))
    tile = next(
        TilingService().iter_tiles(
            path,
            min_valid_pixel_ratio=0.05,
            preprocessing_profile=ORTHO_PROFILE,
            band_indexes=(1, 2, 3),
        )
    )
    assert tile.metadata.valid_pixel_ratio == pytest.approx(100 / (640 * 640))
    assert tile.metadata.skip_inference is True


def test_orthophoto_runs_through_shared_inference_test_only(tmp_path: Path) -> None:
    source = write_orthophoto(tmp_path / "inference.tif", width=700, height=640)
    result = prepare(source, tmp_path / "cache")
    service = AIRasterService(tmp_path / "cache")
    raster_path, sidecar = service.get_validated_artifact(result.raster_id)
    profile, indexes = service.get_preprocessing_context(sidecar)
    tiles = TilingService().iter_tiles(
        raster_path,
        raster_id=result.raster_id,
        preprocessing_profile=profile,
        band_indexes=indexes,
    )
    registry = ModelRegistry()
    registry.register("building", DeterministicAdapter)
    summary = InferenceService(registry).summarize(tiles)
    assert summary["model"]["model_mode"] == "TEST_ONLY"
    assert summary["tiles"] == {"total": 2, "processed": 2, "skipped": 0}
    assert 0.0 <= summary["prediction"]["positive_ratio"] <= 1.0


def test_local_upload_api_is_path_safe_and_reuses_shared_tiling(tmp_path: Path) -> None:
    path = write_orthophoto(tmp_path / "api.tif", width=650, height=640)
    cache = tmp_path / "cache"
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_ai_raster_service] = lambda: AIRasterService(cache)
    client = TestClient(application)

    traversal = client.post(
        "/api/ai/raster/local?filename=../evil.tif",
        content=path.read_bytes(),
        headers={"content-type": "image/tiff"},
    )
    assert traversal.status_code == 422
    assert not (tmp_path / "evil.tif").exists()

    response = client.post(
        "/api/ai/raster/local?filename=api.tif",
        content=path.read_bytes(),
        headers={"content-type": "image/tiff"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "orthophoto_local"
    tiled = client.post("/api/ai/raster/tile", json={"raster_id": body["raster_id"]})
    assert tiled.status_code == 200, tiled.text
    assert tiled.json()["preprocessing"]["profile"] == ORTHO_PROFILE
    assert tiled.json()["tiling"]["tiles_count"] == 2
    assert list(cache.glob(".upload-*")) == []


def test_local_upload_enforces_configurable_size_and_real_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_ai_raster_service] = lambda: AIRasterService(cache)
    client = TestClient(application)

    monkeypatch.setenv("AI_LOCAL_RASTER_MAX_BYTES", "8")
    too_large = client.post(
        "/api/ai/raster/local?filename=large.tif",
        content=b"123456789",
        headers={"content-type": "image/tiff"},
    )
    assert too_large.status_code == 422
    assert too_large.json()["detail"]["code"] == "LOCAL_RASTER_INVALID"
    assert list(cache.glob(".upload-*")) == []

    monkeypatch.setenv("AI_LOCAL_RASTER_MAX_BYTES", "1024")
    fake_tiff = client.post(
        "/api/ai/raster/local?filename=fake.tif",
        content=b"not-a-geotiff",
        headers={"content-type": "image/tiff"},
    )
    assert fake_tiff.status_code == 422
    assert fake_tiff.json()["detail"]["code"] == "LOCAL_RASTER_INVALID"
    assert list(cache.glob(".upload-*")) == []

