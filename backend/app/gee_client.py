from __future__ import annotations

import math
import os
import json
import re
import threading
import time
from collections import Counter
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import IMAGES
from . import db
from .mock_engine import compute_mock_index
from .scalability import adaptive_chunk_plan, classification_cost_policy, surface_policy

# Optional per-thread progress hook used by async analysis jobs.
_CLASSIFICATION_PROGRESS_HOOKS: dict[int, Any] = {}


def set_classification_progress_hook(callback: Any | None) -> None:
    thread_id = threading.get_ident()
    if callback is None:
        _CLASSIFICATION_PROGRESS_HOOKS.pop(thread_id, None)
        return
    _CLASSIFICATION_PROGRESS_HOOKS[thread_id] = callback


def _emit_classification_progress(percent: int, message: str) -> None:
    callback = _CLASSIFICATION_PROGRESS_HOOKS.get(threading.get_ident())
    if not callable(callback):
        return
    with suppress(Exception):
        callback(int(percent), str(message))

try:  # Earth Engine is optional in local MVP mode.
    import ee  # type: ignore
except Exception:  # pragma: no cover - depends on local environment
    ee = None  # type: ignore


S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_PROBABILITY = "COPERNICUS/S2_CLOUD_PROBABILITY"
S2_DATE_MOSAIC_PREFIX = "S2_DATE_MOSAIC_"
# Catalog Available items must cover the AOI; coarse EE estimates can be slightly under 100%.
AVAILABLE_DATE_COVERAGE_MIN_PCT = 97.0
AVAILABLE_DATE_META_LIMIT = 1000
CATALOG_AVAILABLE_LOGIC_VERSION = "date-mosaic-v2"
MOSAIC_GRID_THRESHOLD_KM2 = 350
RGB_VIS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000, "gamma": 1.2}
LANDSAT8_COLLECTION = "LANDSAT/LC08/C02/T1_L2"
LANDSAT9_COLLECTION = "LANDSAT/LC09/C02/T1_L2"
DYNAMIC_WORLD_COLLECTION = "GOOGLE/DYNAMICWORLD/V1"
ESA_WORLDCOVER_COLLECTION = "ESA/WorldCover/v200"
GHSL_BUILT_SURFACE_IMAGE = "JRC/GHSL/P2023A/GHS_BUILT_S_10m/2018"
SENTINEL1_COLLECTION = "COPERNICUS/S1_GRD"
OSI_SAR_ID = "OSI_SAR"
SAVI_CANOPY_L = 0.5
CHANGE_DETECTION_BASES = {"NDVI", "NDWI", "NDBI", "BSI", "SAVI"}
CHANGE_DETECTION_IDS = {f"CHANGE_{item}" for item in CHANGE_DETECTION_BASES}
CHANGE_DETECTION_CONFIG: dict[str, dict[str, Any]] = {
    "NDVI": {
        "palette": ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"],
        "classes": [
            (-2.0, -0.25, "Strong vegetation loss", "#a50026"),
            (-0.25, -0.08, "Moderate vegetation loss", "#f46d43"),
            (-0.08, 0.08, "Stable area", "#fee08b"),
            (0.08, 0.25, "Moderate vegetation gain", "#a6d96a"),
            (0.25, 2.0, "Strong vegetation gain", "#1a9850"),
        ],
        "interpretation": "NDVI Change Detection compares vegetation cover between the two periods. Red classes indicate vegetation loss, grey indicates stable areas, and green classes indicate vegetation gain.",
    },
    "NDWI": {
        "palette": ["#f2c46d", "#b8e65c", "#56e66f", "#22bff0", "#003bff"],
        "classes": [
            (-2.0, -0.25, "Water/moisture disappearance", "#f2c46d"),
            (-0.25, -0.08, "Moisture decrease", "#b8e65c"),
            (-0.08, 0.08, "Stable area", "#56e66f"),
            (0.08, 0.25, "Moisture increase", "#22bff0"),
            (0.25, 2.0, "Probable water appearance", "#003bff"),
        ],
        "interpretation": "NDWI Change Detection highlights water or moisture changes. Orange indicates water or moisture loss, green indicates stable or intermediate moisture response, and blue indicates water or moisture increase.",
    },
    "NDBI": {
        "min": -1.0,
        "max": 1.0,
        "palette": ["#2166AC", "#92C5DE", "#F7F7F7", "#F46D43", "#A50026"],
        "classes": [
            (-2.0, -0.25, "Strong NDBI decrease", "#2166AC"),
            (-0.25, -0.08, "Moderate NDBI decrease", "#92C5DE"),
            (-0.08, 0.08, "Stable area", "#F7F7F7"),
            (0.08, 0.25, "Moderate NDBI increase", "#F46D43"),
            (0.25, 2.0, "Strong NDBI increase", "#A50026"),
        ],
        "interpretation": "NDBI Change Detection compares continuous NDBI as NDBI period 2 minus NDBI period 1 from the same validated NDBI pipeline. Positive values are a stronger NDBI response, not confirmed new construction.",
    },
    "BSI": {
        "palette": ["#f5ecd9", "#e4c58d", "#c99a5d", "#9f6d3c", "#6f4422"],
        "classes": [
            (-2.0, -0.25, "Strong bare-soil decrease", "#f5ecd9"),
            (-0.25, -0.08, "Moderate bare-soil decrease", "#e4c58d"),
            (-0.08, 0.08, "Stable area", "#c99a5d"),
            (0.08, 0.25, "Moderate bare-soil increase", "#9f6d3c"),
            (0.25, 2.0, "Strong bare-soil increase", "#6f4422"),
        ],
        "interpretation": "BSI Change Detection maps changes in exposed bare soil using the same earthy palette family as the base BSI. Lighter tones indicate reduced bare-soil exposure or weak response, while darker browns indicate increased bare-soil exposure.",
    },
    "SAVI": {
        "palette": ["#8c510a", "#d8b365", "#f6e8c3", "#d9ef8b", "#a6d96a", "#006837"],
        "classes": [
            (-2.0, -0.25, "Strong vegetation-cover loss", "#8c510a"),
            (-0.25, -0.08, "Moderate vegetation-cover loss", "#d8b365"),
            (-0.08, 0.08, "Stable area", "#f6e8c3"),
            (0.08, 0.18, "Low vegetation-cover gain", "#d9ef8b"),
            (0.18, 0.30, "Moderate vegetation-cover gain", "#a6d96a"),
            (0.30, 2.0, "Strong vegetation-cover gain", "#006837"),
        ],
        "interpretation": "SAVI Change Detection uses the same semi-arid vegetation palette family as the base SAVI. Brown and beige tones indicate vegetation-cover loss or stable sparse response, while green tones indicate vegetation-cover gain.",
    },
}
SAVI_CHANGE_PERIOD_CONFIG = CHANGE_DETECTION_CONFIG["SAVI"]
S2_SR_REFLECTANCE_SCALE = 0.0001
OSI_SAR_CLASSES: list[dict[str, Any]] = [
    {"code": 0, "name": "Normal water", "color": "#1f78b4"},
    {"code": 1, "name": "Low oil-spill suspicion", "color": "#f6e65a"},
    {"code": 2, "name": "Medium oil-spill suspicion", "color": "#fdae61"},
    {"code": 3, "name": "High oil-spill suspicion", "color": "#d7191c"},
]
OSI_SAR_STRICT_CLASSES: list[dict[str, Any]] = [
    {"code": 0, "name": "Normal water", "color": "#1f78b4"},
    {"code": 1, "name": "Oil-spill suspect", "color": "#d7191c"},
]
OSI_SAR_VIS = {"min": 0, "max": 3, "palette": [item["color"] for item in OSI_SAR_CLASSES]}
OSI_SAR_STRICT_VIS = {"min": 0, "max": 1, "palette": [item["color"] for item in OSI_SAR_STRICT_CLASSES]}
OSI_SAR_CONNECTED_PIXEL_MAX = 100
OSI_SAR_WATER_MASK_VERSION = "worldcover-water-80-coast-buffer-v1"
OSI_SAR_ANGLE_MASK_VERSION = "incidence-30-45-v1"
OSI_SAR_CALM_WIND_MS = 3.0
OSI_SAR_LOW_WIND_WARNING = (
    "Low wind conditions can produce natural dark SAR areas. "
    "Oil-spill interpretation has reduced confidence."
)
OSI_SAR_REFERENCE: dict[str, Any] = {
    "dataset": SENTINEL1_COLLECTION,
    "instrument_mode": "IW",
    "polarizations": ("VV", "VH"),
    "resolution_meters": 10,
    "units": "dB",
    "logic": "AND",
    "vv_dark_threshold_db": -18.0,
    "vh_dark_threshold_db": -25.0,
    "contrast_threshold_db": 2.5,
    "contrast_radius_m": 500,
    "min_connected_pixels": 8,
    "connected_pixel_max": 100,
    "angle_min_deg": 30.0,
    "angle_max_deg": 45.0,
    "coast_buffer_m": 150,
    "water_occurrence_threshold": 50,
    "speckle_radius_m": 0,
    "high_vv_db": -20.0,
    "high_vh_db": -27.0,
    "high_contrast_db": 4.0,
    "medium_vv_db": -19.0,
    "medium_contrast_db": 3.5,
    "water_mask_version": OSI_SAR_WATER_MASK_VERSION,
    "angle_mask_version": OSI_SAR_ANGLE_MASK_VERSION,
    "calm_wind_m_s": OSI_SAR_CALM_WIND_MS,
}

SENSOR_META: dict[str, dict[str, Any]] = {
    "sentinel-2": {
        "label": "Sentinel-2",
        "collection": S2_COLLECTION,
        "resolution": "10 m",
        "vis": RGB_VIS,
        "cloud_property": "CLOUDY_PIXEL_PERCENTAGE",
        "coverage_band": "B4",
    },
    "landsat-8-9": {
        "label": "Landsat 8/9",
        "collection": f"{LANDSAT8_COLLECTION} + {LANDSAT9_COLLECTION}",
        "resolution": "30 m",
        "vis": {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0.02, "max": 0.35, "gamma": 1.2},
        "cloud_property": "CLOUD_COVER",
        "coverage_band": "SR_B4",
    },
    "dynamic-world": {
        "label": "Dynamic World",
        "collection": DYNAMIC_WORLD_COLLECTION,
        "resolution": "10 m",
        "vis": {"bands": ["label"], "min": 0, "max": 8, "palette": ["#419bdf", "#397d49", "#88b053", "#7a87c6", "#e49635", "#dfc35a", "#c4281b", "#a59b8f", "#b39fe1"]},
        "cloud_property": None,
        "coverage_band": "label",
    },
    "esa-worldcover": {
        "label": "ESA WorldCover",
        "collection": ESA_WORLDCOVER_COLLECTION,
        "resolution": "10 m",
        "vis": {"bands": ["Map"], "min": 10, "max": 100, "palette": ["#006400", "#ffbb22", "#ffff4c", "#f096ff", "#fa0000", "#b4b4b4", "#f0f0f0", "#0064c8", "#0096a0", "#00cf75", "#fae6a0"]},
        "cloud_property": None,
        "coverage_band": "Map",
    },
    "sentinel-1": {
        "label": "Sentinel-1",
        "collection": SENTINEL1_COLLECTION,
        "resolution": "10 m",
        "vis": {"bands": ["VV"], "min": -20, "max": 0},
        "cloud_property": None,
        "coverage_band": "VV",
    },
}
INDEX_CONFIG: dict[str, dict[str, Any]] = {
    "NDVI": {
        "formula": "(NIR - Red) / (NIR + Red)",
        "bands": ["B8", "B4"],
        # Continuous stretch kept for the optional raw layer / scientific export.
        # User-facing map uses discrete class thresholds below (stable absolute
        # cuts — never AOI min/max). Arid soil typically sits ~0.05–0.15; real
        # vegetation pockets start to separate above ~0.15–0.25.
        "min": -0.20,
        "max": 0.80,
        "palette": ["#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837"],
        "classes": [
            (-1.0, 0.0, "Water / negative values", "#a50026"),
            (0.0, 0.08, "Bare soil / very dry desert", "#d73027"),
            (0.08, 0.15, "Very low vegetation activity", "#f46d43"),
            (0.15, 0.25, "Very sparse vegetation", "#fdae61"),
            (0.25, 0.35, "Low vegetation", "#fee08b"),
            (0.35, 0.50, "Moderate vegetation", "#a6d96a"),
            (0.50, 0.70, "Dense vegetation", "#1a9850"),
            (0.70, 2.0, "Very dense vegetation", "#006837"),
        ],
    },
    "NDWI": {
        "formula": "(Green - NIR) / (Green + NIR)",
        "bands": ["B3", "B8"],
        "min": -0.50,
        "max": 0.50,
        "palette": ["#8C510A", "#BF812D", "#DFC27D", "#F6E8C3", "#F5F5F5", "#C7EAE5", "#80CDC1", "#35978F", "#01665E"],
        "classes": [
            (-2.0, -0.20, "Strong negative NDWI response / probable dry land", "#8C510A"),
            (-0.20, 0.0, "Negative NDWI response", "#DFC27D"),
            (0.0, 0.10, "Transition / weak water response", "#F5F5F5"),
            (0.10, 0.30, "Water-compatible NDWI response", "#80CDC1"),
            (0.30, 2.0, "Strong water response", "#01665E"),
        ],
    },
    "NDBI": {
        "formula": "(SWIR - NIR) / (SWIR + NIR)",
        "bands": ["B11", "B8"],
        # Continuous stretch focused on the useful arid/urban response range.
        # Formula unchanged; only cartographic stretch/classes are refined.
        "min": -0.20,
        "max": 0.25,
        "palette": ["#EDE6DA", "#F3EBD4", "#F5E6A3", "#F5C56B", "#F08A3C", "#E85D2A", "#C41E1E"],
        "classes": [
            (-2.0, 0.0, "Non-built / vegetation / water", "#EDE6DA"),
            (0.0, 0.05, "Transition / weak response", "#F5E6A3"),
            (0.05, 0.12, "Moderate positive (possible built or bare)", "#F08A3C"),
            (0.12, 2.0, "Strong positive (dense built or bright bare)", "#C41E1E"),
        ],
    },
    "BSI": {
        "formula": "((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))",
        "bands": ["B11", "B4", "B8", "B2"],
        "min": -0.40,
        "max": 0.40,
        "palette": ["#006837", "#31a354", "#78c679", "#c2e699", "#ffffcc", "#fed98e", "#fe9929", "#d95f0e", "#993404"],
        "classes": [
            (-2.0, -0.20, "Very negative BSI value", "#006837"),
            (-0.20, 0.0, "Negative BSI value", "#78c679"),
            (0.0, 0.10, "Transition", "#ffffcc"),
            (0.10, 0.20, "Probable bare soil", "#fe9929"),
            (0.20, 2.0, "Strong bare-soil / dry signature", "#993404"),
        ],
    },
    "SAVI": {
        "formula": "((NIR - Red) / (NIR + Red + 0.5)) * 1.5",
        "bands": ["B8", "B4"],
        "l": SAVI_CANOPY_L,
        "s2_reflectance_scale": S2_SR_REFLECTANCE_SCALE,
        "min": -0.20,
        "max": 0.80,
        "palette": ["#8C510A", "#BF812D", "#DFC27D", "#F6E8C3", "#FFFFBF", "#D9EF8B", "#A6D96A", "#66BD63", "#1A9850", "#006837"],
        "classes": [
            (-2.0, 0.10, "No / very sparse vegetation", "#8C510A"),
            (0.10, 0.25, "Low vegetation", "#DFC27D"),
            (0.25, 0.40, "Moderate vegetation", "#FFFFBF"),
            (0.40, 0.60, "Dense vegetation", "#A6D96A"),
            (0.60, 2.0, "Very dense vegetation", "#006837"),
        ],
    },
}
INDEX_VIS_CONFIG = INDEX_CONFIG

NDBI_BUILT_DETECTION_CONFIG = {
    "palette": ["#f2eadf", "#f5b66f", "#ef6c3e", "#ff2a2a"],
    "classes": [
        (-1.0, 0.0, "No built-up evidence", "#f2eadf"),
        (0.0, 1.0, "Potential impervious surface or road", "#f5b66f"),
        (1.0, 2.0, "Built-up area detected", "#ef6c3e"),
        (2.0, 3.0, "High-confidence built-up area", "#ff2a2a"),
    ],
}

NDBI_RAW_CLASS_DESCRIPTIONS = [
    "Negative NDBI: vegetation, water, moisture, or shaded non-built surfaces.",
    "Near-zero to weakly positive response; mixed or transitional surfaces.",
    "Positive NDBI compatible with built-up or dry bare/mineral soil in arid landscapes.",
    "Strong positive SWIR response; dense built-up is likely but bright bare soil can look similar. Use Built-up detection for a stricter check.",
]


def _describe_raw_ndbi_classes(classes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for idx, item in enumerate(classes):
        if idx < len(NDBI_RAW_CLASS_DESCRIPTIONS):
            item["description"] = NDBI_RAW_CLASS_DESCRIPTIONS[idx]
    return classes


INDEX_BANDS_BY_SENSOR: dict[str, dict[str, list[str]]] = {
    "sentinel-2": {
        "NDVI": ["B8", "B4"],
        "NDWI": ["B3", "B8"],
        "NDBI": ["B11", "B8"],
        "BSI": ["B11", "B4", "B8", "B2"],
        "SAVI": ["B8", "B4"],
    },
    "landsat-8-9": {
        "NDVI": ["SR_B5", "SR_B4"],
        "NDWI": ["SR_B3", "SR_B5"],
        "NDBI": ["SR_B6", "SR_B5"],
        "BSI": ["SR_B6", "SR_B4", "SR_B5", "SR_B2"],
        "SAVI": ["SR_B5", "SR_B4"],
    },
}
INDEX_SCALE_BY_SENSOR = {"sentinel-2": 10, "landsat-8-9": 30}
INDEX_RGB_VIS_BY_SENSOR = {"sentinel-2": RGB_VIS, "landsat-8-9": SENSOR_META["landsat-8-9"]["vis"]}
SUPERVISED_CLASSIFICATION_ID = "SUPERVISED_CLASSIFICATION"
UNSUPERVISED_CLASSIFICATION_ID = "UNSUPERVISED_CLASSIFICATION"
LAND_COVER_CLASSES: list[dict[str, Any]] = [
    {"code": 1, "name": "Water", "color": "#2b83ba", "worldcover": [80]},
    {"code": 2, "name": "Dense vegetation / trees", "color": "#1a9850", "worldcover": [10]},
    {"code": 3, "name": "Crops / low vegetation", "color": "#a6d96a", "worldcover": [20, 30, 40]},
    {"code": 4, "name": "Built-up area", "color": "#d7191c", "worldcover": [50]},
    {"code": 5, "name": "Bare soil / sand", "color": "#dfc27d", "worldcover": [60]},
    {"code": 6, "name": "Wetland", "color": "#80cdc1", "worldcover": [90]},
    {"code": 7, "name": "Mangrove / specific vegetation", "color": "#01665e", "worldcover": [95]},
    {"code": 8, "name": "Snow / ice", "color": "#ffffff", "worldcover": [70]},
]
UNSUPERVISED_LAND_COVER_CLASSES: list[dict[str, Any]] = [
    {"code": 1, "name": "Water", "color": "#2b83ba"},
    {"code": 2, "name": "Dense vegetation", "color": "#1a9850"},
    {"code": 3, "name": "Crops / low vegetation", "color": "#a6d96a"},
    {"code": 4, "name": "Built-up area", "color": "#d7191c"},
    {"code": 5, "name": "Bare soil / sand", "color": "#dfc27d"},
    {"code": 6, "name": "Wetland / mixed class", "color": "#80cdc1"},
    {"code": 7, "name": "Uninterpreted cluster", "color": "#bdbdbd"},
]


_GEE_INITIALIZED = False
_GEE_ERROR: str | None = None
_GEE_INIT_LOCK = threading.Lock()
_GEE_INIT_THREAD: threading.Thread | None = None
_GEE_LAST_ATTEMPT_AT = 0.0
_GEE_INIT_STARTED_AT = 0.0
_GEE_INIT_TIMEOUT_SECONDS = 90.0
_GEE_RETRY_INTERVAL_SECONDS = 10.0
_GEE_HUNG_WORKER_SECONDS = 120.0


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept old and new frontend payloads without discarding user intent."""
    normalized = dict(payload or {})
    if normalized.get("geometry") and not normalized.get("aoi"):
        normalized["aoi"] = {"geojson": normalized.get("geometry")}
    if normalized.get("start_date") and not normalized.get("date_start"):
        normalized["date_start"] = normalized.get("start_date")
    if normalized.get("end_date") and not normalized.get("date_end"):
        normalized["date_end"] = normalized.get("end_date")
    if normalized.get("cloud_max") is not None:
        normalized["max_cloud_pct"] = normalized.get("cloud_max")

    normalized["sensor"] = normalized.get("sensor") or "sentinel-2"
    normalized["resolution"] = normalized.get("resolution") or "auto"
    normalized["source"] = normalized.get("source") or "S2_SR_HARMONIZED"

    # OSI-SAR always analyses one Sentinel-1 acquisition. Optical workflows
    # preserve the explicit scene/composite choice from the canonical request.
    if str(normalized.get("index") or "").upper() == OSI_SAR_ID:
        normalized["image_method"] = normalized.get("image_method") or "single_scene"
    else:
        method = str(normalized.get("image_method") or "median_composite").strip().lower()
        normalized["image_method"] = method if method in {
            "least_cloudy",
            "median_composite",
            "mosaic_by_date",
            "selected_scene",
            "single_scene",
        } else "median_composite"
    normalized["cloud_probability_threshold"] = 40
    return normalized


def _sensor_id(payload: dict[str, Any]) -> str:
    sensor = str(payload.get("sensor") or "sentinel-2")
    return sensor if sensor in SENSOR_META else "sentinel-2"


def _sensor_label(payload: dict[str, Any]) -> str:
    return SENSOR_META[_sensor_id(payload)]["label"]


def _sensor_resolution(payload: dict[str, Any]) -> str:
    requested = str(payload.get("resolution") or "auto")
    if requested != "auto":
        return requested.replace("m", " m")
    return SENSOR_META[_sensor_id(payload)]["resolution"]


def _requested_resolution_m(payload: dict[str, Any]) -> int | None:
    """Return the explicit output/export resolution requested by the user."""
    return {"10m": 10, "20m": 20, "30m": 30}.get(str(payload.get("resolution") or "auto"))


def _effective_output_resolution_m(payload: dict[str, Any], native_scale_m: int) -> int:
    """Never advertise or export a resolution finer than the source raster."""
    requested = _requested_resolution_m(payload)
    return max(int(native_scale_m), int(requested)) if requested else int(native_scale_m)


def _resolution_contract(payload: dict[str, Any], native_scale_m: int, statistics_scale_m: int) -> dict[str, Any]:
    """Describe native, requested, statistics and export resolution explicitly."""
    requested = _requested_resolution_m(payload)
    effective = _effective_output_resolution_m(payload, native_scale_m)
    return {
        "native_resolution_m": int(native_scale_m),
        "requested_export_resolution_m": requested,
        "effective_export_resolution_m": effective,
        "statistics_scale_m": int(statistics_scale_m),
        "continuous_resampling": "bilinear",
        "categorical_resampling": "nearest_neighbor",
    }


def _load_ee_user_credentials() -> Any | None:
    """Refresh local Earth Engine user credentials explicitly (avoids hung default init)."""
    if ee is None:
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except Exception:
        return None

    candidates = [
        Path.home() / ".config" / "earthengine" / "credentials",
        Path(os.environ.get("APPDATA", "") or "") / "earthengine" / "credentials",
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            refresh_token = data.get("refresh_token")
            if not refresh_token:
                continue
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=getattr(ee.oauth, "TOKEN_URI", "https://oauth2.googleapis.com/token"),
                # Notebook authentication stores the OAuth client alongside
                # the refresh token. Prefer those values; the package
                # defaults can belong to a different client and produce
                # ``unauthorized_client`` during refresh.
                client_id=data.get("client_id") or ee.oauth.CLIENT_ID,
                client_secret=data.get("client_secret") or ee.oauth.CLIENT_SECRET,
                scopes=data.get("scopes") or getattr(ee.oauth, "SCOPES", None),
            )
            creds.refresh(Request())
            return creds
        except Exception:
            continue
    return None


def gee_status(*, wait_seconds: float | None = None) -> dict[str, Any]:
    """Return the local Earth Engine availability without raising."""
    ok = _ensure_gee(wait_seconds=wait_seconds)
    project = os.getenv("GEE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    return {
        "enabled": ok,
        "project": project,
        "account": os.getenv("GEE_ACCOUNT_EMAIL") or None,
        "collection": S2_COLLECTION,
        "error": None if ok else _GEE_ERROR,
    }


def _gee_initialize_worker(project: str | None) -> None:
    global _GEE_INITIALIZED, _GEE_ERROR, _GEE_INIT_THREAD, _GEE_LAST_ATTEMPT_AT
    try:
        import socket

        # Explicit oauth refresh + credentials avoids Windows hangs seen with bare
        # ee.Initialize(project=...) after a backend restart.
        credentials = _load_ee_user_credentials()
        if credentials is None:
            raise RuntimeError(
                "Credentials Earth Engine introuvables ou invalides. "
                "Lancez: earthengine authenticate"
            )
        if not project:
            raise RuntimeError(
                "GEE_PROJECT_ID / GOOGLE_CLOUD_PROJECT manquant pour initialiser Earth Engine."
            )

        # Optional STAC deprecation catalog fetch can hang forever on SSL reads.
        # Core EE calls already work without that optional startup step.
        if hasattr(ee, "_InitializeDeprecatedAssets"):
            ee._InitializeDeprecatedAssets = lambda: None  # type: ignore[attr-defined]

        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(45)
        try:
            ee.Initialize(credentials=credentials, project=project)
        finally:
            socket.setdefaulttimeout(previous_timeout)

        ee.Number(1).getInfo()
        with _GEE_INIT_LOCK:
            _GEE_INITIALIZED = True
            _GEE_ERROR = None
    except Exception as exc:  # pragma: no cover - depends on auth/network
        with _GEE_INIT_LOCK:
            _GEE_INITIALIZED = False
            _GEE_ERROR = str(exc)
    finally:
        with _GEE_INIT_LOCK:
            _GEE_LAST_ATTEMPT_AT = time.time()
            _GEE_INIT_THREAD = None


def warm_gee_connection() -> None:
    """Kick off GEE authentication in the background at process start."""
    threading.Thread(
        target=lambda: _ensure_gee(wait_seconds=_GEE_INIT_TIMEOUT_SECONDS),
        daemon=True,
    ).start()


def _ensure_gee(wait_seconds: float | None = None) -> bool:
    global _GEE_INITIALIZED, _GEE_ERROR, _GEE_INIT_THREAD, _GEE_LAST_ATTEMPT_AT, _GEE_INIT_STARTED_AT
    if _GEE_INITIALIZED:
        return True
    if ee is None:
        _GEE_ERROR = "earthengine-api n'est pas installe. Lancez: python -m pip install earthengine-api"
        return False

    now = time.time()
    timeout = _GEE_INIT_TIMEOUT_SECONDS if wait_seconds is None else float(wait_seconds)
    project = os.getenv("GEE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")

    with _GEE_INIT_LOCK:
        if _GEE_INITIALIZED:
            return True

        running = _GEE_INIT_THREAD
        if (
            running is not None
            and running.is_alive()
            and _GEE_INIT_STARTED_AT > 0
            and (now - _GEE_INIT_STARTED_AT) > _GEE_HUNG_WORKER_SECONDS
        ):
            # Abandon a stuck Initialize thread reference so a new attempt can start.
            _GEE_INIT_THREAD = None
            _GEE_ERROR = "Nouvelle tentative de connexion a Google Earth Engine..."
            running = None

        if running is not None and running.is_alive():
            worker = running
            _GEE_ERROR = _GEE_ERROR or "Initialisation GEE en cours."
        else:
            if (
                _GEE_ERROR
                and _GEE_LAST_ATTEMPT_AT > 0
                and (now - _GEE_LAST_ATTEMPT_AT) < _GEE_RETRY_INTERVAL_SECONDS
                and "en cours" not in str(_GEE_ERROR).lower()
                and "nouvelle tentative" not in str(_GEE_ERROR).lower()
                and "connexion a google earth engine" not in str(_GEE_ERROR).lower()
            ):
                return False
            _GEE_ERROR = "Connexion a Google Earth Engine..."
            worker = threading.Thread(target=_gee_initialize_worker, args=(project,), daemon=True)
            _GEE_INIT_THREAD = worker
            _GEE_INIT_STARTED_AT = now
            worker.start()

    worker.join(timeout)
    with _GEE_INIT_LOCK:
        if _GEE_INITIALIZED:
            return True
        if _GEE_INIT_THREAD is worker and worker.is_alive():
            _GEE_ERROR = (
                "La verification Google Earth Engine depasse le delai. "
                "Verifiez l'authentification, le projet GEE et la connexion reseau."
            )
            _GEE_LAST_ATTEMPT_AT = time.time()
            return False
        return bool(_GEE_INITIALIZED)


def _aoi_geometry(aoi: dict[str, Any]) -> Any:
    if not _ensure_gee():
        raise RuntimeError(_GEE_ERROR or "GEE unavailable")

    geojson = aoi.get("geojson")
    if geojson:
        geometry = geojson.get("geometry", geojson)
        geom_type = str(geometry.get("type", "")).lower() if isinstance(geometry, dict) else ""
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if geom_type == "polygon" and coordinates:
            return ee.Geometry.Polygon(coordinates)
        if geom_type == "multipolygon" and coordinates:
            return ee.Geometry.MultiPolygon(coordinates)
        if geom_type == "point" and coordinates:
            return ee.Geometry.Point(coordinates)
        return ee.Geometry(geometry)

    bbox = aoi.get("bbox")
    if bbox and len(bbox) == 2:
        (south, west), (north, east) = bbox
        return ee.Geometry.Rectangle([float(west), float(south), float(east), float(north)])

    raise ValueError("AOI invalide: fournir bbox [[south, west], [north, east]] ou GeoJSON.")


def _bbox_from_aoi(aoi: dict[str, Any]) -> list[float]:
    bbox = aoi.get("bbox")
    if bbox and len(bbox) == 2:
        (south, west), (north, east) = bbox
        return [float(south), float(west), float(north), float(east)]

    geojson = aoi.get("geojson")
    geometry = geojson.get("geometry", geojson) if isinstance(geojson, dict) else None
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if coordinates:
        points: list[tuple[float, float]] = []

        def collect(value: Any) -> None:
            if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
                points.append((float(value[1]), float(value[0])))  # GeoJSON lon/lat -> south/west order.
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    collect(item)

        collect(coordinates)
        if points:
            lats = [lat for lat, _lon in points]
            lons = [lon for _lat, lon in points]
            return [min(lats), min(lons), max(lats), max(lons)]

    return [0, 0, 0, 0]


def _gee_end_date(payload: dict[str, Any]) -> Any:
    """Return an inclusive UI end date as GEE's exclusive end boundary."""
    end = payload.get("date_end") or payload.get("end_date")
    if not end:
        return end
    return ee.Date(str(end)).advance(1, "day")


def _scl_reference_payload(payload: dict[str, Any]) -> bool:
    index = str(payload.get("index") or "").upper().replace("CHANGE_", "")
    return index in {"NDVI", "NDWI", "NDBI", "BSI", "SAVI"}


def _collection(payload: dict[str, Any], geom: Any | None = None) -> Any:
    payload = _normalize_payload(payload)
    geom = geom or _aoi_geometry(payload.get("aoi") or {})
    sensor = _sensor_id(payload)

    if sensor == "sentinel-2":
        return (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(geom)
            .filterDate(payload.get("date_start"), _gee_end_date(payload))
            .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", int(payload.get("max_cloud_pct", 20))))
            .sort("CLOUDY_PIXEL_PERCENTAGE")
        )

    if sensor == "landsat-8-9":
        lc08 = ee.ImageCollection(LANDSAT8_COLLECTION)
        lc09 = ee.ImageCollection(LANDSAT9_COLLECTION)
        return (
            lc08.merge(lc09)
            .filterBounds(geom)
            .filterDate(payload.get("date_start"), _gee_end_date(payload))
            .filter(ee.Filter.lte("CLOUD_COVER", int(payload.get("max_cloud_pct", 20))))
            .sort("CLOUD_COVER")
        )

    if sensor == "dynamic-world":
        return (
            ee.ImageCollection(DYNAMIC_WORLD_COLLECTION)
            .filterBounds(geom)
            .filterDate(payload.get("date_start"), _gee_end_date(payload))
        )

    if sensor == "esa-worldcover":
        return ee.ImageCollection(ESA_WORLDCOVER_COLLECTION).filterBounds(geom)

    return (
        ee.ImageCollection(SENTINEL1_COLLECTION)
        .filterBounds(geom)
        .filterDate(payload.get("date_start"), _gee_end_date(payload))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    )


def _join_cloud_probability(collection: Any, payload: dict[str, Any], geom: Any) -> Any:
    cloud_collection = (
        ee.ImageCollection(S2_CLOUD_PROBABILITY)
        .filterBounds(geom)
        .filterDate(payload.get("date_start"), _gee_end_date(payload))
    )
    joined = ee.Join.saveFirst("cloud_probability_image").apply(
        primary=collection,
        secondary=cloud_collection,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    return ee.ImageCollection(joined)


def _mask_s2_clouds(image: Any, payload: dict[str, Any]) -> Any:
    """Mask clouds/shadows with SCL plus Sentinel-2 cloud probability."""
    scl = image.select("SCL")
    scl_mask = (
        scl.neq(0)
        .And(scl.neq(1))
        .And(scl.neq(3))
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    threshold = int(payload.get("cloud_probability_threshold", 40))
    cloud_prob = ee.Image(image.get("cloud_probability_image")).select("probability")
    probability_mask = cloud_prob.lt(threshold)
    return image.updateMask(scl_mask.And(probability_mask))


def _mask_landsat_l2(image: Any) -> Any:
    """Mask Landsat Collection 2 L2 clouds and scale optical SR bands to reflectance."""
    qa = image.select("QA_PIXEL")
    mask = (
        qa.bitwiseAnd(1 << 1).eq(0)
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )
    optical = image.select(["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]).multiply(0.0000275).add(-0.2)
    return image.addBands(optical, None, True).updateMask(mask)


def _prepared_collection_for_sensor(payload: dict[str, Any], geom: Any | None = None) -> Any:
    payload = _normalize_payload(payload)
    geom = geom or _aoi_geometry(payload.get("aoi") or {})
    sensor = _sensor_id(payload)
    if sensor == "sentinel-2":
        return _prepared_collection(payload, geom)
    if sensor == "landsat-8-9":
        return _collection(payload, geom).map(_mask_landsat_l2)
    return _collection(payload, geom)


def _index_bands_for_sensor(index_id: str, sensor: str) -> list[str]:
    bands = INDEX_BANDS_BY_SENSOR.get(sensor, {}).get(index_id)
    if not bands:
        label = SENSOR_META.get(sensor, {}).get("label", sensor)
        raise ValueError(
            f"L'indice {index_id} n'est pas disponible pour {label}. "
            "Solution: utilisez Sentinel-2 ou Landsat 8/9 pour les indices spectraux."
        )
    return bands


def _analysis_scale_for_sensor(sensor: str) -> int:
    return int(INDEX_SCALE_BY_SENSOR.get(sensor, 10))


def _index_native_scale(index_id: str, sensor: str) -> int:
    """Scientific scale; Sentinel-2 SWIR1 indices follow native B11 (20 m)."""
    if sensor == "sentinel-2" and str(index_id).upper() in {"NDBI", "BSI"}:
        return 20
    return _analysis_scale_for_sensor(sensor)


def _analysis_rgb_vis_for_sensor(sensor: str) -> dict[str, Any]:
    return dict(INDEX_RGB_VIS_BY_SENSOR.get(sensor, RGB_VIS))



def _compute_index_image(image: Any, index_id: str, bands: list[str]) -> Any:
    """Build the requested spectral index image. Formulas stay backend-only."""
    if index_id in {"NDVI", "NDWI"}:
        return image.normalizedDifference(bands).rename(index_id)
    if index_id == "NDBI":
        swir, nir = bands
        return image.expression(
            "(swir - nir) / (swir + nir)",
            {"swir": image.select(swir), "nir": image.select(nir)},
        ).rename(index_id).setDefaultProjection(image.select(swir).projection())
    if index_id == "BSI":
        swir, red, nir, blue = bands
        return image.expression(
            "((swir + red) - (nir + blue)) / ((swir + red) + (nir + blue))",
            {
                "swir": image.select(swir),
                "red": image.select(red),
                "nir": image.select(nir),
                "blue": image.select(blue),
            },
        ).rename(index_id).setDefaultProjection(image.select(swir).projection())
    if index_id == "SAVI":
        nir, red = bands
        savi = image.expression(
            "((nir - red) / (nir + red + 0.5)) * 1.5",
            {"nir": image.select(nir), "red": image.select(red)},
        )
        return savi.clamp(-1, 1).rename(index_id)
    raise ValueError(f"Indice {index_id} non disponible.")


def _compute_savi_float_image(image: Any, bands: list[str]) -> Any:
    nir_band, red_band = bands
    nir = image.select(nir_band)
    red = image.select(red_band)
    if not nir_band.startswith("SR_"):
        nir = nir.multiply(S2_SR_REFLECTANCE_SCALE)
    if not red_band.startswith("SR_"):
        red = red.multiply(S2_SR_REFLECTANCE_SCALE)
    return image.expression(
        "((nir - red) / (nir + red + L)) * (1 + L)",
        {"nir": nir, "red": red, "L": SAVI_CANOPY_L},
    ).rename("SAVI")


def _ndbi_support_images(image: Any, sensor: str, geom: Any) -> tuple[Any, Any, Any]:
    ndvi = _compute_index_image(image, "NDVI", _index_bands_for_sensor("NDVI", sensor)).clip(geom)
    ndwi = _compute_index_image(image, "NDWI", _index_bands_for_sensor("NDWI", sensor)).clip(geom)
    bsi = _compute_index_image(image, "BSI", _index_bands_for_sensor("BSI", sensor)).clip(geom)
    return ndvi, ndwi, bsi


def _ndbi_built_probability_images(
    analysis: dict[str, Any],
    sensor: str,
    geom: Any,
) -> tuple[Any | None, Any | None]:
    """Return temporal built/bare probabilities used only to refine NDBI classes."""
    if sensor != "sentinel-2":
        return None, None

    date_start = str(analysis.get("date_start") or analysis.get("start_date") or "")
    date_end = str(analysis.get("date_end") or analysis.get("end_date") or "")
    if not date_start or not date_end:
        return None, None

    collection = (
        ee.ImageCollection(DYNAMIC_WORLD_COLLECTION)
        .filterBounds(geom)
        .filterDate(date_start, ee.Date(date_end).advance(1, "day"))
        .select(["built", "bare"])
    )
    empty = ee.Image.constant([0, 1]).rename(["built", "bare"])
    probabilities = ee.Image(
        ee.Algorithms.If(
            collection.size().gt(0),
            collection.median(),
            empty,
        )
    ).clip(geom)
    return probabilities.select("built"), probabilities.select("bare")


def _ndbi_built_detection_context(
    analysis: dict[str, Any],
    source_image: Any,
    ndbi_image: Any,
    sensor: str,
    geom: Any,
) -> dict[str, Any]:
    """Build the same multi-observation NDBI interpretation used by the base analysis."""
    ndvi_image, ndwi_image, bsi_image = _ndbi_support_images(source_image, sensor, geom)
    built_probability, bare_probability = _ndbi_built_probability_images(analysis, sensor, geom)
    stable_built_reference = _ndbi_stable_built_reference(geom)
    historical_built_surface = (
        _ndbi_historical_built_surface_reference(geom)
        if sensor == "sentinel-2"
        else None
    )
    cfg = dict(NDBI_BUILT_DETECTION_CONFIG)
    classified, vis = _classified_ndbi_image(
        ndbi_image,
        ndvi_image,
        ndwi_image,
        bsi_image,
        cfg,
        built_probability,
        bare_probability,
        stable_built_reference,
        historical_built_surface,
    )
    return {
        "classified": classified,
        "vis": vis,
        "cfg": cfg,
        "ndvi": ndvi_image,
        "ndwi": ndwi_image,
        "bsi": bsi_image,
        "built_probability": built_probability,
        "bare_probability": bare_probability,
        "stable_built_reference": stable_built_reference,
        "historical_built_surface": historical_built_surface,
    }


def _ndbi_stable_built_reference(geom: Any) -> Any:
    """Return the 10 m stable built-up reference used by the separate detection layer."""
    return (
        ee.ImageCollection(ESA_WORLDCOVER_COLLECTION)
        .first()
        .select("Map")
        .eq(50)
        .rename("stable_built_reference")
        .clip(geom)
    )


def _ndbi_historical_built_surface_reference(geom: Any) -> Any:
    """Return GHSL built surface in square metres per 10 m grid cell."""
    return (
        ee.Image(GHSL_BUILT_SURFACE_IMAGE)
        .select("built_surface")
        .rename("historical_built_surface_m2")
        .clip(geom)
    )


def _selected_scene_system_index(image_id: str, sensor: str) -> str:
    raw = str(image_id or "").strip()
    allowed_prefixes = [S2_COLLECTION] if sensor == "sentinel-2" else [LANDSAT8_COLLECTION, LANDSAT9_COLLECTION]
    for prefix in allowed_prefixes:
        if raw.startswith(f"{prefix}/"):
            return raw[len(prefix) + 1 :]
    if "/" in raw:
        raise ValueError("L'identifiant de la scene selectionnee n'appartient pas au capteur choisi.")
    return raw


def _build_selected_scene_mosaic(payload: dict[str, Any]) -> dict[str, Any]:
    """Build an analysis source from the exact selected optical acquisition."""
    payload = _normalize_payload(payload)
    sensor = _sensor_id(payload)
    if sensor not in {"sentinel-2", "landsat-8-9"}:
        raise ValueError("Le mode scene selectionnee exige Sentinel-2 ou Landsat 8/9.")

    image_id = str(payload.get("image_id") or "").strip()
    if not image_id:
        raise ValueError(
            "Le mode scene selectionnee exige une image du catalogue. "
            "Selectionnez une acquisition ou utilisez le composite temporel."
        )

    aoi = payload.get("aoi") or {}
    geom = _aoi_geometry(aoi)
    area_km2 = _aoi_area_km2(aoi)
    native_scale = _analysis_scale_for_sensor(sensor)
    surface = surface_policy(area_km2, native_scale)
    chunk_plan = adaptive_chunk_plan(_bbox_from_aoi(aoi), area_km2)
    acquisition_date = _parse_s2_date_mosaic_id(image_id) if sensor == "sentinel-2" else None

    if acquisition_date:
        start = ee.Date(acquisition_date)
        collection = _prepared_collection(payload, geom).filterDate(start, start.advance(1, "day"))
        scene_label = f"Sentinel-2 {acquisition_date}"
        method = "selected_date_mosaic"
    else:
        system_index = _selected_scene_system_index(image_id, sensor)
        if not system_index:
            raise ValueError("L'identifiant de la scene selectionnee est vide.")
        collection = _prepared_collection_for_sensor(payload, geom).filter(
            ee.Filter.eq("system:index", system_index)
        )
        scene_label = system_index
        method = "selected_scene"

    images_count = int(collection.size().getInfo() or 0)
    if images_count <= 0:
        raise ValueError(
            "La scene selectionnee n'est plus disponible pour cette AOI, cette periode "
            "ou ce seuil de nuages. Relancez la recherche d'images."
        )

    image = (
        _composite(collection, "least_cloudy")
        if acquisition_date
        else ee.Image(collection.first())
    ).clip(geom)
    coverage_percent: float | None = None
    if not surface.get("async_recommended"):
        try:
            if sensor == "sentinel-2":
                coverage_percent = _estimate_coverage_percent(
                    image,
                    geom,
                    area_km2,
                    scale=int(surface.get("statistics_scale_m") or native_scale),
                )
            else:
                coverage_percent = _estimate_generic_coverage_percent(
                    image,
                    geom,
                    area_km2,
                    str(SENSOR_META[sensor]["coverage_band"]),
                    int(surface.get("statistics_scale_m") or native_scale),
                )
        except Exception:
            coverage_percent = None

    warning = surface["message"] if surface["status"] != "ok" else None
    if coverage_percent is not None and coverage_percent < 55:
        warning = "Low selected-scene coverage: choose another acquisition or use the temporal composite."
    return {
        "image": image,
        "geom": geom,
        "area_km2": round(area_km2, 2),
        "surface": surface,
        "images_count": images_count,
        "tiles_count": chunk_plan.count,
        "valid_tiles_count": chunk_plan.count,
        "empty_tiles_count": 0,
        "low_coverage_tiles_count": 0 if coverage_percent is None or coverage_percent >= 30 else 1,
        "error_tiles_count": 0,
        "coverage_percent": coverage_percent,
        "method": method,
        "quality": _quality_label(coverage_percent) if coverage_percent is not None else "a_evaluer",
        "warning": warning,
        "message": f"Scene selectionnee utilisee pour l'analyse: {scene_label}.",
        "cloud_probability_threshold": int(payload.get("cloud_probability_threshold", 40)) if sensor == "sentinel-2" else None,
        "async_recommended": surface["async_recommended"],
        "chunking": {
            "strategy": chunk_plan.strategy,
            "rows": chunk_plan.rows,
            "columns": chunk_plan.columns,
            "count": chunk_plan.count,
            "side_km": chunk_plan.side_km,
        },
        "tile_reports": [],
        "sensor": sensor,
        "selected_image_id": image_id,
        "resolution": _sensor_resolution(payload),
    }


def _build_analysis_mosaic(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload(payload)
    if str(payload.get("image_method") or "") in {"selected_scene", "single_scene"}:
        return _build_selected_scene_mosaic(payload)
    sensor = _sensor_id(payload)
    if sensor == "sentinel-2":
        return _build_sentinel2_mosaic(payload, eager_tile_qa=False)
    if sensor == "landsat-8-9":
        return _build_generic_mosaic(payload)
    label = SENSOR_META.get(sensor, {}).get("label", sensor)
    raise ValueError(
        f"Les indices spectraux ne sont pas calculables sur {label}. "
        "Solution: selectionnez Sentinel-2 ou Landsat 8/9 pour lancer l'analyse raster."
    )


def _build_lazy_analysis_mosaic(payload: dict[str, Any]) -> dict[str, Any]:
    """Build only the lazy GEE image graph required for first map rendering."""
    payload = _normalize_payload(payload)
    if str(payload.get("image_method") or "") in {"selected_scene", "single_scene"}:
        return _build_selected_scene_mosaic(payload)
    sensor = _sensor_id(payload)
    geom = _aoi_geometry(payload.get("aoi") or {})
    aoi = payload.get("aoi") or {}
    area_km2 = _aoi_area_km2(aoi)
    surface = _surface_level(area_km2)
    chunk_plan = adaptive_chunk_plan(_bbox_from_aoi(aoi), area_km2)

    if sensor == "sentinel-2":
        collection = _prepared_collection(payload, geom)
        method = "median_composite"
        image = _composite(collection, method).clip(geom)
        label = "Sentinel-2"
    elif sensor == "landsat-8-9":
        collection = _prepared_collection_for_sensor(payload, geom)
        method = "median_composite"
        image = _composite(collection, method).clip(geom)
        label = SENSOR_META[sensor]["label"]
    else:
        label = SENSOR_META.get(sensor, {}).get("label", sensor)
        raise ValueError(
            f"Les indices spectraux ne sont pas calculables sur {label}. "
            "Solution: selectionnez Sentinel-2 ou Landsat 8/9 pour lancer l'analyse raster."
        )

    return {
        "image": image,
        "geom": geom,
        "area_km2": round(area_km2, 2),
        "surface": surface,
        "images_count": None,
        "tiles_count": chunk_plan.count,
        "valid_tiles_count": None,
        "empty_tiles_count": None,
        "low_coverage_tiles_count": None,
        "error_tiles_count": None,
        "coverage_percent": None,
        "method": f"{method}_large_aoi",
        "quality": "a_evaluer",
        "warning": "Detailed coverage omitted to speed up processing of the large AOI.",
        "message": f"Mosaic {label} prepared over the full area of interest.",
        "cloud_probability_threshold": int(payload.get("cloud_probability_threshold", 40)) if sensor == "sentinel-2" else None,
        "async_recommended": surface["async_recommended"],
        "chunking": {
            "strategy": chunk_plan.strategy,
            "rows": chunk_plan.rows,
            "columns": chunk_plan.columns,
            "count": chunk_plan.count,
            "side_km": chunk_plan.side_km,
            "optimized_for_large_aoi": True,
        },
        "tile_reports": [],
    }


def _prepared_collection(payload: dict[str, Any], geom: Any | None = None) -> Any:
    geom = geom or _aoi_geometry(payload.get("aoi") or {})
    # NDVI validation follows the Code Editor reference exactly: scene cloud
    # filtering plus SCL classes only. Other indices retain their historical
    # cloud-probability behavior for backwards compatibility.
    if _scl_reference_payload(payload):
        collection = _collection(payload, geom)
        return collection.map(
            lambda image: image.updateMask(
                image.select("SCL").neq(0)
                .And(image.select("SCL").neq(1))
                .And(image.select("SCL").neq(3))
                .And(image.select("SCL").neq(8))
                .And(image.select("SCL").neq(9))
                .And(image.select("SCL").neq(10))
                .And(image.select("SCL").neq(11))
            )
        )
    collection = _join_cloud_probability(_collection(payload, geom), payload, geom)
    return collection.map(lambda image: _mask_s2_clouds(image, payload))


def _aoi_area_km2(aoi: dict[str, Any]) -> float:
    geojson = aoi.get("geojson")
    if isinstance(geojson, dict):
        def ring_area(ring: list[list[float]]) -> float:
            if len(ring) < 4:
                return 0.0
            mean_lat = math.radians(sum(float(point[1]) for point in ring) / len(ring))
            lon_scale = 111.32 * max(math.cos(mean_lat), 0.25)
            lat_scale = 110.57
            doubled = 0.0
            for index in range(len(ring) - 1):
                x1, y1 = float(ring[index][0]) * lon_scale, float(ring[index][1]) * lat_scale
                x2, y2 = float(ring[index + 1][0]) * lon_scale, float(ring[index + 1][1]) * lat_scale
                doubled += (x1 * y2) - (x2 * y1)
            return abs(doubled) / 2

        def polygon_area(polygon: list[list[list[float]]]) -> float:
            if not polygon:
                return 0.0
            return max(ring_area(polygon[0]) - sum(ring_area(ring) for ring in polygon[1:]), 0.0)

        coordinates = geojson.get("coordinates") or []
        geometry_type = str(geojson.get("type") or "")
        try:
            if geometry_type == "Polygon":
                area = polygon_area(coordinates)
            elif geometry_type == "MultiPolygon":
                area = sum(polygon_area(polygon) for polygon in coordinates)
            else:
                area = 0.0
            if area > 0:
                return area
        except (TypeError, ValueError, IndexError):
            pass
    bbox = _bbox_from_aoi(aoi)
    if bbox == [0, 0, 0, 0]:
        return 0.0
    south, west, north, east = bbox
    mean_lat = math.radians((south + north) / 2)
    width_km = abs(east - west) * 111.32 * max(math.cos(mean_lat), 0.25)
    height_km = abs(north - south) * 110.57
    return max(width_km * height_km, 0.0)


def _grid_geometries(aoi: dict[str, Any], geom: Any) -> list[Any]:
    area_km2 = _aoi_area_km2(aoi)
    bbox = _bbox_from_aoi(aoi)
    plan = adaptive_chunk_plan(bbox, area_km2)
    if plan.count == 1:
        return [geom]

    south, west, north, east = bbox
    lat_step = abs(north - south) / plan.rows
    lon_step = abs(east - west) / plan.columns

    tiles: list[Any] = []
    for row in range(plan.rows):
        tile_south = south + row * lat_step
        tile_north = min(tile_south + lat_step, north)
        for col in range(plan.columns):
            tile_west = west + col * lon_step
            tile_east = min(tile_west + lon_step, east)
            # Keep grid cells rectangular here. For an irregular AOI, a cell
            # can lie completely outside the polygon and intersection() then
            # returns an empty geometry, which Image.clip rejects. The final
            # mosaic is clipped once with the complete AOI below, so processing
            # the covering bbox cells is both safe and spatially correct.
            tile = ee.Geometry.Rectangle([tile_west, tile_south, tile_east, tile_north])
            tiles.append(tile)
    return tiles


def _composite(collection: Any, method: str) -> Any:
    if method == "median_composite":
        return collection.median()
    if method == "mosaic_by_date":
        return collection.sort("system:time_start").mosaic()
    # Mosaic uses the last image on top; reverse cloud sorting so least-cloudy pixels win.
    return collection.sort("CLOUDY_PIXEL_PERCENTAGE", False).mosaic()


def _estimate_coverage_percent(image: Any, geom: Any, area_km2: float, scale: int = 10) -> float:
    if area_km2 <= 0:
        return 0.0
    raw = image.select("B4").mask().rename("valid").reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geom,
        scale=scale,
        bestEffort=True,
        maxPixels=1e8,
        tileScale=4,
    ).getInfo()
    valid_pixels = float(raw.get("valid") or 0)
    expected_pixels = max((area_km2 * 1_000_000) / (scale * scale), 1)
    return round(min(100.0, (valid_pixels / expected_pixels) * 100), 1)


def _catalog_coverage_scale_m(area_km2: float) -> int:
    """Coarser scale for interactive catalog QA (still representative of AOI fill)."""
    if area_km2 >= 5000:
        return 120
    if area_km2 >= 1500:
        return 80
    if area_km2 >= 500:
        return 60
    return 40


def _estimate_aoi_scl_cloud_percent(image: Any, geom: Any, area_km2: float, scale: int = 60) -> float | None:
    """Share of valid AOI pixels classified as cloud/cirrus on SCL (8/9/10)."""
    stats = _estimate_date_mosaic_qa(image, geom, area_km2, scale=scale)
    return None if stats is None else stats.get("cloud_percent")


def _estimate_date_mosaic_qa(
    image: Any,
    geom: Any,
    area_km2: float,
    scale: int = 60,
) -> dict[str, float] | None:
    """One reduceRegion: AOI coverage (B4 mask) + SCL cloud share among valid pixels."""
    if area_km2 <= 0:
        return None
    try:
        scl = image.select("SCL")
        valid = image.select("B4").mask().rename("valid")
        cloudy = scl.eq(8).Or(scl.eq(9)).Or(scl.eq(10)).And(valid).rename("cloud")
        raw = (
            ee.Image.cat([cloudy, valid])
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=geom,
                scale=scale,
                bestEffort=True,
                maxPixels=1e8,
                tileScale=4,
            )
            .getInfo()
            or {}
        )
        valid_pixels = float(raw.get("valid") or 0)
        expected_pixels = max((area_km2 * 1_000_000) / (scale * scale), 1)
        coverage = round(min(100.0, (valid_pixels / expected_pixels) * 100), 1)
        if valid_pixels <= 0:
            return {"coverage_percent": coverage, "cloud_percent": 100.0}
        cloud_pixels = float(raw.get("cloud") or 0)
        cloud = round(min(100.0, max(0.0, (cloud_pixels / valid_pixels) * 100)), 1)
        return {"coverage_percent": coverage, "cloud_percent": cloud}
    except Exception:
        return None


def _parse_s2_date_mosaic_id(scene_id: str | None) -> str | None:
    raw = str(scene_id or "").strip()
    if not raw:
        return None
    if raw.startswith(f"{S2_COLLECTION}/"):
        raw = raw[len(S2_COLLECTION) + 1 :]
    if not raw.startswith(S2_DATE_MOSAIC_PREFIX):
        return None
    date = raw[len(S2_DATE_MOSAIC_PREFIX) :]
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None
    return date


def _sentinel2_date_mosaic_image(payload: dict[str, Any], acquisition_date: str, geom: Any | None = None) -> Any:
    """Mosaic all Sentinel-2 granules for one calendar day, clipped to the AOI."""
    geom = geom or _aoi_geometry(payload.get("aoi") or {})
    day_start = ee.Date(str(acquisition_date))
    day_collection = (
        _collection(payload, geom)
        .filterDate(day_start, day_start.advance(1, "day"))
    )
    return _composite(day_collection, "least_cloudy").clip(geom)


def _surface_level(area_km2: float) -> dict[str, Any]:
    return surface_policy(area_km2)


def _quality_label(coverage_percent: float) -> str:
    if coverage_percent >= 85:
        return "bonne"
    if coverage_percent >= 55:
        return "moyenne"
    return "faible"


def _tile_area_km2(tile: Any) -> float:
    try:
        return round(float(tile.area(1).divide(1_000_000).getInfo() or 0), 2)
    except Exception:
        return 0.0


def _mean_cloud_pct(collection: Any, cloud_property: str = "CLOUDY_PIXEL_PERCENTAGE") -> float | None:
    try:
        value = collection.aggregate_mean(cloud_property).getInfo()
        return round(float(value), 2) if value is not None else None
    except Exception:
        return None


def _mosaic_quality_payload(mosaic: dict[str, Any]) -> dict[str, Any]:
    return {
        "area_km2": mosaic.get("area_km2"),
        "surface": mosaic.get("surface"),
        "images_count": mosaic.get("images_count"),
        "tiles_count": mosaic.get("tiles_count"),
        "valid_tiles_count": mosaic.get("valid_tiles_count"),
        "empty_tiles_count": mosaic.get("empty_tiles_count"),
        "low_coverage_tiles_count": mosaic.get("low_coverage_tiles_count"),
        "error_tiles_count": mosaic.get("error_tiles_count"),
        "coverage_percent": mosaic.get("coverage_percent"),
        "method": mosaic.get("method"),
        "quality": mosaic.get("quality"),
        "warning": mosaic.get("warning"),
        "message": mosaic.get("message"),
        "cloud_probability_threshold": mosaic.get("cloud_probability_threshold"),
        "async_recommended": mosaic.get("async_recommended"),
        "chunking": mosaic.get("chunking"),
        "tile_reports": mosaic.get("tile_reports", []),
    }


def _estimate_generic_coverage_percent(image: Any, geom: Any, area_km2: float, band: str, scale: int) -> float:
    if area_km2 <= 0:
        return 0.0
    raw = image.select(band).mask().rename("valid").reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geom,
        scale=scale,
        bestEffort=True,
        maxPixels=1e8,
        tileScale=4,
    ).getInfo()
    valid_pixels = float(raw.get("valid") or 0)
    expected_pixels = max((area_km2 * 1_000_000) / (scale * scale), 1)
    return round(min(100.0, (valid_pixels / expected_pixels) * 100), 1)


def _build_generic_mosaic(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload(payload)
    sensor = _sensor_id(payload)
    geom = _aoi_geometry(payload.get("aoi") or {})
    aoi = payload.get("aoi") or {}
    area_km2 = _aoi_area_km2(aoi)
    surface = _surface_level(area_km2)
    chunk_plan = adaptive_chunk_plan(_bbox_from_aoi(aoi), area_km2)

    collection = _prepared_collection_for_sensor(payload, geom)
    images_count = int(collection.size().getInfo())
    if images_count == 0:
        raise ValueError(f"Aucune image {SENSOR_META[sensor]['label']} trouvee. Solution: elargir la periode, augmenter le seuil de nuages, ou verifier l'AOI.")

    image = _composite(collection, "median_composite").clip(geom)
    meta = SENSOR_META[sensor]
    scale = 30 if sensor == "landsat-8-9" else 10
    if surface.get("async_recommended"):
        coverage_percent = None
    else:
        coverage_percent = _estimate_generic_coverage_percent(image, geom, area_km2, str(meta["coverage_band"]), scale)
    return {
        "image": image,
        "geom": geom,
        "area_km2": round(area_km2, 2),
        "surface": surface,
        "images_count": images_count,
        "tiles_count": chunk_plan.count,
        "valid_tiles_count": chunk_plan.count,
        "empty_tiles_count": 0,
        "low_coverage_tiles_count": 0 if coverage_percent is None or coverage_percent >= 30 else 1,
        "error_tiles_count": 0,
        "coverage_percent": coverage_percent,
        "method": "median_composite",
        "quality": _quality_label(coverage_percent) if coverage_percent is not None else "a_evaluer",
        "warning": surface["message"] if surface["status"] != "ok" else None,
        "message": f"Mosaique {meta['label']} generee sur la zone d'interet.",
        "cloud_probability_threshold": 40 if sensor == "sentinel-2" else None,
        "async_recommended": surface["async_recommended"],
        "chunking": {
            "strategy": chunk_plan.strategy,
            "rows": chunk_plan.rows,
            "columns": chunk_plan.columns,
            "count": chunk_plan.count,
            "side_km": chunk_plan.side_km,
        },
        "tile_reports": [],
        "sensor": sensor,
        "resolution": _sensor_resolution(payload),
    }


def _build_catalog_mosaic(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload(payload)
    if _sensor_id(payload) == "sentinel-2":
        return _build_sentinel2_mosaic(payload)
    return _build_generic_mosaic(payload)


def _sentinel2_mosaic_uses_lazy_tile_graph(*, tile_count: int, eager_tile_qa: bool) -> bool:
    """Reuse the already-validated lazy per-cell median graph whenever tile QA getInfo is not required."""
    return int(tile_count) > 16 or (int(tile_count) > 1 and not eager_tile_qa)


def should_prioritize_first_map(index_id: str, area_km2: float) -> bool:
    """Return tiles before reduceRegion only for very large spectral / change analyses."""
    kind = str(index_id or "").upper()
    if float(area_km2 or 0) <= FAST_MAP_AOI_THRESHOLD_KM2:
        return False
    return kind in FAST_MAP_INDICES or kind in CHANGE_DETECTION_IDS


def _build_sentinel2_mosaic(payload: dict[str, Any], *, eager_tile_qa: bool = True) -> dict[str, Any]:
    payload = _normalize_payload(payload)
    geom = _aoi_geometry(payload.get("aoi") or {})
    aoi = payload.get("aoi") or {}
    area_km2 = _aoi_area_km2(aoi)
    surface = _surface_level(area_km2)
    chunk_plan = adaptive_chunk_plan(_bbox_from_aoi(aoi), area_km2)

    collection = _prepared_collection(payload, geom)
    images_count = int(collection.size().getInfo())
    if images_count == 0:
        raise ValueError(
            "Aucune image Sentinel-2 trouvee. Solution: elargir la periode, augmenter le seuil de nuages, ou verifier l'AOI."
        )

    method = "median_composite"
    tiles = _grid_geometries(aoi, geom)
    tile_reports: list[dict[str, Any]] = []
    valid_tile_images = []

    def build_tile(tile: Any, tile_id: str, source_collection: Any) -> None:
        tile_report: dict[str, Any] = {
            "tile_id": tile_id,
            "surface_km2": _tile_area_km2(tile),
            "images_count": 0,
            "mean_cloud_pct": None,
            "coverage_percent": 0.0,
            "status": "vide",
            "message": None,
        }
        try:
            tile_collection = source_collection.filterBounds(tile)
            tile_count = int(tile_collection.size().getInfo())
            tile_report["images_count"] = tile_count
            tile_report["mean_cloud_pct"] = _mean_cloud_pct(tile_collection)
            if tile_count == 0:
                tile_report["message"] = "Tuile vide: aucune image apres filtrage."
                tile_reports.append(tile_report)
                return
            tile_image = _composite(tile_collection, method).clip(tile)
            tile_coverage = _estimate_coverage_percent(tile_image, tile, tile_report["surface_km2"])
            tile_report["coverage_percent"] = tile_coverage
            if tile_coverage < 30:
                tile_report["status"] = "faible_couverture"
                tile_report["message"] = "Couverture faible: elargir la periode ou augmenter les seuils nuages."
            else:
                tile_report["status"] = "valide"
                valid_tile_images.append(tile_image)
            tile_reports.append(tile_report)
        except Exception as exc:
            tile_report["status"] = "erreur"
            tile_report["message"] = str(exc)
            tile_reports.append(tile_report)

    use_lazy_grid = _sentinel2_mosaic_uses_lazy_tile_graph(
        tile_count=len(tiles),
        eager_tile_qa=eager_tile_qa,
    )
    if use_lazy_grid:
        # Same per-cell median graph already used above 16 tiles. Catalog
        # discovery keeps eager getInfo QA; analysis avoids those round-trips.
        base_image = _composite(collection, method)
        approximate_tile_area = round(area_km2 / max(len(tiles), 1), 2)
        for index, tile in enumerate(tiles, start=1):
            tile_collection = collection.filterBounds(tile)
            tile_image = ee.Image(
                ee.Algorithms.If(
                    tile_collection.size().gt(0),
                    _composite(tile_collection, method),
                    base_image.updateMask(ee.Image(0)),
                )
            ).clip(tile)
            valid_tile_images.append(tile_image)
            tile_reports.append({
                "tile_id": f"tile_{index:03d}",
                "surface_km2": approximate_tile_area,
                "images_count": images_count,
                "mean_cloud_pct": None,
                "coverage_percent": None,
                "status": "valide",
                "message": "Tuile planifiee; qualite consolidee sur la mosaique finale.",
            })
        image = ee.ImageCollection.fromImages(valid_tile_images).mosaic().clip(geom)
        mosaic_method = f"{method}_adaptive_grid_mosaic"
    elif not eager_tile_qa:
        image = _composite(collection, method).clip(geom)
        mosaic_method = f"{method}_mosaic"
        tile_reports.append({
            "tile_id": "tile_001",
            "surface_km2": round(area_km2, 2),
            "images_count": images_count,
            "mean_cloud_pct": None,
            "coverage_percent": None,
            "status": "valide",
            "message": "Tuile unique; qualite consolidee sur la mosaique finale.",
        })
        valid_tile_images.append(image)
    elif len(tiles) == 1:
        build_tile(tiles[0], "tile_001", collection)
        if not valid_tile_images:
            raise ValueError("Aucune couverture Sentinel-2 valide sur cette AOI. Solution: elargir la periode ou utiliser median composite.")
        image = valid_tile_images[0].clip(geom)
        mosaic_method = f"{method}_mosaic"
    else:
        for index, tile in enumerate(tiles, start=1):
            build_tile(tile, f"tile_{index:03d}", collection)
        if not valid_tile_images:
            raise ValueError("Aucune tuile Sentinel-2 exploitable pour cette AOI/periode/seuil nuage.")
        image = ee.ImageCollection.fromImages(valid_tile_images).mosaic().clip(geom)
        mosaic_method = f"{method}_grid_mosaic"

    warning = None
    if surface.get("async_recommended"):
        coverage_percent = None
        warning = "Detailed coverage deferred to speed up processing of the large AOI."
    else:
        try:
            coverage_percent = _estimate_coverage_percent(
                image,
                geom,
                area_km2,
                scale=int(surface.get("statistics_scale_m") or 10),
            )
        except Exception as exc:
            coverage_percent = 0.0
            warning = f"Coverage could not be computed: {exc}"
    if coverage_percent is not None and coverage_percent < 55 and not warning:
        warning = "Low Sentinel-2 coverage: widen the period, raise the cloud threshold, or use a median composite."

    valid_tiles = len([tile for tile in tile_reports if tile["status"] == "valide"])
    empty_tiles = len([tile for tile in tile_reports if tile["status"] == "vide"])
    low_tiles = len([tile for tile in tile_reports if tile["status"] == "faible_couverture"])
    error_tiles = len([tile for tile in tile_reports if tile["status"] == "erreur"])
    async_recommended = surface["async_recommended"]

    return {
        "image": image,
        "geom": geom,
        "area_km2": round(area_km2, 2),
        "surface": surface,
        "images_count": images_count,
        "tiles_count": len(tiles),
        "valid_tiles_count": valid_tiles,
        "empty_tiles_count": empty_tiles,
        "low_coverage_tiles_count": low_tiles,
        "error_tiles_count": error_tiles,
        "coverage_percent": coverage_percent,
        "method": mosaic_method,
        "quality": _quality_label(coverage_percent) if coverage_percent is not None else "a_evaluer",
        "warning": warning or (surface["message"] if surface["status"] != "ok" else None),
        "message": "Mosaique Sentinel-2 finale generee sur toute la zone d'interet.",
        "cloud_probability_threshold": int(payload.get("cloud_probability_threshold", 40)),
        "async_recommended": async_recommended,
        "chunking": {
            "strategy": chunk_plan.strategy,
            "rows": chunk_plan.rows,
            "columns": chunk_plan.columns,
            "count": chunk_plan.count,
            "side_km": chunk_plan.side_km,
        },
        "tile_reports": tile_reports,
    }


def _tile_url(image: Any, vis: dict[str, Any]) -> str | None:
    try:
        map_id = image.visualize(**vis).getMapId()
        return map_id["tile_fetcher"].url_format
    except Exception:
        return None


def _format_date(timestamp_ms: int | float | None) -> str:
    if not timestamp_ms:
        return ""
    return datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc).date().isoformat()


def _image_item(image: Any, payload: dict[str, Any]) -> dict[str, Any]:
    info = image.getInfo()
    props = info.get("properties") or {}
    image_id = image.id().getInfo()
    # Some EE collection images expose only system:index. Keep a full asset id for ee.Image(...).
    gee_id = image_id if "/" in image_id else f"{S2_COLLECTION}/{image_id}"
    date = _format_date(props.get("system:time_start"))
    cloud = round(float(props.get("CLOUDY_PIXEL_PERCENTAGE") or 0), 2)
    bbox = _bbox_from_aoi(payload.get("aoi") or {})
    rgb_tile_url = _tile_url(image.clip(_aoi_geometry(payload.get("aoi") or {})), RGB_VIS)
    region_name = _region_name(payload.get("aoi") or {})

    return {
        "id": image_id,
        "gee_id": gee_id,
        "name": f"Sentinel-2 {region_name} {date}".strip(),
        "sensor": "Sentinel-2",
        "date": date,
        "resolution": "10 m",
        "projection": "EPSG:4326",
        "cloud": cloud,
        "bands": ["B2", "B3", "B4", "B8", "B11", "B12"],
        "size": "GEE",
        "region": region_name,
        "status": "Disponible",
        "bbox": bbox,
        "source": "S2_SR_HARMONIZED",
        "tile_url": rgb_tile_url,
    }


def _region_name(aoi: dict[str, Any]) -> str:
    bbox = _bbox_from_aoi(aoi)
    if bbox == [0, 0, 0, 0]:
        return "AOI"
    lat = (bbox[0] + bbox[2]) / 2
    lon = (bbox[1] + bbox[3]) / 2
    if 24.3 <= lat <= 25.1 and 46.3 <= lon <= 47.1:
        return "Riyadh"
    if 21.2 <= lat <= 21.9 and 39.0 <= lon <= 39.6:
        return "Jeddah"
    if 24.1 <= lat <= 25.0 and 39.1 <= lon <= 40.1:
        return "Medina"
    if 16.0 <= lat <= 32.5 and 34.0 <= lon <= 56.5:
        return "Saudi Arabia"
    return "AOI"

def _select_analysis_image(analysis: dict[str, Any]) -> Any:
    """Resolve the selected image safely for GEE processing.

    The frontend can send either a full GEE asset id, a Sentinel-2 system index,
    or a legacy/mock id. Legacy ids are not valid Earth Engine assets, so we
    fall back to the least-cloudy image from the requested AOI/date window.
    """
    image_id = str(analysis.get("image_id") or "").strip()
    if image_id.startswith(S2_COLLECTION):
        return ee.Image(image_id)
    if image_id.startswith("20") and "_T" in image_id:
        return ee.Image(f"{S2_COLLECTION}/{image_id}")
    return ee.Image(_collection(analysis).first())


def _build_fast_catalog_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a lazy web preview without running analysis-grade reductions.

    Catalog discovery must stay interactive. Coverage statistics and per-chunk
    validation belong to the analysis job, not to the scene-list request.
    """
    payload = _normalize_payload(payload)
    sensor = _sensor_id(payload)
    if sensor == "sentinel-1":
        raise ValueError("OSI-SAR / Sentinel-1 catalog must list individual IW scenes, never a period mosaic.")
    aoi = payload.get("aoi") or {}
    geom = _aoi_geometry(aoi)
    area_km2 = _aoi_area_km2(aoi)
    collection = _collection(payload, geom)
    images_count = int(collection.size().getInfo() or 0)
    if images_count == 0:
        raise ValueError(
            f"Aucune image {SENSOR_META[sensor]['label']} trouvee. "
            "Solution: elargir la periode ou augmenter le seuil de nuages."
        )
    image = _composite(collection, "median_composite").clip(geom)
    plan = adaptive_chunk_plan(_bbox_from_aoi(aoi), area_km2)
    policy = surface_policy(area_km2, 30 if sensor == "landsat-8-9" else 10)
    return {
        "image": image,
        "geom": geom,
        "area_km2": round(area_km2, 2),
        "surface": policy,
        "images_count": images_count,
        "tiles_count": plan.count,
        "valid_tiles_count": None,
        "empty_tiles_count": None,
        "low_coverage_tiles_count": None,
        "error_tiles_count": None,
        "coverage_percent": None,
        "method": "median_composite_lazy_preview",
        "quality": "a_evaluer",
        "warning": policy["message"] if policy["status"] != "ok" else None,
        "message": "Apercu rapide; la couverture detaillee sera calculee pendant l'analyse.",
        "cloud_probability_threshold": None,
        "async_recommended": policy["async_recommended"],
        "chunking": {
            "strategy": plan.strategy,
            "rows": plan.rows,
            "columns": plan.columns,
            "count": plan.count,
            "side_km": plan.side_km,
        },
        "tile_reports": [],
    }


def _fast_scene_items(payload: dict[str, Any], collection: Any, count: int, limit: int) -> list[dict[str, Any]]:
    """Build Available catalog rows: one full-AOI Sentinel-2 mosaic per acquisition date.

    Individual granules are grouped by calendar day, mosaicked over the AOI, and kept
    only when the day covers the AOI. Cloud % is measured from SCL cloud pixels inside
    the AOI (not the scene-level CLOUDY_PIXEL_PERCENTAGE of a single tile).
    """
    wanted = min(max(int(count or 0), 0), max(int(limit or 0), 0), 24)
    if wanted <= 0:
        return []

    aoi = payload.get("aoi") or {}
    geom = _aoi_geometry(aoi)
    bbox = _bbox_from_aoi(aoi)
    region_name = _region_name(aoi)
    area_km2 = float(_aoi_area_km2(aoi) or 0)
    max_cloud = float(payload.get("max_cloud_pct", 20) or 20)
    qa_scale = _catalog_coverage_scale_m(area_km2)

    sample_size = min(max(int(count or 0), 1), AVAILABLE_DATE_META_LIMIT)
    # Prefer a chronological sample so each date keeps its intersecting tiles,
    # instead of only the globally least-cloudy granules (which under-covers large AOIs).
    dated_sample = collection.sort("system:time_start", False).limit(sample_size)
    image_list = dated_sample.toList(sample_size)
    dictionaries = ee.List.sequence(0, sample_size - 1).map(
        lambda index: ee.Image(image_list.get(index)).toDictionary(
            ["system:index", "system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "MGRS_TILE"]
        )
    )
    metadata = dictionaries.getInfo() or []

    by_date: dict[str, list[dict[str, Any]]] = {}
    for props in metadata:
        if not isinstance(props, dict):
            continue
        date = _format_date(props.get("system:time_start"))
        if not date:
            continue
        by_date.setdefault(date, []).append(props)

    if not by_date:
        return []

    period_tiles: set[str] = set()
    try:
        distinct_tiles = collection.aggregate_array("MGRS_TILE").distinct().getInfo() or []
        period_tiles = {str(tile).strip() for tile in distinct_tiles if str(tile).strip()}
    except Exception:
        for scenes in by_date.values():
            for item in scenes:
                tile = str(item.get("MGRS_TILE") or "").strip()
                if tile:
                    period_tiles.add(tile)

    # Soft prefilter only: skip dates that clearly cannot fill a multi-tile AOI.
    # Final acceptance is always pixel coverage inside the AOI (not MGRS equality).
    min_tiles_guess = 1
    if len(period_tiles) >= 4:
        min_tiles_guess = max(2, int(math.ceil(len(period_tiles) * 0.6)))
    elif len(period_tiles) >= 2:
        min_tiles_guess = max(1, len(period_tiles) - 1)

    candidates: list[tuple[str, list[dict[str, Any]], float, set[str]]] = []
    for date, scenes in by_date.items():
        tiles = {str(item.get("MGRS_TILE") or "").strip() for item in scenes}
        tiles.discard("")
        if len(tiles) < min_tiles_guess:
            continue
        clouds = [float(item.get("CLOUDY_PIXEL_PERCENTAGE") or 0) for item in scenes]
        mean_meta_cloud = sum(clouds) / max(len(clouds), 1)
        candidates.append((date, scenes, mean_meta_cloud, tiles))

    # Try the most complete / least cloudy dates first (critical for very large AOIs).
    candidates.sort(key=lambda row: (-len(row[3]), row[2], row[0]))

    scenes_out: list[dict[str, Any]] = []
    attempts = 0
    max_attempts = max(wanted * 4, wanted)
    for date, day_scenes, _mean_meta_cloud, tiles in candidates:
        if len(scenes_out) >= wanted or attempts >= max_attempts:
            break
        attempts += 1
        try:
            mosaic = _sentinel2_date_mosaic_image(payload, date, geom)
            qa = _estimate_date_mosaic_qa(mosaic, geom, area_km2, scale=qa_scale)
            if not qa:
                continue
            coverage = float(qa["coverage_percent"])
            if coverage < AVAILABLE_DATE_COVERAGE_MIN_PCT:
                continue
            cloud = float(qa["cloud_percent"])
            if cloud > max_cloud + 1e-6:
                continue
            # Attach preview tiles during catalog search so Show on map covers the full AOI
            # immediately (same path as the multi-date Mosaic item).
            tile_url = _tile_url(mosaic, RGB_VIS)
            if not tile_url:
                continue
            mosaic_id = f"{S2_DATE_MOSAIC_PREFIX}{date}"
            scenes_out.append(
                {
                    "id": mosaic_id,
                    "gee_id": mosaic_id,
                    "name": f"Sentinel-2 {region_name} {date}".strip(),
                    "sensor": "Sentinel-2",
                    "date": date,
                    "acquisition_date": date,
                    "resolution": "10 m",
                    "projection": "EPSG:4326",
                    "cloud": cloud,
                    "bands": ["B2", "B3", "B4", "B8", "B11", "B12"],
                    "size": "GEE date mosaic",
                    "region": region_name,
                    "status": "Disponible",
                    "bbox": bbox,
                    "source": "S2_SR_HARMONIZED",
                    "tile_url": tile_url,
                    "mosaic": False,
                    "date_mosaic": True,
                    "images_count": len(day_scenes),
                    "tiles_count": len(tiles),
                    "coverage_percent": coverage,
                    "cloud_source": "scl_aoi",
                    "catalog_logic": CATALOG_AVAILABLE_LOGIC_VERSION,
                }
            )
        except Exception:
            continue

    # Prefer chronological display (newest first) for Available cards.
    scenes_out.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    return scenes_out


def _fast_landsat_scene_items(payload: dict[str, Any], collection: Any, count: int, limit: int) -> list[dict[str, Any]]:
    """Return selectable Landsat 8/9 acquisitions from the filtered catalogue."""
    wanted = min(max(int(count or 0), 0), max(int(limit or 0), 0), 24)
    if wanted <= 0:
        return []
    sample = collection.sort("system:time_start", False).limit(wanted)
    metadata = sample.toList(wanted).map(
        lambda image: ee.Image(image).toDictionary(
            ["system:index", "system:time_start", "CLOUD_COVER", "SPACECRAFT_ID", "WRS_PATH", "WRS_ROW"]
        )
    ).getInfo() or []
    bbox = _bbox_from_aoi(payload.get("aoi") or {})
    region_name = _region_name(payload.get("aoi") or {})
    scenes: list[dict[str, Any]] = []
    for props in metadata:
        if not isinstance(props, dict):
            continue
        system_index = str(props.get("system:index") or "").strip()
        if not system_index:
            continue
        collection_id = LANDSAT9_COLLECTION if system_index.startswith("LC09_") else LANDSAT8_COLLECTION
        acquisition_date = _format_date(props.get("system:time_start"))
        spacecraft = str(props.get("SPACECRAFT_ID") or ("LANDSAT_9" if system_index.startswith("LC09_") else "LANDSAT_8"))
        scenes.append(
            {
                "id": system_index,
                "gee_id": f"{collection_id}/{system_index}",
                "name": f"{spacecraft.replace('_', ' ').title()} {region_name} {acquisition_date}".strip(),
                "sensor": "Landsat 8/9",
                "date": acquisition_date,
                "acquisition_date": acquisition_date,
                "resolution": "30 m",
                "projection": "EPSG:4326",
                "cloud": round(float(props.get("CLOUD_COVER") or 0), 2),
                "bands": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"],
                "size": "GEE scene",
                "region": region_name,
                "status": "Disponible",
                "bbox": bbox,
                "source": collection_id,
                "tile_url": None,
                "mosaic": False,
                "path": props.get("WRS_PATH"),
                "row": props.get("WRS_ROW"),
            }
        )
    return scenes


def _fast_s1_scene_items(payload: dict[str, Any], collection: Any, image_count: int, limit: int) -> list[dict[str, Any]]:
    sample = collection.sort("system:time_start", False).limit(min(max(int(limit), 1), 32))
    property_keys = [
        "system:index",
        "system:time_start",
        "orbitProperties_pass",
        "relativeOrbitNumber_start",
        "relativeOrbitNumber_stop",
        "platform_number",
    ]
    metadata = sample.toList(32).map(lambda image: ee.Image(image).toDictionary(property_keys)).getInfo() or []
    bbox = _bbox_from_aoi(payload.get("aoi") or {})
    region_name = _region_name(payload.get("aoi") or {})
    scenes: list[dict[str, Any]] = []
    for props in metadata:
        if not isinstance(props, dict):
            continue
        image_id = str(props.get("system:index") or "")
        date = _format_date(props.get("system:time_start"))
        orbit_pass = str(props.get("orbitProperties_pass") or "")
        relative_orbit = props.get("relativeOrbitNumber_start")
        if relative_orbit is None:
            relative_orbit = props.get("relativeOrbitNumber_stop")
        platform = props.get("platform_number") or (image_id[:3] if image_id else "S1")
        gee_id = f"{SENTINEL1_COLLECTION}/{image_id}" if image_id else None
        scenes.append({
            "id": image_id,
            "gee_id": gee_id,
            "name": f"Sentinel-1 {date} {orbit_pass} orbit {relative_orbit}".strip(),
            "sensor": "Sentinel-1",
            "date": date,
            "resolution": "10 m",
            "projection": "EPSG:4326",
            "cloud": 0,
            "bands": ["VV", "VH", "angle"],
            "size": "GEE scene",
            "region": region_name,
            "status": "Disponible",
            "bbox": bbox,
            "source": SENTINEL1_COLLECTION,
            "tile_url": None,
            "mosaic": False,
            "orbit_pass": orbit_pass,
            "relative_orbit": relative_orbit,
            "platform": platform,
            "acquisition_timestamp": props.get("system:time_start"),
        })
    return scenes


def _search_sentinel1_scenes(payload: dict[str, Any], limit: int = 16, progress_callback: Any | None = None) -> dict[str, Any]:
    geom = _aoi_geometry(payload.get("aoi") or {})
    options = _osi_sar_options(payload)
    if progress_callback:
        progress_callback(40, "Filtrage Sentinel-1 IW VV/VH", "filter_date_sensor")
    collection = _build_osi_sar_collection(payload, geom, options)
    if progress_callback:
        progress_callback(70, "Liste des acquisitions Sentinel-1", "detect_scenes")
    image_count = int(collection.size().getInfo() or 0)
    if image_count <= 0:
        raise ValueError("Aucune scene Sentinel-1 IW VV/VH trouvee. Solution: elargir la periode ou verifier l'AOI marine.")
    scenes = _fast_s1_scene_items(payload, collection, image_count, limit)
    if progress_callback:
        progress_callback(90, "Preparation du catalogue Sentinel-1", "prepare_catalog")
    warning = (
        "OSI-SAR uses one Sentinel-1 acquisition, not a multi-month mosaic. "
        "Select a scene or the most recent acquisition will be used."
    )
    return {
        "gee": gee_status(),
        "items": scenes,
        "scenes": scenes,
        "mosaic": {
            "images_count": image_count,
            "tiles_count": 0,
            "coverage_percent": None,
            "method": "single_scene",
            "quality": "scene",
            "warning": warning,
            "message": warning,
        },
        "mode": "gee",
        "count": image_count,
        "warning": warning,
    }


def search_sentinel2(payload: dict[str, Any], limit: int = 10, progress_callback: Any | None = None) -> dict[str, Any]:
    payload = _normalize_payload(payload)
    sensor = _sensor_id(payload)
    sensor_meta = SENSOR_META[sensor]
    if progress_callback:
        progress_callback(10, "Lecture de la zone d'interet", "aoi")
    if progress_callback:
        progress_callback(25, "Connexion a Google Earth Engine", "gee_connection")
    if not _ensure_gee():
        return {
            "gee": gee_status(),
            "items": [],
            "scenes": [],
            "mosaic": None,
            "mode": "unavailable",
            "count": 0,
            "warning": "Google Earth Engine is unavailable. No mock satellite images are shown.",
        }

    if sensor == "sentinel-1":
        try:
            result = _search_sentinel1_scenes(payload, limit=max(limit, 16), progress_callback=progress_callback)
        except Exception as exc:
            message = str(exc)
            return {
                "gee": gee_status(),
                "items": [],
                "scenes": [],
                "mosaic": {
                    "images_count": 0,
                    "tiles_count": 0,
                    "coverage_percent": 0,
                    "method": "single_scene",
                    "quality": "faible",
                    "warning": message,
                    "message": message,
                },
                "mode": "gee",
                "count": 0,
                "warning": message,
            }
        if progress_callback:
            progress_callback(100, "Images pretes a l'affichage", "completed")
        return result

    try:
        if progress_callback:
            progress_callback(40, "Filtrage par date et capteur", "filter_date_sensor")
        if progress_callback:
            progress_callback(55, "Filtrage par couverture nuageuse", "filter_clouds")
        if progress_callback:
            progress_callback(70, "Detection des scenes disponibles", "detect_scenes")
        mosaic = _build_fast_catalog_preview(payload)
        if progress_callback:
            progress_callback(85, "Preparation du catalogue ou de la mosaique", "prepare_catalog")
    except Exception as exc:
        message = str(exc)
        return {
            "gee": gee_status(),
            "items": [],
            "scenes": [],
            "mosaic": {
                "images_count": 0,
                "tiles_count": 0,
                "coverage_percent": 0,
                "method": None,
                "quality": "faible",
                "warning": message,
                "message": message,
            },
            "mode": "gee",
            "count": 0,
            "warning": message,
        }
    if sensor == "sentinel-2":
        if progress_callback:
            progress_callback(90, "Preparation des apercus des images", "prepare_previews")
        collection = _collection(payload)
        scenes = _fast_scene_items(payload, collection, mosaic["images_count"], limit)
    elif sensor == "landsat-8-9":
        collection = _collection(payload)
        scenes = _fast_landsat_scene_items(payload, collection, mosaic["images_count"], limit)
    else:
        scenes = []
    bbox = _bbox_from_aoi(payload.get("aoi") or {})
    region_name = _region_name(payload.get("aoi") or {})
    date_start = payload.get("date_start")
    date_end = payload.get("date_end")
    mosaic_quality = _mosaic_quality_payload(mosaic)
    mosaic_item = {
        "id": f"{sensor.upper()}_MOSAIC_{date_start}_{date_end}_{region_name}".replace(" ", "_"),
        "gee_id": None,
        "name": f"Mosaique {sensor_meta['label']} {region_name} {date_start} -> {date_end}".strip(),
        "sensor": sensor_meta["label"],
        "date": f"{date_start} -> {date_end}",
        "resolution": _sensor_resolution(payload),
        "projection": "EPSG:4326",
        "cloud": int(payload.get("max_cloud_pct", 20)),
        "bands": list(sensor_meta["vis"].get("bands", [])),
        "size": "GEE mosaic",
        "region": region_name,
        "status": "Mosaique",
        "bbox": bbox,
        "source": sensor_meta["collection"],
        "tile_url": _tile_url(mosaic["image"], sensor_meta["vis"]),
        "mosaic": True,
        "quality": mosaic_quality,
    }
    result = {
        "gee": gee_status(),
        "items": [mosaic_item, *scenes],
        "scenes": scenes,
        "mosaic": mosaic_quality,
        "mode": "gee",
        "count": mosaic["images_count"],
    }
    if progress_callback:
        progress_callback(100, "Images pretes a l'affichage", "completed")
    return result


def preview_sentinel2(payload: dict[str, Any]) -> dict[str, Any]:
    """Return selected raster preview, real GEE when available."""
    requested_scene_id = str(payload.get("scene_id") or "").strip()
    payload = _normalize_payload(payload)
    sensor = _sensor_id(payload)
    sensor_meta = SENSOR_META[sensor]
    if not _ensure_gee():
        return {
            "source": sensor_meta["collection"],
            "collection": sensor_meta["collection"],
            "method": payload.get("image_method", "median_composite"),
            "image": None,
            "quality": {"available_images": 0, "images_count": 0, "tiles_count": 0, "coverage_percent": 0, "quality": "unavailable"},
            "preview": {"type": "xyz", "tile_url": None, "rgb_bands": ["B4", "B3", "B2"]},
            "gee": gee_status(),
            "warning": "Google Earth Engine is unavailable. No mock preview is returned.",
        }

    if requested_scene_id:
        if sensor not in {"sentinel-2", "landsat-8-9"}:
            raise ValueError("Individual RGB previews require Sentinel-2 or Landsat 8/9.")
        acquisition_date = _parse_s2_date_mosaic_id(requested_scene_id) if sensor == "sentinel-2" else None
        if acquisition_date:
            geom = _aoi_geometry(payload.get("aoi") or {})
            image = _sentinel2_date_mosaic_image(payload, acquisition_date, geom)
            day_count = int(
                _collection(payload, geom)
                .filterDate(ee.Date(acquisition_date), ee.Date(acquisition_date).advance(1, "day"))
                .size()
                .getInfo()
                or 0
            )
            if day_count <= 0:
                raise ValueError("The selected acquisition date is no longer available for the current AOI, period, or cloud filter.")
            tile_url = _tile_url(image, RGB_VIS)
            area_km2 = float(_aoi_area_km2(payload.get("aoi") or {}) or 0)
            qa_scale = _catalog_coverage_scale_m(area_km2)
            qa = _estimate_date_mosaic_qa(image, geom, area_km2, scale=qa_scale) if area_km2 > 0 else None
            coverage = None if qa is None else qa.get("coverage_percent")
            cloud = None if qa is None else qa.get("cloud_percent")
            region_name = _region_name(payload.get("aoi") or {})
            mosaic_id = f"{S2_DATE_MOSAIC_PREFIX}{acquisition_date}"
            selected = {
                "id": mosaic_id,
                "gee_id": mosaic_id,
                "name": f"Sentinel-2 {region_name} {acquisition_date}".strip(),
                "sensor": "Sentinel-2",
                "date": acquisition_date,
                "acquisition_date": acquisition_date,
                "resolution": "10 m",
                "projection": "EPSG:4326",
                "cloud": cloud,
                "bands": ["B2", "B3", "B4", "B8", "B11", "B12"],
                "size": "GEE date mosaic",
                "region": region_name,
                "status": "Disponible",
                "bbox": _bbox_from_aoi(payload.get("aoi") or {}),
                "source": "S2_SR_HARMONIZED",
                "tile_url": tile_url,
                "mosaic": False,
                "date_mosaic": True,
                "images_count": day_count,
                "coverage_percent": coverage,
                "cloud_source": "scl_aoi",
            }
            return {
                "source": sensor_meta["collection"],
                "collection": sensor_meta["collection"],
                "method": "date_mosaic",
                "image": selected,
                "quality": {
                    "available_images": day_count,
                    "images_count": day_count,
                    "tiles_count": day_count,
                    "coverage_percent": coverage,
                    "quality": "date_mosaic",
                    "acquisition_date": acquisition_date,
                },
                "preview": {"type": "xyz", "tile_url": tile_url, "rgb_bands": ["B4", "B3", "B2"]},
                "gee": gee_status(),
            }
        geom = _aoi_geometry(payload.get("aoi") or {})
        scene_id = _selected_scene_system_index(requested_scene_id, sensor)
        if not scene_id:
            raise ValueError("The requested scene identifier is invalid.")
        collection = _prepared_collection_for_sensor(payload, geom).filter(
            ee.Filter.eq("system:index", scene_id)
        )
        if int(collection.size().getInfo() or 0) <= 0:
            raise ValueError("The selected scene is no longer available for the current AOI, period, or cloud filter.")
        image = ee.Image(collection.first()).clip(geom)
        tile_url = _tile_url(image, sensor_meta["vis"])
        selected = {
            "id": scene_id,
            "gee_id": requested_scene_id,
            "name": f"{sensor_meta['label']} {_region_name(payload.get('aoi') or {})} selected scene",
            "sensor": sensor_meta["label"],
            "date": "",
            "resolution": sensor_meta["resolution"],
            "projection": "EPSG:4326",
            "cloud": None,
            "bands": list(sensor_meta["vis"].get("bands", [])),
            "size": "GEE scene",
            "region": _region_name(payload.get("aoi") or {}),
            "status": "Disponible",
            "bbox": _bbox_from_aoi(payload.get("aoi") or {}),
            "source": sensor_meta["collection"],
            "tile_url": tile_url,
            "mosaic": False,
        }
        return {
            "source": sensor_meta["collection"],
            "collection": sensor_meta["collection"],
            "method": "single_scene",
            "image": selected,
            "quality": {"available_images": 1, "images_count": 1, "tiles_count": 1, "coverage_percent": None, "quality": "scene"},
            "preview": {"type": "xyz", "tile_url": tile_url, "rgb_bands": sensor_meta["vis"].get("bands", [])},
            "gee": gee_status(),
        }

    try:
        search = search_sentinel2(payload, limit=1)
    except ValueError:
        return {
            "source": "S2_SR_HARMONIZED",
            "collection": S2_COLLECTION,
            "method": payload.get("image_method", "least_cloudy"),
            "image": None,
            "quality": {
                "available_images": 0,
                "images_count": 0,
                "tiles_count": 0,
                "coverage_percent": 0,
                "method": None,
                "quality": "faible",
                "warning": "Aucune image Sentinel-2 trouvee pour cette AOI/periode/seuil nuage.",
            },
            "preview": {"type": "xyz", "tile_url": None, "rgb_bands": ["B4", "B3", "B2"]},
            "gee": gee_status(),
        }

    selected = (search.get("items") or [None])[0]
    mosaic_quality = search.get("mosaic") or {}
    return {
        "source": sensor_meta["collection"],
        "collection": sensor_meta["collection"],
        "method": mosaic_quality.get("method") or payload.get("image_method", "least_cloudy"),
        "image": selected,
        "quality": {
            "available_images": search.get("count", 0),
            "images_count": mosaic_quality.get("images_count", search.get("count", 0)),
            "tiles_count": mosaic_quality.get("tiles_count"),
            "coverage_percent": mosaic_quality.get("coverage_percent"),
            "method": mosaic_quality.get("method"),
            "quality": mosaic_quality.get("quality"),
            "warning": mosaic_quality.get("warning"),
        },
        "preview": {
            "type": "xyz",
            "tile_url": selected.get("tile_url") if selected else None,
            "rgb_bands": ["B4", "B3", "B2"],
            "false_color_bands": ["B8", "B4", "B3"],
        },
        "gee": gee_status(),
    }


FAST_MAP_AOI_THRESHOLD_KM2 = 15000
FAST_MAP_INDICES = {"NDVI", "NDWI", "NDBI", "BSI", "SAVI"}


def _perf_log(metric: str, value_ms: float, **extra: Any) -> None:
    details = " ".join(f"{key}={value}" for key, value in extra.items() if value is not None)
    suffix = f" {details}" if details else ""
    print(f"[PERF] {metric}={round(value_ms, 2)}ms{suffix}", flush=True)


def _deferred_index_classes(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "surface_ha": 0.0,
            "pct": 0.0,
            "color": color,
            "deferred": True,
        }
        for _low, _high, name, color in cfg.get("classes", [])
    ]


def _fast_map_index_result(analysis: dict[str, Any], surface_ha: int) -> dict[str, Any]:
    """Return a GEE tile layer without blocking on reduceRegion statistics."""
    started = time.perf_counter()
    analysis = _normalize_payload(analysis)
    sensor = _sensor_id(analysis)
    index_id = str(analysis.get("index", "NDVI")).upper()
    if index_id not in FAST_MAP_INDICES:
        raise ValueError(f"Fast map mode is not available for {index_id}.")

    mosaic_started = time.perf_counter()
    mosaic = _build_lazy_analysis_mosaic(analysis)
    _perf_log("collection_build_ms", (time.perf_counter() - mosaic_started) * 1000, index=index_id, mode="fast_map")
    geom = mosaic["geom"]
    image = mosaic["image"]

    graph_started = time.perf_counter()
    cfg = dict(INDEX_CONFIG[index_id])
    cfg["bands"] = _index_bands_for_sensor(index_id, sensor)
    native_scale = _index_native_scale(index_id, sensor)
    output_scale = _effective_output_resolution_m(analysis, native_scale)
    policy = surface_policy(surface_ha / 100.0, output_scale)
    index_image = _index_raster_for_analysis(image, index_id, cfg["bands"]).clip(geom)
    active_comparison_layer = None
    if index_id == "NDBI":
        # Large-AOI first paint must use the same Built-up detection graph as the
        # full compute. Raw NDBI value classes ("built or bare") over-paint arid
        # soils and must not be shown as the user-facing NDBI result.
        built = _ndbi_built_detection_context(analysis, image, index_image, sensor, geom)
        index_tile_image, index_tile_vis = built["classified"], built["vis"]
        palette = list(built["cfg"]["palette"])
        deferred_cfg = built["cfg"]
        active_comparison_layer = "ndbi_built_detection"
    elif index_id == "NDVI":
        # Discrete NDVI classes (stable absolute thresholds) so arid landscapes
        # do not collapse into one continuous stretch color.
        index_tile_image, index_tile_vis = _classified_index_image(index_image, cfg, index_id)
        palette = [item[3] for item in cfg["classes"]]
        deferred_cfg = cfg
    elif index_id in {"NDWI", "BSI"}:
        index_tile_image, index_tile_vis = index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}
        palette = cfg["palette"]
        deferred_cfg = cfg
    else:
        index_tile_image, index_tile_vis = _classified_index_image(index_image, cfg, index_id)
        palette = [item[3] for item in cfg["classes"]]
        deferred_cfg = cfg
    _perf_log("index_graph_ms", (time.perf_counter() - graph_started) * 1000, index=index_id, mode="fast_map")

    mapid_started = time.perf_counter()
    tiles = {
        "rgb_tile_url": None,
        "index_tile_url": _tile_url(index_tile_image, index_tile_vis),
    }
    _perf_log("gee_mapid_ms", (time.perf_counter() - mapid_started) * 1000, index=index_id, mode="fast_map")

    stats = {
        "surface_ha": surface_ha,
        **_resolution_contract(
            analysis,
            native_scale,
            int(policy["statistics_scale_m"]),
        ),
        "processing_policy": policy,
        "statistics_status": "deferred_for_first_map",
        "first_map_tile_priority": True,
    }
    result = {
        "stats": stats,
        "histogram": [],
        "classes": _deferred_index_classes(deferred_cfg),
        "palette": palette,
        "tiles": tiles,
        "comparison_layers": [],
        "active_comparison_layer": active_comparison_layer,
        "mosaic": _mosaic_quality_payload(mosaic),
        "quality_summary": {
            "statistics_status": "deferred_for_first_map",
            "first_map_tile_priority": True,
            "warning": "Map tiles are returned first; exact statistics continue in the background.",
        },
        "mode": "gee",
        "gee": gee_status(),
        "performance": {
            "strategy": "gee_lazy_tiles_first",
            "stats_deferred": True,
            "first_response_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }
    _perf_log("first_response_ms", result["performance"]["first_response_ms"], index=index_id, mode="fast_map")
    return result


def compute_sentinel2_index(
    analysis: dict[str, Any],
    surface_ha: int,
    *,
    first_map_priority: bool = False,
) -> dict[str, Any]:
    """Compute supported spectral indices from GEE for compatible optical sensors."""
    atomic_started = time.perf_counter()
    analysis = _normalize_payload(analysis)
    sensor = _sensor_id(analysis)
    index_id = str(analysis.get("index", "NDVI")).upper()
    if str(analysis.get("analysis_type") or "").lower() == "supervised_classification":
        index_id = SUPERVISED_CLASSIFICATION_ID
    if str(analysis.get("analysis_type") or "").lower() == "unsupervised_classification":
        index_id = UNSUPERVISED_CLASSIFICATION_ID
    if index_id == SUPERVISED_CLASSIFICATION_ID:
        return compute_supervised_classification(analysis, surface_ha=surface_ha)
    if index_id == UNSUPERVISED_CLASSIFICATION_ID:
        return compute_unsupervised_classification(analysis, surface_ha=surface_ha)
    if index_id == OSI_SAR_ID:
        return compute_osi_sar_index(analysis, surface_ha=surface_ha)
    if index_id in CHANGE_DETECTION_IDS:
        return compute_change_detection_index(
            analysis,
            surface_ha=surface_ha,
            first_map_priority=first_map_priority,
        )
    if index_id not in INDEX_CONFIG:
        raise ValueError(f"Indice {index_id} non disponible. Utilisez NDVI, NDWI, NDBI, BSI, SAVI, OSI-SAR, Change Detection, Supervised Classification ou Unsupervised Classification.")

    if not _ensure_gee():
        result = compute_mock_index(index_id, surface_ha=surface_ha)
        result["tiles"] = {"rgb_tile_url": None, "index_tile_url": None}
        result["mode"] = "mock"
        result["gee"] = gee_status()
        return result
    if index_id in FAST_MAP_INDICES and first_map_priority:
        return _fast_map_index_result(analysis, surface_ha)

    # A very large AOI must not build hundreds of per-cell median branches:
    # filtering the prepared collection by the complete geometry and clipping
    # the final median produces the same index formulas with a much smaller EE
    # graph. Detailed tile QA remains available in catalog discovery.
    if (surface_ha / 100.0) > FAST_MAP_AOI_THRESHOLD_KM2 and index_id in FAST_MAP_INDICES:
        mosaic = _build_lazy_analysis_mosaic(analysis)
    else:
        mosaic = _build_analysis_mosaic(analysis)
    geom = mosaic["geom"]
    image = mosaic["image"]

    cfg = dict(INDEX_CONFIG[index_id])
    cfg["bands"] = _index_bands_for_sensor(index_id, sensor)
    native_scale = _index_native_scale(index_id, sensor)
    output_scale = _effective_output_resolution_m(analysis, native_scale)
    policy = surface_policy(surface_ha / 100.0, output_scale)
    scale = int(policy["statistics_scale_m"])
    index_image = _index_raster_for_analysis(image, index_id, cfg["bands"]).clip(geom)
    analysis_crs = _analysis_crs(analysis)
    summary_started = time.perf_counter()
    stats, histogram, classes = _compute_index_summary(
        index_image,
        index_id,
        geom,
        cfg,
        surface_ha,
        scale=scale,
        analysis_crs=analysis_crs,
    )
    _perf_log(
        "atomic_statistics_ms",
        (time.perf_counter() - summary_started) * 1000,
        index=index_id,
        area_km2=round(surface_ha / 100.0, 2),
        scale_m=scale,
    )
    stats.update(_resolution_contract(analysis, native_scale, scale))
    stats["processing_policy"] = policy
    comparison_layers: list[dict[str, Any]] = []
    active_comparison_layer: str | None = None
    if index_id == "NDBI":
        classes = _describe_raw_ndbi_classes(classes)
        class_palette = [item[3] for item in cfg["classes"]]
        classified_map, classified_vis = _classified_index_image(index_image, cfg, index_id)

        built = _ndbi_built_detection_context(analysis, image, index_image, sensor, geom)
        built_cfg = built["cfg"]
        built_classes = _compute_ndbi_classes(
            index_image,
            built["ndvi"],
            built["ndwi"],
            built["bsi"],
            geom,
            built_cfg,
            surface_ha,
            scale=scale,
            analysis_crs=analysis_crs,
            built_probability_image=built["built_probability"],
            bare_probability_image=built["bare_probability"],
            stable_built_reference=built["stable_built_reference"],
            historical_built_surface=built["historical_built_surface"],
        )
        built_image, built_vis = built["classified"], built["vis"]
        built_surface_ha = round(sum(float(item.get("surface_ha") or 0) for item in built_classes[1:]), 2)
        built_stats = {
            **stats,
            "built_surface_ha": built_surface_ha,
            "built_pct": round((built_surface_ha / surface_ha) * 100, 1) if surface_ha else 0,
        }
        class_tile_url = _tile_url(classified_map, classified_vis)
        raw_tile_url = _tile_url(index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]})
        built_tile_url = _tile_url(built_image, built_vis)
        comparison_layers = [
            {
                "key": "ndbi_classes",
                "index": "NDBI",
                "title": "NDBI - Built-up classes",
                "topic": "Readable NDBI value classes for built-up interpretation",
                "stats": stats,
                "histogram": histogram,
                "classes": classes,
                "legend": classes,
                "palette": class_palette,
                "tiles": {"index_tile_url": class_tile_url, "rgb_tile_url": None},
                "user_visible": False,
                "metadata": {
                    "formula": cfg["formula"],
                    "bands": cfg["bands"],
                    "interpretation": (
                        "Discrete NDBI value classes for map reading. In arid areas, positive NDBI "
                        "can also come from bare soil; this is not a confirmed land-cover map."
                    ),
                },
            },
            {
                "key": "ndbi_raw",
                "index": "NDBI_RAW",
                "title": "NDBI - Raw index",
                "topic": "Continuous SWIR-to-NIR spectral response",
                "stats": stats,
                "histogram": histogram,
                "classes": classes,
                "legend": classes,
                "palette": cfg["palette"],
                "tiles": {"index_tile_url": raw_tile_url, "rgb_tile_url": None},
                "user_visible": False,
                "metadata": {
                    "formula": cfg["formula"],
                    "bands": cfg["bands"],
                    "interpretation": "Pure continuous NDBI response computed server-side without land-cover relabelling.",
                },
            },
            {
                "key": "ndbi_built_detection",
                "index": "BUILT_DETECTION",
                "title": "Built-up detection",
                "topic": "Built-up and impervious-surface interpretation",
                "stats": built_stats,
                "histogram": [
                    {"bin": item["name"], "count": int(round(float(item.get("surface_ha") or 0) * 100))}
                    for item in built_classes
                ],
                "classes": built_classes,
                "legend": built_classes,
                "palette": built_cfg["palette"],
                "tiles": {"index_tile_url": built_tile_url, "rgb_tile_url": None},
                "user_visible": True,
                "metadata": {
                    "interpretation": "Primary user-facing NDBI result: multi-observation built-up interpretation.",
                    "resolution_m": 10,
                    "auxiliary_sources": [
                        DYNAMIC_WORLD_COLLECTION,
                        ESA_WORLDCOVER_COLLECTION,
                        GHSL_BUILT_SURFACE_IMAGE,
                    ],
                    "ghsl_recovery_threshold_m2_per_100m2_cell": 50,
                },
            },
        ]
        # User-facing NDBI result is Built-up detection only; raw/classes remain internal.
        active_comparison_layer = "ndbi_built_detection"
        index_tile_image, index_tile_vis = built_image, built_vis
        classes = built_classes
        histogram = [
            {"bin": item["name"], "count": int(round(float(item.get("surface_ha") or 0) * 100))}
            for item in built_classes
        ]
        stats = built_stats
        cfg = {**cfg, "palette": built_cfg["palette"]}
    elif index_id == "NDVI":
        # Scientific NDVI values stay continuous in stats/histogram. The map uses
        # stable absolute class thresholds so desert soil and vegetation pockets
        # remain distinguishable on small and very large AOIs alike.
        classified_map, classified_vis = _classified_index_image(index_image, cfg, index_id)
        class_palette = [item[3] for item in cfg["classes"]]
        raw_tile_url = _tile_url(index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]})
        class_tile_url = _tile_url(classified_map, classified_vis)
        comparison_layers = [
            {
                "key": "ndvi_raw",
                "index": "NDVI_RAW",
                "title": "NDVI - Continuous",
                "topic": "Continuous NDVI stretch",
                "stats": stats,
                "histogram": histogram,
                "classes": classes,
                "legend": classes,
                "palette": cfg["palette"],
                "tiles": {"index_tile_url": raw_tile_url, "rgb_tile_url": None},
                "user_visible": False,
                "metadata": {
                    "formula": cfg["formula"],
                    "bands": cfg["bands"],
                    "interpretation": "Scientific continuous NDVI; not the primary map.",
                },
            },
            {
                "key": "ndvi_classes",
                "index": "NDVI",
                "title": "NDVI - Classified",
                "topic": "Stable NDVI value classes",
                "stats": stats,
                "histogram": histogram,
                "classes": classes,
                "legend": classes,
                "palette": class_palette,
                "tiles": {"index_tile_url": class_tile_url, "rgb_tile_url": None},
                "user_visible": True,
                "metadata": {
                    "formula": cfg["formula"],
                    "bands": cfg["bands"],
                    "interpretation": "Primary NDVI map: absolute class thresholds shared by every AOI size.",
                },
            },
        ]
        active_comparison_layer = "ndvi_classes"
        index_tile_image, index_tile_vis = classified_map, classified_vis
        cfg = {**cfg, "palette": class_palette}
    elif index_id == "BSI":
        # Keep the scientific BSI continuous; class thresholds are exposed as
        # interpretation metadata/legend only.
        index_tile_image, index_tile_vis = index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}
    elif index_id == "NDWI":
        classified_image, classified_vis = _classified_index_image(index_image, cfg, index_id)
        index_tile_image, index_tile_vis = index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}
    else:
        classified_image, classified_vis = _classified_index_image(index_image, cfg, index_id)
        index_tile_image, index_tile_vis = classified_image, classified_vis

    result = {
        "stats": stats,
        "histogram": histogram,
        "classes": classes,
        "palette": cfg["palette"] if index_id in {"NDVI", "NDWI", "NDBI", "BSI"} else [item[3] for item in cfg["classes"]],
        "tiles": {
            "rgb_tile_url": _tile_url(image.clip(geom), _analysis_rgb_vis_for_sensor(sensor)),
            "index_tile_url": _tile_url(index_tile_image, index_tile_vis),
        },
        "comparison_layers": comparison_layers,
        "active_comparison_layer": active_comparison_layer,
        "mosaic": _mosaic_quality_payload(mosaic),
        "mode": "gee",
        "gee": gee_status(),
        "performance": {
            "strategy": "gee_atomic_adaptive_statistics",
            "stats_deferred": False,
            "statistics_scale_m": scale,
            "statistics_pixel_budget": policy.get("statistics_pixel_budget"),
            "total_response_ms": round((time.perf_counter() - atomic_started) * 1000, 2),
        },
    }
    _perf_log(
        "atomic_total_response_ms",
        result["performance"]["total_response_ms"],
        index=index_id,
        area_km2=round(surface_ha / 100.0, 2),
    )
    return result


def _change_base_index(index_id: str) -> str:
    base = str(index_id or "").upper().replace("CHANGE_", "")
    if base not in CHANGE_DETECTION_BASES:
        raise ValueError("Change Detection supports NDVI, NDWI, NDBI, BSI, and SAVI.")
    return base


def _period_payload(analysis: dict[str, Any], key: str) -> dict[str, Any]:
    period = dict(analysis.get(key) or {})
    start = period.get("start_date") or period.get("date_start") or analysis.get("date_start")
    end = period.get("end_date") or period.get("date_end") or analysis.get("date_end")
    source_index = str(analysis.get("index") or "").upper()
    base_index = _change_base_index(source_index) if source_index.startswith("CHANGE_") else source_index
    return {
        **analysis,
        "index": base_index,
        "date_start": start,
        "date_end": end,
        "start_date": start,
        "end_date": end,
        "image_method": "median_composite",
    }


def _index_raster_for_analysis(image: Any, index_id: str, bands: list[str]) -> Any:
    if index_id == "SAVI":
        return _compute_savi_float_image(image, bands)
    return _compute_index_image(image, index_id, bands)


def _change_index_image(image: Any, index_id: str, sensor: str, geom: Any) -> Any:
    return _index_raster_for_analysis(image, index_id, _index_bands_for_sensor(index_id, sensor)).clip(geom)


def _base_index_tile(index_id: str, image: Any, cfg: dict[str, Any]) -> tuple[Any, dict[str, Any], list[str]]:
    """Reuse the exact map visualization of the validated simple index."""
    vis_cfg = INDEX_VIS_CONFIG[index_id]
    if index_id in {"NDVI", "NDWI", "NDBI", "BSI"}:
        vis = {"min": vis_cfg["min"], "max": vis_cfg["max"], "palette": vis_cfg["palette"]}
        return image, vis, list(vis_cfg["palette"])
    classified, vis = _classified_index_image(image, vis_cfg, index_id)
    return classified, vis, [item[3] for item in vis_cfg["classes"]]


def _legend_from_index_config(index_id: str, classes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if classes:
        return classes
    return [
        {
            "name": name,
            "label": name,
            "color": color,
            "min": low,
            "max": high,
            "surface_ha": 0.0,
            "pct": 0.0,
        }
        for low, high, name, color in INDEX_VIS_CONFIG[index_id]["classes"]
    ]


def _change_classified_image(delta_image: Any, cfg: dict[str, Any], index_id: str) -> tuple[Any, dict[str, Any]]:
    classified = ee.Image(0).rename(f"{index_id}_CLASS").updateMask(delta_image.mask())
    colors: list[str] = []
    for class_id, (low, high, _name, color) in enumerate(cfg["classes"], start=1):
        mask = delta_image.gte(float(low)).And(delta_image.lt(float(high)))
        classified = classified.where(mask, class_id)
        colors.append(color)
    return classified.toInt(), {"min": 1, "max": len(colors), "palette": colors}


def _analysis_crs(analysis: dict[str, Any] | None) -> str | None:
    spatial_reference = (analysis or {}).get("spatial_reference") or {}
    value = spatial_reference.get("analysis_crs")
    return str(value) if value else None


def _gee_stats_crs_for_analysis(analysis: dict[str, Any] | None) -> str | None:
    """Keep KSA grids in KSA and use the AOI's local UTM grid elsewhere."""
    analysis_crs = _analysis_crs(analysis)
    spatial_reference = (analysis or {}).get("spatial_reference") or {}
    try:
        longitude = float(spatial_reference.get("center_longitude"))
        latitude = float(spatial_reference.get("center_latitude"))
    except (TypeError, ValueError):
        return analysis_crs

    gee_crs = _gee_metric_crs(analysis_crs)
    if not gee_crs or not re.fullmatch(r"EPSG:32[67]\d{2}", gee_crs):
        return analysis_crs
    local_zone = max(1, min(60, int(math.floor((longitude + 180.0) / 6.0)) + 1))
    local_epsg = (32600 if latitude >= 0 else 32700) + local_zone
    selected_epsg = int(gee_crs.split(":")[-1])
    return analysis_crs if selected_epsg == local_epsg else f"EPSG:{local_epsg}"


def _gee_metric_crs(analysis_crs: str | None) -> str | None:
    """Use Earth Engine's accepted WGS84 UTM equivalent for KSA-GRF17 UTM."""
    code = str(analysis_crs) if analysis_crs else None
    if code in {"EPSG:9332", "EPSG:9333"}:
        return None
    return {
        "EPSG:9356": "EPSG:32636",
        "EPSG:9357": "EPSG:32637",
        "EPSG:9358": "EPSG:32638",
        "EPSG:9359": "EPSG:32639",
        "EPSG:9360": "EPSG:32640",
    }.get(code, code)


def _align_change_periods(index_1: Any, index_2: Any, *, analysis_crs: str | None, scale: int) -> tuple[Any, Any]:
    """Give both change periods the same CRS and nominal scale before subtraction."""
    if not analysis_crs:
        return index_1, index_2
    return (
        index_1.setDefaultProjection(crs=_gee_metric_crs(analysis_crs), scale=scale),
        index_2.setDefaultProjection(crs=_gee_metric_crs(analysis_crs), scale=scale),
    )


def _metric_spatial_params(scale: int, analysis_crs: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {"scale": scale}
    if analysis_crs:
        params["crs"] = _gee_metric_crs(analysis_crs)
    return params


def _compute_change_classes(delta_image: Any, classified: Any, geom: Any, cfg: dict[str, Any], surface_ha: int, scale: int, analysis_crs: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    band = delta_image.bandNames().get(0).getInfo()
    for code, (low, high, name, color) in enumerate(cfg["classes"], start=1):
        mask = classified.eq(code)
        area_img = ee.Image.pixelArea().divide(10000).rename("area").updateMask(mask)
        area_raw = area_img.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            **_metric_spatial_params(scale, analysis_crs),
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ).getInfo() or {}
        values_raw = delta_image.updateMask(mask).reduceRegion(
            reducer=ee.Reducer.minMax().combine(reducer2=ee.Reducer.mean(), sharedInputs=True).combine(reducer2=ee.Reducer.count(), sharedInputs=True),
            geometry=geom,
            **_metric_spatial_params(scale, analysis_crs),
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ).getInfo() or {}
        area = round(float(area_raw.get("area") or 0), 2)
        rows.append(
            {
                "code": code,
                "name": name,
                "surface_ha": area,
                "pixels": int(values_raw.get(f"{band}_count", 0) or 0),
                "mean_change": round(float(values_raw.get(f"{band}_mean", 0) or 0), 4),
                "min": round(float(values_raw.get(f"{band}_min", 0) or 0), 4),
                "max": round(float(values_raw.get(f"{band}_max", 0) or 0), 4),
                "color": color,
            }
        )
    total_classified_area = sum(float(item.get("surface_ha") or 0) for item in rows)
    for item in rows:
        area = float(item.get("surface_ha") or 0)
        item["pct"] = round((area / total_classified_area) * 100, 1) if total_classified_area else 0
        item["pct_aoi"] = round((area / surface_ha) * 100, 1) if surface_ha else 0
    return rows


def _same_season_warning(period_1: dict[str, Any], period_2: dict[str, Any]) -> str | None:
    with suppress(Exception):
        m1 = int(str(period_1.get("date_start") or period_1.get("start_date"))[5:7])
        m2 = int(str(period_2.get("date_start") or period_2.get("start_date"))[5:7])
        diff = abs(m1 - m2)
        if min(diff, 12 - diff) > 2:
            return "The selected periods may belong to different seasons. Detected changes can be influenced by seasonality and not only by real land-cover change."
    return None


def _analysis_change_detection_image(
    analysis: dict[str, Any],
    *,
    lazy_mosaic: bool = False,
) -> tuple[Any, Any, dict[str, Any], int, str, Any, Any, dict[str, Any], Any, Any, Any, dict[str, Any] | None, dict[str, Any] | None]:
    analysis = _normalize_payload(analysis)
    if not _ensure_gee():
        raise RuntimeError(_GEE_ERROR or "GEE unavailable")
    index_id = str(analysis.get("index") or "").upper()
    base = _change_base_index(index_id)
    sensor = _sensor_id(analysis)
    if sensor not in {"sentinel-2", "landsat-8-9"}:
        raise ValueError("Change Detection requires Sentinel-2 or Landsat 8/9.")

    period_1_payload = _period_payload(analysis, "period_1")
    period_2_payload = _period_payload(analysis, "period_2")
    mosaic_builder = _build_lazy_analysis_mosaic if lazy_mosaic else _build_analysis_mosaic
    mosaic_1 = mosaic_builder(period_1_payload)
    mosaic_2 = mosaic_builder(period_2_payload)
    geom = mosaic_1["geom"]
    scale = _index_native_scale(base, sensor)
    index_1 = _change_index_image(mosaic_1["image"], base, sensor, geom)
    index_2 = _change_index_image(mosaic_2["image"], base, sensor, geom)
    analysis_crs = _analysis_crs(analysis)
    index_1, index_2 = _align_change_periods(index_1, index_2, analysis_crs=analysis_crs, scale=scale)
    delta = index_2.subtract(index_1).rename(index_id).clip(geom)
    cfg = {
        "min": -1.0,
        "max": 1.0,
        "scale": scale,
        **CHANGE_DETECTION_CONFIG[base],
    }
    classified, vis = _change_classified_image(delta, cfg, index_id)
    quality = {
        "period_1_images_count": mosaic_1.get("images_count"),
        "period_2_images_count": mosaic_2.get("images_count"),
        "period_1": {"start_date": period_1_payload.get("date_start"), "end_date": period_1_payload.get("date_end")},
        "period_2": {"start_date": period_2_payload.get("date_start"), "end_date": period_2_payload.get("date_end")},
        "period_1_mosaic": _mosaic_quality_payload(mosaic_1),
        "period_2_mosaic": _mosaic_quality_payload(mosaic_2),
        "cloud_max": analysis.get("max_cloud_pct"),
        "sensor": sensor,
        "method": f"Delta {base} = {base} period 2 - {base} period 1 from the validated {base} pipeline",
        "period_layer_method": f"Period 1 and Period 2 reuse the validated {base} map, legend and statistics",
        "warning": _same_season_warning(period_1_payload, period_2_payload),
        "native_resolution_m": scale,
    }
    if not lazy_mosaic and (int(mosaic_1.get("images_count") or 0) < 2 or int(mosaic_2.get("images_count") or 0) < 2):
        low_count_warning = "One of the selected periods contains very few images. Review date range, AOI, or cloud threshold."
        quality["warning"] = " ".join([item for item in [quality.get("warning"), low_count_warning] if item])
    return (
        classified,
        geom,
        vis,
        scale,
        base,
        delta,
        mosaic_2["image"],
        quality,
        index_1,
        index_2,
        mosaic_1["image"],
        None,
        None,
    )


def _change_period_layer(
    *,
    key: str,
    index_key: str,
    title: str,
    topic: str,
    period: dict[str, Any],
    image: Any,
    geom: Any,
    surface_ha: int,
    scale: int,
    sensor: str,
    source_image: Any | None = None,
    analysis_crs: str | None = None,
    built_context: dict[str, Any] | None = None,
    include_summary: bool = True,
    include_tiles: bool = True,
    layer_mode: str = "index",
) -> dict[str, Any]:
    cfg = dict(INDEX_VIS_CONFIG[index_key])
    cfg["bands"] = _index_bands_for_sensor(index_key, sensor)
    if layer_mode == "built" and index_key == "NDBI":
        if source_image is None:
            raise ValueError("The source mosaic is required for an NDBI built-up period layer.")
        period_analysis = {
            "date_start": period.get("start_date") or period.get("date_start"),
            "date_end": period.get("end_date") or period.get("date_end"),
        }
        built = built_context or _ndbi_built_detection_context(
            period_analysis, source_image, image, sensor, geom
        )
        tile_image = built["classified"]
        vis = built["vis"]
        built_cfg = built["cfg"]
        if include_summary:
            classes = _compute_ndbi_classes(
                image,
                built["ndvi"],
                built["ndwi"],
                built["bsi"],
                geom,
                built_cfg,
                surface_ha,
                scale=scale,
                analysis_crs=analysis_crs,
                built_probability_image=built["built_probability"],
                bare_probability_image=built["bare_probability"],
                stable_built_reference=built["stable_built_reference"],
                historical_built_surface=built["historical_built_surface"],
            )
            built_surface_ha = round(sum(float(item.get("surface_ha") or 0) for item in classes[1:]), 2)
            stats = {
                **_compute_stats(image, index_key, geom, surface_ha, scale=scale, analysis_crs=analysis_crs),
                "built_surface_ha": built_surface_ha,
                "built_pct": round((built_surface_ha / surface_ha) * 100, 1) if surface_ha else 0,
            }
            histogram = [
                {"bin": item["name"], "count": int(round(float(item.get("surface_ha") or 0) * 100))}
                for item in classes
            ]
        else:
            stats = {"surface_ha": surface_ha, "statistics_deferred": True}
            histogram = []
            classes = []
        palette = built_cfg["palette"]
        visualization = "Optional built-up interpretation; not the scientific Change Detection source."
    else:
        tile_image, vis, palette = _base_index_tile(index_key, image, cfg)
        if include_summary:
            stats, histogram, classes = _compute_index_summary(
                image,
                index_key,
                geom,
                cfg,
                surface_ha,
                scale=scale,
                analysis_crs=analysis_crs,
            )
        else:
            stats = {"surface_ha": surface_ha, "statistics_deferred": True}
            histogram = []
            classes = _legend_from_index_config(index_key)
        visualization = f"Same validated {index_key} visualization as the simple {index_key} analysis."
    legend = _legend_from_index_config(index_key, classes)
    return {
        "key": key,
        "index": index_key,
        "title": title,
        "topic": topic,
        "period": period,
        "stats": stats,
        "histogram": histogram,
        "classes": classes or legend,
        "legend": legend,
        "palette": palette,
        "tiles": {
            "index_tile_url": _tile_url(tile_image, vis) if include_tiles else None,
            "rgb_tile_url": None,
        },
        "metadata": {
            "formula": cfg["formula"],
            "bands": cfg["bands"],
            "visualization": visualization,
            "min": cfg.get("min"),
            "max": cfg.get("max"),
            "layer_mode": layer_mode,
        },
    }


def _change_delta_layer(
    *,
    key: str,
    index_key: str,
    title: str,
    topic: str,
    period_1: dict[str, Any],
    period_2: dict[str, Any],
    stats: dict[str, Any],
    histogram: list[dict[str, Any]],
    classes: list[dict[str, Any]],
    tiles: dict[str, Any],
    palette: list[str],
) -> dict[str, Any]:
    return {
        "key": key,
        "index": index_key,
        "title": title,
        "topic": topic,
        "period_1": period_1,
        "period_2": period_2,
        "stats": stats,
        "histogram": histogram,
        "classes": classes,
        "legend": classes,
        "palette": palette,
        "tiles": {
            "index_tile_url": tiles.get("index_tile_url"),
            "rgb_tile_url": tiles.get("rgb_tile_url"),
        },
        "metadata": {
            "formula": (
                f"Delta {index_key.replace('CHANGE_', '')} = {index_key.replace('CHANGE_', '')} period 2 - {index_key.replace('CHANGE_', '')} period 1"
            ),
            "visualization": "Change-specific classified map of P2 minus P1. Period layers keep the base index visualization.",
        },
    }


def _deferred_change_classes(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "code": code,
            "name": name,
            "label": name,
            "surface_ha": 0.0,
            "pct": 0.0,
            "pct_aoi": 0.0,
            "pixels": 0,
            "mean_change": None,
            "min": low,
            "max": high,
            "color": color,
            "deferred": True,
        }
        for code, (low, high, name, color) in enumerate(cfg.get("classes", []), start=1)
    ]


def _change_topics(index_id: str) -> tuple[str, str]:
    if index_id == "CHANGE_NDVI":
        return "Vegetation", "Vegetation Change"
    if index_id == "CHANGE_NDWI":
        return "Water / Moisture", "Water / Moisture Change"
    if index_id == "CHANGE_NDBI":
        return "Built-up / Artificialization", "Built-up Change"
    if index_id == "CHANGE_BSI":
        return "Bare soil exposure", "Bare soil exposure change"
    return "Vegetation cover", "Vegetation cover change"


def _fast_change_detection_result(analysis: dict[str, Any], surface_ha: int) -> dict[str, Any]:
    """Return Change Detection tiles first, then let statistics run separately."""
    started = time.perf_counter()
    analysis = _normalize_payload(analysis)
    index_id = str(analysis.get("index") or "").upper()
    (
        classified,
        geom,
        vis,
        scale,
        base,
        _delta,
        mosaic_2_image,
        quality,
        index_1,
        index_2,
        mosaic_1_image,
        _period_1_built_context,
        _period_2_built_context,
    ) = _analysis_change_detection_image(analysis, lazy_mosaic=True)
    analysis_crs = _analysis_crs(analysis)
    native_scale = scale
    output_scale = _effective_output_resolution_m(analysis, native_scale)
    policy = surface_policy(surface_ha / 100.0, output_scale)
    reduction_scale = int(policy["statistics_scale_m"])
    change_cfg = {"min": -1.0, "max": 1.0, **CHANGE_DETECTION_CONFIG[base]}
    classes = _deferred_change_classes(change_cfg)
    stats = {
        "surface_ha": surface_ha,
        "classes_count": len(classes),
        "period_1": quality["period_1"],
        "period_2": quality["period_2"],
        **_resolution_contract(analysis, native_scale, reduction_scale),
        "processing_policy": policy,
        "statistics_status": "deferred_for_first_map",
        "first_map_tile_priority": True,
    }
    mapid_started = time.perf_counter()
    tiles = {
        "rgb_tile_url": None,
        "index_tile_url": _tile_url(classified, vis),
    }
    _perf_log("gee_mapid_ms", (time.perf_counter() - mapid_started) * 1000, index=index_id, mode="fast_change")

    comparison_layers: list[dict[str, Any]] = []
    if index_id in {"CHANGE_NDVI", "CHANGE_NDWI", "CHANGE_NDBI", "CHANGE_BSI", "CHANGE_SAVI"}:
        base_topic, change_topic = _change_topics(index_id)
        base_key_lower = base.lower()
        sensor = _sensor_id(analysis)
        comparison_layers = [
            _change_period_layer(
                key=f"{base_key_lower}_period_1",
                index_key=base,
                title=f"{base} - Period 1",
                topic=base_topic,
                period=quality["period_1"],
                image=index_1,
                geom=geom,
                surface_ha=surface_ha,
                scale=reduction_scale,
                sensor=sensor,
                source_image=mosaic_1_image,
                analysis_crs=analysis_crs,
                include_summary=False,
                include_tiles=False,
            ),
            _change_period_layer(
                key=f"{base_key_lower}_period_2",
                index_key=base,
                title=f"{base} - Period 2",
                topic=base_topic,
                period=quality["period_2"],
                image=index_2,
                geom=geom,
                surface_ha=surface_ha,
                scale=reduction_scale,
                sensor=sensor,
                source_image=mosaic_2_image,
                analysis_crs=analysis_crs,
                include_summary=False,
                include_tiles=False,
            ),
            _change_delta_layer(
                key=f"{base_key_lower}_change",
                index_key=index_id,
                title=f"{base} Change - Period 2 minus Period 1",
                topic=change_topic,
                period_1=quality["period_1"],
                period_2=quality["period_2"],
                stats=stats,
                histogram=[],
                classes=classes,
                tiles=tiles,
                palette=vis["palette"],
            ),
        ]

    quality = {
        **quality,
        "statistics_status": "deferred_for_first_map",
        "first_map_tile_priority": True,
        "warning": "Change map tiles are returned first; exact P1/P2/Delta statistics continue in the background.",
    }
    result = {
        "analysis_type": f"change_detection_{base.lower()}",
        "stats": stats,
        "histogram": [],
        "classes": classes,
        "palette": vis["palette"],
        "tiles": tiles,
        "comparison_layers": comparison_layers,
        "active_comparison_layer": f"{base.lower()}_change" if comparison_layers else None,
        "mosaic": quality,
        "quality_summary": quality,
        "interpretation": CHANGE_DETECTION_CONFIG[base]["interpretation"],
        "mode": "gee",
        "gee": gee_status(),
        "performance": {
            "strategy": "gee_change_lazy_tiles_first",
            "stats_deferred": True,
            "first_response_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }
    _perf_log("first_response_ms", result["performance"]["first_response_ms"], index=index_id, mode="fast_change")
    return result


def compute_change_detection_index(
    analysis: dict[str, Any],
    surface_ha: int,
    *,
    first_map_priority: bool = False,
) -> dict[str, Any]:
    analysis = _normalize_payload(analysis)
    index_id = str(analysis.get("index") or "").upper()
    base = _change_base_index(index_id)
    if not _ensure_gee():
        result = compute_mock_index(index_id, surface_ha=surface_ha)
        result["tiles"] = {"rgb_tile_url": None, "index_tile_url": None}
        result["mode"] = "mock"
        result["gee"] = gee_status()
        return result
    if first_map_priority:
        return _fast_change_detection_result(analysis, surface_ha)

    (
        classified,
        geom,
        vis,
        scale,
        base,
        delta,
        mosaic_2_image,
        quality,
        index_1,
        index_2,
        mosaic_1_image,
        _period_1_built_context,
        _period_2_built_context,
    ) = _analysis_change_detection_image(analysis)
    analysis_crs = _analysis_crs(analysis)
    native_scale = scale
    output_scale = _effective_output_resolution_m(analysis, native_scale)
    policy = surface_policy(surface_ha / 100.0, output_scale)
    reduction_scale = int(policy["statistics_scale_m"])
    change_cfg = {"min": -1.0, "max": 1.0, **CHANGE_DETECTION_CONFIG[base]}
    stats, histogram, classes = _compute_change_summary(
        delta,
        classified,
        index_id,
        geom,
        change_cfg,
        surface_ha,
        reduction_scale,
        analysis_crs,
    )
    stats.update(_resolution_contract(analysis, native_scale, reduction_scale))
    stats["processing_policy"] = policy
    tiles = {
        "rgb_tile_url": _tile_url(mosaic_2_image.clip(geom), _analysis_rgb_vis_for_sensor(_sensor_id(analysis))),
        "index_tile_url": _tile_url(classified, vis),
    }
    comparison_layers = []
    if index_id in {"CHANGE_NDVI", "CHANGE_NDWI", "CHANGE_NDBI", "CHANGE_BSI", "CHANGE_SAVI"}:
        if index_id == "CHANGE_NDVI":
            base_topic = "Vegetation"
            change_topic = "Vegetation Change"
        elif index_id == "CHANGE_NDWI":
            base_topic = "Water / Moisture"
            change_topic = "Water / Moisture Change"
        elif index_id == "CHANGE_NDBI":
            base_topic = "Built-up / Artificialization"
            change_topic = "Built-up Change"
        elif index_id == "CHANGE_BSI":
            base_topic = "Bare soil exposure"
            change_topic = "Bare soil exposure change"
        else:
            base_topic = "Vegetation cover"
            change_topic = "Vegetation cover change"
        base_index_key = base
        base_key_lower = base.lower()
        sensor = _sensor_id(analysis)
        comparison_layers = [
            _change_period_layer(
                key=f"{base_key_lower}_period_1",
                index_key=base_index_key,
                title=f"{base} - Period 1",
                topic=base_topic,
                period=quality["period_1"],
                image=index_1,
                geom=geom,
                surface_ha=surface_ha,
                scale=reduction_scale,
                sensor=sensor,
                source_image=mosaic_1_image,
                analysis_crs=analysis_crs,
                include_summary=True,
            ),
            _change_period_layer(
                key=f"{base_key_lower}_period_2",
                index_key=base_index_key,
                title=f"{base} - Period 2",
                topic=base_topic,
                period=quality["period_2"],
                image=index_2,
                geom=geom,
                surface_ha=surface_ha,
                scale=reduction_scale,
                sensor=sensor,
                source_image=mosaic_2_image,
                analysis_crs=analysis_crs,
                include_summary=True,
            ),
            _change_delta_layer(
                key=f"{base_key_lower}_change",
                index_key=index_id,
                title=f"{base} Change - Period 2 minus Period 1",
                topic=change_topic,
                period_1=quality["period_1"],
                period_2=quality["period_2"],
                stats=stats,
                histogram=histogram,
                classes=classes,
                tiles=tiles,
                palette=vis["palette"],
            ),
        ]
    return {
        "analysis_type": f"change_detection_{base.lower()}",
        "stats": {
            **stats,
            "classes_count": len(classes),
            "period_1": quality["period_1"],
            "period_2": quality["period_2"],
        },
        "histogram": histogram,
        "classes": classes,
        "palette": vis["palette"],
        "tiles": tiles,
        "comparison_layers": comparison_layers,
        "active_comparison_layer": f"{base.lower()}_change" if comparison_layers else None,
        "mosaic": quality,
        "quality_summary": quality,
        "interpretation": CHANGE_DETECTION_CONFIG[base]["interpretation"],
        "mode": "gee",
        "gee": gee_status(),
    }


def _osi_sar_log(**fields: Any) -> None:
    parts = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    print(f"[OSI-SAR] {parts}", flush=True)


def osi_sar_suspicion_class(
    *,
    vv_db: float,
    vh_db: float,
    contrast_db: float,
    water: bool = True,
    angle_ok: bool = True,
    connected_pixels: int = 8,
    vv_dark_threshold_db: float = OSI_SAR_REFERENCE["vv_dark_threshold_db"],
    vh_dark_threshold_db: float = OSI_SAR_REFERENCE["vh_dark_threshold_db"],
    contrast_threshold_db: float = OSI_SAR_REFERENCE["contrast_threshold_db"],
    min_connected_pixels: int = OSI_SAR_REFERENCE["min_connected_pixels"],
    high_vv_db: float = OSI_SAR_REFERENCE["high_vv_db"],
    high_vh_db: float = OSI_SAR_REFERENCE["high_vh_db"],
    high_contrast_db: float = OSI_SAR_REFERENCE["high_contrast_db"],
    medium_vv_db: float = OSI_SAR_REFERENCE["medium_vv_db"],
    medium_contrast_db: float = OSI_SAR_REFERENCE["medium_contrast_db"],
) -> int:
    candidate = (
        vv_db < vv_dark_threshold_db
        and vh_db < vh_dark_threshold_db
        and contrast_db >= contrast_threshold_db
        and bool(water)
        and bool(angle_ok)
        and int(connected_pixels) >= int(min_connected_pixels)
    )
    if not candidate:
        return 0
    if vv_db < high_vv_db and vh_db < high_vh_db and contrast_db >= high_contrast_db:
        return 3
    if vv_db < medium_vv_db or contrast_db >= medium_contrast_db:
        return 2
    return 1


def _osi_sar_options(analysis: dict[str, Any]) -> dict[str, Any]:
    options = dict(analysis.get("osi_sar_options") or {})
    orbit_pass = str(options.get("orbit_pass") or "ANY").upper()
    if orbit_pass not in {"ANY", "ASCENDING", "DESCENDING"}:
        orbit_pass = "ANY"
    if options.get("min_connected_pixels") is not None:
        min_connected_pixels = max(1, int(options.get("min_connected_pixels")))
    elif options.get("min_patch_ha") is not None:
        min_connected_pixels = max(1, int((float(options.get("min_patch_ha")) * 10000) / 100))
    else:
        min_connected_pixels = int(OSI_SAR_REFERENCE["min_connected_pixels"])
    return {
        "dark_threshold_db": float(options.get("dark_threshold_db", OSI_SAR_REFERENCE["vv_dark_threshold_db"])),
        "vh_dark_threshold_db": float(options.get("vh_dark_threshold_db", OSI_SAR_REFERENCE["vh_dark_threshold_db"])),
        "contrast_threshold_db": float(options.get("contrast_threshold_db", OSI_SAR_REFERENCE["contrast_threshold_db"])),
        "contrast_radius_m": int(options.get("contrast_radius_m", OSI_SAR_REFERENCE["contrast_radius_m"])),
        "speckle_radius_m": int(options.get("speckle_radius_m", OSI_SAR_REFERENCE["speckle_radius_m"])),
        "min_connected_pixels": min_connected_pixels,
        "min_patch_ha": float(options.get("min_patch_ha", round((min_connected_pixels * 100) / 10000, 4))),
        "water_mask": bool(options.get("water_mask", True)),
        "water_occurrence_threshold": int(options.get("water_occurrence_threshold", OSI_SAR_REFERENCE["water_occurrence_threshold"])),
        "coast_buffer_m": int(options.get("coast_buffer_m", OSI_SAR_REFERENCE["coast_buffer_m"])),
        "angle_min_deg": float(options.get("angle_min_deg", OSI_SAR_REFERENCE["angle_min_deg"])),
        "angle_max_deg": float(options.get("angle_max_deg", OSI_SAR_REFERENCE["angle_max_deg"])),
        "orbit_pass": orbit_pass,
        "wind_validation": bool(options.get("wind_validation", True)),
        "wind_min_m_s": float(options.get("wind_min_m_s", 2.0)),
        "wind_max_m_s": float(options.get("wind_max_m_s", 10.0)),
        "sentinel2_validation": bool(options.get("sentinel2_validation", False)),
        "stats_scale_m": int(options.get("stats_scale_m", 30)),
        "scene_id": str(options.get("scene_id") or "").strip() or None,
        "acquisition_timestamp": options.get("acquisition_timestamp"),
        "scene_orbit_pass": options.get("scene_orbit_pass"),
        "relative_orbit": options.get("relative_orbit"),
        "platform": options.get("platform"),
        "available_images": int(options.get("available_images") or 0),
        "gee_strict_validation": bool(options.get("gee_strict_validation", True)),
        "high_vv_db": float(options.get("high_vv_db", OSI_SAR_REFERENCE["high_vv_db"])),
        "high_vh_db": float(options.get("high_vh_db", OSI_SAR_REFERENCE["high_vh_db"])),
        "high_contrast_db": float(options.get("high_contrast_db", OSI_SAR_REFERENCE["high_contrast_db"])),
        "medium_vv_db": float(options.get("medium_vv_db", OSI_SAR_REFERENCE["medium_vv_db"])),
        "medium_contrast_db": float(options.get("medium_contrast_db", OSI_SAR_REFERENCE["medium_contrast_db"])),
        "water_mask_version": OSI_SAR_WATER_MASK_VERSION,
        "angle_mask_version": OSI_SAR_ANGLE_MASK_VERSION,
        "processing_logic": "AND",
    }


def _sentinel1_asset_id(image_id: str | None) -> str | None:
    raw = str(image_id or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered.startswith("sentinel-1-sar-") or "_mosaic_" in lowered or lowered.startswith("sentinel-1_mosaic"):
        return None
    if raw.startswith(SENTINEL1_COLLECTION):
        return raw
    if raw.startswith("S1") and "_IW_" in raw:
        return f"{SENTINEL1_COLLECTION}/{raw}"
    return None


def _build_osi_sar_collection(analysis: dict[str, Any], geom: Any, options: dict[str, Any]) -> Any:
    collection = (
        ee.ImageCollection(SENTINEL1_COLLECTION)
        .filterBounds(geom)
        .filterDate(analysis.get("date_start"), _gee_end_date(analysis))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("resolution_meters", OSI_SAR_REFERENCE["resolution_meters"]))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )
    if options["orbit_pass"] != "ANY":
        collection = collection.filter(ee.Filter.eq("orbitProperties_pass", options["orbit_pass"]))
    return collection


def _osi_sar_water_mask(geom: Any, options: dict[str, Any]) -> Any:
    if not options["water_mask"]:
        return ee.Image(1).clip(geom).rename("water_mask")
    worldcover = ee.ImageCollection(ESA_WORLDCOVER_COLLECTION).first().select("Map")
    water = worldcover.eq(80)
    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    gsw_defined = occurrence.mask()
    gsw_water = occurrence.gte(options["water_occurrence_threshold"])
    water = water.And(gsw_defined.Not().Or(gsw_water))
    buffer_m = max(0, int(options.get("coast_buffer_m") or 0))
    if buffer_m > 0:
        water = water.focal_min(radius=buffer_m, units="meters")
    return water.clip(geom).rename("water_mask")


def _osi_sar_scene_metadata(image: Any) -> dict[str, Any]:
    info = image.getInfo() or {}
    props = info.get("properties") or {}
    image_id = image.id().getInfo()
    gee_id = image_id if "/" in str(image_id) else f"{SENTINEL1_COLLECTION}/{image_id}"
    time_start = props.get("system:time_start")
    relative_orbit = props.get("relativeOrbitNumber_start")
    if relative_orbit is None:
        relative_orbit = props.get("relativeOrbitNumber_stop")
    platform = props.get("platform_number")
    if not platform:
        prefix = str(image_id or "").split("_", 1)[0]
        platform = prefix.replace("COPERNICUS/S1_GRD/", "") if prefix else None
    return {
        "scene_id": gee_id,
        "system_index": props.get("system:index") or str(image_id).split("/")[-1],
        "acquisition_timestamp": time_start,
        "acquisition_date": _format_date(time_start),
        "orbit_pass": props.get("orbitProperties_pass"),
        "relative_orbit": relative_orbit,
        "platform": platform,
        "satellite": f"Sentinel-1{platform}" if platform and not str(platform).startswith("Sentinel") else (platform or "Sentinel-1"),
    }


def _resolve_osi_sar_scene(analysis: dict[str, Any], geom: Any, options: dict[str, Any]) -> tuple[Any, int, dict[str, Any]]:
    collection = _build_osi_sar_collection(analysis, geom, options)
    image_count = int(collection.size().getInfo() or 0)
    requested = _sentinel1_asset_id(options.get("scene_id") or analysis.get("image_id"))
    if requested:
        image = ee.Image(requested)
    else:
        if image_count <= 0:
            raise ValueError("No Sentinel-1 VV/VH IW scenes found for this AOI and period.")
        image = collection.sort("system:time_start", False).first()
    metadata = _osi_sar_scene_metadata(image)
    _osi_sar_log(
        collection_count=image_count,
        selected_scene_id=metadata.get("scene_id"),
        acquisition_date=metadata.get("acquisition_date"),
        platform=metadata.get("platform") or metadata.get("satellite"),
        orbit_pass=metadata.get("orbit_pass"),
        relative_orbit=metadata.get("relative_orbit"),
    )
    if not metadata.get("acquisition_date") or not metadata.get("orbit_pass"):
        raise ValueError("The selected Sentinel-1 scene has no acquisition metadata. OSI-SAR cannot use a mosaic.")
    return image.clip(geom), max(image_count, 1), metadata


def prepare_osi_sar_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(analysis)
    if not _ensure_gee():
        return prepared
    geom = _aoi_geometry(prepared.get("aoi") or {})
    options = _osi_sar_options(prepared)
    _image, image_count, metadata = _resolve_osi_sar_scene(prepared, geom, options)
    prepared["osi_sar_options"] = {
        **(prepared.get("osi_sar_options") or {}),
        "scene_id": metadata["scene_id"],
        "acquisition_timestamp": metadata.get("acquisition_timestamp"),
        "scene_orbit_pass": metadata.get("orbit_pass"),
        "relative_orbit": metadata.get("relative_orbit"),
        "platform": metadata.get("platform") or metadata.get("satellite"),
        "available_images": image_count,
        "water_mask_version": OSI_SAR_WATER_MASK_VERSION,
        "angle_mask_version": OSI_SAR_ANGLE_MASK_VERSION,
        "processing_logic": "AND",
        "gee_strict_validation": options.get("gee_strict_validation", True),
    }
    prepared["image_id"] = metadata["scene_id"]
    prepared["image_method"] = "single_scene"
    return prepared


def _analysis_osi_sar_image(analysis: dict[str, Any]) -> tuple[Any, Any, dict[str, Any], int, dict[str, Any]]:
    analysis = _normalize_payload(analysis)
    if not _ensure_gee():
        raise RuntimeError(_GEE_ERROR or "GEE unavailable")

    geom = _aoi_geometry(analysis.get("aoi") or {})
    options = _osi_sar_options(analysis)
    source, image_count, scene = _resolve_osi_sar_scene(analysis, geom, options)
    source = source.select(["VV", "VH", "angle"])
    speckle_radius = max(0, int(options["speckle_radius_m"]))
    contrast_radius = max(60, int(options["contrast_radius_m"]))
    vv = source.select("VV")
    vh = source.select("VH")
    if speckle_radius > 0:
        vv = vv.focal_median(radius=speckle_radius, units="meters")
        vh = vh.focal_median(radius=speckle_radius, units="meters")
    vv = vv.rename("VV")
    vh = vh.rename("VH")
    angle = source.select("angle")
    angle_mask = angle.gt(options["angle_min_deg"]).And(angle.lt(options["angle_max_deg"])).rename("angle_mask")
    water_mask = _osi_sar_water_mask(geom, options)
    valid_mask = water_mask.And(angle_mask).rename("valid_marine_mask")
    local_mean = vv.focal_mean(radius=contrast_radius, kernelType="circle", units="meters")
    contrast = local_mean.subtract(vv).rename("local_contrast_db")
    osi_raw = (
        vv.lt(options["dark_threshold_db"])
        .And(vh.lt(options["vh_dark_threshold_db"]))
        .And(contrast.gte(options["contrast_threshold_db"]))
        .And(valid_mask)
        .rename("OSI_RAW")
    )
    connected_pixels = osi_raw.selfMask().connectedPixelCount(OSI_SAR_CONNECTED_PIXEL_MAX, True)
    candidate = osi_raw.And(connected_pixels.unmask(0).gte(options["min_connected_pixels"])).rename("OSI_CANDIDATE")
    strict = bool(options.get("gee_strict_validation", True))
    if strict:
        classified = ee.Image(0).rename("OSI_SAR_CLASS").where(candidate, 1).updateMask(valid_mask).clip(geom).toInt()
        vis = dict(OSI_SAR_STRICT_VIS)
    else:
        classified = ee.Image(0).rename("OSI_SAR_CLASS")
        classified = classified.where(candidate, 1)
        medium = candidate.And(vv.lt(options["medium_vv_db"]).Or(contrast.gte(options["medium_contrast_db"])))
        classified = classified.where(medium, 2)
        high = candidate.And(vv.lt(options["high_vv_db"])).And(vh.lt(options["high_vh_db"])).And(contrast.gte(options["high_contrast_db"]))
        classified = classified.where(high, 3).updateMask(valid_mask).clip(geom).toInt()
        vis = dict(OSI_SAR_VIS)
    _osi_sar_log(
        vv_threshold=options["dark_threshold_db"],
        vh_threshold=options["vh_dark_threshold_db"],
        contrast_threshold=options["contrast_threshold_db"],
        local_radius=contrast_radius,
        min_connected_pixels=options["min_connected_pixels"],
        gee_strict_validation=strict,
        logic="AND",
    )
    return classified, geom, vis, 10, {
        "image_count": image_count,
        "scene": scene,
        "vv": vv,
        "vh": vh,
        "contrast": contrast,
        "candidate": candidate,
        "osi_raw": osi_raw,
        "water_mask": water_mask,
        "angle_mask": angle_mask,
        "valid_mask": valid_mask,
        "min_connected_pixels": options["min_connected_pixels"],
        "options": options,
        "selection_mode": "single_scene",
        "strict": strict,
        "vis": vis,
    }


def _osi_sar_visual_layer(classified: Any, geom: Any, vis: dict[str, Any], meta: dict[str, Any], layer_key: str | None = None) -> tuple[Any, dict[str, Any]]:
    vv_vis = {"min": -25, "max": 0, "palette": ["#050505", "#e5e7eb"]}
    contrast_vis = {"min": 0, "max": 6, "palette": ["#ffffcc", "#fd8d3c", "#800026"]}
    raw_vis = {"min": 0, "max": 1, "palette": ["#000000", "#d7191c"]}
    valid = meta["valid_mask"]
    if layer_key == "osi_vv":
        return meta["vv"].updateMask(valid).clip(geom), vv_vis
    if layer_key == "osi_vh":
        return meta["vh"].updateMask(valid).clip(geom), vv_vis
    if layer_key == "osi_contrast":
        return meta["contrast"].updateMask(valid).clip(geom), contrast_vis
    if layer_key == "osi_raw_candidates":
        return meta["osi_raw"].selfMask().clip(geom), raw_vis
    return classified, vis


def _osi_sar_wind_context(analysis: dict[str, Any], geom: Any, options: dict[str, Any], scale: int, scene_time_ms: Any | None = None) -> dict[str, Any]:
    if not options["wind_validation"]:
        return {"enabled": False}
    date_filter_start = analysis.get("date_start")
    date_filter_end = _gee_end_date(analysis)
    if scene_time_ms:
        scene_date = ee.Date(int(scene_time_ms))
        date_filter_start = scene_date
        date_filter_end = scene_date.advance(1, "day")
    for collection_id in ("ECMWF/ERA5_LAND/DAILY_AGGR", "ECMWF/ERA5/DAILY"):
        try:
            wind = (
                ee.ImageCollection(collection_id)
                .filterBounds(geom)
                .filterDate(date_filter_start, date_filter_end)
                .select(["u_component_of_wind_10m", "v_component_of_wind_10m"])
                .mean()
            )
            speed = wind.expression(
                "sqrt((u * u) + (v * v))",
                {"u": wind.select("u_component_of_wind_10m"), "v": wind.select("v_component_of_wind_10m")},
            ).rename("wind_speed_m_s")
            raw = speed.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=max(scale, 1000),
                bestEffort=True,
                maxPixels=1e8,
                tileScale=4,
            ).getInfo() or {}
            mean_wind = raw.get("wind_speed_m_s")
            if mean_wind is None:
                continue
            value = round(float(mean_wind), 2)
            is_calm = value < OSI_SAR_CALM_WIND_MS
            in_configured_range = options["wind_min_m_s"] <= value <= options["wind_max_m_s"]
            if is_calm:
                status = "low_wind_high_false_positive_risk"
                confidence = "low"
                warning = OSI_SAR_LOW_WIND_WARNING
            elif not in_configured_range:
                status = "outside_optimal_range"
                confidence = "low"
                warning = f"ERA5 mean wind is {value} m/s, outside the configured reliable range."
            else:
                status = "optimal"
                confidence = "moderate"
                warning = None
            return {
                "enabled": True,
                "collection": collection_id,
                "mean_wind_m_s": value,
                "min_m_s": options["wind_min_m_s"],
                "max_m_s": options["wind_max_m_s"],
                "is_optimal": status == "optimal",
                "status": status,
                "confidence": confidence,
                "warning": warning,
                "calm_wind_m_s": OSI_SAR_CALM_WIND_MS,
            }
        except Exception:
            continue
    return {"enabled": True, "status": "unavailable", "warning": "ERA5 wind context could not be computed for this AOI and period."}


def _osi_sar_sentinel2_context(analysis: dict[str, Any], geom: Any) -> dict[str, Any]:
    try:
        count = (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(geom)
            .filterDate(analysis.get("date_start"), _gee_end_date(analysis))
            .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", int(analysis.get("max_cloud_pct", 20))))
            .size()
            .getInfo()
        )
        return {
            "enabled": True,
            "collection": S2_COLLECTION,
            "available_images": int(count or 0),
            "status": "available" if int(count or 0) > 0 else "no_clear_scene",
        }
    except Exception as exc:
        return {"enabled": True, "status": "unavailable", "warning": str(exc)}


def _osi_sar_mask_area_ha(mask: Any, geom: Any, scale: int) -> float:
    raw = (
        ee.Image.pixelArea()
        .divide(10000)
        .rename("area")
        .updateMask(mask)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            scale=scale,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        )
        .getInfo()
        or {}
    )
    return round(float(raw.get("area") or 0), 2)


def compute_osi_sar_index(analysis: dict[str, Any], surface_ha: int) -> dict[str, Any]:
    """Detect oil-spill suspects from one Sentinel-1 IW VV/VH acquisition."""
    analysis = _normalize_payload({**analysis, "sensor": "sentinel-1", "source": "S1_GRD", "index": OSI_SAR_ID})
    if not _ensure_gee():
        result = compute_mock_index(OSI_SAR_ID, surface_ha=surface_ha)
        result["tiles"] = {"rgb_tile_url": None, "index_tile_url": None}
        result["mode"] = "mock"
        result["gee"] = gee_status()
        return result

    classified, geom, vis, scale, meta = _analysis_osi_sar_image(analysis)
    options = meta["options"]
    scene = meta.get("scene") or {}
    strict = bool(meta.get("strict", True))
    class_defs = OSI_SAR_STRICT_CLASSES if strict else OSI_SAR_CLASSES
    policy = surface_policy(surface_ha / 100.0, scale)
    stats_scale = max(scale, int(options.get("stats_scale_m") or 30), int(policy["statistics_scale_m"]))
    classes = _compute_categorical_classes_grouped(classified, geom, surface_ha, class_defs, scale=stats_scale, analysis_crs=_analysis_crs(analysis))
    water_surface_ha = round(sum(float(item.get("surface_ha") or 0) for item in classes), 2)
    pct_denominator = water_surface_ha or surface_ha
    for item in classes:
        item["pct"] = round((float(item.get("surface_ha") or 0) / pct_denominator) * 100, 1) if pct_denominator else 0
    suspect_surface = round(sum(float(item.get("surface_ha") or 0) for item in classes if int(item.get("code") or 0) > 0), 2)
    count_summary = ee.Dictionary({
        "raw": meta["osi_raw"].rename("OSI_RAW").selfMask().reduceRegion(ee.Reducer.count(), geom, stats_scale, bestEffort=True, maxPixels=1e8, tileScale=4),
        "clean": meta["candidate"].rename("OSI_CANDIDATE").selfMask().reduceRegion(ee.Reducer.count(), geom, stats_scale, bestEffort=True, maxPixels=1e8, tileScale=4),
        "stats": ee.Image.cat([meta["vv"], meta["vh"], meta["contrast"]]).updateMask(meta["valid_mask"]).reduceRegion(ee.Reducer.mean(), geom, stats_scale, bestEffort=True, maxPixels=1e8, tileScale=4),
    }).getInfo() or {}
    raw_count = int((count_summary.get("raw") or {}).get("OSI_RAW") or 0)
    clean_count = int((count_summary.get("clean") or {}).get("OSI_CANDIDATE") or 0)
    raw_stats = count_summary.get("stats") or {}
    _osi_sar_log(raw_candidate_pixels=raw_count, cleaned_candidate_pixels=clean_count, suspect_area_km2=round(suspect_surface / 100.0, 4))
    wind_context = _osi_sar_wind_context(analysis, geom, options, stats_scale, scene.get("acquisition_timestamp"))
    sentinel2_context = _osi_sar_sentinel2_context(analysis, geom) if options["sentinel2_validation"] else {"enabled": False}
    warnings = [
        "OSI-SAR is a dark-target suspect detector over water, not a confirmed oil-spill product.",
        "Detection uses one Sentinel-1 IW VV/VH acquisition with VV < -18 dB AND VH < -25 dB AND local contrast >= 2.5 dB.",
    ]
    if wind_context.get("warning"):
        warnings.append(str(wind_context["warning"]))
    quality = {
        "collection": SENTINEL1_COLLECTION,
        "available_images": meta["image_count"],
        "images_count": 1,
        "selection_mode": "single_scene",
        "scene_id": scene.get("scene_id"),
        "acquisition_date": scene.get("acquisition_date"),
        "satellite": scene.get("satellite") or scene.get("platform") or "Sentinel-1",
        "orbit_pass": scene.get("orbit_pass"),
        "relative_orbit": scene.get("relative_orbit"),
        "instrument_mode": "IW",
        "polarizations": "VV,VH",
        "resolution_meters": 10,
        "units": "dB",
        "logic": "AND",
        "gee_strict_validation": strict,
        "dark_threshold_db": options["dark_threshold_db"],
        "vh_dark_threshold_db": options["vh_dark_threshold_db"],
        "contrast_threshold_db": options["contrast_threshold_db"],
        "contrast_radius_m": options["contrast_radius_m"],
        "min_connected_pixels": options["min_connected_pixels"],
        "angle_min_deg": options["angle_min_deg"],
        "angle_max_deg": options["angle_max_deg"],
        "water_mask": options["water_mask"],
        "water_mask_version": OSI_SAR_WATER_MASK_VERSION,
        "angle_mask_version": OSI_SAR_ANGLE_MASK_VERSION,
        "coast_buffer_m": options["coast_buffer_m"],
        "raw_candidate_pixels": raw_count,
        "cleaned_candidate_pixels": clean_count,
        "wind": wind_context,
        "sentinel2_validation": sentinel2_context,
        "confidence": wind_context.get("confidence"),
        "warning": " ".join(warnings),
        "method": "single_scene",
        "quality": "scene",
        "source": SENTINEL1_COLLECTION,
    }
    stats = {
        "surface_ha": surface_ha,
        "total_area_ha": surface_ha,
        "water_surface_ha": water_surface_ha,
        "suspect_surface_ha": suspect_surface,
        "suspect_pct": round((suspect_surface / pct_denominator) * 100, 1) if pct_denominator else 0,
        "mean_vv_db": round(float(raw_stats.get("VV") or 0), 2),
        "mean_vh_db": round(float(raw_stats.get("VH") or 0), 2),
        "mean_local_contrast_db": round(float(raw_stats.get("local_contrast_db") or 0), 2),
        "mean_wind_m_s": wind_context.get("mean_wind_m_s"),
        "min_connected_pixels": options["min_connected_pixels"],
        "stats_scale_m": stats_scale,
        "classes_count": len(class_defs),
        "pixels": int(surface_ha * 100),
        "scene_id": scene.get("scene_id"),
        "acquisition_date": scene.get("acquisition_date"),
        "orbit_pass": scene.get("orbit_pass"),
        "relative_orbit": scene.get("relative_orbit"),
        "satellite": quality["satellite"],
        "confidence": wind_context.get("confidence"),
    }
    vv_vis = {"min": -25, "max": 0, "palette": ["#050505", "#e5e7eb"]}
    contrast_vis = {"min": 0, "max": 6, "palette": ["#ffffcc", "#fd8d3c", "#800026"]}
    raw_vis = {"min": 0, "max": 1, "palette": ["#000000", "#d7191c"]}
    comparison_layers = [
        {"key": "osi_vv", "index": OSI_SAR_ID, "title": "Sentinel-1 VV", "topic": "OSI-SAR", "stats": stats, "histogram": [], "classes": [], "legend": [], "palette": vv_vis["palette"], "tiles": {"index_tile_url": _tile_url(meta["vv"].updateMask(meta["valid_mask"]).clip(geom), vv_vis), "rgb_tile_url": None}, "metadata": {"visualization": "VV dB of the selected scene"}},
        {"key": "osi_vh", "index": OSI_SAR_ID, "title": "Sentinel-1 VH", "topic": "OSI-SAR", "stats": stats, "histogram": [], "classes": [], "legend": [], "palette": vv_vis["palette"], "tiles": {"index_tile_url": _tile_url(meta["vh"].updateMask(meta["valid_mask"]).clip(geom), vv_vis), "rgb_tile_url": None}, "metadata": {"visualization": "VH dB of the selected scene"}},
        {"key": "osi_contrast", "index": OSI_SAR_ID, "title": "Local contrast VV", "topic": "OSI-SAR", "stats": stats, "histogram": [], "classes": [], "legend": [], "palette": contrast_vis["palette"], "tiles": {"index_tile_url": _tile_url(meta["contrast"].updateMask(meta["valid_mask"]).clip(geom), contrast_vis), "rgb_tile_url": None}, "metadata": {"visualization": "localMeanVV - VV"}},
        {"key": "osi_raw_candidates", "index": OSI_SAR_ID, "title": "OSI-SAR raw candidates", "topic": "OSI-SAR", "stats": stats, "histogram": [], "classes": [], "legend": [], "palette": raw_vis["palette"], "tiles": {"index_tile_url": _tile_url(meta["osi_raw"].selfMask(), {"palette": ["#d7191c"]}), "rgb_tile_url": None}, "metadata": {"visualization": "AND mask before connected-pixel filter"}},
        {"key": "osi_final_candidates", "index": OSI_SAR_ID, "title": "OSI-SAR final candidates", "topic": "OSI-SAR", "stats": stats, "histogram": [{"bin": item["name"], "count": int(float(item.get("surface_ha") or 0) * 100)} for item in classes], "classes": classes, "legend": classes, "palette": vis["palette"], "tiles": {"index_tile_url": _tile_url(classified, vis), "rgb_tile_url": _tile_url(meta["vv"].updateMask(meta["valid_mask"]).clip(geom), vv_vis)}, "metadata": {"visualization": "Oil-spill suspect binary mask after connected-pixel filter"}},
    ]
    return {
        "analysis_type": "oil_spill_suspect_index",
        "stats": stats,
        "histogram": [{"bin": item["name"], "count": int(float(item.get("surface_ha") or 0) * 100)} for item in classes],
        "classes": classes,
        "palette": vis["palette"],
        "tiles": {
            "rgb_tile_url": _tile_url(meta["vv"].updateMask(meta["valid_mask"]).clip(geom), vv_vis),
            "index_tile_url": _tile_url(classified, vis),
        },
        "comparison_layers": comparison_layers,
        "active_comparison_layer": "osi_final_candidates",
        "mosaic": quality,
        "quality_summary": quality,
        "interpretation": "OSI-SAR – Oil Spill Suspect maps Sentinel-1 dark-target candidates over water. This is not a confirmed oil spill.",
        "mode": "gee",
        "gee": gee_status(),
    }


def compute_supervised_classification(analysis: dict[str, Any], surface_ha: int) -> dict[str, Any]:
    """Classify land cover from the analysis mosaic using ESA WorldCover training labels."""
    started = time.perf_counter()
    analysis = _normalize_payload(analysis)
    sensor = _sensor_id(analysis)
    if sensor not in {"sentinel-2", "landsat-8-9"}:
        label = SENSOR_META.get(sensor, {}).get("label", sensor)
        raise ValueError(f"Supervised Classification requires Sentinel-2 or Landsat 8/9. Selected sensor: {label}.")

    options = _supervised_options(analysis)
    if not _ensure_gee():
        if options["require_user_samples"]:
            raise RuntimeError(_GEE_ERROR or "Google Earth Engine is unavailable for the guided supervised workflow.")
        result = compute_mock_index(SUPERVISED_CLASSIFICATION_ID, surface_ha=surface_ha)
        result["tiles"] = {"rgb_tile_url": None, "index_tile_url": None}
        result["mode"] = "mock"
        result["gee"] = gee_status()
        return result

    area_km2 = surface_ha / 100.0
    scale = _analysis_scale_for_sensor(sensor)
    policy = classification_cost_policy(area_km2, scale)
    stats_scale = int(policy["statistics_scale_m"])
    tile_scale = int(policy["tile_scale"])
    options = _apply_supervised_cost_policy(options, policy)

    _emit_classification_progress(15, "Preparation...")
    mosaic_started = time.perf_counter()
    mosaic = _build_analysis_mosaic(analysis)
    _perf_log("supervised_mosaic_ms", (time.perf_counter() - mosaic_started) * 1000, level=policy["level"])
    geom = mosaic["geom"]
    image = mosaic["image"]

    _emit_classification_progress(28, "Preparing spectral bands...")
    stack_started = time.perf_counter()
    stack, input_bands = _classification_feature_stack(image, sensor)
    _perf_log("supervised_stack_ms", (time.perf_counter() - stack_started) * 1000, level=policy["level"])

    _emit_classification_progress(40, "Sampling...")
    sample_started = time.perf_counter()
    training, validation, class_defs, sample_meta = _build_supervised_datasets(
        analysis, stack, geom, scale, options, tile_scale=tile_scale
    )
    _perf_log("supervised_sampling_ms", (time.perf_counter() - sample_started) * 1000, level=policy["level"])
    sample_count = int(sample_meta.get("sampled_pixels_count") or 0)
    training_count = int(sample_meta.get("training_samples_count") or 0)
    validation_count = int(sample_meta.get("validation_samples_count") or 0)
    if sample_count < 60:
        raise ValueError("Not enough training samples for supervised classification. Enlarge the AOI or select another period.")
    if training_count < 40 or validation_count < 10:
        raise ValueError("Not enough validation samples for supervised classification. Enlarge the AOI or select another period.")

    classifier_defs = _supervised_classifier_defs(options)
    selected_algorithm = options["algorithm"]
    _emit_classification_progress(52, "Training...")
    train_started = time.perf_counter()
    classifier = _train_supervised_classifier(classifier_defs[selected_algorithm], training, input_bands)
    classified = stack.classify(classifier).rename("landcover")
    # Match unsupervised policy: skip focal smoothing on large AOIs to cut cost
    # while keeping identical class labels from the trained classifier.
    if bool(policy.get("apply_focal_mode", True)):
        classified = classified.focal_mode(radius=1, kernelType="square", units="pixels")
    classified = classified.clip(geom).updateMask(classified.gt(0))
    _perf_log("supervised_train_classify_ms", (time.perf_counter() - train_started) * 1000, level=policy["level"])

    vis = _classification_vis(class_defs)
    _emit_classification_progress(68, "Classification statistics...")
    stats_started = time.perf_counter()
    # One grouped reduceRegion instead of one getInfo per class (critical on large AOIs).
    classes = _compute_categorical_classes_grouped(
        classified,
        geom,
        surface_ha,
        class_defs,
        scale=stats_scale,
        analysis_crs=_analysis_crs(analysis),
        tile_scale=tile_scale,
    )
    accuracy = _classification_accuracy(validation, classifier, class_defs)
    _perf_log("supervised_stats_ms", (time.perf_counter() - stats_started) * 1000, level=policy["level"])

    comparisons: list[dict[str, Any]] = []
    compare_note = None
    if options["compare_algorithms"] and policy["allow_algorithm_comparison"]:
        compare_started = time.perf_counter()
        comparisons = _compare_supervised_algorithms(classifier_defs, training, validation, input_bands, class_defs)
        _perf_log("supervised_compare_ms", (time.perf_counter() - compare_started) * 1000, level=policy["level"])
    elif options["compare_algorithms"]:
        # Keep selected-algorithm metrics visible without training CART/SVM on huge AOIs.
        compare_note = "Algorithm comparison auto-disabled for large AOI cost control; selected classifier unchanged."
        comparisons = [
            {
                "algorithm": selected_algorithm,
                "label": classifier_defs[selected_algorithm]["label"],
                "overall_accuracy": accuracy.get("overall_accuracy"),
                "kappa": accuracy.get("kappa"),
                "comparison_scope": "selected_only",
            }
        ]

    accuracy_warning = None
    if accuracy.get("overall_accuracy") is not None and float(accuracy["overall_accuracy"]) < 0.65:
        accuracy_warning = "Overall accuracy is low. Review the AOI, date range, cloud limit, or training reference before operational use."
    spatial_warning = sample_meta.get("spatial_coverage_warning")
    if spatial_warning:
        accuracy_warning = f"{accuracy_warning} {spatial_warning}".strip() if accuracy_warning else spatial_warning
    interpretation = _supervised_interpretation(accuracy, classes, selected_algorithm)

    _emit_classification_progress(85, "Rendering...")
    tiles_started = time.perf_counter()
    tiles = {
        "rgb_tile_url": _tile_url(image.clip(geom), _analysis_rgb_vis_for_sensor(sensor)),
        "index_tile_url": _tile_url(classified, vis),
    }
    _perf_log("supervised_tiles_ms", (time.perf_counter() - tiles_started) * 1000, level=policy["level"])
    total_ms = round((time.perf_counter() - started) * 1000, 2)
    _perf_log("supervised_total_ms", total_ms, level=policy["level"], samples=sample_count)
    _emit_classification_progress(95, "Completed")

    return {
        "analysis_type": "supervised_classification",
        "stats": {
            "total_area_ha": surface_ha,
            "surface_ha": surface_ha,
            "classes_count": len([item for item in classes if item.get("surface_ha", 0) > 0]),
            "training_samples_count": training_count,
            "validation_samples_count": validation_count,
            "samples_count": sample_count,
            **_resolution_contract(analysis, scale, stats_scale),
            "processing_policy": policy,
        },
        "histogram": [{"bin": item["name"], "count": int(round(float(item.get("surface_ha", 0)) * 100))} for item in classes],
        "classes": classes,
        "palette": vis["palette"],
        "accuracy": accuracy,
        "algorithm_comparison": comparisons,
        "interpretation": interpretation,
        "quality_summary": {
            "coverage_percent": mosaic.get("coverage_percent"),
            "samples_count": sample_count,
            "training_samples_count": training_count,
            "validation_samples_count": validation_count,
            "classifier": classifier_defs[selected_algorithm]["label"],
            "algorithm": selected_algorithm,
            "algorithm_params": classifier_defs[selected_algorithm]["params"],
            "training_split": options["training_split"],
            "reference": sample_meta.get("reference") or "User training samples",
            "sample_source": sample_meta.get("source"),
            "project_id": sample_meta.get("project_id"),
            "validation_split_mode": sample_meta.get("validation_split_mode"),
            "classes_reference": ", ".join(item["name"] for item in class_defs),
            "warning": accuracy_warning,
            "samples_per_class": options["samples_per_class"],
            "spatial_coverage": sample_meta.get("spatial_coverage"),
            "apply_focal_mode": bool(policy.get("apply_focal_mode", True)),
            **({"compare_note": compare_note} if compare_note else {}),
            **({"fallback_reason": sample_meta.get("fallback_reason")} if sample_meta.get("fallback_reason") else {}),
        },
        "tiles": tiles,
        "mosaic": _mosaic_quality_payload(mosaic),
        "mode": "gee",
        "gee": gee_status(),
        "performance": {
            "strategy": "supervised_cost_policy_v2_spatial_quality",
            "total_ms": total_ms,
            "level": policy["level"],
        },
    }


def compute_unsupervised_classification(analysis: dict[str, Any], surface_ha: int) -> dict[str, Any]:
    """Cluster land cover from the analysis mosaic using K-Means and spectral interpretation."""
    started = time.perf_counter()
    analysis = _normalize_payload(analysis)
    sensor = _sensor_id(analysis)
    if sensor not in {"sentinel-2", "landsat-8-9"}:
        label = SENSOR_META.get(sensor, {}).get("label", sensor)
        raise ValueError(f"Unsupervised Classification requires Sentinel-2 or Landsat 8/9. Selected sensor: {label}.")

    if not _ensure_gee():
        result = compute_mock_index(UNSUPERVISED_CLASSIFICATION_ID, surface_ha=surface_ha)
        result["tiles"] = {"rgb_tile_url": None, "index_tile_url": None}
        result["mode"] = "mock"
        result["gee"] = gee_status()
        return result

    area_km2 = surface_ha / 100.0
    scale = _analysis_scale_for_sensor(sensor)
    policy = classification_cost_policy(area_km2, scale)
    stats_scale = int(policy["statistics_scale_m"])
    tile_scale = int(policy["tile_scale"])
    cluster_stats_scale = int(policy["cluster_stats_scale_m"])

    _emit_classification_progress(15, "Preparation...")
    mosaic_started = time.perf_counter()
    mosaic = _build_analysis_mosaic(analysis)
    _perf_log("unsupervised_mosaic_ms", (time.perf_counter() - mosaic_started) * 1000, level=policy["level"])
    geom = mosaic["geom"]
    image = mosaic["image"]

    _emit_classification_progress(28, "Preparing spectral bands...")
    stack, input_bands = _unsupervised_feature_stack(image, sensor)
    options = _unsupervised_options(analysis, input_bands)
    options = _apply_unsupervised_cost_policy(options, policy)

    _emit_classification_progress(42, "Sampling / Clustering...")
    cluster_started = time.perf_counter()
    classified, class_map, samples_count = _unsupervised_classified_image(
        stack,
        options["input_bands"],
        geom,
        scale,
        clusters_count=options["clusters_count"],
        samples_count=options["samples_count"],
        seed=options["seed"],
        feature_standardization=options["feature_standardization"],
        tile_scale=tile_scale,
        cluster_stats_scale=cluster_stats_scale,
        sample_scale=int(policy["sample_scale_m"]),
        apply_focal_mode=bool(policy.get("apply_unsupervised_focal_mode", True)),
        sensor=sensor,
    )
    _perf_log(
        "unsupervised_cluster_ms",
        (time.perf_counter() - cluster_started) * 1000,
        level=policy["level"],
        sample_scale=policy["sample_scale_m"],
        samples=samples_count,
    )
    class_defs = _unsupervised_cluster_class_defs(class_map)
    # The clusterer is a lazy Earth Engine graph. Computing one class per
    # reduceRegion can evaluate that graph several times and let Weka remap
    # internal labels between requests. Group all class areas in one server
    # evaluation so the statistics use exactly one label realization.
    _emit_classification_progress(68, "Classification statistics...")
    stats_started = time.perf_counter()
    classes = _compute_categorical_classes_grouped(
        classified,
        geom,
        surface_ha,
        class_defs,
        scale=stats_scale,
        analysis_crs=_gee_stats_crs_for_analysis(analysis),
        tile_scale=tile_scale,
    )
    _perf_log("unsupervised_stats_ms", (time.perf_counter() - stats_started) * 1000, level=policy["level"])
    classified_surface_ha = round(sum(float(item.get("surface_ha") or 0) for item in classes), 2)
    for item in classes:
        item["pct"] = round((float(item.get("surface_ha") or 0) / classified_surface_ha) * 100, 1) if classified_surface_ha else 0
    classified_pct_of_aoi = (
        round(min(100.0, (classified_surface_ha / float(surface_ha)) * 100), 2)
        if surface_ha
        else 0.0
    )
    vis = _unsupervised_classification_vis(class_defs)
    interpretation = _unsupervised_interpretation(classes, class_map, options)

    _emit_classification_progress(85, "Rendering...")
    tiles_started = time.perf_counter()
    tiles = {
        "rgb_tile_url": _tile_url(image.clip(geom), _analysis_rgb_vis_for_sensor(sensor)),
        "index_tile_url": _tile_url(classified, vis),
    }
    _perf_log("unsupervised_tiles_ms", (time.perf_counter() - tiles_started) * 1000, level=policy["level"])
    total_ms = round((time.perf_counter() - started) * 1000, 2)
    _perf_log("unsupervised_total_ms", total_ms, level=policy["level"], samples=samples_count)
    _emit_classification_progress(95, "Completed")

    return {
        "analysis_type": "unsupervised_classification",
        "stats": {
            "total_area_ha": surface_ha,
            "surface_ha": surface_ha,
            "classified_surface_ha": classified_surface_ha,
            "classified_pct_of_aoi": classified_pct_of_aoi,
            "unclassified_surface_ha": round(max(0.0, float(surface_ha) - classified_surface_ha), 2),
            "area_measurement_delta_pct": (
                round(((classified_surface_ha - float(surface_ha)) / float(surface_ha)) * 100, 3)
                if surface_ha
                else 0.0
            ),
            "classes_count": len(class_defs),
            "samples_count": samples_count,
            **_resolution_contract(analysis, scale, stats_scale),
            "processing_policy": policy,
        },
        "histogram": [{"bin": item["name"], "count": int(round(float(item.get("surface_ha", 0)) * 100))} for item in classes],
        "classes": classes,
        "cluster_interpretation": class_map,
        "palette": vis["palette"],
        "interpretation": interpretation,
        "quality_summary": {
            "samples_count": samples_count,
            "coverage_percent": mosaic.get("coverage_percent"),
            "cluster_method": "ee.Clusterer.wekaKMeans",
            "clusterer_parameters": {
                "init": 1,
                "preserve_order": True,
                "seed": options["seed"],
            },
            "clusters_count": options["clusters_count"],
            "mode": options["mode"],
            "input_bands": options["input_bands"],
            "available_bands": input_bands,
            "seed": options["seed"],
            "sample_scale_m": int(policy["sample_scale_m"]),
            "cluster_stats_scale_m": cluster_stats_scale,
            "apply_focal_mode": bool(policy.get("apply_unsupervised_focal_mode", True)),
            "sampling_strategy": policy.get("sampling_strategy"),
            "sampling_distribution": "uniform_random_over_valid_pixels",
            "sampling_geometries": False,
            "sampling_tile_scale": tile_scale,
            "max_unsupervised_samples": int(policy.get("max_unsupervised_samples") or options["samples_count"]),
            "feature_scaling": (
                "sentinel2_reflectance_0_1"
                if sensor == "sentinel-2"
                else "landsat_l2_scaled_reflectance"
            ),
            "feature_standardization": options["feature_standardization"],
            "post_processing": "3x3_focal_mode" if bool(policy.get("apply_unsupervised_focal_mode", True)) else "raw_clusters",
            "valid_data_coverage_pct": classified_pct_of_aoi,
            "reference_validation_available": False,
            "reference_validation_message": "No independent reference validation is available; only exploratory spectral summaries are reported.",
        },
        "tiles": tiles,
        "mosaic": _mosaic_quality_payload(mosaic),
        "mode": "gee",
        "gee": gee_status(),
        "performance": {
            "strategy": "unsupervised_cost_policy_v3_adaptive_density",
            "total_ms": total_ms,
            "level": policy["level"],
            "sample_scale_m": int(policy["sample_scale_m"]),
        },
    }


def _unsupervised_options(analysis: dict[str, Any], available_bands: list[str]) -> dict[str, Any]:
    raw = analysis.get("unsupervised_options") or {}
    mode = str(raw.get("mode") or "simple").lower()
    if mode not in {"simple", "expert"}:
        mode = "simple"
    clusters_count = int(raw.get("clusters_count", 6))
    clusters_count = max(2, min(clusters_count, 12))
    samples_count = int(raw.get("samples_count", 5000))
    samples_count = max(500, min(samples_count, 20000))
    seed = int(raw.get("seed", 91))
    feature_standardization = str(raw.get("feature_standardization") or "none").lower()
    if feature_standardization not in {"none", "zscore"}:
        feature_standardization = "none"
    # Track whether the UI left the historical default cluster count so the
    # cost policy can raise it on large heterogeneous AOIs without overriding
    # an explicit expert choice.
    # The frontend always sends the visible slider value. Treat it as an
    # explicit scientific choice, including the default value 6; silently
    # changing K made the result disagree with the control shown to users.
    clusters_explicit = "clusters_count" in raw

    requested = raw.get("input_bands")
    if mode == "expert" and isinstance(requested, list):
        input_bands = [str(band) for band in requested if str(band) in available_bands]
    else:
        input_bands = [band for band in ["B2", "B3", "B4", "B8", "B11", "B12", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"] if band in available_bands]
    if len(input_bands) < 2:
        input_bands = available_bands[:]
    return {
        "mode": mode,
        "clusters_count": clusters_count,
        "samples_count": samples_count,
        "seed": seed,
        "feature_standardization": feature_standardization,
        "input_bands": input_bands,
        "clusters_explicit": clusters_explicit,
    }


def _unsupervised_classified_image(
    stack: Any,
    input_bands: list[str],
    geom: Any,
    scale: int,
    *,
    clusters_count: int,
    samples_count: int,
    seed: int,
    feature_standardization: str = "none",
    tile_scale: int = 4,
    cluster_stats_scale: int | None = None,
    sample_scale: int | None = None,
    apply_focal_mode: bool = True,
    sensor: str = "sentinel-2",
) -> tuple[Any, list[dict[str, Any]], int]:
    """Train KMeans on a controlled sample, then apply the clusterer to the AOI.

    Sampling may use a coarser scale on large AOIs so GEE does not scan every
    native pixel just to draw training samples. The clusterer is still applied
    to the full spectral stack at the analysis scale for the map result.
    """
    train_scale = int(sample_scale or scale)
    sample_started = time.perf_counter()
    samples = stack.select(input_bands).sample(
        region=geom,
        scale=train_scale,
        numPixels=samples_count,
        seed=seed,
        geometries=False,
        tileScale=tile_scale,
    )
    sampled_count = int(samples.size().getInfo() or 0)
    _perf_log(
        "unsupervised_sample_getinfo_ms",
        (time.perf_counter() - sample_started) * 1000,
        samples=sampled_count,
        sample_scale=train_scale,
    )
    if sampled_count < 60:
        raise ValueError("Not enough samples for unsupervised classification. Enlarge the AOI or select another period.")

    clustering_stack = stack
    training_samples = samples
    if feature_standardization == "zscore":
        statistic_reducer = ee.Reducer.mean().repeat(len(input_bands)).combine(
            reducer2=ee.Reducer.stdDev().repeat(len(input_bands)),
            sharedInputs=True,
        )
        sample_stats = samples.reduceColumns(
            reducer=statistic_reducer,
            selectors=input_bands,
        ).getInfo() or {}
        means = sample_stats.get("mean") or []
        deviations = sample_stats.get("stdDev") or []
        if len(means) != len(input_bands) or len(deviations) != len(input_bands):
            raise ValueError("Unable to calculate feature normalization from the training sample.")
        safe_deviations = [max(float(value or 0), 1e-6) for value in deviations]
        mean_by_band = dict(zip(input_bands, (float(value) for value in means)))
        deviation_by_band = dict(zip(input_bands, safe_deviations))

        def standardize_feature(feature: Any) -> Any:
            values = {
                band: ee.Number(feature.get(band))
                .subtract(mean_by_band[band])
                .divide(deviation_by_band[band])
                for band in input_bands
            }
            return ee.Feature(feature).set(values)

        training_samples = samples.map(standardize_feature)
        normalized_predictors = (
            stack.select(input_bands)
            .subtract(ee.Image.constant([mean_by_band[band] for band in input_bands]).rename(input_bands))
            .divide(ee.Image.constant([deviation_by_band[band] for band in input_bands]).rename(input_bands))
        )
        clustering_stack = stack.addBands(normalized_predictors, None, True)

    clusterer = ee.Clusterer.wekaKMeans(
        nClusters=clusters_count,
        init=1,
        preserveOrder=True,
        seed=seed,
    ).train(
        features=training_samples,
        inputProperties=input_bands,
        subsamplingSeed=seed,
    )
    # Apply trained clusterer over the full AOI at analysis/native scale.
    clusters = clustering_stack.select(input_bands).cluster(clusterer).rename("cluster").clip(geom)
    interpret_started = time.perf_counter()
    raw_class_map = _interpret_clusters(
        stack,
        clusters,
        geom,
        cluster_stats_scale or train_scale,
        clusters_count,
        tile_scale=tile_scale,
        sensor=sensor,
    )
    _perf_log(
        "unsupervised_interpret_ms",
        (time.perf_counter() - interpret_started) * 1000,
        clusters=clusters_count,
        interpret_scale=cluster_stats_scale or train_scale,
    )
    class_map = []
    stable_palette = _unsupervised_cluster_palette(clusters_count)
    classified = ee.Image(0).rename("cluster").updateMask(clusters.mask())
    for stable_code, raw_item in enumerate(sorted(raw_class_map, key=_unsupervised_cluster_sort_key), start=1):
        raw_cluster = int(raw_item["cluster"])
        item = dict(raw_item)
        item["cluster"] = stable_code - 1
        item["code"] = stable_code
        item["color"] = stable_palette[stable_code - 1]
        item["probable_label"] = item.get("semantic_name") or "Uninterpreted cluster"
        item["name"] = f"Cluster {stable_code}"
        class_map.append(item)
        classified = classified.where(clusters.eq(raw_cluster), stable_code)
    if apply_focal_mode:
        classified = (
            classified
            .focal_mode(radius=1, kernelType="square", units="pixels")
            .updateMask(clusters.mask())
            .clip(geom)
        )
    else:
        # Large AOIs skip focal smoothing: same cluster labels, lower compute graph cost.
        classified = classified.clip(geom)
    return classified.updateMask(classified.gt(0)), class_map, sampled_count


def _interpret_clusters(
    stack: Any,
    clusters: Any,
    geom: Any,
    scale: int,
    clusters_count: int,
    *,
    tile_scale: int = 4,
    sensor: str = "sentinel-2",
) -> list[dict[str, Any]]:
    """Interpret clusters from spectral means.

    On large AOIs (coarser stats/sample scale), prefer a bounded sample for
    cluster means so legend labeling does not force a full-AOI reduceRegion on
    the KMeans graph. Semantic rules are unchanged. Small AOIs keep the
    grouped reduceRegion path.
    """
    palette = _unsupervised_cluster_palette(clusters_count)
    index_bands = ["NDVI", "NDWI", "NDBI", "BSI", "SAVI"]
    spectral_bands = (
        ["B2", "B3", "B4", "B8", "B11", "B12"]
        if sensor == "sentinel-2"
        else ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
    )
    profile_bands = spectral_bands + index_bands
    means_by_cluster: dict[int, dict[str, float]] = {}
    try:
        # Keep the group band after the values it partitions. The reducer needs
        # one mean input for every predictor and one additional grouping input.
        combined = stack.select(profile_bands).addBands(clusters.toInt().rename("cluster"))
        reducer = (
            ee.Reducer.mean()
            .repeat(len(profile_bands))
            .group(groupField=len(profile_bands), groupName="cluster")
        )
        raw = combined.reduceRegion(
            reducer=reducer,
            geometry=geom,
            scale=scale,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=max(tile_scale, 4),
        ).getInfo() or {}
        for group in raw.get("groups") or []:
            cluster_id = int(group.get("cluster"))
            profile_values = group.get("mean") or []
            if len(profile_values) != len(profile_bands):
                raise ValueError("Grouped spectral profile returned an unexpected number of values.")
            means_by_cluster[cluster_id] = {
                band: float(value)
                for band, value in zip(profile_bands, profile_values)
                if value is not None
            }
    except Exception as exc:
        # Bounded fallback: transfer only a few thousand sampled records.
        _perf_log(
            "unsupervised_interpret_grouped_failed_ms",
            0,
            error=type(exc).__name__,
            detail=str(exc)[:500],
        )
        means_by_cluster = _interpret_clusters_via_sample(
            stack,
            clusters,
            geom,
            scale,
            clusters_count,
            index_bands=profile_bands,
            tile_scale=tile_scale,
        )

    mapping = []
    for cluster_id in range(clusters_count):
        means = means_by_cluster.get(cluster_id) or {}
        profile_available = all(means.get(band) is not None for band in index_bands)
        ndvi = float(means.get("NDVI") or 0)
        ndwi = float(means.get("NDWI") or 0)
        ndbi = float(means.get("NDBI") or 0)
        bsi = float(means.get("BSI") or 0)
        savi = float(means.get("SAVI") or 0)
        code = (
            _semantic_code_from_cluster(ndvi=ndvi, ndwi=ndwi, ndbi=ndbi, bsi=bsi, savi=savi)
            if profile_available
            else 7
        )
        class_def = next((item for item in UNSUPERVISED_LAND_COVER_CLASSES if item["code"] == code), UNSUPERVISED_LAND_COVER_CLASSES[-1])
        mapping.append(
            {
                "cluster": cluster_id,
                "code": cluster_id + 1,
                "semantic_code": code,
                "name": f"Cluster {cluster_id + 1} - {class_def['name']}",
                "semantic_name": class_def["name"],
                "color": palette[cluster_id],
                "means": {
                    "NDVI": round(ndvi, 4),
                    "NDWI": round(ndwi, 4),
                    "NDBI": round(ndbi, 4),
                    "BSI": round(bsi, 4),
                    "SAVI": round(savi, 4),
                },
                "spectral_means": {
                    band: round(float(means[band]), 6)
                    for band in spectral_bands
                    if means.get(band) is not None
                },
                "profile_available": profile_available,
            }
        )
    return _differentiate_relative_cluster_labels(mapping)


def _interpret_clusters_via_sample(
    stack: Any,
    clusters: Any,
    geom: Any,
    scale: int,
    clusters_count: int,
    *,
    index_bands: list[str],
    tile_scale: int = 4,
) -> dict[int, dict[str, float]]:
    """Estimate cluster spectral means from a bounded sample when full reduceRegion fails."""
    means_by_cluster: dict[int, dict[str, float]] = {
        cluster_id: {band: 0.0 for band in index_bands} for cluster_id in range(clusters_count)
    }
    counts: dict[int, int] = {cluster_id: 0 for cluster_id in range(clusters_count)}
    try:
        sampled = (
            clusters.toInt()
            .rename("cluster")
            .addBands(stack.select(index_bands))
            .sample(
                region=geom,
                scale=scale,
                numPixels=min(8000, max(1500, clusters_count * 400)),
                seed=17,
                geometries=False,
                tileScale=tile_scale,
            )
        )
        payload = sampled.limit(8000).getInfo() or {}
        rows = payload.get("features") or []
        for feature in rows:
            props = feature.get("properties") or {}
            try:
                cluster_id = int(props.get("cluster"))
            except Exception:
                continue
            if cluster_id not in means_by_cluster:
                continue
            counts[cluster_id] += 1
            for band in index_bands:
                means_by_cluster[cluster_id][band] += float(props.get(band) or 0)
        for cluster_id, count in counts.items():
            if count <= 0:
                means_by_cluster.pop(cluster_id, None)
                continue
            for band in index_bands:
                means_by_cluster[cluster_id][band] /= count
    except Exception as exc:
        _perf_log("unsupervised_interpret_sample_failed_ms", 0, error=type(exc).__name__)
    return means_by_cluster


def _semantic_code_from_cluster(*, ndvi: float, ndwi: float, ndbi: float, bsi: float, savi: float) -> int:
    """Map cluster spectral means to exploratory land-cover labels.

    In arid landscapes bright bare soil often elevates NDBI. Prefer bare-soil
    labels when BSI is strong, and reserve built-up for clearer urban signatures.
    """
    if ndwi >= 0.25 and ndvi < 0.35:
        return 1
    if ndwi >= 0.05 and ndvi >= 0.18:
        return 6
    if ndvi >= 0.45 or savi >= 0.45:
        return 2
    if ndvi >= 0.22:
        return 3
    # Bright mineral / bare surfaces first (common false built-up in deserts).
    if bsi >= 0.18 and ndvi < 0.25:
        return 5
    if bsi >= 0.12 and ndbi < 0.14 and ndvi < 0.22:
        return 5
    # Stricter built-up: stronger NDBI and limited bare-soil dominance.
    if ndbi >= 0.12 and bsi < 0.28 and ndvi < 0.22:
        return 4
    if ndbi >= 0.08 and bsi < 0.18 and ndvi < 0.18:
        return 4
    if bsi >= 0.12 and ndvi < 0.25:
        return 5
    return 7


def _differentiate_relative_cluster_labels(mapping: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """When arid scenes collapse many clusters to the same semantic label, add
    relative spectral traits so the legend stays distinguishable.

    Pixel cluster IDs and colours are unchanged; only display names/descriptions.
    """
    if len(mapping) < 2:
        for item in mapping:
            if not item.get("profile_available", True):
                item["semantic_name"] = "Uninterpreted cluster"
                item["probable_label"] = "Uninterpreted cluster"
                item["name"] = f"Cluster {int(item.get('code') or 1)}"
                item["description"] = "Spectral profile unavailable; interpretation was not calculated."
                continue
            means = item.get("means") or {}
            item["probable_label"] = item.get("semantic_name") or "Uninterpreted cluster"
            item["name"] = f"Cluster {int(item.get('code') or 1)}"
            item.setdefault(
                "description",
                (
                    f"Probable interpretation: {item['probable_label']}. "
                    f"Spectral means NDVI={float(means.get('NDVI') or 0):.2f}, "
                    f"NDWI={float(means.get('NDWI') or 0):.2f}, "
                    f"NDBI={float(means.get('NDBI') or 0):.2f}, "
                    f"BSI={float(means.get('BSI') or 0):.2f}."
                ),
            )
        return mapping

    names = [str(item.get("semantic_name") or "") for item in mapping]
    most_common, count = Counter(names).most_common(1)[0]
    by_ndvi = sorted(range(len(mapping)), key=lambda i: float((mapping[i].get("means") or {}).get("NDVI") or 0))
    by_ndwi = sorted(range(len(mapping)), key=lambda i: float((mapping[i].get("means") or {}).get("NDWI") or 0))
    by_ndbi = sorted(range(len(mapping)), key=lambda i: float((mapping[i].get("means") or {}).get("NDBI") or 0))
    by_bsi = sorted(range(len(mapping)), key=lambda i: float((mapping[i].get("means") or {}).get("BSI") or 0))
    collapse = count >= max(2, len(mapping) - 1)

    for index, item in enumerate(mapping):
        means = item.get("means") or {}
        if not item.get("profile_available", True):
            item["semantic_name"] = "Uninterpreted cluster"
            item["probable_label"] = "Uninterpreted cluster"
            item["name"] = f"Cluster {int(item.get('code') or index + 1)}"
            item["description"] = "Spectral profile unavailable; interpretation was not calculated."
            continue
        traits: list[str] = []
        if index == by_ndwi[-1] and float(means.get("NDWI") or 0) >= -0.05:
            traits.append("relatively higher moisture / NDWI")
        if index == by_ndvi[-1]:
            traits.append("relatively higher vegetation response")
        elif index == by_ndvi[0]:
            traits.append("drier / lower vegetation")
        if index == by_ndbi[-1]:
            traits.append("stronger SWIR/NDBI signature")
        if index == by_bsi[-1]:
            traits.append("stronger bare-soil (BSI)")
        elif index == by_bsi[0]:
            traits.append("weaker bare-soil response")

        base = str(item.get("semantic_name") or "Uninterpreted cluster")
        if collapse and base == most_common and traits:
            item["semantic_name"] = f"{base} ({traits[0]})"

        item["probable_label"] = item.get("semantic_name") or base
        item["name"] = f"Cluster {int(item.get('code') or index + 1)}"

        trait_text = ("; ".join(traits) + ". ") if traits else ""
        item["description"] = (
            f"Probable interpretation: {item['probable_label']}. "
            f"Spectral means NDVI={float(means.get('NDVI') or 0):.2f}, "
            f"NDWI={float(means.get('NDWI') or 0):.2f}, "
            f"NDBI={float(means.get('NDBI') or 0):.2f}, "
            f"BSI={float(means.get('BSI') or 0):.2f}. "
            f"{trait_text}Exploratory interpretation — review before operational use."
        )
    return mapping


def _unsupervised_cluster_palette(clusters_count: int) -> list[str]:
    base = [
        "#0072B2",
        "#E69F00",
        "#009E73",
        "#D55E00",
        "#CC79A7",
        "#56B4E9",
        "#6A3D9A",
        "#8C564B",
        "#1B9E77",
        "#E7298A",
        "#66A61E",
        "#A6761D",
    ]
    return base[:clusters_count]


def _unsupervised_cluster_sort_key(item: dict[str, Any]) -> tuple[float, ...]:
    means = item.get("means") or {}
    return tuple(
        round(float(means.get(index_id) or 0), 6)
        for index_id in ("NDVI", "NDWI", "NDBI", "BSI", "SAVI")
    )


def normalize_unsupervised_result_order(result: dict[str, Any]) -> dict[str, Any]:
    """Migrate stored cluster metadata to the deterministic spectral order."""
    normalized = dict(result or {})
    if normalized.get("analysis_type") != "unsupervised_classification":
        return normalized

    interpretations = [
        dict(item)
        for item in (normalized.get("cluster_interpretation") or [])
        if isinstance(item, dict)
    ]
    classes = [
        dict(item)
        for item in (normalized.get("classes") or [])
        if isinstance(item, dict)
    ]
    if not interpretations or len(interpretations) != len(classes):
        return normalized

    class_by_old_code = {int(item.get("code") or 0): item for item in classes}
    ordered_classes: list[dict[str, Any]] = []
    ordered_interpretations: list[dict[str, Any]] = []
    for stable_code, interpretation in enumerate(sorted(interpretations, key=_unsupervised_cluster_sort_key), start=1):
        old_code = int(interpretation.get("code") or (int(interpretation.get("cluster") or 0) + 1))
        class_item = class_by_old_code.get(old_code)
        if class_item is None:
            return normalized
        class_item["code"] = stable_code
        interpretation["code"] = stable_code
        interpretation["cluster"] = stable_code - 1
        interpretation["name"] = class_item.get("name") or interpretation.get("name")
        interpretation["color"] = class_item.get("color") or interpretation.get("color")
        ordered_classes.append(class_item)
        ordered_interpretations.append(interpretation)

    normalized["classes"] = ordered_classes
    normalized["cluster_interpretation"] = ordered_interpretations
    normalized["palette"] = [str(item.get("color") or "") for item in ordered_classes]
    return normalized


def _unsupervised_cluster_class_defs(class_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "code": int(item["code"]),
            "name": item["name"],
            "color": item["color"],
            "description": item.get("description") or "",
            "probable_label": item.get("probable_label") or item.get("semantic_name") or "",
        }
        for item in class_map
    ]


def _unsupervised_interpretation(classes: list[dict[str, Any]], class_map: list[dict[str, Any]], options: dict[str, Any]) -> str:
    dominant = max(classes, key=lambda item: float(item.get("surface_ha") or 0), default=None)
    dominant_text = f" Dominant cluster: {dominant['name']} ({dominant.get('pct', 0)}%)." if dominant else ""
    return (
        f"The analysis produced {options['clusters_count']} spectral groups from "
        f"{len(options['input_bands'])} input bands in {options['mode']} mode."
        f"{dominant_text} Cluster IDs are spectral groups, not validated land-cover classes. "
        "Probable interpretations are exploratory and should be reviewed before operational use."
    )


def _unsupervised_classification_vis(class_defs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    classes = class_defs or UNSUPERVISED_LAND_COVER_CLASSES
    return {
        "min": 1,
        "max": len(classes),
        "palette": [item["color"] for item in classes],
    }


def _unsupervised_result_vis(result: dict[str, Any], default_vis: dict[str, Any]) -> dict[str, Any]:
    """Apply a stored user palette without changing the classified pixel values."""
    normalized = normalize_unsupervised_result_order(result)
    classes = [item for item in (normalized.get("classes") or []) if isinstance(item, dict)]
    ordered_classes = sorted(classes, key=lambda item: int(item.get("code") or 0))
    palette = [str(item.get("color") or "") for item in ordered_classes]
    expected_count = int(default_vis.get("max") or 0) - int(default_vis.get("min") or 0) + 1
    if expected_count > 0 and len(palette) == expected_count and all(re.fullmatch(r"#[0-9A-Fa-f]{6}", color) for color in palette):
        return {**default_vis, "palette": palette}
    return default_vis


def _classification_feature_stack(image: Any, sensor: str) -> tuple[Any, list[str]]:
    spectral_bands = {
        "sentinel-2": ["B2", "B3", "B4", "B8", "B11", "B12"],
        "landsat-8-9": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"],
    }[sensor]
    index_images = []
    for index_id in ["NDVI", "NDWI", "NDBI", "BSI", "SAVI"]:
        bands = _index_bands_for_sensor(index_id, sensor)
        index_images.append(_index_raster_for_analysis(image, index_id, bands))
    stack = image.select(spectral_bands).addBands(ee.Image.cat(index_images)).toFloat()
    return stack, spectral_bands + ["NDVI", "NDWI", "NDBI", "BSI", "SAVI"]


def _unsupervised_feature_stack(image: Any, sensor: str) -> tuple[Any, list[str]]:
    """Build distance-compatible features without changing supervised inputs.

    Sentinel-2 SR bands are stored as scaled integers (roughly 0..10000),
    while spectral indices are roughly -1..1. K-Means uses Euclidean distance,
    so leaving those units mixed makes the raw bands overwhelm every index.
    Convert Sentinel-2 reflectance to physical 0..1 units only for this module.
    Landsat L2 is already scaled during preprocessing.
    """
    stack, input_bands = _classification_feature_stack(image, sensor)
    if sensor == "sentinel-2":
        spectral_bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
        scaled_reflectance = stack.select(spectral_bands).multiply(0.0001)
        stack = stack.addBands(scaled_reflectance, None, True)
    return stack, input_bands


def _worldcover_reference(geom: Any) -> Any:
    worldcover = ee.ImageCollection(ESA_WORLDCOVER_COLLECTION).first().select("Map").clip(geom)
    from_values: list[int] = []
    to_values: list[int] = []
    for item in LAND_COVER_CLASSES:
        for code in item["worldcover"]:
            from_values.append(int(code))
            to_values.append(int(item["code"]))
    return worldcover.remap(from_values, to_values, 0).rename("landcover").updateMask(worldcover.neq(0))


def _project_landcover_classes(project_id: str, selected_class_ids: list[str] | None = None) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT id, project_id, code, name, description, color, sort_order, is_active, created_at
            FROM landcover_classes
            WHERE (project_id = ? OR project_id = 'default') AND is_active = 1
            ORDER BY sort_order, code
            """,
            (project_id,),
        )
    classes = [dict(row) for row in rows]
    if selected_class_ids:
        selected = set(selected_class_ids)
        classes = [item for item in classes if str(item.get("id") or "") in selected]
    return classes


def _geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    coords = geometry.get("coordinates")
    if not coords:
        return None
    points: list[tuple[float, float]] = []

    def collect(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            points.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                collect(item)

    collect(coords)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _bounds_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _geometry_to_ee(geometry: dict[str, Any]) -> Any | None:
    geom_type = str(geometry.get("type") or "").lower()
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return None
    if geom_type == "point":
        return ee.Geometry.Point(coordinates)
    if geom_type == "polygon":
        return ee.Geometry.Polygon(coordinates)
    if geom_type == "multipolygon":
        return ee.Geometry.MultiPolygon(coordinates)
    if geom_type == "linestring":
        return ee.Geometry.LineString(coordinates)
    return ee.Geometry(geometry)


def _load_user_training_features(analysis: dict[str, Any], geom: Any) -> tuple[Any | None, list[dict[str, Any]], dict[str, Any]]:
    options = analysis.get("supervised_options") or {}
    project_id = str(options.get("project_id") or "default")
    selected_class_ids = [str(value) for value in (options.get("class_ids") or []) if str(value).strip()]
    class_defs = _project_landcover_classes(project_id, selected_class_ids)
    if not class_defs:
        return None, LAND_COVER_CLASSES, {"source": "worldcover_fallback", "reason": "no_active_classes"}

    class_by_id = {item["id"]: item for item in class_defs if item.get("id")}
    class_by_code = {int(item["code"]): item for item in class_defs if item.get("code") is not None}
    aoi_bounds = _bbox_from_aoi(analysis.get("aoi") or {})
    if aoi_bounds == [0, 0, 0, 0]:
        return None, class_defs, {"source": "worldcover_fallback", "reason": "invalid_aoi_bounds"}
    aoi_rect = (aoi_bounds[1], aoi_bounds[0], aoi_bounds[3], aoi_bounds[2])

    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT id, class_id, geometry_json, usage, quality_status, source, properties_json
            FROM training_samples
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        )

    features = []
    feature_bounds: list[tuple[float, float, float, float]] = []
    counts = {"training": 0, "validation": 0}
    class_feature_counts = {
        str(item["id"]): {"training": 0, "validation": 0}
        for item in class_defs
        if item.get("id")
    }
    polygon_class_roles: set[tuple[int, str]] = set()
    point_class_roles: set[tuple[int, str]] = set()
    for row in rows:
        class_id = row["class_id"]
        if not class_id or class_id not in class_by_id:
            continue
        geometry = db.json_loads(row["geometry_json"] or "{}")
        if not isinstance(geometry, dict):
            continue
        bounds = _geometry_bounds(geometry)
        if bounds and not _bounds_intersect(bounds, aoi_rect):
            continue
        ee_geom = _geometry_to_ee(geometry)
        if ee_geom is None:
            continue
        landcover_class = class_by_id[class_id]
        usage = str(row["usage"] or "training").lower()
        sample_role = usage if usage in {"training", "validation"} else "training"
        geometry_type = str(geometry.get("type") or "")
        counts[sample_role] += 1
        class_feature_counts[str(class_id)][sample_role] += 1
        if bounds:
            feature_bounds.append(bounds)
        if geometry_type == "Polygon":
            polygon_class_roles.add((int(landcover_class["code"]), sample_role))
        elif geometry_type == "Point":
            point_class_roles.add((int(landcover_class["code"]), sample_role))
        properties = db.json_loads(row["properties_json"] or "{}")
        feature = ee.Feature(
            ee_geom,
            {
                "sample_id": row["id"],
                "landcover": int(landcover_class["code"]),
                "class_name": landcover_class["name"],
                "sample_role": sample_role,
                "geometry_type": geometry_type,
                "quality_status": row["quality_status"] or "valid",
                "sample_source": row["source"] or "manual",
                "properties_json": db.json_dumps(properties),
            },
        )
        features.append(feature)

    missing_training_class_ids = [
        class_id
        for class_id, role_counts in class_feature_counts.items()
        if role_counts["training"] == 0
    ]
    if not features:
        return None, class_defs, {
            "source": "worldcover_fallback",
            "reason": "no_user_samples",
            "missing_training_class_ids": missing_training_class_ids,
        }

    return ee.FeatureCollection(features).filterBounds(geom), list(class_by_code.values()), {
        "source": "user_samples",
        "project_id": project_id,
        "sample_features_count": len(features),
        "training_features_count": counts["training"],
        "validation_features_count": counts["validation"],
        "class_feature_counts": class_feature_counts,
        "missing_training_class_ids": missing_training_class_ids,
        "polygon_class_roles": sorted(polygon_class_roles),
        "point_class_roles": sorted(point_class_roles),
        "feature_bounds": feature_bounds,
    }


def _collection_role_counts(sampled: Any, training: Any, validation: Any) -> tuple[int, int, int]:
    """Fetch sample/training/validation sizes in one GEE round-trip when possible."""
    try:
        raw = ee.Dictionary(
            {
                "sample": sampled.size(),
                "training": training.size(),
                "validation": validation.size(),
            }
        ).getInfo() or {}
        return (
            int(raw.get("sample") or 0),
            int(raw.get("training") or 0),
            int(raw.get("validation") or 0),
        )
    except Exception:
        return (
            int(sampled.size().getInfo() or 0),
            int(training.size().getInfo() or 0),
            int(validation.size().getInfo() or 0),
        )


def _apply_supervised_cost_policy(options: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    capped = dict(options)
    max_samples = int(policy.get("max_samples_per_class") or capped["samples_per_class"])
    # Prefer the higher of the user request and a quality floor derived from the
    # adaptive policy, without exceeding the hard GEE safety cap.
    requested = int(capped["samples_per_class"])
    quality_floor = min(max_samples, max(80, int(max_samples * 0.75)))
    capped["samples_per_class"] = max(40, min(max(requested, quality_floor), max_samples))
    return capped


def _apply_unsupervised_cost_policy(options: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    capped = dict(options)
    max_samples = int(policy.get("max_unsupervised_samples") or capped["samples_count"])
    requested = int(capped["samples_count"])
    # On large AOIs the historical UI default (5000) was often capped far too
    # low. Raise toward the adaptive budget while still honouring an explicit
    # lower expert request only when it stays above the quality floor.
    quality_floor = min(max_samples, max(2_000, int(max_samples * 0.7)))
    if str(capped.get("mode") or "simple") == "simple" and str(policy.get("level")) in {
        "large",
        "very_large",
    }:
        # Simple mode is quality-first: use the full bounded budget so rare but
        # spatially extensive structures are less likely to be missed.
        capped["samples_count"] = max_samples
    else:
        capped["samples_count"] = max(500, min(max(requested, quality_floor), max_samples))
    recommended = int(policy.get("recommended_clusters") or capped["clusters_count"])
    if (
        str(capped.get("mode") or "simple") == "simple"
        and not bool(capped.get("clusters_explicit"))
        and recommended > int(capped["clusters_count"])
    ):
        capped["clusters_count"] = max(2, min(recommended, 12))
    return capped


def _assess_supervised_spatial_coverage(
    sample_meta: dict[str, Any],
    aoi: dict[str, Any],
    area_km2: float,
) -> dict[str, Any]:
    """Estimate whether user samples span the AOI (client geometries in meta)."""
    feature_bounds = sample_meta.get("feature_bounds") or []
    aoi_bounds = _bbox_from_aoi(aoi or {})
    coverage: dict[str, Any] = {
        "area_km2": round(float(area_km2 or 0), 2),
        "feature_count": int(sample_meta.get("sample_features_count") or 0),
        "quadrants_occupied": 0,
        "quadrant_coverage_ratio": 0.0,
        "sufficient": True,
    }
    if aoi_bounds == [0, 0, 0, 0] or not feature_bounds:
        return coverage

    south, west, north, east = aoi_bounds
    mid_lat = (south + north) / 2.0
    mid_lon = (west + east) / 2.0
    occupied = set()
    for bounds in feature_bounds:
        try:
            min_x, min_y, max_x, max_y = (float(v) for v in bounds)
        except Exception:
            continue
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        # bounds are lon/lat (x/y)
        east_half = cx >= mid_lon
        north_half = cy >= mid_lat
        occupied.add((1 if east_half else 0, 1 if north_half else 0))
    coverage["quadrants_occupied"] = len(occupied)
    coverage["quadrant_coverage_ratio"] = round(len(occupied) / 4.0, 2)
    # Large heterogeneous AOIs need samples in at least 2 quadrants.
    if area_km2 >= 2_000 and len(occupied) < 2:
        coverage["sufficient"] = False
    elif area_km2 >= 5_000 and len(occupied) < 3:
        coverage["sufficient"] = False
    return coverage


def _build_supervised_datasets(
    analysis: dict[str, Any],
    stack: Any,
    geom: Any,
    scale: int,
    options: dict[str, Any],
    *,
    tile_scale: int = 4,
) -> tuple[Any, Any, list[dict[str, Any]], dict[str, Any]]:
    sample_fc, class_defs, sample_meta = _load_user_training_features(analysis, geom)
    require_user_samples = bool(options.get("require_user_samples"))
    if require_user_samples and len(class_defs) < 2:
        raise ValueError("Supervised classification requires at least two selected land-cover classes.")
    if require_user_samples and sample_meta.get("missing_training_class_ids"):
        raise ValueError("Each selected land-cover class must contain at least one training sample inside the AOI.")
    if require_user_samples and sample_fc is None:
        reason = str(sample_meta.get("reason") or "no_user_samples")
        raise ValueError(f"User training samples are required for this supervised workflow ({reason}).")
    if sample_fc is not None:
        area_km2 = float(_aoi_area_km2(analysis.get("aoi") or {}) or 0)
        spatial_coverage = _assess_supervised_spatial_coverage(sample_meta, analysis.get("aoi") or {}, area_km2)
        sample_meta["spatial_coverage"] = spatial_coverage
        if not spatial_coverage.get("sufficient", True):
            sample_meta["spatial_coverage_warning"] = (
                "Training samples cover too little of this large AOI. "
                "Add points/polygons in other parts of the area so each class represents the landscape heterogeneity."
            )

        sample_properties = [
            "landcover",
            "sample_role",
            "class_name",
            "sample_source",
            "quality_status",
            "geometry_type",
            "sample_id",
        ]
        class_by_code = {int(item["code"]): item for item in class_defs}
        # Feature-level train/val split when the user did not draw validation geometries.
        # This reduces optimistic leakage from densifying the same polygon into both sets.
        # Fall back to pixel-level split when there are too few geometries to split safely.
        has_user_validation = int(sample_meta.get("validation_features_count") or 0) > 0
        working_fc = sample_fc
        point_class_roles = list(sample_meta.get("point_class_roles") or [])
        polygon_class_roles = list(sample_meta.get("polygon_class_roles") or [])
        feature_count = int(sample_meta.get("sample_features_count") or 0)
        if not has_user_validation and feature_count >= 6:
            working_fc = sample_fc.randomColumn("feature_split", options["seed"])
            train_features = working_fc.filter(ee.Filter.lt("feature_split", options["training_split"])).map(
                lambda f: f.set("sample_role", "training")
            )
            val_features = working_fc.filter(ee.Filter.gte("feature_split", options["training_split"])).map(
                lambda f: f.set("sample_role", "validation")
            )
            try:
                split_sizes = ee.Dictionary(
                    {"train": train_features.size(), "val": val_features.size()}
                ).getInfo() or {}
                if int(split_sizes.get("train") or 0) > 0 and int(split_sizes.get("val") or 0) > 0:
                    working_fc = train_features.merge(val_features)
                    sample_meta["validation_split_mode"] = "feature_level_random_split"
                    # Densify every class for both roles; empty role collections are no-ops.
                    point_class_roles = [
                        (int(code), role)
                        for code in class_by_code
                        for role in ("training", "validation")
                    ]
                    polygon_class_roles = list(point_class_roles)
                else:
                    working_fc = sample_fc
                    sample_meta["validation_split_mode"] = "automatic_random_split"
            except Exception:
                working_fc = sample_fc
                sample_meta["validation_split_mode"] = "automatic_random_split"
        elif not has_user_validation:
            sample_meta["validation_split_mode"] = "automatic_random_split"

        point_features = working_fc.filter(ee.Filter.eq("geometry_type", "Point"))
        sampled = stack.sampleRegions(
            collection=point_features,
            properties=sample_properties,
            scale=scale,
            geometries=True,
            tileScale=tile_scale,
        )
        # Sparse click points yield only one pixel each. Densify them by sampling
        # inside a buffer around each class/role. Larger AOIs use a slightly
        # wider buffer so isolated clicks remain trainable.
        point_buffer_m = float(max(int(scale) * 3, 30))
        if area_km2 >= 5_000:
            point_buffer_m = float(max(point_buffer_m, 90))
        elif area_km2 >= 2_000:
            point_buffer_m = float(max(point_buffer_m, 60))

        for class_code, sample_role in point_class_roles:
            point_role_features = (
                point_features
                .filter(ee.Filter.eq("landcover", int(class_code)))
                .filter(ee.Filter.eq("sample_role", sample_role))
            )
            class_item = class_by_code[int(class_code)]
            role_seed_offset = 1000 if sample_role == "validation" else 0
            point_properties = {
                "landcover": int(class_code),
                "sample_role": sample_role,
                "class_name": class_item["name"],
                "sample_source": "draw_point_buffer",
                "quality_status": "valid",
                "geometry_type": "Point",
            }
            buffered = point_role_features.geometry().buffer(point_buffer_m).intersection(geom, 1)
            point_region_samples = stack.sample(
                region=buffered,
                scale=scale,
                numPixels=options["samples_per_class"],
                seed=options["seed"] + int(class_code) + role_seed_offset + 17,
                geometries=True,
                tileScale=tile_scale,
            ).map(lambda feature: ee.Feature(feature).set(point_properties))
            sampled = sampled.merge(point_region_samples)
        for class_code, sample_role in polygon_class_roles:
            polygon_features = (
                working_fc
                .filter(ee.Filter.eq("geometry_type", "Polygon"))
                .filter(ee.Filter.eq("landcover", int(class_code)))
                .filter(ee.Filter.eq("sample_role", sample_role))
            )
            class_item = class_by_code[int(class_code)]
            role_seed_offset = 1000 if sample_role == "validation" else 0
            polygon_properties = {
                "landcover": int(class_code),
                "sample_role": sample_role,
                "class_name": class_item["name"],
                "sample_source": "draw_polygon",
                "quality_status": "valid",
                "geometry_type": "Polygon",
            }
            polygon_samples = stack.sample(
                region=polygon_features.geometry(),
                scale=scale,
                numPixels=options["samples_per_class"],
                seed=options["seed"] + int(class_code) + role_seed_offset,
                geometries=True,
                tileScale=tile_scale,
            ).map(
                lambda feature: ee.Feature(feature).set(polygon_properties)
            )
            sampled = sampled.merge(polygon_samples)
        training = sampled.filter(ee.Filter.eq("sample_role", "training"))
        validation = sampled.filter(ee.Filter.eq("sample_role", "validation"))
        sample_count, training_count, validation_count = _collection_role_counts(sampled, training, validation)
        if validation_count == 0:
            sampled = sampled.randomColumn("split", options["seed"])
            training = sampled.filter(ee.Filter.lt("split", options["training_split"]))
            validation = sampled.filter(ee.Filter.gte("split", options["training_split"]))
            sample_count, training_count, validation_count = _collection_role_counts(sampled, training, validation)
            # Tiny collections can land entirely on one side of the random split.
            if validation_count == 0 and sample_count >= 2:
                for threshold in (0.85, 0.9, 0.95):
                    training = sampled.filter(ee.Filter.lt("split", threshold))
                    validation = sampled.filter(ee.Filter.gte("split", threshold))
                    _, training_count, validation_count = _collection_role_counts(sampled, training, validation)
                    if training_count > 0 and validation_count > 0:
                        break
            sample_meta["validation_split_mode"] = sample_meta.get("validation_split_mode") or "automatic_random_split"
        elif sample_meta.get("validation_split_mode") != "feature_level_random_split":
            sample_meta["validation_split_mode"] = "user_defined"
        sample_meta.update(
            {
                "sampled_pixels_count": sample_count,
                "training_samples_count": training_count,
                "validation_samples_count": validation_count,
                "class_count": len(class_defs),
                "point_buffer_m": point_buffer_m if point_class_roles else None,
            }
        )
        if training_count >= 40 and validation_count >= 10:
            return training, validation, class_defs, sample_meta
        sample_meta["fallback_reason"] = "insufficient_user_samples_after_sampling"
        if require_user_samples:
            raise ValueError(
                "User samples produced too few valid pixels for training and validation "
                f"({training_count} training, {validation_count} validation; minimum 40 and 10). "
                "Add more point/polygon samples inside the AOI for each class."
            )

    reference = _worldcover_reference(geom)
    samples = stack.addBands(reference).stratifiedSample(
        numPoints=options["samples_per_class"],
        classBand="landcover",
        region=geom,
        scale=scale,
        seed=options["seed"],
        geometries=True,
        tileScale=tile_scale,
    ).randomColumn("split", options["seed"])
    training = samples.filter(ee.Filter.lt("split", options["training_split"]))
    validation = samples.filter(ee.Filter.gte("split", options["training_split"]))
    sample_count, training_count, validation_count = _collection_role_counts(samples, training, validation)
    sample_meta = {
        "source": "worldcover_reference",
        "reference": "ESA WorldCover v200",
        "sampled_pixels_count": sample_count,
        "training_samples_count": training_count,
        "validation_samples_count": validation_count,
        "samples_per_class": options["samples_per_class"],
        **({"fallback_reason": sample_meta.get("fallback_reason")} if sample_fc is not None and sample_meta.get("fallback_reason") else {}),
    }
    return training, validation, LAND_COVER_CLASSES, sample_meta


def _supervised_options(analysis: dict[str, Any]) -> dict[str, Any]:
    raw = analysis.get("supervised_options") or {}
    algorithm = str(raw.get("algorithm") or "random_forest").lower()
    if algorithm not in {"random_forest", "cart", "svm"}:
        algorithm = "random_forest"
    training_split = float(raw.get("training_split", 0.7))
    training_split = max(0.5, min(training_split, 0.85))
    samples_per_class = int(raw.get("samples_per_class", 160))
    samples_per_class = max(40, min(samples_per_class, 500))
    trees = int(raw.get("trees", 150))
    trees = max(50, min(trees, 500))
    return {
        "algorithm": algorithm,
        "training_split": training_split,
        "samples_per_class": samples_per_class,
        "trees": trees,
        "seed": int(raw.get("seed", 37)),
        "compare_algorithms": bool(raw.get("compare_algorithms", True)),
        "project_id": str(raw.get("project_id") or "default"),
        "class_ids": [str(value) for value in (raw.get("class_ids") or []) if str(value).strip()],
        "require_user_samples": bool(raw["require_user_samples"]) if "require_user_samples" in raw else True,
    }


def _supervised_classifier_defs(options: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "random_forest": {
            "label": "Random Forest",
            "classifier": ee.Classifier.smileRandomForest(numberOfTrees=options["trees"], seed=options["seed"]),
            "params": {"numberOfTrees": options["trees"], "seed": options["seed"]},
        },
        "cart": {
            "label": "CART",
            "classifier": ee.Classifier.smileCart(),
            "params": {},
        },
        "svm": {
            "label": "SVM",
            "classifier": ee.Classifier.libsvm(kernelType="RBF", gamma=0.5, cost=10),
            "params": {"kernelType": "RBF", "gamma": 0.5, "cost": 10},
        },
    }


def _train_supervised_classifier(defn: dict[str, Any], training: Any, input_bands: list[str]) -> Any:
    return defn["classifier"].train(
        features=training,
        classProperty="landcover",
        inputProperties=input_bands,
    )


def _compare_supervised_algorithms(
    classifier_defs: dict[str, dict[str, Any]],
    training: Any,
    validation: Any,
    input_bands: list[str],
    class_defs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    comparisons = []
    for algorithm, defn in classifier_defs.items():
        try:
            classifier = _train_supervised_classifier(defn, training, input_bands)
            metrics = _classification_accuracy(validation, classifier, class_defs)
            comparisons.append(
                {
                    "algorithm": algorithm,
                    "label": defn["label"],
                    "overall_accuracy": metrics.get("overall_accuracy"),
                    "kappa": metrics.get("kappa"),
                }
            )
        except Exception as exc:
            comparisons.append({"algorithm": algorithm, "label": defn["label"], "error": str(exc)})
    return comparisons


def _classification_vis(class_defs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    classes = class_defs or LAND_COVER_CLASSES
    codes = [int(item["code"]) for item in classes]
    minimum = min(codes)
    maximum = max(codes)
    colors_by_code = {int(item["code"]): str(item["color"]) for item in classes}
    return {
        "min": minimum,
        "max": maximum,
        "palette": [colors_by_code.get(code, "#000000") for code in range(minimum, maximum + 1)],
    }


def _compute_land_cover_classes(classified: Any, geom: Any, surface_ha: int, scale: int = 10) -> list[dict[str, Any]]:
    return _compute_categorical_classes(classified, geom, surface_ha, LAND_COVER_CLASSES, scale=scale)


def _compute_categorical_classes(classified: Any, geom: Any, surface_ha: int, class_defs: list[dict[str, Any]], scale: int = 10, analysis_crs: str | None = None) -> list[dict[str, Any]]:
    classes = []
    for item in class_defs:
        mask = classified.eq(int(item["code"]))
        area_img = ee.Image.pixelArea().divide(10000).rename("area").updateMask(mask)
        raw = area_img.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            **_metric_spatial_params(scale, analysis_crs),
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ).getInfo()
        area = round(float(raw.get("area") or 0), 2)
        classes.append(
            {
                "code": item["code"],
                "name": item["name"],
                "surface_ha": area,
                "pct": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": item["color"],
                "description": item.get("description") or "",
            }
        )
    return classes


def _compute_categorical_classes_grouped(classified: Any, geom: Any, surface_ha: int, class_defs: list[dict[str, Any]], scale: int = 30, analysis_crs: str | None = None, tile_scale: int = 4) -> list[dict[str, Any]]:
    area_by_code: dict[int, float] = {}
    try:
        area_img = ee.Image.pixelArea().divide(10000).rename("area").addBands(classified.toInt().rename("class"))
        raw = area_img.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
            geometry=geom,
            **_metric_spatial_params(scale, analysis_crs),
            bestEffort=True,
            maxPixels=1e8,
            tileScale=tile_scale,
        ).getInfo() or {}
        for group in raw.get("groups") or []:
            code = int(group.get("class"))
            area_by_code[code] = round(float(group.get("sum") or 0), 2)
    except Exception:
        return _compute_categorical_classes(classified, geom, surface_ha, class_defs, scale=scale, analysis_crs=analysis_crs)

    classes = []
    for item in class_defs:
        area = area_by_code.get(int(item["code"]), 0.0)
        classes.append(
            {
                "code": item["code"],
                "name": item["name"],
                "surface_ha": area,
                "pct": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": item["color"],
                "description": item.get("description") or "",
            }
        )
    return classes


def _matrix_vector(values: Any) -> list[float | None]:
    if values is None:
        return []
    if isinstance(values, list) and values and isinstance(values[0], list):
        values = values[0]
    if not isinstance(values, list):
        return []
    output: list[float | None] = []
    for value in values:
        try:
            output.append(round(float(value), 4))
        except Exception:
            output.append(None)
    return output


def _classification_accuracy(validation: Any, classifier: Any, class_defs: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        validated = validation.classify(classifier)
        class_order = [int(item["code"]) for item in class_defs]
        matrix = validated.errorMatrix("landcover", "classification", class_order)
        # One getInfo for matrix metrics instead of five separate round-trips.
        bundled = ee.Dictionary(
            {
                "confusion_matrix": matrix.array(),
                "producers": matrix.producersAccuracy(),
                "consumers": matrix.consumersAccuracy(),
                "overall_accuracy": matrix.accuracy(),
                "kappa": matrix.kappa(),
                "validation_count": validation.size(),
            }
        ).getInfo() or {}
        confusion_matrix = bundled.get("confusion_matrix")
        producers = _matrix_vector(bundled.get("producers"))
        consumers = _matrix_vector(bundled.get("consumers"))
        # Per-class reference counts from the confusion matrix diagonal/row sums.
        ref_counts: list[int] = []
        if isinstance(confusion_matrix, list):
            for row in confusion_matrix:
                if isinstance(row, list):
                    try:
                        ref_counts.append(int(round(sum(float(v or 0) for v in row))))
                    except Exception:
                        ref_counts.append(0)
                else:
                    ref_counts.append(0)
        class_metrics = []
        for index, item in enumerate(class_defs):
            producer = producers[index] if index < len(producers) else None
            user = consumers[index] if index < len(consumers) else None
            ref_n = ref_counts[index] if index < len(ref_counts) else None
            # Hide meaningless 0/0 accuracies for classes absent from validation.
            if ref_n == 0:
                producer = None
            class_metrics.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "producer_accuracy": producer,
                    "user_accuracy": user,
                    "omission_error": round(1 - producer, 4) if producer is not None else None,
                    "commission_error": round(1 - user, 4) if user is not None else None,
                    "validation_count": ref_n,
                }
            )
        return {
            "overall_accuracy": round(float(bundled.get("overall_accuracy") or 0), 4),
            "kappa": round(float(bundled.get("kappa") or 0), 4),
            "confusion_matrix": confusion_matrix,
            "producer_accuracy": producers,
            "user_accuracy": consumers,
            "class_metrics": class_metrics,
            "validation_samples_count": int(bundled.get("validation_count") or 0),
        }
    except Exception:
        return {"overall_accuracy": None, "kappa": None, "confusion_matrix": [], "class_metrics": []}


def _supervised_interpretation(accuracy: dict[str, Any], classes: list[dict[str, Any]], algorithm: str) -> str:
    overall = accuracy.get("overall_accuracy")
    kappa = accuracy.get("kappa")
    dominant = max(classes, key=lambda item: float(item.get("surface_ha") or 0), default=None)
    algorithm_label = {"random_forest": "Random Forest", "cart": "CART", "svm": "SVM"}.get(algorithm, algorithm)
    if overall is None:
        quality = "Validation metrics are unavailable; review training and validation samples before operational use."
    elif overall >= 0.85 and (kappa or 0) >= 0.8:
        quality = "The validation quality is high and suitable for professional land-cover interpretation."
    elif overall >= 0.7:
        quality = "The validation quality is acceptable, but classes with spectral confusion should be reviewed."
    else:
        quality = "The validation quality is low; improve samples or AOI/date selection before relying on the map."
    dominant_text = f" Dominant class: {dominant['name']} ({dominant.get('pct', 0)}%)." if dominant else ""
    return f"{algorithm_label} classification completed. {quality}{dominant_text}"


def _classified_index_image(index_image: Any, cfg: dict[str, Any], index_id: str) -> tuple[Any, dict[str, Any]]:
    """Render the map as discrete business classes using INDEX_CONFIG thresholds."""
    classes = list(cfg.get("classes") or [])
    if not classes:
        return index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}

    classified = ee.Image(0).rename(f"{index_id}_class").updateMask(index_image.mask())
    colors: list[str] = []
    for class_id, (low, high, _name, color) in enumerate(classes):
        mask = index_image.gte(float(low)).And(index_image.lt(float(high)))
        classified = classified.where(mask, class_id)
        colors.append(color)

    return classified, {"min": 0, "max": max(len(colors) - 1, 0), "palette": colors}


def _ndbi_class_masks(
    ndbi_image: Any,
    ndvi_image: Any,
    ndwi_image: Any,
    bsi_image: Any,
    built_probability_image: Any | None = None,
    bare_probability_image: Any | None = None,
    stable_built_reference: Any | None = None,
    historical_built_surface: Any | None = None,
) -> list[Any]:
    # Built-up detection should stay stricter than raw NDBI because bright dry
    # soil, rubble, and exposed land can also produce positive SWIR>NIR values.
    # We therefore require a clearer NDBI dominance over vegetation/moisture
    # signals and reject pixels with a strong bare-soil response.
    #
    # Important: arid bare soil often has HIGH NDBI (SWIR>>NIR). Do not gate the
    # bare-soil rejection on low NDBI — that previously let desert pixels with
    # NDBI>=0.10 into spectral "dense built".
    vegetation_or_water = ndvi_image.gte(0.24).Or(ndwi_image.gte(0.04))
    strong_bare_soil_risk = (
        bsi_image.gte(0.24)
        .And(ndvi_image.lt(0.18))
        .And(ndwi_image.lt(0.03))
    )
    built_signature = (
        ndbi_image.gte(0.04)
        .And(ndbi_image.gt(ndvi_image.add(0.01)))
        .And(ndbi_image.gt(ndwi_image.add(0.01)))
    )

    spectral_dense_built = (
        ndbi_image.gte(0.14)
        .And(built_signature)
        .And(ndvi_image.lt(0.22))
        .And(ndwi_image.lt(0.05))
        .And(bsi_image.lt(0.28))
        .And(strong_bare_soil_risk.Not())
    )
    spectral_probable_built = (
        ndbi_image.gte(0.08)
        .And(ndbi_image.lt(0.14))
        .And(built_signature)
        .And(ndvi_image.lt(0.26))
        .And(ndwi_image.lt(0.06))
        .And(bsi_image.lt(0.32))
        .And(strong_bare_soil_risk.Not())
    )
    spectral_low_artificialization = (
        ndbi_image.gte(0.04)
        .And(ndbi_image.lt(0.08))
        .And(built_signature)
        .And(ndvi_image.lt(0.30))
        .And(ndwi_image.lt(0.07))
        .And(bsi_image.lt(0.36))
        .And(strong_bare_soil_risk.Not())
        .And(vegetation_or_water.Not())
    )

    dense_built = spectral_dense_built
    probable_built = spectral_probable_built
    low_artificialization = spectral_low_artificialization
    if built_probability_image is not None and bare_probability_image is not None:
        # When Dynamic World says bare dominates built, do not keep a spectral
        # built label for arid mineral soils with positive NDBI.
        bare_dominated = (
            bare_probability_image.gt(built_probability_image.add(0.10))
            .And(built_probability_image.lt(0.35))
        )
        dense_built = dense_built.And(bare_dominated.Not())
        probable_built = probable_built.And(bare_dominated.Not())
        low_artificialization = low_artificialization.And(bare_dominated.Not())

        # Bright roofs can have low/negative NDBI and a strong bare-soil
        # response. Dynamic temporal probabilities rescue only pixels whose
        # built response is sufficiently confident relative to bare land.
        auxiliary_common = ndwi_image.lt(0.12).And(ndvi_image.lt(0.42))
        auxiliary_dense = (
            built_probability_image.gte(0.65)
            .And(built_probability_image.gt(bare_probability_image.add(0.05)))
            .And(auxiliary_common)
        )
        auxiliary_probable = (
            built_probability_image.gte(0.40)
            .And(built_probability_image.gt(bare_probability_image))
            .And(auxiliary_common)
        )
        auxiliary_low = (
            built_probability_image.gte(0.30)
            .And(built_probability_image.gt(bare_probability_image))
            .And(auxiliary_common)
        )
        dense_built = dense_built.Or(auxiliary_dense)
        probable_built = probable_built.Or(auxiliary_probable).And(dense_built.Not())
        low_artificialization = (
            low_artificialization
            .Or(auxiliary_low)
            .And(dense_built.Not())
            .And(probable_built.Not())
        )
    else:
        probable_built = probable_built.And(dense_built.Not())
        low_artificialization = (
            low_artificialization
            .And(dense_built.Not())
            .And(probable_built.Not())
        )

    if stable_built_reference is not None:
        stable_built = stable_built_reference.eq(1)
        # WorldCover is a supporting land-cover reference, not building
        # ground truth. In arid urban fringes it can label compacted bare
        # ground as class 50 over large areas, so it must never create a
        # built-up detection on its own.
        stable_high_confidence = stable_built.And(probable_built)
        stable_probable = stable_built.And(low_artificialization)
        dense_built = dense_built.Or(stable_high_confidence)
        probable_built = (
            probable_built
            .Or(stable_probable)
            .And(dense_built.Not())
        )
        low_artificialization = (
            low_artificialization
            .And(dense_built.Not())
            .And(probable_built.Not())
        )

    if historical_built_surface is not None:
        # GHSL stores built surface (m2) in each 10 m cell. A conservative
        # >=50 m2 threshold only recovers pixels that are still unclassified
        # after the current Sentinel-2, Dynamic World, and WorldCover logic.
        # The historical reference can therefore promote a missed bright roof
        # to "detected", but can never create a high-confidence detection.
        historical_recovery = (
            historical_built_surface.gte(50)
            .And(ndvi_image.lt(0.42))
            .And(ndwi_image.lt(0.12))
            .And(dense_built.Not())
            .And(probable_built.Not())
            .And(low_artificialization.Not())
        )
        probable_built = probable_built.Or(historical_recovery).And(dense_built.Not())
        low_artificialization = (
            low_artificialization
            .And(dense_built.Not())
            .And(probable_built.Not())
        )

    non_built = (
        dense_built.Not()
        .And(probable_built.Not())
        .And(low_artificialization.Not())
    )

    return [
        non_built,
        low_artificialization,
        probable_built,
        dense_built,
    ]


def _classified_ndbi_image(
    ndbi_image: Any,
    ndvi_image: Any,
    ndwi_image: Any,
    bsi_image: Any,
    cfg: dict[str, Any],
    built_probability_image: Any | None = None,
    bare_probability_image: Any | None = None,
    stable_built_reference: Any | None = None,
    historical_built_surface: Any | None = None,
) -> tuple[Any, dict[str, Any]]:
    classes = list(cfg.get("classes") or [])
    colors = [item[3] for item in classes]
    classified = ee.Image(0).rename("NDBI_class").updateMask(ndbi_image.mask())
    masks = _ndbi_class_masks(
        ndbi_image,
        ndvi_image,
        ndwi_image,
        bsi_image,
        built_probability_image,
        bare_probability_image,
        stable_built_reference,
        historical_built_surface,
    )
    for class_id, mask in enumerate(masks):
        classified = classified.where(mask, class_id)
    return classified, {"min": 0, "max": max(len(colors) - 1, 0), "palette": colors}


def _compute_stats(index_image: Any, index_id: str, geom: Any, surface_ha: int, scale: int = 10, analysis_crs: str | None = None) -> dict[str, Any]:
    reducer = (
        ee.Reducer.minMax()
        .combine(reducer2=ee.Reducer.mean(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
    )
    raw = index_image.reduceRegion(
        reducer=reducer,
        geometry=geom,
        **_metric_spatial_params(scale, analysis_crs),
        bestEffort=True,
        maxPixels=1e8,
        tileScale=4,
    ).getInfo()
    return {
        "min": round(float(raw.get(f"{index_id}_min", 0)), 4),
        "max": round(float(raw.get(f"{index_id}_max", 0)), 4),
        "mean": round(float(raw.get(f"{index_id}_mean", 0)), 4),
        "std": round(float(raw.get(f"{index_id}_stdDev", 0)), 4),
        "surface_ha": surface_ha,
        "pixels": int(raw.get(f"{index_id}_count", 0) or 0),
    }


def _compute_histogram(index_image: Any, index_id: str, geom: Any, cfg: dict[str, Any], scale: int = 10, analysis_crs: str | None = None) -> list[dict[str, Any]]:
    raw = index_image.reduceRegion(
        reducer=ee.Reducer.fixedHistogram(float(cfg["min"]), float(cfg["max"]), 24),
        geometry=geom,
        **_metric_spatial_params(scale, analysis_crs),
        bestEffort=True,
        maxPixels=1e8,
        tileScale=4,
    ).getInfo()
    values = raw.get(index_id) or []
    histogram = []
    for bucket in values:
        if len(bucket) >= 2:
            histogram.append({"bin": round(float(bucket[0]), 3), "count": int(bucket[1])})
    return histogram


def _compute_classes(index_image: Any, geom: Any, cfg: dict[str, Any], surface_ha: int, scale: int = 10, analysis_crs: str | None = None) -> list[dict[str, Any]]:
    # Build one categorical band and aggregate every class in a single EE
    # request. Previously one reduceRegion was executed per class, multiplying
    # the cost of NDVI/NDWI/NDBI/BSI/SAVI statistics on large AOIs.
    classified = ee.Image(0).rename("class").updateMask(index_image.mask())
    for class_id, (low, high, _name, _color) in enumerate(cfg["classes"]):
        mask = index_image.gte(float(low)).And(index_image.lt(float(high)))
        classified = classified.where(mask, class_id)
    area_img = ee.Image.pixelArea().divide(10000).rename("area").addBands(classified.toInt())
    raw = area_img.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
        geometry=geom,
        **_metric_spatial_params(scale, analysis_crs),
        bestEffort=True,
        maxPixels=1e8,
        tileScale=4,
    ).getInfo() or {}
    area_by_class = {
        int(group.get("class")): round(float(group.get("sum") or 0), 2)
        for group in raw.get("groups") or []
    }
    return [
        {
            "name": name,
            "surface_ha": area_by_class.get(class_id, 0.0),
            "pct": round((area_by_class.get(class_id, 0.0) / surface_ha) * 100, 1) if surface_ha else 0,
            "color": color,
        }
        for class_id, (_low, _high, name, color) in enumerate(cfg["classes"])
    ]


def _compute_index_summary(
    index_image: Any,
    index_id: str,
    geom: Any,
    cfg: dict[str, Any],
    surface_ha: int,
    scale: int = 10,
    analysis_crs: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve statistics, histogram and class areas in one GEE evaluation."""
    stats_reducer = (
        ee.Reducer.minMax()
        .combine(reducer2=ee.Reducer.mean(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
    )
    classified = ee.Image(0).rename("class").updateMask(index_image.mask())
    for class_id, (low, high, _name, _color) in enumerate(cfg["classes"]):
        classified = classified.where(index_image.gte(float(low)).And(index_image.lt(float(high))), class_id)
    area_image = ee.Image.pixelArea().divide(10000).rename("area").addBands(classified.toInt())
    spatial = _metric_spatial_params(scale, analysis_crs)
    summary = ee.Dictionary({
        "stats": index_image.reduceRegion(
            reducer=stats_reducer,
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
        "histogram": index_image.reduceRegion(
            reducer=ee.Reducer.fixedHistogram(float(cfg["min"]), float(cfg["max"]), 24),
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
        "classes": area_image.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
    }).getInfo() or {}
    raw_stats = summary.get("stats") or {}
    stats = {
        "min": round(float(raw_stats.get(f"{index_id}_min", 0)), 4),
        "max": round(float(raw_stats.get(f"{index_id}_max", 0)), 4),
        "mean": round(float(raw_stats.get(f"{index_id}_mean", 0)), 4),
        "std": round(float(raw_stats.get(f"{index_id}_stdDev", 0)), 4),
        "surface_ha": surface_ha,
        "pixels": int(raw_stats.get(f"{index_id}_count", 0) or 0),
    }
    histogram = [
        {"bin": round(float(bucket[0]), 3), "count": int(bucket[1])}
        for bucket in (summary.get("histogram") or {}).get(index_id, [])
        if len(bucket) >= 2
    ]
    area_by_class = {
        int(group.get("class")): round(float(group.get("sum") or 0), 2)
        for group in (summary.get("classes") or {}).get("groups", [])
    }
    classes = [
        {
            "name": name,
            "surface_ha": area_by_class.get(class_id, 0.0),
            "pct": round((area_by_class.get(class_id, 0.0) / surface_ha) * 100, 1) if surface_ha else 0,
            "color": color,
        }
        for class_id, (_low, _high, name, color) in enumerate(cfg["classes"])
    ]
    return stats, histogram, classes


def _compute_change_summary(
    delta_image: Any,
    classified: Any,
    index_id: str,
    geom: Any,
    cfg: dict[str, Any],
    surface_ha: int,
    scale: int = 10,
    analysis_crs: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve change stats, histogram and class summaries in one GEE evaluation."""
    band = delta_image.bandNames().get(0).getInfo()
    stats_reducer = (
        ee.Reducer.minMax()
        .combine(reducer2=ee.Reducer.mean(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
    )
    class_band = classified.toInt().rename("class")
    area_image = ee.Image.pixelArea().divide(10000).rename("area").addBands(class_band)
    value_image = delta_image.rename(band).addBands(class_band)
    class_value_reducer = (
        ee.Reducer.minMax()
        .combine(reducer2=ee.Reducer.mean(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.count(), sharedInputs=True)
        .group(groupField=1, groupName="class")
    )
    spatial = _metric_spatial_params(scale, analysis_crs)
    summary = ee.Dictionary({
        "stats": delta_image.reduceRegion(
            reducer=stats_reducer,
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
        "histogram": delta_image.reduceRegion(
            reducer=ee.Reducer.fixedHistogram(float(cfg["min"]), float(cfg["max"]), 24),
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
        "class_areas": area_image.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
        "class_values": value_image.reduceRegion(
            reducer=class_value_reducer,
            geometry=geom,
            **spatial,
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        ),
    }).getInfo() or {}
    raw_stats = summary.get("stats") or {}
    stats = {
        "min": round(float(raw_stats.get(f"{index_id}_min", raw_stats.get(f"{band}_min", 0)) or 0), 4),
        "max": round(float(raw_stats.get(f"{index_id}_max", raw_stats.get(f"{band}_max", 0)) or 0), 4),
        "mean": round(float(raw_stats.get(f"{index_id}_mean", raw_stats.get(f"{band}_mean", 0)) or 0), 4),
        "std": round(float(raw_stats.get(f"{index_id}_stdDev", raw_stats.get(f"{band}_stdDev", 0)) or 0), 4),
        "surface_ha": surface_ha,
        "pixels": int(raw_stats.get(f"{index_id}_count", raw_stats.get(f"{band}_count", 0)) or 0),
    }
    histogram = [
        {"bin": round(float(bucket[0]), 3), "count": int(bucket[1])}
        for bucket in (summary.get("histogram") or {}).get(index_id, [])
        if len(bucket) >= 2
    ]
    area_by_class = {
        int(group.get("class")): round(float(group.get("sum") or 0), 2)
        for group in (summary.get("class_areas") or {}).get("groups", [])
    }
    values_by_class = {
        int(group.get("class")): group
        for group in (summary.get("class_values") or {}).get("groups", [])
    }
    total_classified_area = sum(float(value or 0) for value in area_by_class.values())
    classes = []
    for code, (_low, _high, name, color) in enumerate(cfg["classes"], start=1):
        area = area_by_class.get(code, 0.0)
        raw_values = values_by_class.get(code, {})
        classes.append(
            {
                "code": code,
                "name": name,
                "surface_ha": area,
                "pixels": int(raw_values.get(f"{band}_count", raw_values.get("count", 0)) or 0),
                "mean_change": round(float(raw_values.get(f"{band}_mean", raw_values.get("mean", 0)) or 0), 4),
                "min": round(float(raw_values.get(f"{band}_min", raw_values.get("min", 0)) or 0), 4),
                "max": round(float(raw_values.get(f"{band}_max", raw_values.get("max", 0)) or 0), 4),
                "pct": round((area / total_classified_area) * 100, 1) if total_classified_area else 0,
                "pct_aoi": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": color,
            }
        )
    return stats, histogram, classes


def _compute_ndbi_classes(
    ndbi_image: Any,
    ndvi_image: Any,
    ndwi_image: Any,
    bsi_image: Any,
    geom: Any,
    cfg: dict[str, Any],
    surface_ha: int,
    scale: int = 10,
    analysis_crs: str | None = None,
    built_probability_image: Any | None = None,
    bare_probability_image: Any | None = None,
    stable_built_reference: Any | None = None,
    historical_built_surface: Any | None = None,
) -> list[dict[str, Any]]:
    masks = _ndbi_class_masks(
        ndbi_image,
        ndvi_image,
        ndwi_image,
        bsi_image,
        built_probability_image,
        bare_probability_image,
        stable_built_reference,
        historical_built_surface,
    )
    descriptions = [
        "No consistent built-up evidence in the combined observation.",
        "Spectral response compatible with roads or other impervious surfaces.",
        "Built-up evidence identified by temporal, spectral, or reference observations.",
        "Built-up evidence confirmed by multiple independent observations.",
    ]
    classified = ee.Image(0).rename("class").updateMask(ndbi_image.mask())
    for class_id, mask in enumerate(masks):
        classified = classified.where(mask, class_id)

    # Resolve all four class surfaces in one grouped reduction. This preserves
    # the exact masks while avoiding four sequential Earth Engine requests.
    area_by_class: dict[int, float] = {}
    raw = (
        ee.Image.pixelArea()
        .divide(10000)
        .rename("area")
        .addBands(classified.toInt())
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
            geometry=geom,
            **_metric_spatial_params(scale, analysis_crs),
            bestEffort=True,
            maxPixels=1e8,
            tileScale=4,
        )
        .getInfo()
        or {}
    )
    for group in raw.get("groups") or []:
        area_by_class[int(group.get("class"))] = round(float(group.get("sum") or 0), 2)

    classes = []
    areas = [area_by_class.get(idx, 0.0) for idx in range(len(cfg["classes"]))]
    total_classified_area = round(sum(areas), 2)
    for idx, ((_low, _high, name, color), area) in enumerate(zip(cfg["classes"], areas)):
        classes.append(
            {
                "name": name,
                "description": descriptions[idx] if idx < len(descriptions) else "",
                "surface_ha": area,
                "pct": round((area / total_classified_area) * 100, 1) if total_classified_area else 0,
                "pct_aoi": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": color,
            }
        )
    return classes



def _analysis_index_context(analysis: dict[str, Any]) -> tuple[Any, Any, dict[str, Any], str, Any, str]:
    """Rebuild the clipped index image and source mosaic used by map/export endpoints."""
    analysis = _normalize_payload(analysis)
    if not _ensure_gee():
        raise RuntimeError(_GEE_ERROR or "GEE unavailable")

    index_id = str(analysis.get("index", "NDVI")).upper()
    if index_id not in INDEX_CONFIG:
        raise ValueError(f"Indice {index_id} non disponible. Utilisez NDVI, NDWI, NDBI, BSI ou SAVI.")

    sensor = _sensor_id(analysis)
    mosaic = _build_analysis_mosaic(analysis)
    geom = mosaic["geom"]
    image = mosaic["image"]
    cfg = dict(INDEX_CONFIG[index_id])
    cfg["bands"] = _index_bands_for_sensor(index_id, sensor)
    index_image = _index_raster_for_analysis(image, index_id, cfg["bands"]).clip(geom)
    cfg["scale"] = _index_native_scale(index_id, sensor)
    return index_image, geom, cfg, index_id, image, sensor


def _analysis_index_image(analysis: dict[str, Any]) -> tuple[Any, Any, dict[str, Any], str]:
    """Rebuild the clipped index image used by map/export endpoints."""
    index_image, geom, cfg, index_id, _image, _sensor = _analysis_index_context(analysis)
    return index_image, geom, cfg, index_id


def _analysis_ndbi_built_detection_image(
    analysis: dict[str, Any],
) -> tuple[Any, Any, dict[str, Any], int]:
    index_image, geom, _cfg, index_id, image, sensor = _analysis_index_context(analysis)
    if index_id != "NDBI":
        raise ValueError("Built-up detection is only available from an NDBI analysis.")
    built = _ndbi_built_detection_context(analysis, image, index_image, sensor, geom)
    return built["classified"], geom, built["vis"], _analysis_scale_for_sensor(sensor)


def _analysis_classification_image(analysis: dict[str, Any]) -> tuple[Any, Any, dict[str, Any], int]:
    analysis = _normalize_payload(analysis)
    if not _ensure_gee():
        raise RuntimeError(_GEE_ERROR or "GEE unavailable")
    sensor = _sensor_id(analysis)
    if sensor not in {"sentinel-2", "landsat-8-9"}:
        raise ValueError("Supervised Classification requires Sentinel-2 or Landsat 8/9.")

    mosaic = _build_analysis_mosaic(analysis)
    geom = mosaic["geom"]
    image = mosaic["image"]
    scale = _analysis_scale_for_sensor(sensor)
    stack, input_bands = _classification_feature_stack(image, sensor)
    options = _supervised_options(analysis)
    training, _validation, class_defs, sample_meta = _build_supervised_datasets(analysis, stack, geom, scale, options)
    if int(sample_meta.get("training_samples_count") or 0) < 40:
        raise ValueError("Not enough training samples for supervised classification export.")
    classifier_def = _supervised_classifier_defs(options)[options["algorithm"]]
    classifier = _train_supervised_classifier(classifier_def, training, input_bands)
    classified = (
        stack.classify(classifier)
        .rename("landcover")
        .focal_mode(radius=1, kernelType="square", units="pixels")
        .clip(geom)
        .updateMask(stack.select(input_bands[0]).mask())
    )
    return classified, geom, _classification_vis(class_defs), scale


def _analysis_unsupervised_classification_image(analysis: dict[str, Any]) -> tuple[Any, Any, dict[str, Any], int]:
    analysis = _normalize_payload(analysis)
    if not _ensure_gee():
        raise RuntimeError(_GEE_ERROR or "GEE unavailable")
    sensor = _sensor_id(analysis)
    if sensor not in {"sentinel-2", "landsat-8-9"}:
        raise ValueError("Unsupervised Classification requires Sentinel-2 or Landsat 8/9.")

    mosaic = _build_analysis_mosaic(analysis)
    geom = mosaic["geom"]
    image = mosaic["image"]
    scale = _analysis_scale_for_sensor(sensor)
    area_km2 = _aoi_area_km2(analysis.get("aoi") or {})
    policy = classification_cost_policy(area_km2, scale)
    stack, input_bands = _unsupervised_feature_stack(image, sensor)
    options = _apply_unsupervised_cost_policy(_unsupervised_options(analysis, input_bands), policy)
    classified, class_map, _samples_count = _unsupervised_classified_image(
        stack,
        options["input_bands"],
        geom,
        scale,
        clusters_count=options["clusters_count"],
        samples_count=options["samples_count"],
        seed=options["seed"],
        feature_standardization=options["feature_standardization"],
        tile_scale=int(policy["tile_scale"]),
        cluster_stats_scale=int(policy["cluster_stats_scale_m"]),
        sample_scale=int(policy["sample_scale_m"]),
        apply_focal_mode=bool(policy.get("apply_unsupervised_focal_mode", True)),
        sensor=sensor,
    )
    return classified, geom, _unsupervised_classification_vis(_unsupervised_cluster_class_defs(class_map)), scale


def create_index_png_url(result: dict[str, Any], layer_key: str | None = None) -> str:
    """Create a GEE thumbnail URL for the computed spectral index."""
    if result.get("mode") != "gee":
        raise RuntimeError("Export PNG GEE indisponible en mode mock.")
    analysis = result.get("analysis") or {}
    if result.get("analysis_type") == "supervised_classification" or str(analysis.get("index", "")).upper() == SUPERVISED_CLASSIFICATION_ID:
        classified, geom, vis, _scale = _analysis_classification_image(analysis)
        return classified.getThumbURL(
            {
                "region": geom,
                "dimensions": 1800,
                "format": "png",
                "min": vis["min"],
                "max": vis["max"],
                "palette": vis["palette"],
                "name": "supervised_classification_map",
            }
        )
    if result.get("analysis_type") == "unsupervised_classification" or str(analysis.get("index", "")).upper() == UNSUPERVISED_CLASSIFICATION_ID:
        classified, geom, vis, _scale = _analysis_unsupervised_classification_image(analysis)
        vis = _unsupervised_result_vis(result, vis)
        return classified.getThumbURL(
            {
                "region": geom,
                "dimensions": 1800,
                "format": "png",
                "min": vis["min"],
                "max": vis["max"],
                "palette": vis["palette"],
                "name": "unsupervised_classification_map",
            }
        )
    if str(analysis.get("index", "")).upper() in CHANGE_DETECTION_IDS:
        (
            classified,
            geom,
            vis,
            _scale,
            base,
            delta,
            _image,
            _quality,
            index_1,
            index_2,
            _mosaic_1,
            _period_1_built,
            _period_2_built,
        ) = _analysis_change_detection_image(analysis)
        cfg = INDEX_VIS_CONFIG[base]
        if layer_key == f"{base.lower()}_period_1":
            image, layer_vis, _palette = _base_index_tile(base, index_1, cfg)
            return image.getThumbURL(
                {
                    "region": geom,
                    "dimensions": 1800,
                    "format": "png",
                    "min": layer_vis["min"],
                    "max": layer_vis["max"],
                    "palette": layer_vis["palette"],
                    "name": f"{base.lower()}_period_1_map",
                }
            )
        if layer_key == f"{base.lower()}_period_2":
            image, layer_vis, _palette = _base_index_tile(base, index_2, cfg)
            return image.getThumbURL(
                {
                    "region": geom,
                    "dimensions": 1800,
                    "format": "png",
                    "min": layer_vis["min"],
                    "max": layer_vis["max"],
                    "palette": layer_vis["palette"],
                    "name": f"{base.lower()}_period_2_map",
                }
            )
        return classified.getThumbURL(
            {
                "region": geom,
                "dimensions": 1800,
                "format": "png",
                "min": vis["min"],
                "max": vis["max"],
                "palette": vis["palette"],
                "name": f"change_detection_{base.lower()}_map",
            }
        )
    if str(analysis.get("index", "")).upper() == OSI_SAR_ID:
        classified, geom, vis, _scale, meta = _analysis_osi_sar_image(analysis)
        image, layer_vis = _osi_sar_visual_layer(classified, geom, vis, meta, layer_key)
        return image.getThumbURL(
            {
                "region": geom,
                "dimensions": 1800,
                "format": "png",
                "min": layer_vis["min"],
                "max": layer_vis["max"],
                "palette": layer_vis["palette"],
                "name": f"osi_sar_{(layer_key or 'oil_spill_suspects')}_map",
            }
        )
    if str(analysis.get("index", "")).upper() == "NDBI" and layer_key == "ndbi_built_detection":
        classified_image, geom, classified_vis, _scale = _analysis_ndbi_built_detection_image(analysis)
        return classified_image.getThumbURL(
            {
                "region": geom,
                "dimensions": 1800,
                "format": "png",
                "min": classified_vis["min"],
                "max": classified_vis["max"],
                "palette": classified_vis["palette"],
                "name": "ndbi_built_detection_map",
            }
        )
    index_image, geom, cfg, index_id, image, sensor = _analysis_index_context(analysis)
    if index_id == "NDBI":
        classified_image = index_image
        classified_vis = {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}
    else:
        classified_image, classified_vis = _classified_index_image(index_image, cfg, index_id)
    return classified_image.getThumbURL(
        {
            "region": geom,
            "dimensions": 1800,
            "format": "png",
            "min": classified_vis["min"],
            "max": classified_vis["max"],
            "palette": classified_vis["palette"],
            "name": f"{index_id}_classified_map",
        }
    )


def create_reference_png_url(result: dict[str, Any]) -> str:
    """Create a GEE thumbnail URL for the source RGB mosaic used in the analysis."""
    if result.get("mode") != "gee":
        raise RuntimeError("Reference PNG GEE indisponible en mode mock.")
    analysis = result.get("analysis") or {}
    if str(analysis.get("index") or "").upper() == OSI_SAR_ID:
        _classified, geom, _vis, _scale, meta = _analysis_osi_sar_image(analysis)
        return meta["vv"].updateMask(meta["valid_mask"]).clip(geom).getThumbURL(
            {
                "region": geom,
                "dimensions": 1800,
                "format": "png",
                "min": -25,
                "max": 0,
                "palette": ["#050505", "#e5e7eb"],
                "name": "osi_sar_sentinel1_vv_reference",
            }
        )
    mosaic = _build_analysis_mosaic(analysis)
    geom = mosaic["geom"]
    image = mosaic["image"]
    sensor = _sensor_id(analysis)
    return image.clip(geom).getThumbURL(
        {
            "region": geom,
            "dimensions": 1800,
            "format": "png",
            "min": _analysis_rgb_vis_for_sensor(sensor)["min"],
            "max": _analysis_rgb_vis_for_sensor(sensor)["max"],
            "gamma": _analysis_rgb_vis_for_sensor(sensor).get("gamma", 1.2),
            "bands": _analysis_rgb_vis_for_sensor(sensor)["bands"],
            "name": f"{analysis.get('index', 'analysis')}_reference_map",
        }
    )


def _direct_download_scale(result: dict[str, Any], native_scale: int) -> int:
    """Honor export resolution without claiming detail finer than the source."""
    analysis = result.get("analysis") or {}
    effective_scale = _effective_output_resolution_m(analysis, native_scale)
    stats = result.get("stats") or {}
    policy = stats.get("processing_policy") or {}
    mosaic = result.get("mosaic") or result.get("quality") or result.get("quality_summary") or {}
    area_km2 = policy.get("area_km2") or mosaic.get("area_km2")
    try:
        area_m2 = float(area_km2) * 1_000_000.0
    except (TypeError, ValueError):
        return int(effective_scale)
    if area_m2 <= 0:
        return int(effective_scale)
    target_pixels = 6_000_000
    return max(int(effective_scale), int(math.ceil(math.sqrt(area_m2 / target_pixels))))


def create_ai_rgb_geotiff_download(analysis: dict[str, Any]) -> dict[str, Any]:
    """Prepare the existing Sentinel-2 mosaic as a raw 10 m RGB GeoTIFF.

    This is deliberately a thin adapter over ``_build_analysis_mosaic``: AOI,
    collection filtering, selected-scene behavior, cloud masking and composite
    construction remain the same as the existing GeoRaster workflow.
    """
    payload = _normalize_payload(analysis)
    if _sensor_id(payload) != "sentinel-2":
        raise ValueError("La preparation raster IA actuelle accepte uniquement Sentinel-2.")

    south, west, north, east = _bbox_from_aoi(payload.get("aoi") or {})
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("AOI invalide pour la preparation du GeoTIFF RGB.")

    mosaic = _build_analysis_mosaic(payload)
    longitude = (west + east) / 2.0
    latitude = (south + north) / 2.0
    zone = max(1, min(60, int(math.floor((longitude + 180.0) / 6.0)) + 1))
    export_crs = f"EPSG:{(32600 if latitude >= 0 else 32700) + zone}"
    rgb = (
        mosaic["image"]
        .select(["B4", "B3", "B2"])
        .rename(["B4", "B3", "B2"])
        .toUint16()
        .clip(mosaic["geom"])
    )
    url = rgb.getDownloadURL(
        {
            "name": "georaster_ai_sentinel2_rgb",
            "bands": ["B4", "B3", "B2"],
            "region": mosaic["geom"],
            "scale": 10,
            "crs": export_crs,
            "format": "GEO_TIFF",
            "filePerBand": False,
        }
    )
    return {
        "url": url,
        "source": "sentinel2",
        "bands": ["B4", "B3", "B2"],
        "resolution_m": 10,
        "crs": export_crs,
        "aoi_bounds_wgs84": [west, south, east, north],
        "images_count": mosaic.get("images_count"),
        "mosaic_method": mosaic.get("method"),
    }


def create_index_geotiff_url(result: dict[str, Any], layer_key: str | None = None) -> str:
    """Create a GEE GeoTIFF download URL for the computed spectral index."""
    if result.get("mode") != "gee":
        raise RuntimeError("Export GeoTIFF GEE indisponible en mode mock.")
    analysis = result.get("analysis") or {}
    spatial_reference = analysis.get("spatial_reference") or {}
    requested_export_crs = str(
        spatial_reference.get("effective_analysis_crs")
        or spatial_reference.get("analysis_crs")
        or "EPSG:4326"
    )
    # Earth Engine accepts the WGS84/UTM equivalents for the KSA-GRF17
    # projected zones, while rejecting the national EPSG codes in
    # getDownloadURL. Keep the requested CRS in metadata and use this
    # controlled processing fallback only for the EE request.
    export_crs = _gee_metric_crs(requested_export_crs) or requested_export_crs
    if result.get("analysis_type") == "supervised_classification" or str(analysis.get("index", "")).upper() == SUPERVISED_CLASSIFICATION_ID:
        classified, geom, _vis, scale = _analysis_classification_image(analysis)
        export_scale = _direct_download_scale(result, scale)
        return classified.getDownloadURL(
            {
                "name": "supervised_classification_georaster",
                "region": geom,
                "scale": export_scale,
                "crs": export_crs,
                "format": "GEO_TIFF",
            }
        )
    if result.get("analysis_type") == "unsupervised_classification" or str(analysis.get("index", "")).upper() == UNSUPERVISED_CLASSIFICATION_ID:
        classified, geom, _vis, scale = _analysis_unsupervised_classification_image(analysis)
        export_scale = _direct_download_scale(result, scale)
        return classified.getDownloadURL(
            {
                "name": "unsupervised_classification_georaster",
                "region": geom,
                "scale": export_scale,
                "crs": export_crs,
                "format": "GEO_TIFF",
            }
        )
    if str(analysis.get("index", "")).upper() in CHANGE_DETECTION_IDS:
        (
            classified,
            geom,
            _vis,
            scale,
            base,
            delta,
            _image,
            _quality,
            index_1,
            index_2,
            _mosaic_1,
            _period_1_built,
            _period_2_built,
        ) = _analysis_change_detection_image(analysis)
        export_scale = _direct_download_scale(result, scale)
        export_image = classified
        export_name = f"change_detection_{base.lower()}_georaster"
        if layer_key == f"{base.lower()}_period_1":
            export_image = index_1
            export_name = f"{base.lower()}_period_1_float"
        elif layer_key == f"{base.lower()}_period_2":
            export_image = index_2
            export_name = f"{base.lower()}_period_2_float"
        elif layer_key == f"{base.lower()}_change_float":
            export_image = delta
            export_name = f"{base.lower()}_delta_float"
        return export_image.getDownloadURL(
            {
                "name": export_name,
                "region": geom,
                "scale": export_scale,
                "crs": export_crs,
                "format": "GEO_TIFF",
            }
        )
    if str(analysis.get("index", "")).upper() == OSI_SAR_ID:
        classified, geom, vis, scale, meta = _analysis_osi_sar_image(analysis)
        image, _layer_vis = _osi_sar_visual_layer(classified, geom, vis, meta, layer_key)
        export_scale = _direct_download_scale(result, scale)
        return image.getDownloadURL(
            {
                "name": f"osi_sar_{(layer_key or 'oil_spill_suspects')}_georaster",
                "region": geom,
                "scale": export_scale,
                "crs": export_crs,
                "format": "GEO_TIFF",
            }
        )
    if str(analysis.get("index", "")).upper() == "NDBI" and layer_key == "ndbi_built_detection":
        classified, geom, _vis, scale = _analysis_ndbi_built_detection_image(analysis)
        export_scale = _direct_download_scale(result, scale)
        return classified.toInt().getDownloadURL(
            {
                "name": "ndbi_built_detection_georaster",
                "region": geom,
                "scale": export_scale,
                "crs": export_crs,
                "format": "GEO_TIFF",
            }
        )
    index_image, geom, _cfg, index_id = _analysis_index_image(analysis)
    export_scale = _direct_download_scale(result, int(_cfg.get("scale", 10)))
    return index_image.getDownloadURL(
        {
            "name": f"{index_id}_georaster",
            "region": geom,
            "scale": export_scale,
            "crs": export_crs,
            "format": "GEO_TIFF",
        }
    )


def create_run_tile_urls(result: dict[str, Any], include_rgb: bool = True) -> dict[str, str | None]:
    """Create fresh GEE tile URLs for a stored run without recalculating its stats."""
    if result.get("mode") != "gee":
        raise RuntimeError("Live GEE tiles are unavailable in mock mode.")

    analysis = result.get("analysis") or {}
    index_key = str(analysis.get("index", "")).upper()

    if result.get("analysis_type") == "supervised_classification" or index_key == SUPERVISED_CLASSIFICATION_ID:
        classified, _geom, vis, _scale = _analysis_classification_image(analysis)
        return {"rgb_tile_url": None, "index_tile_url": _tile_url(classified, vis)}

    if result.get("analysis_type") == "unsupervised_classification" or index_key == UNSUPERVISED_CLASSIFICATION_ID:
        classified, _geom, vis, _scale = _analysis_unsupervised_classification_image(analysis)
        vis = _unsupervised_result_vis(result, vis)
        return {"rgb_tile_url": None, "index_tile_url": _tile_url(classified, vis)}

    if index_key in CHANGE_DETECTION_IDS:
        (
            classified,
            geom,
            vis,
            scale,
            _base,
            _delta,
            mosaic_2_image,
            quality,
            index_1,
            index_2,
            mosaic_1_image,
            _period_1_built_context,
            _period_2_built_context,
        ) = _analysis_change_detection_image(analysis)
        tiles = {
            "rgb_tile_url": _tile_url(mosaic_2_image.clip(geom), _analysis_rgb_vis_for_sensor(_sensor_id(analysis))) if include_rgb else None,
            "index_tile_url": _tile_url(classified, vis),
        }
        if index_key in {"CHANGE_NDVI", "CHANGE_NDWI", "CHANGE_NDBI", "CHANGE_BSI", "CHANGE_SAVI"}:
            base = _change_base_index(index_key)
            cfg = INDEX_VIS_CONFIG[base]
            base_key_lower = base.lower()
            period_1_image, period_vis, _palette = _base_index_tile(base, index_1, cfg)
            period_2_image, period_vis_2, _palette_2 = _base_index_tile(base, index_2, cfg)
            tiles["comparison_layers"] = [
                {
                    "key": f"{base_key_lower}_period_1",
                    "tiles": {
                        "index_tile_url": _tile_url(period_1_image, period_vis),
                        "rgb_tile_url": None,
                    },
                    "period": quality.get("period_1"),
                },
                {
                    "key": f"{base_key_lower}_period_2",
                    "tiles": {
                        "index_tile_url": _tile_url(period_2_image, period_vis_2),
                        "rgb_tile_url": None,
                    },
                    "period": quality.get("period_2"),
                },
                {
                    "key": f"{base_key_lower}_change",
                    "tiles": {
                        "index_tile_url": tiles["index_tile_url"],
                        "rgb_tile_url": tiles["rgb_tile_url"],
                    },
                    "period_1": quality.get("period_1"),
                    "period_2": quality.get("period_2"),
                },
            ]
        return tiles

    if index_key == OSI_SAR_ID:
        classified, geom, vis, _scale, meta = _analysis_osi_sar_image(analysis)
        vv_vis = {"min": -25, "max": 0, "palette": ["#050505", "#e5e7eb"]}
        contrast_vis = {"min": 0, "max": 6, "palette": ["#ffffcc", "#fd8d3c", "#800026"]}
        valid = meta["valid_mask"]
        return {
            "rgb_tile_url": _tile_url(meta["vv"].updateMask(valid).clip(geom), vv_vis) if include_rgb else None,
            "index_tile_url": _tile_url(classified, vis),
            "comparison_layers": [
                {"key": "osi_vv", "tiles": {"index_tile_url": _tile_url(meta["vv"].updateMask(valid).clip(geom), vv_vis), "rgb_tile_url": None}},
                {"key": "osi_vh", "tiles": {"index_tile_url": _tile_url(meta["vh"].updateMask(valid).clip(geom), vv_vis), "rgb_tile_url": None}},
                {"key": "osi_contrast", "tiles": {"index_tile_url": _tile_url(meta["contrast"].updateMask(valid).clip(geom), contrast_vis), "rgb_tile_url": None}},
                {"key": "osi_raw_candidates", "tiles": {"index_tile_url": _tile_url(meta["osi_raw"].selfMask(), {"palette": ["#d7191c"]}), "rgb_tile_url": None}},
                {"key": "osi_final_candidates", "tiles": {"index_tile_url": _tile_url(classified, vis), "rgb_tile_url": _tile_url(meta["vv"].updateMask(valid).clip(geom), vv_vis) if include_rgb else None}},
            ],
        }

    index_image, geom, cfg, index_id, image, sensor = _analysis_index_context(analysis)
    if index_id == "NDBI":
        ndvi_image, ndwi_image, bsi_image = _ndbi_support_images(image, sensor, geom)
        built_probability, bare_probability = _ndbi_built_probability_images(analysis, sensor, geom)
        stable_built_reference = _ndbi_stable_built_reference(geom)
        historical_built_surface = (
            _ndbi_historical_built_surface_reference(geom)
            if sensor == "sentinel-2"
            else None
        )
        built_cfg = dict(NDBI_BUILT_DETECTION_CONFIG)
        built_image, built_vis = _classified_ndbi_image(
            index_image,
            ndvi_image,
            ndwi_image,
            bsi_image,
            built_cfg,
            built_probability,
            bare_probability,
            stable_built_reference,
            historical_built_surface,
        )
        # Primary user-facing NDBI tile is Built-up detection (same as full compute).
        index_tile_image, index_tile_vis = built_image, built_vis
        raw_tile_url = _tile_url(
            index_image,
            {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]},
        )
    elif index_id in {"NDWI", "BSI"}:
        index_tile_image, index_tile_vis = index_image, {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}
    else:
        index_tile_image, index_tile_vis = _classified_index_image(index_image, cfg, index_id)

    tiles = {
        "rgb_tile_url": _tile_url(image.clip(geom), _analysis_rgb_vis_for_sensor(sensor)) if include_rgb else None,
        "index_tile_url": _tile_url(index_tile_image, index_tile_vis),
    }
    if index_id == "NDBI":
        tiles["comparison_layers"] = [
            {
                "key": "ndbi_raw",
                "tiles": {"index_tile_url": raw_tile_url, "rgb_tile_url": None},
            },
            {
                "key": "ndbi_built_detection",
                "tiles": {"index_tile_url": tiles["index_tile_url"], "rgb_tile_url": None},
            },
        ]
    elif index_id == "NDVI":
        tiles["comparison_layers"] = [
            {
                "key": "ndvi_raw",
                "tiles": {
                    "index_tile_url": _tile_url(
                        index_image,
                        {"min": cfg["min"], "max": cfg["max"], "palette": list(INDEX_CONFIG["NDVI"]["palette"])},
                    ),
                    "rgb_tile_url": None,
                },
            },
            {
                "key": "ndvi_classes",
                "tiles": {"index_tile_url": tiles["index_tile_url"], "rgb_tile_url": None},
            },
        ]
    return tiles

def _mock_images_for_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _normalize_payload(payload)
    max_cloud = int(payload.get("max_cloud_pct", 20))
    candidates = [img for img in IMAGES if img["cloud"] <= max_cloud]
    return candidates or IMAGES


def _mock_preview(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload(payload)
    sensor_meta = SENSOR_META[_sensor_id(payload)]
    max_cloud = int(payload.get("max_cloud_pct", 20))
    candidates = [img for img in IMAGES if img["cloud"] <= max_cloud]
    selected = min(candidates or IMAGES, key=lambda img: img["cloud"])

    return {
        "source": sensor_meta["collection"],
        "collection": sensor_meta["collection"],
        "method": payload.get("image_method", "least_cloudy"),
        "image": selected,
        "quality": {
            "available_images": len(candidates),
            "min_cloud_pct": selected["cloud"],
            "best_image_date": selected["date"],
            "warning": "GEE non configure; preview mock retournee.",
        },
        "preview": {
            "type": "xyz",
            "tile_url": None,
            "rgb_bands": ["B4", "B3", "B2"],
            "false_color_bands": ["B8", "B4", "B3"],
        },
        "gee": gee_status(),
    }
