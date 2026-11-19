from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...models import RasterRequestBase


class AIRasterPrepareRequest(RasterRequestBase):
    """Existing GeoRaster AOI/Sentinel contract, scoped to raster preparation."""

    image_id: str | None = None


class RasterBounds(BaseModel):
    left: float
    bottom: float
    right: float
    top: float


class AIRasterValidation(BaseModel):
    valid: bool
    source: str
    source_type: str | None = None
    source_profile: str | None = None
    bands: int
    band_names: list[str]
    band_indexes: list[int] = Field(default_factory=lambda: [1, 2, 3])
    color_interpretation: list[str] = Field(default_factory=list)
    crs: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    resolution_x: float = Field(gt=0)
    resolution_y: float = Field(gt=0)
    resolution_m: float = Field(gt=0)
    resolution_class: str | None = None
    bounds: RasterBounds
    transform: list[float]
    dtype: str
    nodata: float | None = None
    aoi_match: bool | None = None


class AIRasterPrepareResponse(BaseModel):
    success: bool = True
    source: str = "sentinel2"
    raster_id: str
    validation: AIRasterValidation
    quality_mode: str = "integration_test"
    warning: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIRasterCleanupResponse(BaseModel):
    success: bool
    raster_id: str
    removed: bool

