from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from .postprocessing_schemas import BuildingPostProcessRequest


class BuildingVectorPipelineRequest(BuildingPostProcessRequest):
    polygon_connectivity: int = Field(default=8)
    simplify_tolerance: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_vectorization(self) -> "BuildingVectorPipelineRequest":
        if self.polygon_connectivity not in {4, 8}:
            raise ValueError("polygon_connectivity doit valoir 4 ou 8")
        return self


class BuildingVectorizationRequest(BuildingVectorPipelineRequest):
    include_geojson: bool = False


class BuildingResultsRequest(BuildingVectorPipelineRequest):
    pass


class BuildingVectorizationSummary(BaseModel):
    feature_count: int
    candidate_label: str = "building candidates vectorized"
    geometry_types: dict[str, int]
    crs: str
    bounds: dict[str, float]
    total_area_map_units: float
    total_area_m2: float | None
    polygonization_time_ms: float


class BuildingVectorizationResponse(BaseModel):
    success: bool = True
    raster_id: str
    result_type: str = "building_vector_candidates"
    scientific_accuracy: str = "NOT_VALIDATED"
    warning: str
    vectorization: BuildingVectorizationSummary
    polygonization_config: dict[str, Any]
    postprocessing_config: dict[str, Any]
    geojson: dict[str, Any] | None = None
