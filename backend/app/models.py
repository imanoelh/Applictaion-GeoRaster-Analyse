from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .request_contracts import normalize_analysis_payload, normalize_raster_request_payload


class Coordinate3D(BaseModel):
    """Optional future-simulation coordinate; never used by raster workflows."""
    crs: Literal["EPSG:9332"] = "EPSG:9332"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    ellipsoidal_height_m: float | None = None


SourceId = Literal["S2_SR_HARMONIZED", "S1_GRD"]
SensorId = Literal["sentinel-2", "landsat-8-9", "dynamic-world", "esa-worldcover", "sentinel-1"]
ResolutionId = Literal["10m", "20m", "30m", "auto"]
IndexId = Literal[
    "NDVI",
    "NDWI",
    "NDBI",
    "BSI",
    "SAVI",
    "OSI_SAR",
    "CHANGE_NDVI",
    "CHANGE_NDWI",
    "CHANGE_NDBI",
    "CHANGE_BSI",
    "CHANGE_SAVI",
    "SUPERVISED_CLASSIFICATION",
    "UNSUPERVISED_CLASSIFICATION",
]
RunStatus = Literal["queued", "running", "succeeded", "failed"]
ImageMethod = Literal[
    "least_cloudy",
    "median_composite",
    "mosaic_by_date",
    "selected_scene",
    "single_scene",
]
SupervisedAlgorithm = Literal["random_forest", "cart", "svm"]


class AOI(BaseModel):
    # MVP: on accepte un bbox (SW/NE) et/ou GeoJSON
    bbox: list[list[float]] | None = None  # [[south, west], [north, east]]
    geojson: dict[str, Any] | None = None


class RasterRequestBase(BaseModel):
    # Ancien contrat garde pour compatibilite avec les composants existants.
    source: SourceId = "S2_SR_HARMONIZED"
    date_start: str | None = None
    date_end: str | None = None
    max_cloud_pct: int = Field(default=20, ge=0, le=100)
    image_method: ImageMethod = "median_composite"
    cloud_probability_threshold: int = Field(default=40, ge=0, le=100)
    aoi: AOI | None = None

    # Nouveau contrat simplifie envoye par le frontend.
    geometry: dict[str, Any] | None = None
    start_date: str | None = None
    end_date: str | None = None
    cloud_max: int | None = Field(default=None, ge=0, le=100)
    sensor: SensorId = "sentinel-2"
    resolution: ResolutionId = "auto"
    analysis_type: str | None = None

    @model_validator(mode="after")
    def normalize_request(self) -> "RasterRequestBase":
        normalized = normalize_raster_request_payload(self.model_dump(mode="python"))
        self.source = normalized["source"]
        self.date_start = normalized["date_start"]
        self.date_end = normalized["date_end"]
        self.max_cloud_pct = int(normalized["max_cloud_pct"])
        self.image_method = normalized["image_method"]
        self.cloud_probability_threshold = int(normalized["cloud_probability_threshold"])
        self.aoi = AOI.model_validate(normalized["aoi"])
        self.geometry = normalized.get("geometry")
        self.start_date = normalized.get("start_date")
        self.end_date = normalized.get("end_date")
        self.cloud_max = normalized.get("cloud_max")
        self.sensor = normalized["sensor"]
        self.resolution = normalized["resolution"]
        return self


class AnalysisCreate(RasterRequestBase):
    name: str = Field(min_length=1)
    objective: str | None = None
    description: str | None = None
    image_id: str | None = None
    index: IndexId = "NDVI"
    supervised_options: dict[str, Any] | None = None
    unsupervised_options: dict[str, Any] | None = None
    osi_sar_options: dict[str, Any] | None = None
    period_1: dict[str, Any] | None = None
    period_2: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize_analysis_type(self) -> "AnalysisCreate":
        normalized = normalize_analysis_payload(self.model_dump(mode="python"))
        self.index = normalized.get("index", self.index)
        return self


class Analysis(AnalysisCreate):
    id: str
    created_at: str
    updated_at: str


class Run(BaseModel):
    id: str
    analysis_id: str
    status: RunStatus
    message: str | None = None
    created_at: str
    updated_at: str


class RunResult(BaseModel):
    run: Run
    stats: dict[str, Any] | None = None
    histogram: list[dict[str, Any]] | None = None
    classes: list[dict[str, Any]] | None = None
    tiles: dict[str, Any] | None = None


class ExportCreate(BaseModel):
    kind: Literal["stats_csv", "stats_json", "report_pdf", "map_png", "geotiff"] = "stats_csv"
    layer_key: Literal["ndbi_raw", "ndbi_built_detection"] | None = None
    language: Literal["en", "ar"] = "en"


class MapPdfExportRequest(BaseModel):
    analysis_id: str | None = None
    analysis_type: str
    language: Literal["en", "ar"] = "en"
    geometry_info: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    map_screenshot: str = Field(min_length=1)
    locator_screenshot: str | None = None
    legend: list[dict[str, Any]] | None = None
    statistics: dict[str, Any] | None = None
    histogram: list[dict[str, Any]] | None = None
    classes: list[dict[str, Any]] | None = None
    quality_summary: dict[str, Any] | None = None
    interpretation: str | None = None
    user_name: str | None = None
    metadata: dict[str, Any] | None = None


class ExportRef(BaseModel):
    id: str
    run_id: str
    kind: str
    filename: str
    content_type: str
    created_at: str


class PreviewRequest(RasterRequestBase):
    index: IndexId = "NDVI"
    # Optional `system:index` of a scene returned by the live catalogue.
    # It is used only to request that scene's RGB preview; the server still
    # validates it against the filtered Sentinel-2 collection.
    scene_id: str | None = None
