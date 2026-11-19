from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BuildingStatistics(BaseModel):
    candidate_count: int = Field(ge=0)
    total_area_map_units: float
    mean_area_map_units: float | None
    median_area_map_units: float | None
    min_area_map_units: float | None
    max_area_map_units: float | None
    total_perimeter_map_units: float
    mean_perimeter_map_units: float | None
    total_area_m2: float | None
    mean_area_m2: float | None
    median_area_m2: float | None
    min_area_m2: float | None
    max_area_m2: float | None
    total_perimeter_m: float | None
    mean_perimeter_m: float | None


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict[str, Any]
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]


class BuildingProcessingMetadata(BaseModel):
    postprocessing_time_ms: float
    polygonization_time_ms: float
    results_build_time_ms: float
    geojson_serialization_time_ms: float
    polygonization_config: dict[str, Any]
    postprocessing_config: dict[str, Any]
    model_c_inference_time_ms: float | None = None
    model_d_inference_time_ms: float | None = None
    fusion_time_ms: float | None = None
    total_processing_time_ms: float | None = None


class BuildingAnalysisResult(BaseModel):
    success: bool = True
    result_schema_version: str = "1.0"
    analysis_id: str
    analysis_type: Literal["ai_object_detection"] = "ai_object_detection"
    object_type: Literal["building"] = "building"
    raster_id: str
    source_type: str | None
    source_resolution: list[float]
    source_crs: str
    feature_collection_crs: Literal["EPSG:4326"] = "EPSG:4326"
    native_bounds: dict[str, float]
    wgs84_bounds: dict[str, float]
    model_name: str
    model_version: str
    model_mode: str
    probability_threshold: float
    postprocessing_version: str
    polygonization_version: str
    quality_mode: str
    quality_note: str
    scientific_accuracy_status: Literal["NOT_VALIDATED"] = "NOT_VALIDATED"
    candidate_count: int = Field(ge=0)
    statistics: BuildingStatistics
    feature_collection: GeoJSONFeatureCollection
    processing_metadata: BuildingProcessingMetadata
    model_id: str = "unet_resnet34"
    model_architecture: str | None = None
    model_checkpoint_hash: str | None = None
    tile_size: int | None = None
    preprocessing_profile: str | None = None
    model_metadata: dict[str, Any] = Field(default_factory=dict)
