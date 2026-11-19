from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BuildingPostProcessRequest(BaseModel):
    raster_id: str = Field(min_length=1)
    model_id: str = Field(default="spacenet2_deeplab", min_length=1)
    tile_size: int = Field(default=640, gt=0, le=4096)
    overlap_ratio: float = Field(default=0.20, ge=0.0, lt=1.0)
    probability_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    min_valid_pixel_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    min_object_pixels: int = Field(default=4, ge=0)
    max_hole_pixels: int = Field(default=0, ge=0)
    opening_enabled: bool = False
    closing_enabled: bool = False
    morphology_kernel_size: int = Field(default=3, ge=1, le=15)
    morphology_iterations: int = Field(default=1, ge=1, le=10)
    connectivity: int = Field(default=8)
    inference_mode: str = Field(default="standard", pattern="^(standard|tta|multi_scale|enhanced)$")

    @model_validator(mode="after")
    def validate_postprocessing(self) -> "BuildingPostProcessRequest":
        if self.morphology_kernel_size % 2 == 0:
            raise ValueError("morphology_kernel_size doit etre impair")
        if self.connectivity not in {4, 8}:
            raise ValueError("connectivity doit valoir 4 ou 8")
        return self


class BuildingMaskGridSummary(BaseModel):
    width: int
    height: int
    crs: str
    transform: list[float]
    bounds: dict[str, float]
    resolution_x: float
    resolution_y: float
    pixel_area: float


class BuildingMaskModelSummary(BaseModel):
    name: str
    version: str
    mode: str
    id: str = "unet_resnet34"
    architecture: str | None = None
    checkpoint_hash: str | None = None
    tile_size: int | None = None
    preprocessing_profile: str | None = None


class BuildingMaskPixelSummary(BaseModel):
    positive_pixel_count: int
    valid_pixel_count: int
    positive_pixel_ratio: float


class BuildingMaskTileSummary(BaseModel):
    total: int
    processed: int
    skipped: int


class BuildingMaskPerformanceSummary(BaseModel):
    postprocessing_time_ms: float
    estimated_global_memory_bytes: int


class BuildingPostProcessResponse(BaseModel):
    success: bool = True
    raster_id: str
    result_type: str = "building_raster_mask"
    quality_mode: str = "technical_unvalidated_scientifically"
    threshold_status: str = "NOT_CALIBRATED"
    warning: str
    model: BuildingMaskModelSummary
    grid: BuildingMaskGridSummary
    mask: BuildingMaskPixelSummary
    tiles: BuildingMaskTileSummary
    postprocessing_config: dict[str, object]
    performance: BuildingMaskPerformanceSummary
