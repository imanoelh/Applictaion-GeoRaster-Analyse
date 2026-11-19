from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AITilingRequest(BaseModel):
    raster_id: str = Field(min_length=1)
    tile_size: int = Field(default=640, gt=0, le=4096)
    overlap_ratio: float = Field(default=0.20, ge=0.0, lt=1.0)
    min_valid_pixel_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    max_tiles_metadata: int = Field(default=10, ge=0, le=100)

    @field_validator("overlap_ratio")
    @classmethod
    def validate_stride(cls, value: float, info: object) -> float:
        # The exact pixel stride also depends on tile_size and is validated by
        # TilingService. This validator keeps NaN/Infinity out of the contract.
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("overlap_ratio doit etre un nombre fini")
        return value


class TileBounds(BaseModel):
    left: float
    bottom: float
    right: float
    top: float


class TileMetadata(BaseModel):
    tile_id: str
    row_index: int = Field(ge=0)
    col_index: int = Field(ge=0)
    row_offset: int = Field(ge=0)
    col_offset: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    valid_width: int = Field(gt=0)
    valid_height: int = Field(gt=0)
    tile_size: int = Field(gt=0)
    overlap_pixels: int = Field(ge=0)
    stride: int = Field(gt=0)
    padding_top: int = Field(ge=0)
    padding_bottom: int = Field(ge=0)
    padding_left: int = Field(ge=0)
    padding_right: int = Field(ge=0)
    valid_pixel_ratio: float = Field(ge=0.0, le=1.0)
    skip_inference: bool
    transform: list[float]
    bounds: TileBounds
    crs: str
    source_raster_id: str | None = None
    source_profile: str | None = None


class PreprocessingMetadata(BaseModel):
    profile: str = "sentinel2_sr_v1"
    bands: list[str]
    band_mapping: dict[str, str]
    band_indexes: list[int] = Field(default_factory=lambda: [1, 2, 3])
    input_dtype: str
    output_dtype: str
    normalization_method: str
    normalization_version: str
    input_range: list[float] = Field(default_factory=lambda: [0.0, 10_000.0])
    clipping_min: float
    clipping_max: float
    scale_factor: float
    nodata: float | None = None


class TilingSummary(BaseModel):
    tile_size: int
    overlap_ratio: float
    overlap_pixels: int
    stride: int
    tiles_count: int
    valid_tiles: int
    skipped_tiles: int
    min_valid_pixel_ratio: float
    metadata_returned: int


class AITilingResponse(BaseModel):
    success: bool = True
    raster_id: str
    preprocessing: PreprocessingMetadata
    tiling: TilingSummary
    tiles: list[TileMetadata]

