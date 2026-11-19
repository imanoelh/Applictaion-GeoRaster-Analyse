from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


CHANGE_DETECTION_ANALYSIS_TYPES = {
    "change_detection_ndvi": "CHANGE_NDVI",
    "change_detection_ndwi": "CHANGE_NDWI",
    "change_detection_ndbi": "CHANGE_NDBI",
    "change_detection_bsi": "CHANGE_BSI",
    "change_detection_savi": "CHANGE_SAVI",
}

SUPPORTED_INDEX_SENSORS: dict[str, tuple[str, ...]] = {
    "NDVI": ("sentinel-2", "landsat-8-9"),
    "NDWI": ("sentinel-2", "landsat-8-9"),
    "NDBI": ("sentinel-2", "landsat-8-9"),
    "BSI": ("sentinel-2", "landsat-8-9"),
    "SAVI": ("sentinel-2", "landsat-8-9"),
    "CHANGE_NDVI": ("sentinel-2", "landsat-8-9"),
    "CHANGE_NDWI": ("sentinel-2", "landsat-8-9"),
    "CHANGE_NDBI": ("sentinel-2", "landsat-8-9"),
    "CHANGE_BSI": ("sentinel-2", "landsat-8-9"),
    "CHANGE_SAVI": ("sentinel-2", "landsat-8-9"),
    "SUPERVISED_CLASSIFICATION": ("sentinel-2", "landsat-8-9"),
    "UNSUPERVISED_CLASSIFICATION": ("sentinel-2", "landsat-8-9"),
    "OSI_SAR": ("sentinel-1",),
}

SUPPORTED_IMAGE_METHODS = {
    "least_cloudy",
    "median_composite",
    "mosaic_by_date",
    "selected_scene",
    "single_scene",
}


def normalize_raster_request_payload(
    payload: Mapping[str, Any],
    *,
    require_dates: bool = True,
    require_aoi: bool = True,
) -> dict[str, Any]:
    """Normalize both legacy and canonical frontend payloads.

    The frontend should now send canonical fields (`geometry`, `start_date`,
    `end_date`, `sensor`, `resolution`, `cloud_max`), while the backend keeps
    deriving legacy fields so older internal code paths remain stable.
    """

    normalized = deepcopy(dict(payload or {}))

    geometry = normalized.get("geometry")
    aoi = normalized.get("aoi")
    if geometry and not aoi:
        normalized["aoi"] = {"geojson": geometry}
    elif isinstance(aoi, Mapping):
        normalized["aoi"] = dict(aoi)

    if normalized.get("start_date") and not normalized.get("date_start"):
        normalized["date_start"] = normalized.get("start_date")
    if normalized.get("end_date") and not normalized.get("date_end"):
        normalized["date_end"] = normalized.get("end_date")
    if normalized.get("cloud_max") is not None:
        normalized["max_cloud_pct"] = normalized.get("cloud_max")

    sensor = str(normalized.get("sensor") or "sentinel-2")
    normalized["sensor"] = sensor
    normalized["resolution"] = normalized.get("resolution") or "auto"
    normalized["source"] = normalized.get("source") or ("S1_GRD" if sensor == "sentinel-1" else "S2_SR_HARMONIZED")

    image_method = str(normalized.get("image_method") or "median_composite").strip().lower()
    if image_method not in SUPPORTED_IMAGE_METHODS:
        raise ValueError(
            "image_method doit etre median_composite, selected_scene, "
            "least_cloudy ou mosaic_by_date"
        )
    normalized["image_method"] = image_method
    normalized["cloud_probability_threshold"] = 40

    if require_dates and (not normalized.get("date_start") or not normalized.get("date_end")):
        raise ValueError("date_start/date_end ou start_date/end_date sont requis")
    if require_aoi and not normalized.get("aoi"):
        raise ValueError("aoi ou geometry est requis")
    return normalized


def normalize_analysis_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_raster_request_payload(payload)
    analysis_type = str(normalized.get("analysis_type") or "").lower()
    if analysis_type == "supervised_classification":
        normalized["index"] = "SUPERVISED_CLASSIFICATION"
    elif analysis_type == "unsupervised_classification":
        normalized["index"] = "UNSUPERVISED_CLASSIFICATION"
    elif analysis_type in CHANGE_DETECTION_ANALYSIS_TYPES:
        normalized["index"] = CHANGE_DETECTION_ANALYSIS_TYPES[analysis_type]
    return normalized


def supported_sensors_for_index(index_id: str) -> tuple[str, ...]:
    return SUPPORTED_INDEX_SENSORS.get(str(index_id or "").upper(), ("sentinel-2", "landsat-8-9"))
