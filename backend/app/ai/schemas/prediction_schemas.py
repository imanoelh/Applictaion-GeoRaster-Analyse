from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from .tile_schemas import TileMetadata


PredictionStatus = Literal["processed", "skipped"]


class BuildingInferenceRequest(BaseModel):
    raster_id: str = Field(min_length=1)
    model_id: str = Field(default="spacenet2_deeplab", min_length=1)
    tile_size: int = Field(default=640, gt=0, le=4096)
    overlap_ratio: float = Field(default=0.20, ge=0.0, lt=1.0)
    probability_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    min_valid_pixel_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    inference_mode: str = Field(default="standard", pattern="^(standard|tta|multi_scale|enhanced)$")


class TilePredictionMetadata(BaseModel):
    tile_id: str
    raster_id: str | None
    model_name: str
    model_version: str
    model_id: str = "unet_resnet34"
    model_architecture: str | None = None
    model_checkpoint_hash: str | None = None
    preprocessing_profile: str | None = None
    tile_size: int | None = None
    checkpoint_id: str | None = None
    runtime: str
    device: str
    model_mode: str
    status: PredictionStatus
    reason: str | None = None
    threshold: float
    valid_width: int
    valid_height: int
    valid_pixel_count: int
    valid_pixel_ratio: float
    prediction_shape: list[int]
    positive_pixel_count: int
    positive_pixel_ratio: float
    inference_time_ms: float
    source_type: str | None = None
    source_resolution: float | None = None
    model_details: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class TilePrediction:
    """Metadata plus in-memory payload, never serialized wholesale by the API."""

    metadata: TilePredictionMetadata
    probability_map: np.ndarray | None
    binary_mask: np.ndarray | None
    valid_mask: np.ndarray
    tile_metadata: TileMetadata


class ModelSummary(BaseModel):
    name: str
    version: str
    id: str = "spacenet2_deeplab"
    architecture: str | None = None
    checkpoint_id: str | None = None
    checkpoint_hash: str | None = None
    preprocessing_profile: str | None = None
    input_size: int | None = None
    runtime: str
    device: str
    loaded: bool
    model_mode: str
    threshold_status: str = "NOT_CALIBRATED"


class InferenceTilesSummary(BaseModel):
    total: int
    processed: int
    skipped: int


class InferencePredictionSummary(BaseModel):
    threshold: float
    positive_pixels: int
    valid_pixels: int
    positive_ratio: float
    inference_mode: str = "standard"


class InferencePerformanceSummary(BaseModel):
    model_load_time_ms: float
    total_inference_time_ms: float
    average_tile_inference_time_ms: float
    min_inference_time_ms: float = 0.0
    max_inference_time_ms: float = 0.0
    total_pipeline_time_ms: float
    tiles_per_second: float | None = None


class BuildingInferenceResponse(BaseModel):
    success: bool = True
    object_type: str = "building"
    quality_mode: str = "integration_test"
    warning: str
    model: ModelSummary
    tiles: InferenceTilesSummary
    prediction: InferencePredictionSummary
    performance: InferencePerformanceSummary

