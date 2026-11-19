from __future__ import annotations

import base64
import copy
import csv
import hashlib
import io
import json
import math
import os
import logging
import re
import threading
import uuid
import urllib.request
import urllib.error
from urllib.parse import quote, urlsplit
import time
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display as bidi_get_display

try:
    import certifi
except Exception:  # pragma: no cover
    certifi = None  # type: ignore


def _normalize_tls_certificate_env() -> None:
    fallback = None
    if certifi is not None:
        with suppress(Exception):
            fallback = certifi.where()
    if not fallback:
        fallback = os.environ.get("SSL_CERT_FILE")
    if not fallback or not Path(str(fallback)).exists():
        return
    for key in ("CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        value = os.environ.get(key)
        if value and not Path(value).exists():
            os.environ[key] = str(fallback)


_normalize_tls_certificate_env()


def _normalize_rasterio_proj_environment() -> None:
    """Prefer Rasterio's bundled PROJ database over incompatible system copies.

    Some Windows installations expose a PostgreSQL/PostGIS ``proj.db`` through
    PROJ_LIB. That database can be older than the one required by Rasterio and
    causes every CRS operation to fail before a raster reaches the AI pipeline.
    """
    try:
        import rasterio

        bundled = Path(rasterio.__file__).resolve().parent / "proj_data"
        if (bundled / "proj.db").is_file():
            os.environ["PROJ_LIB"] = str(bundled)
    except Exception:  # pragma: no cover - optional environment guard
        return


_normalize_rasterio_proj_environment()

from . import db
from .catalog import IMAGES, INDICES, SOURCES
from .platform_store import PlatformSettingsStore
from .gee_client import (
    should_prioritize_first_map,
    INDEX_CONFIG,
    _analysis_index_context,
    _analysis_rgb_vis_for_sensor,
    _classified_index_image,
    _compute_classes,
    _sensor_id,
    _tile_url,
    compute_sentinel2_index,
    create_index_geotiff_url,
    create_index_png_url,
    create_reference_png_url,
    create_run_tile_urls,
    gee_status,
    normalize_unsupervised_result_order,
    prepare_osi_sar_analysis,
    preview_sentinel2,
    search_sentinel2,
    set_classification_progress_hook,
    warm_gee_connection,
)
from .models import Analysis, AnalysisCreate, ExportCreate, ExportRef, MapPdfExportRequest, PreviewRequest, Run, RunResult
from .ai.api.ai_raster_routes import router as ai_raster_router
from .ai.api.ai_inference_routes import router as ai_inference_router
from .ai.api.ai_postprocessing_routes import router as ai_postprocessing_router
from .ai.api.ai_vectorization_routes import router as ai_vectorization_router
from .ai.api.ai_results_routes import router as ai_results_router
from .report_i18n import (
    analysis_label as _report_ar_analysis_label,
    analysis_profile as _report_ar_analysis_profile,
    default_interpretation as _report_ar_default_interpretation,
    legend_text as _report_ar_legend_text,
    normalize_language as _report_language,
    quality_conclusion as _report_ar_quality_conclusion,
    report_text as _report_text,
    value_meaning as _report_ar_value_meaning,
)
from .run_tile_cache import InMemoryRunTileCache
from .scalability import (
    ANALYSIS_CACHE_TTL_SECONDS,
    CATALOG_CACHE_TTL_SECONDS,
    cache_timestamp_is_fresh,
    surface_policy,
)
from .aoi_split import CELLS_ALONG_LENGTH, AoiSplitError, split_aoi_grid


GEE_CATALOG_JOBS: dict[str, dict[str, Any]] = {}
GEE_CATALOG_JOBS_LOCK = threading.Lock()
GEE_CATALOG_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
GEE_CATALOG_CACHE_LOCK = threading.Lock()
ANALYSIS_JOBS: dict[str, dict[str, Any]] = {}
ANALYSIS_JOBS_LOCK = threading.Lock()
ASYNC_JOB_KIND_ANALYSIS = "analysis"
ASYNC_JOB_KIND_CATALOG = "gee_catalog"
STALE_ASYNC_JOB_STATUSES = {"queued", "processing", "running"}
INTERRUPTED_JOB_MESSAGE = "Job interrupted by server restart."
RUN_TILE_CACHE = InMemoryRunTileCache()

BACKEND_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BACKEND_DIR / "uploads"
EXPORTS_DIR = BACKEND_DIR / "exports"
REPORTS_DIR = EXPORTS_DIR / "reports"
MAP_LAYOUTS_DIR = EXPORTS_DIR / "map-layouts"
PLATFORM_UPLOAD_DIR = UPLOADS_DIR / "platform"
PLATFORM_CONFIG_PATH = BACKEND_DIR / "data" / "platform_settings.json"
MAX_LOGO_BYTES = 2 * 1024 * 1024
LOGGER = logging.getLogger("georaster.report")
CURRENT_NDVI_PROCESSING_VERSION = "ndvi-gee-reference-classified-arid-v7+analysis-lazy-grid-v1"
CURRENT_NDWI_PROCESSING_VERSION = "ndwi-gee-reference-surface-water-fast-map-v7+analysis-lazy-grid-v1"
CURRENT_NDBI_PROCESSING_VERSION = "ndbi-gee-reference-20m-built-detection-ui-v19-arid-stable+analysis-lazy-grid-v1"
CURRENT_BSI_PROCESSING_VERSION = "bsi-gee-reference-20m-fast-map-v4+analysis-lazy-grid-v1"
CURRENT_SAVI_PROCESSING_VERSION = "savi-gee-reference-reflectance-continuous-v1+analysis-lazy-grid-v1"
CURRENT_CHANGE_DETECTION_PROCESSING_VERSION = "change-detection-base-index-period-layers-v2"
CURRENT_CHANGE_NDVI_PROCESSING_VERSION = f"{CURRENT_CHANGE_DETECTION_PROCESSING_VERSION}+{CURRENT_NDVI_PROCESSING_VERSION}"
CURRENT_CHANGE_NDWI_PROCESSING_VERSION = f"{CURRENT_CHANGE_DETECTION_PROCESSING_VERSION}+{CURRENT_NDWI_PROCESSING_VERSION}"
CURRENT_CHANGE_NDBI_PROCESSING_VERSION = f"{CURRENT_CHANGE_DETECTION_PROCESSING_VERSION}+{CURRENT_NDBI_PROCESSING_VERSION}"
CURRENT_CHANGE_BSI_PROCESSING_VERSION = f"{CURRENT_CHANGE_DETECTION_PROCESSING_VERSION}+{CURRENT_BSI_PROCESSING_VERSION}"
CURRENT_CHANGE_SAVI_PROCESSING_VERSION = f"{CURRENT_CHANGE_DETECTION_PROCESSING_VERSION}+{CURRENT_SAVI_PROCESSING_VERSION}"
CURRENT_SUPERVISED_PROCESSING_VERSION = "supervised-professional-v4-spatial-quality"
CURRENT_UNSUPERVISED_PROCESSING_VERSION = "unsupervised-clustering-v9-grouped-spectral-profiles"
CURRENT_OSI_SAR_PROCESSING_VERSION = "osi-sar-gee-reference-single-scene-v4"
DEFAULT_LANDCOVER_CLASSES = [
    {"code": 1, "name": "Water", "description": "Open water and permanent water surfaces.", "color": "#2b83ba"},
    {"code": 2, "name": "Natural vegetation", "description": "Shrubland, grassland, and natural vegetation.", "color": "#1a9850"},
    {"code": 3, "name": "Agriculture", "description": "Cropland, irrigated parcels, and cultivated areas.", "color": "#a6d96a"},
    {"code": 4, "name": "Forest", "description": "Tree cover and dense forest vegetation.", "color": "#006837"},
    {"code": 5, "name": "Built-up", "description": "Urban, industrial, road, and impervious surfaces.", "color": "#d7191c"},
    {"code": 6, "name": "Bare soil", "description": "Exposed soil, sand, and mineral surfaces.", "color": "#dfc27d"},
    {"code": 7, "name": "Wetlands", "description": "Wetlands, marshes, and mixed water vegetation.", "color": "#80cdc1"},
    {"code": 8, "name": "Cloud or shadow", "description": "Cloud, cloud shadow, snow, or no-data samples.", "color": "#ffffff"},
]
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
MAP_LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
PLATFORM_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PLATFORM_SETTINGS_STORE = PlatformSettingsStore(config_path=PLATFORM_CONFIG_PATH, upload_dir=PLATFORM_UPLOAD_DIR)


def _read_platform_settings() -> dict[str, Any]:
    return PLATFORM_SETTINGS_STORE.read()


def _write_platform_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return PLATFORM_SETTINGS_STORE.write(settings)


CRS_CATALOG: dict[str, dict[str, Any]] = {
    "EPSG:3857": {
        "code": "EPSG:3857",
        "name": "WGS 84 / Web Mercator",
        "unit": "metre",
        "utm_zone": None,
        "selection_mode": "web_map",
    },
    "EPSG:9333": {
        "code": "EPSG:9333",
        "name": "KSA-GRF17 geographic 2D (reference only; raster uses UTM)",
        "label": "KSA-GRF17 Geographic 2D",
        "description": "Geographic 2D reference in degrees. It is not applied to raster analysis, surfaces, or GeoTIFF exports; the effective KSA-GRF17 / UTM CRS is used instead.",
        "type": "geographic_2d",
        "dimension": 2,
        "unit": "degree",
        "utm_zone": None,
        "selection_mode": "manual_geographic_reference",
        "status": "restricted",
        "capabilities": {
            "web_map_display": False,
            "raster_analysis": False,
            "surface_calculation": False,
            "current_geotiff_export": False,
            "simulation_3d": False,
        },
    },
    "EPSG:9332": {
        "code": "EPSG:9332",
        "name": "KSA-GRF17 geographic 3D",
        "label": "KSA-GRF17 Geographic 3D",
        "description": "Geographic 3D reference using longitude, latitude and ellipsoidal height. Reserved for future 3D simulations.",
        "type": "geographic_3d",
        "dimension": 3,
        "horizontal_unit": "degree",
        "vertical_unit": "metre",
        "axes": ["geodetic latitude", "geodetic longitude", "ellipsoidal height"],
        "national_system": "SANSRS",
        "reference_frame": "KSA-GRF17",
        "status": "experimental",
        "capabilities": {"web_map_display": False, "raster_analysis": False, "surface_calculation": False, "current_geotiff_export": False, "simulation_3d": True},
        "unit": "degree",
        "utm_zone": None,
        "selection_mode": "simulation_3d",
    },
    "EPSG:9356": {
        "code": "EPSG:9356",
        "name": "KSA-GRF17 / UTM zone 36N",
        "unit": "metre",
        "utm_zone": 36,
        "selection_mode": "automatic",
    },
    "EPSG:9357": {
        "code": "EPSG:9357",
        "name": "KSA-GRF17 / UTM zone 37N",
        "unit": "metre",
        "utm_zone": 37,
        "selection_mode": "automatic",
    },
    "EPSG:9358": {
        "code": "EPSG:9358",
        "name": "KSA-GRF17 / UTM zone 38N",
        "unit": "metre",
        "utm_zone": 38,
        "selection_mode": "automatic",
    },
    "EPSG:9359": {
        "code": "EPSG:9359",
        "name": "KSA-GRF17 / UTM zone 39N",
        "unit": "metre",
        "utm_zone": 39,
        "selection_mode": "automatic",
    },
    "EPSG:9360": {
        "code": "EPSG:9360",
        "name": "KSA-GRF17 / UTM zone 40N",
        "unit": "metre",
        "utm_zone": 40,
        "selection_mode": "automatic",
    },
}
ALLOWED_MANUAL_ANALYSIS_CRS = {"EPSG:9356", "EPSG:9357", "EPSG:9358", "EPSG:9359", "EPSG:9360"}
ALLOWED_MANUAL_REFERENCE_CRS = ALLOWED_MANUAL_ANALYSIS_CRS | {"EPSG:9332", "EPSG:9333"}
AUTO_ANALYSIS_CRS = "AUTO_KSA_GRF17"


def _clean_platform_settings(settings: dict[str, Any]) -> dict[str, Any]:
    cleaned = _read_platform_settings()
    cleaned.update(
        {
            "platform_name": str(settings.get("platform_name") or cleaned.get("platform_name") or "GeoRaster"),
            "logo_url": settings.get("logo_url", cleaned.get("logo_url")),
        }
    )

    user_profile = dict(cleaned.get("user_profile") or {})
    user_profile.update({key: value for key, value in (settings.get("user_profile") or {}).items() if key in {"name", "email"}})
    cleaned["user_profile"] = {
        "name": str(user_profile.get("name") or "GIS analyst"),
        "email": str(user_profile.get("email") or "user@georaster.app"),
    }

    backend_connection = dict(cleaned.get("backend_connection") or {})
    backend_connection.update(
        {
            key: value
            for key, value in (settings.get("backend_connection") or {}).items()
            if key in {"raster_server", "endpoint", "api_key"}
        }
    )
    cleaned["backend_connection"] = {
        "raster_server": str(backend_connection.get("raster_server") or "fastapi"),
        "endpoint": str(backend_connection.get("endpoint") or "http://127.0.0.1:8010"),
        "api_key": str(backend_connection.get("api_key") or ""),
    }

    basemap = str(settings.get("default_basemap") or cleaned.get("default_basemap") or "osm")
    cleaned["default_basemap"] = basemap if basemap in {"osm", "satellite", "googleSatellite", "terrain", "light"} else "osm"

    export_format = str(settings.get("export_format") or cleaned.get("export_format") or "geotiff").lower()
    cleaned["export_format"] = export_format if export_format in {"geotiff", "png", "pdf", "csv"} else "geotiff"

    unit = str(settings.get("measurement_unit") or cleaned.get("measurement_unit") or "ha").lower()
    cleaned["measurement_unit"] = unit if unit in {"ha", "km2", "m2"} else "ha"

    projection_mode = str(settings.get("projection_mode") or cleaned.get("projection_mode") or "automatic").lower()
    cleaned["projection_mode"] = projection_mode if projection_mode in {"automatic", "manual"} else "automatic"

    cleaned["web_map_crs"] = "EPSG:3857"
    cleaned["analysis_crs"] = AUTO_ANALYSIS_CRS

    manual_crs = settings.get("manual_crs", cleaned.get("manual_crs"))
    if manual_crs is None or str(manual_crs).strip() == "":
        cleaned["manual_crs"] = None
    else:
        cleaned["manual_crs"] = str(manual_crs) if str(manual_crs) in ALLOWED_MANUAL_REFERENCE_CRS else None

    cleaned["simulation_3d_enabled"] = bool(settings.get("simulation_3d_enabled", cleaned.get("simulation_3d_enabled", False)))
    cleaned["simulation_3d_crs"] = "EPSG:9332"

    return cleaned


def _extract_aoi_longitudes(aoi: dict[str, Any] | None) -> list[float]:
    if not isinstance(aoi, dict):
        return []
    values: list[float] = []
    bbox = aoi.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 2:
        with suppress(Exception):
            values.extend([float(bbox[0][1]), float(bbox[1][1])])
    geojson = aoi.get("geojson") or {}
    coordinates = geojson.get("coordinates") or []
    try:
        if geojson.get("type") == "Polygon":
            rings = coordinates
        elif geojson.get("type") == "MultiPolygon":
            rings = [ring for polygon in coordinates for ring in polygon]
        else:
            rings = []
        for ring in rings:
            for point in ring:
                if isinstance(point, list) and len(point) >= 2:
                    values.append(float(point[0]))
    except Exception:
        return values
    return [value for value in values if math.isfinite(value)]


def _extract_aoi_latitudes(aoi: dict[str, Any] | None) -> list[float]:
    if not isinstance(aoi, dict):
        return []
    values: list[float] = []
    bbox = aoi.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 2:
        with suppress(Exception):
            values.extend([float(bbox[0][0]), float(bbox[1][0])])
    geojson = aoi.get("geojson") or {}
    coordinates = geojson.get("coordinates") or []
    try:
        if geojson.get("type") == "Polygon":
            rings = coordinates
        elif geojson.get("type") == "MultiPolygon":
            rings = [ring for polygon in coordinates for ring in polygon]
        else:
            rings = []
        for ring in rings:
            for point in ring:
                if isinstance(point, list) and len(point) >= 2:
                    values.append(float(point[1]))
    except Exception:
        return values
    return [value for value in values if math.isfinite(value)]


def _ksa_utm_crs_for_longitude(longitude: float) -> str:
    if longitude < 36.0:
        return "EPSG:9356"
    if longitude < 42.0:
        return "EPSG:9357"
    if longitude < 48.0:
        return "EPSG:9358"
    if longitude < 54.0:
        return "EPSG:9359"
    return "EPSG:9360"


def _aoi_crosses_utm_zone(aoi: dict[str, Any] | None) -> bool:
    longitudes = _extract_aoi_longitudes(aoi)
    if len(longitudes) < 2:
        return False
    return _ksa_utm_crs_for_longitude(min(longitudes)) != _ksa_utm_crs_for_longitude(max(longitudes))


def _effective_spatial_reference(
    analysis: dict[str, Any] | None,
    *,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = _clean_platform_settings(settings or _read_platform_settings())
    aoi = (analysis or {}).get("aoi") or {}
    longitudes = _extract_aoi_longitudes(aoi)
    latitudes = _extract_aoi_latitudes(aoi)
    center_lon = (min(longitudes) + max(longitudes)) / 2 if longitudes else None
    center_lat = (min(latitudes) + max(latitudes)) / 2 if latitudes else None
    crosses_zone = _aoi_crosses_utm_zone(aoi)

    projection_mode = str(settings.get("projection_mode") or "automatic")
    manual_crs = settings.get("manual_crs")
    warning: str | None = None
    selection_method = "Automatic from AOI"

    selected_reference_crs = manual_crs if projection_mode == "manual" and manual_crs in ALLOWED_MANUAL_REFERENCE_CRS else None
    if selected_reference_crs == "EPSG:9332":
        # EPSG:9332 is persisted as a 3D reference only. Raster work remains
        # on the AOI-derived projected KSA-GRF17 / UTM CRS.
        analysis_crs = _ksa_utm_crs_for_longitude(center_lon) if center_lon is not None else None
        selection_mode = "manual_simulation_reference"
        selection_method = "EPSG:9332 simulation reference; effective UTM analysis CRS"
        warning = "EPSG:9332 is selected as the 3D simulation reference. Current raster analyses and exports continue to use the effective KSA-GRF17 / UTM analysis CRS."
    elif selected_reference_crs == "EPSG:9333":
        # Geographic degrees must not drive metric reduceRegion / GeoTIFF exports.
        analysis_crs = _ksa_utm_crs_for_longitude(center_lon) if center_lon is not None else None
        selection_mode = "manual_geographic_reference"
        selection_method = "EPSG:9333 geographic reference; effective UTM analysis CRS"
        warning = "EPSG:9333 is geographic (degrees) and is not used for raster analysis, surfaces, or GeoTIFF exports. The effective KSA-GRF17 / UTM CRS is applied."
    elif projection_mode == "manual" and manual_crs in ALLOWED_MANUAL_ANALYSIS_CRS:
        analysis_crs = str(manual_crs)
        selection_mode = "manual"
        selection_method = "Manual selection"
    elif center_lon is None:
        analysis_crs = None
        selection_mode = "automatic"
        selection_method = "Waiting for AOI"
    else:
        analysis_crs = _ksa_utm_crs_for_longitude(center_lon)
        selection_mode = "automatic"

    if analysis_crs:
        crs_meta = dict(CRS_CATALOG.get(analysis_crs) or {"code": analysis_crs, "name": analysis_crs, "unit": "metre", "utm_zone": None})
    else:
        crs_meta = {"code": None, "name": "Waiting for AOI", "unit": None, "utm_zone": None}

    if crosses_zone:
        zone_warning = "The AOI crosses multiple UTM zones. GeoRaster uses the central-longitude zone for this run."
        warning = " ".join([item for item in [warning, zone_warning] if item])

    resolution = str((analysis or {}).get("resolution") or "auto")
    scale_m = {"10m": 10, "20m": 20, "30m": 30}.get(resolution)
    grid_seed = db.json_dumps({
        "crs": crs_meta.get("code"),
        "scale_m": scale_m,
        "aoi": aoi,
    })
    grid_signature = hashlib.sha256(grid_seed.encode("utf-8")).hexdigest()[:24]

    return {
        "national_system": "SANSRS",
        "reference_frame": "KSA-GRF17",
        "input_crs": "EPSG:4326",
        "web_map_crs": "EPSG:3857",
        "analysis_crs": crs_meta.get("code"),
        "analysis_crs_name": crs_meta.get("name"),
        "effective_analysis_crs": crs_meta.get("code"),
        "selected_reference_crs": selected_reference_crs,
        "selected_reference_crs_name": (CRS_CATALOG.get(selected_reference_crs) or {}).get("name") if selected_reference_crs else None,
        "selected_reference_crs_type": (CRS_CATALOG.get(selected_reference_crs) or {}).get("type") if selected_reference_crs else None,
        "simulation_crs": "EPSG:9332" if selected_reference_crs == "EPSG:9332" else None,
        "height_type": "ellipsoidal" if selected_reference_crs == "EPSG:9332" else None,
        "height_available": False if selected_reference_crs == "EPSG:9332" else None,
        "gee_analysis_crs": {
            "EPSG:9356": "EPSG:32636",
            "EPSG:9357": "EPSG:32637",
            "EPSG:9358": "EPSG:32638",
            "EPSG:9359": "EPSG:32639",
            "EPSG:9360": "EPSG:32640",
        }.get(crs_meta.get("code"), crs_meta.get("code")),
        "utm_zone": crs_meta.get("utm_zone"),
        "unit": crs_meta.get("unit"),
        "scale_m": scale_m,
        "selection_mode": selection_mode,
        "selection_method": selection_method,
        "projection_mode": projection_mode,
        "configured_analysis_crs": AUTO_ANALYSIS_CRS if projection_mode == "automatic" else manual_crs,
        "crosses_utm_zone": crosses_zone,
        "warning": warning,
        "center_longitude": round(center_lon, 6) if center_lon is not None else None,
        "center_latitude": round(center_lat, 6) if center_lat is not None else None,
        "grid_signature": grid_signature,
        "status": "Active" if crs_meta.get("code") else "Waiting for AOI",
    }


def _apply_spatial_reference_to_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(analysis or {})
    enriched["spatial_reference"] = _effective_spatial_reference(enriched)
    settings = _clean_platform_settings(_read_platform_settings())
    if settings.get("simulation_3d_enabled"):
        enriched["simulation_spatial_reference"] = {
            "crs": "EPSG:9332",
            "name": "KSA-GRF17 Geographic 3D",
            "dimension": 3,
            "horizontal_unit": "degree",
            "vertical_unit": "metre",
            "height_type": "ellipsoidal",
            "status": "configured_not_applied",
        }
    return enriched


MOCK_ANALYSIS_UNAVAILABLE = (
    "Google Earth Engine is unavailable. Mock results are not returned for operational analysis."
)


def _is_mock_result(result: dict[str, Any] | None) -> bool:
    return str((result or {}).get("mode") or "").lower() == "mock"


def _should_reuse_cached_result(result: dict[str, Any], *, gee_enabled: bool) -> bool:
    mode = str(result.get("mode") or "").lower()
    if mode == "mock":
        return False
    if result.get("tiles_stale"):
        return False
    if gee_enabled and mode == "gee" and _result_has_deferred_statistics(result):
        return False
    return True


GEE_EXPORT_URL_TIMEOUT_SECONDS = 60
GEE_UNSUPERVISED_EXPORT_URL_TIMEOUT_SECONDS = 180
GEE_EXPORT_DOWNLOAD_TIMEOUT_SECONDS = 90


def _call_with_timeout(fn: Any, timeout_seconds: float, message: str) -> Any:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            raise TimeoutError(message) from exc


def _export_storage_filename(filename: str, content_type: str) -> str:
    """Keep GEE download URLs out of .tif/.png files on disk."""
    if content_type == "application/vnd.google-earth-engine.url":
        return str(Path(filename).with_suffix(".url"))
    return filename


def _assert_admin(x_user_role: str | None) -> None:
    # MVP guard: real authentication can map user roles to this header later.
    if x_user_role and x_user_role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Seul l'administrateur peut modifier le logo.")


def _logo_extension_for_upload(content_type: str, data: bytes) -> str:
    try:
        return PLATFORM_SETTINGS_STORE.resolve_logo_extension(content_type, data)
    except ValueError as exc:
        message = str(exc)
        if "non supporte" in message:
            raise HTTPException(status_code=415, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


def _clear_platform_logos() -> None:
    PLATFORM_SETTINGS_STORE.clear_uploaded_logos()


def _persist_async_job(kind: str, job_id: str, payload: dict[str, Any]) -> None:
    stored = dict(payload)
    stored["job_id"] = job_id
    stored["kind"] = kind
    created_at = str(stored.get("created_at") or now_iso())
    updated_at = str(stored.get("updated_at") or now_iso())
    try:
        serialized = db.json_dumps(stored)
    except TypeError:
        LOGGER.warning("Could not persist async job %s (%s): payload is not JSON serializable", job_id, kind)
        return
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO async_jobs (job_id, kind, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, kind, created_at, updated_at, serialized),
        )


def _read_async_job(kind: str, job_id: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = db.fetch_one(
            conn,
            "SELECT payload_json FROM async_jobs WHERE job_id = ? AND kind = ?",
            (job_id, kind),
        )
    if not row:
        return None
    payload = db.json_loads(row["payload_json"])
    return dict(payload) if isinstance(payload, dict) else None


def _fail_interrupted_async_jobs() -> int:
    failed = 0
    updated_at = now_iso()
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT job_id, kind, payload_json FROM async_jobs")
        for row in rows:
            payload = db.json_loads(row["payload_json"])
            if not isinstance(payload, dict):
                continue
            if str(payload.get("status") or "").lower() not in STALE_ASYNC_JOB_STATUSES:
                continue
            payload["status"] = "error" if row["kind"] == ASYNC_JOB_KIND_CATALOG else "failed"
            payload["error"] = INTERRUPTED_JOB_MESSAGE
            payload["message"] = INTERRUPTED_JOB_MESSAGE
            payload["status_message"] = INTERRUPTED_JOB_MESSAGE
            payload["updated_at"] = updated_at
            conn.execute(
                "UPDATE async_jobs SET updated_at = ?, payload_json = ? WHERE job_id = ? AND kind = ?",
                (updated_at, db.json_dumps(payload), row["job_id"], row["kind"]),
            )
            failed += 1
    return failed


def _set_gee_catalog_job(job_id: str, **updates: Any) -> None:
    with GEE_CATALOG_JOBS_LOCK:
        job = GEE_CATALOG_JOBS.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = now_iso()
        snapshot = dict(job)
    _persist_async_job(ASYNC_JOB_KIND_CATALOG, job_id, snapshot)


def _get_gee_catalog_job(job_id: str) -> dict[str, Any] | None:
    with GEE_CATALOG_JOBS_LOCK:
        job = GEE_CATALOG_JOBS.get(job_id)
        if job:
            return dict(job)
    stored = _read_async_job(ASYNC_JOB_KIND_CATALOG, job_id)
    if not stored:
        return None
    with GEE_CATALOG_JOBS_LOCK:
        GEE_CATALOG_JOBS.setdefault(job_id, stored)
    return dict(stored)


def _get_cached_run_tiles(run_id: str, *, max_age_seconds: int = 1800) -> dict[str, str | None] | None:
    return RUN_TILE_CACHE.get(run_id, max_age_seconds=max_age_seconds)


def _set_cached_run_tiles(run_id: str, tiles: dict[str, str | None]) -> None:
    RUN_TILE_CACHE.set(run_id, tiles)


def _catalog_cache_key(payload: dict[str, Any], limit: int) -> str:
    relevant = {
        "aoi": payload.get("aoi") or ({"geojson": payload.get("geometry")} if payload.get("geometry") else None),
        "date_start": payload.get("date_start") or payload.get("start_date"),
        "date_end": payload.get("date_end") or payload.get("end_date"),
        "sensor": payload.get("sensor", "sentinel-2"),
        "resolution": payload.get("resolution", "auto"),
        "max_cloud_pct": payload.get("max_cloud_pct", payload.get("cloud_max", 20)),
        "limit": limit,
        # Bump when Available catalog semantics change so stale granule lists are not reused.
        "available_logic": "date-mosaic-v2",
    }
    raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _run_gee_catalog_job(job_id: str, payload: dict[str, Any], limit: int) -> None:
    def progress(percent: int, message: str, step: str) -> None:
        _set_gee_catalog_job(
            job_id,
            status="running",
            progress_percent=max(0, min(int(percent), 99 if percent < 100 else 100)),
            current_step=step,
            status_message=message,
            message=message,
        )

    try:
        cache_key = _catalog_cache_key(payload, limit)
        with GEE_CATALOG_CACHE_LOCK:
            cached = GEE_CATALOG_CACHE.get(cache_key)
        if cached and time.time() - cached[0] <= CATALOG_CACHE_TTL_SECONDS:
            result = copy.deepcopy(cached[1])
            result["cached"] = True
            _set_gee_catalog_job(
                job_id,
                status="completed",
                progress_percent=100,
                current_step="cache_hit",
                status_message="Images chargees depuis le cache",
                message="Recherche GEE reutilisee depuis le cache",
                result=result,
            )
            return
        progress(0, "Initialisation de la requete", "initialization")
        result = search_sentinel2(payload, limit=limit, progress_callback=progress)
        result["cached"] = False
        with GEE_CATALOG_CACHE_LOCK:
            GEE_CATALOG_CACHE[cache_key] = (time.time(), copy.deepcopy(result))
        _set_gee_catalog_job(
            job_id,
            status="completed",
            progress_percent=100,
            current_step="completed",
            status_message="Images pretes a l'affichage",
            message="Images GEE detectees avec succes",
            result=result,
        )
    except Exception as exc:
        _set_gee_catalog_job(
            job_id,
            status="error",
            progress_percent=100,
            current_step="error",
            status_message="Erreur lors de la detection des images GEE.",
            message=str(exc),
            error=str(exc),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _ring_area_ha(coordinates: list[list[float]]) -> float:
    if len(coordinates) < 4:
        return 0.0
    latitudes = [float(point[1]) for point in coordinates]
    mean_lat = math.radians(sum(latitudes) / len(latitudes))
    km_per_deg_lon = 111.32 * max(math.cos(mean_lat), 0.25)
    km_per_deg_lat = 110.57
    area_km2 = 0.0
    for idx in range(len(coordinates) - 1):
        x1 = float(coordinates[idx][0]) * km_per_deg_lon
        y1 = float(coordinates[idx][1]) * km_per_deg_lat
        x2 = float(coordinates[idx + 1][0]) * km_per_deg_lon
        y2 = float(coordinates[idx + 1][1]) * km_per_deg_lat
        area_km2 += (x1 * y2) - (x2 * y1)
    return abs(area_km2) * 50.0


def _geojson_area_ha(geojson: dict[str, Any]) -> int | None:
    try:
        geo_type = str(geojson.get("type") or "")
        coordinates = geojson.get("coordinates") or []
        if geo_type == "Polygon":
            if not coordinates:
                return None
            outer = _ring_area_ha(coordinates[0])
            holes = sum(_ring_area_ha(ring) for ring in coordinates[1:])
            area_ha = outer - holes
            return max(1, int(area_ha)) if area_ha > 0 else None
        if geo_type == "MultiPolygon":
            total_ha = 0.0
            for polygon in coordinates:
                if not polygon:
                    continue
                outer = _ring_area_ha(polygon[0])
                holes = sum(_ring_area_ha(ring) for ring in polygon[1:])
                total_ha += max(0.0, outer - holes)
            return max(1, int(total_ha)) if total_ha > 0 else None
    except Exception:
        return None
    return None


def area_from_bbox_ha(aoi: dict[str, Any]) -> int:
    geojson = aoi.get("geojson")
    geojson_area = _geojson_area_ha(geojson) if isinstance(geojson, dict) else None
    if geojson_area:
        return geojson_area
    bbox = aoi.get("bbox")
    if not bbox or len(bbox) != 2:
        return 1245
    try:
        (south, west), (north, east) = bbox
        mean_lat = math.radians((float(south) + float(north)) / 2)
        width_km = abs(float(east) - float(west)) * 111.32 * max(math.cos(mean_lat), 0.25)
        height_km = abs(float(north) - float(south)) * 110.57
        return max(1, int(width_km * height_km * 100))
    except Exception:
        return 1245


def training_samples_cache_fingerprint(analysis: dict[str, Any]) -> str | None:
    """Deterministic fingerprint of user training samples for supervised cache keys."""
    if analysis_kind(analysis) != "SUPERVISED_CLASSIFICATION":
        return None
    options = analysis.get("supervised_options") or {}
    project_id = str(options.get("project_id") or "default")
    selected = {str(value) for value in (options.get("class_ids") or []) if str(value).strip()}
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT id, class_id, usage, quality_status, geometry_json, created_at
            FROM training_samples
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        )
    items = []
    for row in rows:
        class_id = str(row["class_id"] or "")
        if selected and class_id not in selected:
            continue
        geometry_json = row["geometry_json"] or ""
        items.append(
            {
                "id": row["id"],
                "class_id": class_id,
                "usage": row["usage"] or "training",
                "quality_status": row["quality_status"] or "valid",
                "created_at": row["created_at"],
                "geometry_sha": hashlib.sha256(geometry_json.encode("utf-8")).hexdigest()[:20],
            }
        )
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def cache_key_for_analysis(analysis: dict[str, Any]) -> str:
    spatial_reference = analysis.get("spatial_reference")
    if not isinstance(spatial_reference, dict):
        spatial_reference = _effective_spatial_reference(analysis)
    payload = {
        "scalability_version": "selected-scene-resolution-contract-v3",
        "source": analysis.get("source"),
        "sensor": analysis.get("sensor", "sentinel-2"),
        "resolution": analysis.get("resolution", "auto"),
        "date_start": analysis.get("date_start"),
        "date_end": analysis.get("date_end"),
        "max_cloud_pct": analysis.get("max_cloud_pct"),
        "cloud_probability_threshold": analysis.get("cloud_probability_threshold", 40),
        "image_method": analysis.get("image_method"),
        "index": analysis.get("index"),
        "analysis_type": analysis.get("analysis_type"),
        "supervised_options": analysis.get("supervised_options"),
        "unsupervised_options": analysis.get("unsupervised_options"),
        "osi_sar_options": analysis.get("osi_sar_options"),
        "training_samples_fingerprint": training_samples_cache_fingerprint(analysis),
        # A selected optical scene changes the scientific input just as an
        # OSI-SAR scene does, so it must always participate in cache identity.
        "image_id": analysis.get("image_id"),
        "period_1": analysis.get("period_1"),
        "period_2": analysis.get("period_2"),
        "processing_version": processing_version_for_analysis(analysis),
        "aoi": analysis.get("aoi"),
        "analysis_crs": spatial_reference.get("analysis_crs"),
        "grid_signature": spatial_reference.get("grid_signature"),
        "selection_mode": spatial_reference.get("selection_mode"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def result_context_key_for_analysis(analysis: dict[str, Any]) -> str:
    payload = {
        "source": analysis.get("source"),
        "sensor": analysis.get("sensor", "sentinel-2"),
        "resolution": analysis.get("resolution", "auto"),
        "date_start": analysis.get("date_start"),
        "date_end": analysis.get("date_end"),
        "max_cloud_pct": analysis.get("max_cloud_pct"),
        "cloud_probability_threshold": analysis.get("cloud_probability_threshold", 40),
        "image_method": analysis.get("image_method"),
        "image_id": analysis.get("image_id"),
        "period_1": analysis.get("period_1"),
        "period_2": analysis.get("period_2"),
        "aoi": analysis.get("aoi"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def analysis_kind(analysis: dict[str, Any]) -> str:
    index = str(analysis.get("index") or "NDVI").upper()
    if str(analysis.get("analysis_type") or "").lower() == "supervised_classification":
        return "SUPERVISED_CLASSIFICATION"
    if str(analysis.get("analysis_type") or "").lower() == "unsupervised_classification":
        return "UNSUPERVISED_CLASSIFICATION"
    return index


def processing_version_for_analysis(analysis: dict[str, Any]) -> str:
    kind = analysis_kind(analysis)
    if kind == "NDVI":
        return CURRENT_NDVI_PROCESSING_VERSION
    if kind == "NDWI":
        return CURRENT_NDWI_PROCESSING_VERSION
    if kind == "NDBI":
        return CURRENT_NDBI_PROCESSING_VERSION
    if kind == "BSI":
        return CURRENT_BSI_PROCESSING_VERSION
    if kind == "SAVI":
        return CURRENT_SAVI_PROCESSING_VERSION
    if kind == "CHANGE_NDVI":
        return CURRENT_CHANGE_NDVI_PROCESSING_VERSION
    if kind == "CHANGE_NDWI":
        return CURRENT_CHANGE_NDWI_PROCESSING_VERSION
    if kind == "CHANGE_NDBI":
        return CURRENT_CHANGE_NDBI_PROCESSING_VERSION
    if kind == "CHANGE_SAVI":
        return CURRENT_CHANGE_SAVI_PROCESSING_VERSION
    if kind == "CHANGE_BSI":
        return CURRENT_CHANGE_BSI_PROCESSING_VERSION
    if kind == "SUPERVISED_CLASSIFICATION":
        return CURRENT_SUPERVISED_PROCESSING_VERSION
    if kind == "UNSUPERVISED_CLASSIFICATION":
        return CURRENT_UNSUPERVISED_PROCESSING_VERSION
    if kind == "OSI_SAR":
        return CURRENT_OSI_SAR_PROCESSING_VERSION
    if kind.startswith("CHANGE_"):
        return CURRENT_CHANGE_DETECTION_PROCESSING_VERSION
    return "default-v1"


def is_cache_row_compatible(params: dict[str, Any]) -> bool:
    kind = analysis_kind(params)
    if kind == "NDVI":
        return params.get("processing_version") == CURRENT_NDVI_PROCESSING_VERSION
    if kind == "NDWI":
        return params.get("processing_version") == CURRENT_NDWI_PROCESSING_VERSION
    if kind == "NDBI":
        return params.get("processing_version") == CURRENT_NDBI_PROCESSING_VERSION
    if kind == "BSI":
        return params.get("processing_version") == CURRENT_BSI_PROCESSING_VERSION
    if kind == "SAVI":
        return params.get("processing_version") == CURRENT_SAVI_PROCESSING_VERSION
    if kind == "CHANGE_NDVI":
        return params.get("processing_version") == CURRENT_CHANGE_NDVI_PROCESSING_VERSION
    if kind == "CHANGE_NDWI":
        return params.get("processing_version") == CURRENT_CHANGE_NDWI_PROCESSING_VERSION
    if kind == "CHANGE_NDBI":
        return params.get("processing_version") == CURRENT_CHANGE_NDBI_PROCESSING_VERSION
    if kind == "CHANGE_SAVI":
        return params.get("processing_version") == CURRENT_CHANGE_SAVI_PROCESSING_VERSION
    if kind == "CHANGE_BSI":
        return params.get("processing_version") == CURRENT_CHANGE_BSI_PROCESSING_VERSION
    if kind == "SUPERVISED_CLASSIFICATION":
        return params.get("processing_version") == CURRENT_SUPERVISED_PROCESSING_VERSION
    if kind == "UNSUPERVISED_CLASSIFICATION":
        return params.get("processing_version") == CURRENT_UNSUPERVISED_PROCESSING_VERSION
    if kind == "OSI_SAR":
        return params.get("processing_version") == CURRENT_OSI_SAR_PROCESSING_VERSION
    if kind.startswith("CHANGE_"):
        return params.get("processing_version") == CURRENT_CHANGE_DETECTION_PROCESSING_VERSION
    return True


def purge_incompatible_processing_cache() -> int:
    deleted = 0
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT cache_key, updated_at, params_json FROM processing_cache")
        for row in rows:
            params = db.json_loads(row["params_json"])
            if not is_cache_row_compatible(params) or not cache_timestamp_is_fresh(row["updated_at"]):
                conn.execute("DELETE FROM processing_cache WHERE cache_key = ?", (row["cache_key"],))
                deleted += 1
    return deleted


def ensure_default_landcover_classes() -> None:
    with db.connect() as conn:
        count = db.fetch_one(conn, "SELECT COUNT(*) AS n FROM landcover_classes")["n"]
        if count:
            return
        created_at = now_iso()
        for order, item in enumerate(DEFAULT_LANDCOVER_CLASSES, start=1):
            conn.execute(
                """
                INSERT INTO landcover_classes (id, project_id, code, name, description, color, sort_order, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    "default",
                    item["code"],
                    item["name"],
                    item["description"],
                    item["color"],
                    order,
                    1,
                    created_at,
                ),
            )


def result_layer_label(kind: str) -> str:
    labels = {
        "NDVI": "NDVI classified",
        "NDWI": "NDWI classified",
        "NDBI": "NDBI analysis",
        "BSI": "BSI classified",
        "SAVI": "SAVI",
        "OSI_SAR": "OSI-SAR oil spill suspects",
        "CHANGE_NDVI": "NDVI Change Detection",
        "CHANGE_NDWI": "NDWI Change Detection",
        "CHANGE_NDBI": "NDBI Change Detection",
        "CHANGE_BSI": "BSI Change Detection",
        "CHANGE_SAVI": "SAVI Change Detection",
        "SUPERVISED_CLASSIFICATION": "Supervised Classification",
        "UNSUPERVISED_CLASSIFICATION": "Unsupervised Classification",
    }
    return labels.get(kind, kind)


def cache_row_to_layer(row: Any) -> dict[str, Any]:
    params = db.json_loads(row["params_json"])
    result = _synchronize_result_visual_metadata(db.json_loads(row["result_json"]))
    kind = analysis_kind(params)
    stats = result.get("stats") or {}
    return {
        "cache_key": row["cache_key"],
        "analysis_id": params.get("id"),
        "user_id": params.get("user") or "local-user",
        "aoi_hash": result_context_key_for_analysis(params),
        "start_date": params.get("date_start"),
        "end_date": params.get("date_end"),
        "sensor": params.get("sensor", "sentinel-2"),
        "resolution": params.get("resolution", "auto"),
        "cloud_max": params.get("max_cloud_pct"),
        "analysis_type": result.get("analysis_type") or (
            "supervised_classification" if kind == "SUPERVISED_CLASSIFICATION"
            else "unsupervised_classification" if kind == "UNSUPERVISED_CLASSIFICATION"
            else "spectral_index"
        ),
        "index": kind,
        "name": result_layer_label(kind),
        "tile_url": (result.get("tiles") or {}).get("index_tile_url"),
        "legend": result.get("classes") or [],
        "classes": result.get("classes") or [],
        "statistics": stats,
        "stats": stats,
        "histogram": result.get("histogram") or [],
        "quality_summary": result.get("quality_summary") or result.get("quality") or result.get("mosaic"),
        "accuracy": result.get("accuracy"),
        "algorithm_comparison": result.get("algorithm_comparison"),
        "interpretation": result.get("interpretation"),
        "cluster_interpretation": result.get("cluster_interpretation"),
        "comparison_layers": result.get("comparison_layers") or [],
        "active_comparison_layer": result.get("active_comparison_layer"),
        "palette": result.get("palette"),
        "created_at": row["created_at"],
        "status": "available_from_cache",
        "cached": True,
        "run_id": result.get("latest_run_id"),
        "mode": result.get("mode"),
        "tiles": result.get("tiles"),
        "mosaic": result.get("mosaic"),
        "quality": result.get("quality"),
    }


def _synchronize_result_visual_metadata(result: dict[str, Any]) -> dict[str, Any]:
    synced = normalize_unsupervised_result_order(result)
    analysis = synced.get("analysis") or {}
    index_id = str(analysis.get("index") or "").upper()
    cfg = INDEX_CONFIG.get(index_id)
    expected_classes = list(cfg.get("classes") or []) if cfg else []
    if not expected_classes:
        return synced
    # User-facing NDBI is Built-up detection; do not overwrite with INDEX_CONFIG value ranges.
    if index_id == "NDBI":
        return synced

    classes = list(synced.get("classes") or [])
    if classes:
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(classes):
            current = dict(item)
            if idx < len(expected_classes):
                _low, _high, default_name, color = expected_classes[idx]
                current["name"] = current.get("name") or default_name
                current["color"] = color
            normalized.append(current)
        synced["classes"] = normalized

    synced["palette"] = (
        list(cfg.get("palette") or [])
        if index_id in {"NDVI", "NDWI", "BSI", "SAVI"}
        else [item[3] for item in expected_classes]
    )
    return synced


CSV_METADATA_AR = {
    "Analysis": "التحليل",
    "National system": "النظام المرجعي الوطني",
    "Reference frame": "الإطار المرجعي",
    "Input CRS": "نظام الإحداثيات المرجعي للمدخلات",
    "Analysis CRS": "نظام الإحداثيات المرجعي للتحليل",
    "Analysis CRS name": "اسم نظام الإحداثيات المرجعي للتحليل",
    "UTM zone": "نطاق UTM",
    "Unit": "الوحدة",
    "Resolution": "الدقة المكانية",
    "Projection selection mode": "طريقة اختيار الإسقاط",
    "Crosses UTM zone": "يتقاطع مع أكثر من نطاق UTM",
    "Grid signature": "بصمة الشبكة الراسترية",
    "Analysis ID": "معرّف التحليل",
    "Run ID": "معرّف التنفيذ",
}

CSV_METRICS_AR = {
    "min": "القيمة الدنيا",
    "max": "القيمة العظمى",
    "mean": "المتوسط",
    "std": "الانحراف المعياري",
    "surface_ha": "المساحة بالهكتار",
    "total_area_ha": "المساحة الإجمالية بالهكتار",
    "surface": "المساحة",
    "pixels": "عدد البكسلات",
    "valid_pixels": "عدد البكسلات الصالحة",
    "p5": "المئين 5",
    "p25": "المئين 25",
    "p50": "الوسيط",
    "p75": "المئين 75",
    "p95": "المئين 95",
    "coverage_percent": "نسبة التغطية",
    "area_km2": "المساحة بالكيلومتر المربع",
    "overall_accuracy": "الدقة الإجمالية",
    "kappa": "معامل كابا",
}


def _localized_export_value(value: Any, language: str) -> Any:
    if _report_language(language) != "ar":
        return value
    if value is None or value == "":
        return "غير متاح"
    text = str(value)
    values = {
        "Unknown": "غير معروف",
        "automatic": "تلقائي",
        "manual": "يدوي",
        "metre": "متر",
        "meter": "متر",
        "True": "نعم",
        "False": "لا",
    }
    return values.get(text, value)


def _csv_export_bytes(result: dict[str, Any], language: str = "en") -> bytes:
    language = _report_language(language)
    is_ar = language == "ar"
    buf = io.StringIO()
    # Use the standard comma separator for the Arabic export so desktop
    # spreadsheet applications open the data in distinct columns. Keep the
    # historical English format unchanged.
    writer = csv.writer(buf, delimiter="," if is_ar else ";")
    analysis = result.get("analysis") or {}
    spatial = result.get("spatial_reference") or analysis.get("spatial_reference") or {}
    run = result.get("run") or {}
    metadata = {
        "Analysis": result.get("analysis_type") or analysis.get("index") or analysis.get("analysis_type") or "Unknown",
        "National system": spatial.get("national_system", "Unknown"),
        "Reference frame": spatial.get("reference_frame", "Unknown"),
        "Input CRS": spatial.get("input_crs", "Unknown"),
        "Analysis CRS": spatial.get("analysis_crs", "Unknown"),
        "Analysis CRS name": spatial.get("analysis_crs_name", "Unknown"),
        "UTM zone": spatial.get("utm_zone", "Unknown"),
        "Unit": spatial.get("unit", "Unknown"),
        "Resolution": spatial.get("scale_m", analysis.get("resolution", "Unknown")),
        "Projection selection mode": spatial.get("selection_mode", "Unknown"),
        "Crosses UTM zone": spatial.get("crosses_utm_zone", "Unknown"),
        "Grid signature": spatial.get("grid_signature", "Unknown"),
        "Analysis ID": analysis.get("id", "Unknown"),
        "Run ID": run.get("id", result.get("run_id", "Unknown")),
    }
    metadata_section = "البيانات الوصفية" if is_ar else "metadata"
    statistics_section = "الإحصاءات" if is_ar else "stats"
    classes_section = "الفئات" if is_ar else "classes"
    histogram_section = "المدرج التكراري" if is_ar else "histogram"
    writer.writerow([metadata_section, "المفتاح" if is_ar else "key", "القيمة" if is_ar else "value"])
    for key, value in metadata.items():
        writer.writerow([metadata_section, CSV_METADATA_AR.get(key, key) if is_ar else key, _localized_export_value(value, language)])
    writer.writerow([])
    writer.writerow(["القسم" if is_ar else "section", "المؤشر الإحصائي" if is_ar else "metric", "القيمة" if is_ar else "value"])
    for key, value in (result.get("stats") or {}).items():
        writer.writerow([statistics_section, CSV_METRICS_AR.get(str(key), key) if is_ar else key, _localized_export_value(value, language)])
    writer.writerow([])
    class_headers = (
        [classes_section, "اسم الفئة", "المساحة بالهكتار", "النسبة المئوية", "عدد البكسلات", "متوسط التغير", "المتوسط", "القيمة الدنيا", "القيمة العظمى", "اللون"]
        if is_ar
        else ["classes", "name", "surface_ha", "pct", "pixels", "mean_change", "mean", "min", "max", "color"]
    )
    writer.writerow(class_headers)
    for item in result.get("classes") or []:
        writer.writerow([
            classes_section,
            _report_ar_legend_text(item.get("name") or item.get("label")) if is_ar else item.get("name"),
            item.get("surface_ha"),
            item.get("pct"),
            item.get("pixels"),
            item.get("mean_change"),
            item.get("mean"),
            item.get("min"),
            item.get("max"),
            item.get("color"),
        ])
    writer.writerow([])
    writer.writerow([histogram_section, "الفئة التكرارية" if is_ar else "bin", "العدد" if is_ar else "count"])
    for item in result.get("histogram") or []:
        writer.writerow([histogram_section, item.get("bin"), item.get("count")])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _localize_result_export(result: dict[str, Any], language: str = "en") -> dict[str, Any]:
    language = _report_language(language)
    localized = copy.deepcopy(result)
    if language != "ar":
        return localized

    def localize_legend_items(container: dict[str, Any]) -> None:
        for list_key in ("classes", "legend"):
            items = container.get(list_key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                for text_key in ("name", "label", "meaning", "description"):
                    if item.get(text_key) not in (None, ""):
                        item[text_key] = _report_ar_legend_text(item[text_key])

    localize_legend_items(localized)
    for layer in localized.get("comparison_layers") or []:
        if isinstance(layer, dict):
            localize_legend_items(layer)
    analysis_type = str(localized.get("analysis_type") or (localized.get("analysis") or {}).get("index") or "")
    if localized.get("interpretation") is not None:
        localized["interpretation"] = _report_ar_default_interpretation(analysis_type)
    quality = localized.get("quality_summary")
    if isinstance(quality, dict):
        for key in ("message", "warning", "quality"):
            if quality.get(key) not in (None, ""):
                quality[key] = _report_ar_quality_conclusion()
    return localized


def _export_analysis_type(result: dict[str, Any]) -> str:
    analysis = result.get("analysis") or {}
    return str(result.get("analysis_type") or analysis.get("index") or analysis.get("analysis_type") or "Analysis")


def _export_download_filename(kind: str, run_id: str, result: dict[str, Any], language: str = "en") -> str:
    if _report_language(language) != "ar":
        names = {
            "stats_json": f"stats_{run_id}.json",
            "stats_csv": f"stats_{run_id}.csv",
            "map_png": f"map_{run_id}.png",
            "geotiff": f"raster_{run_id}.tif",
            "report_pdf": f"report_{run_id}.pdf",
        }
        return names[kind]
    official_analysis = _analysis_pdf_slug(_export_analysis_type(result))
    token = re.sub(r"[^A-Za-z0-9]", "", str(run_id))[:12] or "export"
    names = {
        "stats_json": f"GeoRaster_إحصاءات_{official_analysis}_{token}.json",
        "stats_csv": f"GeoRaster_إحصاءات_{official_analysis}_{token}.csv",
        "map_png": f"GeoRaster_خريطة_{official_analysis}_{token}.png",
        "geotiff": f"GeoRaster_راستر_{official_analysis}_{token}.tif",
        "report_pdf": f"GeoRaster_تقرير_{official_analysis}_{token}.pdf",
    }
    return names[kind]


def _content_disposition(filename: str) -> str:
    suffix = Path(filename).suffix
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.encode("ascii", "ignore").decode("ascii")).strip("_")
    if not ascii_name or ascii_name == suffix.lstrip("."):
        ascii_name = f"GeoRaster_export{suffix}"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _export_file_path(kind: str, filename: str) -> Path:
    if kind == "report_pdf":
        folder = REPORTS_DIR
    elif kind == "map_png":
        folder = MAP_LAYOUTS_DIR
    else:
        folder = EXPORTS_DIR / "files" / kind
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def _safe_export_file_path(value: str | None) -> Path | None:
    if not value:
        return None
    with suppress(Exception):
        candidate = Path(value).expanduser().resolve(strict=False)
        exports_root = EXPORTS_DIR.resolve(strict=False)
        if candidate == exports_root or exports_root in candidate.parents:
            return candidate
    return None


def _safe_unlink_export_file(value: str | None) -> bool:
    candidate = _safe_export_file_path(value)
    if candidate is None or not candidate.is_file():
        return False
    with suppress(Exception):
        candidate.unlink()
        return True
    return False


def _pdf_escape(value: Any) -> str:
    text = str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("latin-1", "replace").decode("latin-1")


def _simple_pdf_bytes(title: str, lines: list[str]) -> bytes:
    # Small dependency-free PDF report for the MVP.
    content_lines = ["BT", "/F1 16 Tf", "50 800 Td", f"({_pdf_escape(title)}) Tj", "/F1 10 Tf", "0 -28 Td"]
    for line in lines[:45]:
        content_lines.append(f"({_pdf_escape(line)}) Tj")
        content_lines.append("0 -15 Td")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)


def _report_pdf_bytes(run_id: str, result: dict[str, Any]) -> bytes:
    analysis = result.get("analysis") or {}
    stats = result.get("stats") or {}
    accuracy = result.get("accuracy") or {}
    quality = result.get("quality_summary") or {}
    lines = [
        f"Run: {run_id}",
        f"Analysis: {analysis.get('name', '-')}",
        f"Analysis type: {result.get('analysis_type') or analysis.get('index', '-')}",
        f"Image: {analysis.get('image_id', '-')}",
        f"Period: {analysis.get('date_start', '-')} -> {analysis.get('date_end', '-')}",
        f"Mode: {result.get('mode', '-')}",
        f"Algorithme: {quality.get('classifier', '-')}",
        f"Echantillons entrainement: {quality.get('training_samples_count', '-')}",
        f"Echantillons validation: {quality.get('validation_samples_count', '-')}",
        f"Overall accuracy: {accuracy.get('overall_accuracy', '-')}",
        f"Kappa: {accuracy.get('kappa', '-')}",
        "",
        "Statistics:",
        f"Min: {stats.get('min', '-')}",
        f"Max: {stats.get('max', '-')}",
        f"Mean: {stats.get('mean', '-')}",
        f"Std dev: {stats.get('std', '-')}",
        f"Surface: {stats.get('surface_ha', '-')} ha",
        "",
        "Classes:",
    ]
    for item in result.get("classes") or []:
        lines.append(f"- {item.get('name')}: {item.get('surface_ha')} ha ({item.get('pct')}%)")
    comparisons = result.get("algorithm_comparison") or []
    if comparisons:
        lines.extend(["", "Comparaison algorithmes:"])
        for item in comparisons:
            lines.append(f"- {item.get('label')}: OA {item.get('overall_accuracy', '-')} / Kappa {item.get('kappa', '-')}")
    if accuracy.get("class_metrics"):
        lines.extend(["", "Validation par classe:"])
        for item in accuracy.get("class_metrics") or []:
            lines.append(f"- {item.get('name')}: UA {item.get('user_accuracy', '-')} / PA {item.get('producer_accuracy', '-')}")
    if result.get("interpretation"):
        lines.extend(["", "Interpretation:", str(result.get("interpretation"))])
    return _simple_pdf_bytes("GeoRaster - MVP Map Report", lines)


PDF_PAGE_SIZE = (1240, 1754)
PDF_MARGIN = 82
PDF_TEXT = "#233044"
PDF_MUTED = "#667085"
PDF_BORDER = "#d8dee8"
PDF_ACCENT = "#176d72"
REPORT_APP_VERSION = "0.2.0"


def _pdf_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _pdf_payload_language(payload: MapPdfExportRequest | None) -> str:
    return _report_language(getattr(payload, "language", "en"))


def _pdf_has_arabic(value: Any) -> bool:
    return bool(re.search(r"[\u0600-\u06ff]", str(value or "")))


def _pdf_display_text(value: Any, language: str = "en") -> str:
    text = _pdf_text(value, "")
    if _report_language(language) != "ar" or not _pdf_has_arabic(text):
        return text
    return bidi_get_display(arabic_reshaper.reshape(text))


def _pdf_text_width(draw: ImageDraw.ImageDraw, value: Any, font: ImageFont.ImageFont, language: str = "en") -> int:
    bbox = draw.textbbox((0, 0), _pdf_display_text(value, language), font=font)
    return max(0, int(bbox[2] - bbox[0]))


def _pdf_draw_text(
    draw: ImageDraw.ImageDraw,
    value: Any,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: str = PDF_TEXT,
    *,
    language: str = "en",
    right: int | None = None,
) -> None:
    rendered = _pdf_display_text(value, language)
    if _report_language(language) == "ar":
        anchor = right if right is not None else x
        x = int(anchor - _pdf_text_width(draw, value, font, language))
    draw.text((x, y), rendered, font=font, fill=fill)


def _pdf_text(value: Any, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _pdf_number(value: Any, suffix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if abs(number) >= 100:
        text = f"{number:,.0f}"
    else:
        text = f"{number:,.2f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}".replace(",", " ")


def _pdf_percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if 0 <= number <= 1:
        number *= 100
    return _pdf_number(number, "%")


def _pdf_wrap(
    draw: ImageDraw.ImageDraw,
    text: Any,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int | None = None,
    language: str = "en",
) -> list[str]:
    words = _pdf_text(text, "").replace("\n", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        bbox = draw.textbbox((0, 0), _pdf_display_text(candidate, language), font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if max_lines and len(lines) >= max_lines:
            break
    if current and (not max_lines or len(lines) < max_lines):
        lines.append(current)
    if max_lines and len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = f"{lines[-1].rstrip('.')}..."
    return lines


def _pdf_draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: Any,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str = PDF_TEXT,
    line_gap: int = 7,
    max_lines: int | None = None,
    language: str = "en",
    align: str | None = None,
) -> int:
    resolved_align = align or ("right" if _report_language(language) == "ar" else "left")
    for line in _pdf_wrap(draw, text, font, max_width, max_lines=max_lines, language=language):
        rendered = _pdf_display_text(line, language)
        line_x = x
        if resolved_align == "right":
            line_x = x + max_width - _pdf_text_width(draw, line, font, language)
        draw.text((line_x, y), rendered, font=font, fill=fill)
        y += font.size + line_gap
    return y


def _pdf_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    page = Image.new("RGB", PDF_PAGE_SIZE, "white")
    return page, ImageDraw.Draw(page)


def _pdf_logo_image() -> Image.Image | None:
    logo_url = _read_platform_settings().get("logo_url")
    if not isinstance(logo_url, str) or not logo_url.startswith("/uploads/"):
        return None
    parsed = urlsplit(logo_url)
    logo_path = BACKEND_DIR / parsed.path.lstrip("/")
    if not logo_path.exists():
        return None
    try:
        logo = ImageOps.exif_transpose(Image.open(logo_path))
        if logo.mode in {"RGBA", "LA"}:
            bg = Image.new("RGB", logo.size, "white")
            bg.paste(logo, mask=logo.getchannel("A"))
            logo = bg
        return logo.convert("RGB")
    except Exception:
        return None


def _pdf_logo_fitted(max_width: int, max_height: int) -> Image.Image | None:
    logo = _pdf_logo_image()
    if logo is None:
        return None
    fitted = logo.copy()
    fitted.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return fitted


def _pdf_draw_header(
    draw: ImageDraw.ImageDraw,
    page: Image.Image,
    title: str,
    subtitle: str,
    page_number: int,
    language: str = "en",
) -> None:
    logo = _pdf_logo_fitted(96, 60)
    x = PDF_MARGIN
    y = 54
    is_ar = _report_language(language) == "ar"
    if is_ar:
        brand_right = PDF_PAGE_SIZE[0] - PDF_MARGIN
        if logo:
            logo_x = brand_right - logo.width
            page.paste(logo, (logo_x, y))
        else:
            logo_x = brand_right - 74
            draw.rounded_rectangle((logo_x, y, brand_right, y + 54), radius=10, fill="#e7f4f2", outline="#9bd3cf")
            draw.text((logo_x + 14, y + 12), "GR", font=_pdf_font(24, True), fill=PDF_ACCENT)
        brand_text_right = logo_x - 18
        _pdf_draw_text(draw, "GeoRaster", brand_text_right, y, _pdf_font(26, True), PDF_TEXT, language=language, right=brand_text_right)
        _pdf_draw_text(draw, subtitle, brand_text_right, y + 34, _pdf_font(15), PDF_MUTED, language=language, right=brand_text_right)
        badge_rect = (PDF_MARGIN + 14, y + 6, PDF_MARGIN + 150, y + 44)
        badge_text_right = PDF_MARGIN + 138
    elif logo:
        page.paste(logo, (x, y))
    else:
        draw.rounded_rectangle((x, y, x + 74, y + 54), radius=10, fill="#e7f4f2", outline="#9bd3cf")
        draw.text((x + 14, y + 12), "GR", font=_pdf_font(24, True), fill=PDF_ACCENT)
    if not is_ar:
        draw.text((x + 92, y), "GeoRaster", font=_pdf_font(26, True), fill=PDF_TEXT)
        draw.text((x + 92, y + 34), subtitle, font=_pdf_font(15), fill=PDF_MUTED)
        badge_rect = (PDF_PAGE_SIZE[0] - PDF_MARGIN - 150, y + 6, PDF_PAGE_SIZE[0] - PDF_MARGIN - 14, y + 44)
        badge_text_right = PDF_PAGE_SIZE[0] - PDF_MARGIN - 26
    draw.rounded_rectangle(badge_rect, radius=12, fill="#eef6f6", outline="#bfe0de")
    page_label = f"{_report_text('Page', language)} {page_number}"
    _pdf_draw_text(
        draw,
        page_label,
        badge_text_right,
        y + 14,
        _pdf_font(13, True),
        PDF_ACCENT,
        language=language,
        right=badge_text_right,
    )
    draw.line((PDF_MARGIN, 132, PDF_PAGE_SIZE[0] - PDF_MARGIN, 132), fill=PDF_BORDER, width=2)
    draw.rectangle((PDF_MARGIN, 132, PDF_MARGIN + 82, 138), fill=PDF_ACCENT)
    if _report_language(language) == "ar":
        _pdf_draw_text(draw, title, PDF_PAGE_SIZE[0] - PDF_MARGIN, 154, _pdf_font(25, True), PDF_TEXT, language=language, right=PDF_PAGE_SIZE[0] - PDF_MARGIN)
    else:
        draw.text((PDF_MARGIN, 154), title, font=_pdf_font(25, True), fill=PDF_TEXT)


def _pdf_draw_footer(draw: ImageDraw.ImageDraw, generated_at: str, page_number: int, language: str = "en") -> None:
    y = PDF_PAGE_SIZE[1] - 72
    draw.line((PDF_MARGIN, y - 18, PDF_PAGE_SIZE[0] - PDF_MARGIN, y - 18), fill=PDF_BORDER, width=1)
    footer = _report_text("GeoRaster Analytics Platform - Report automatically generated from raster analysis results.", language)
    if _report_language(language) == "ar":
        _pdf_draw_text(draw, footer, PDF_PAGE_SIZE[0] - PDF_MARGIN - 224, y, _pdf_font(12), PDF_MUTED, language=language, right=PDF_PAGE_SIZE[0] - PDF_MARGIN - 224)
    else:
        draw.text((PDF_MARGIN, y), footer, font=_pdf_font(12), fill=PDF_MUTED)
    draw.rounded_rectangle((PDF_PAGE_SIZE[0] - PDF_MARGIN - 206, y - 4, PDF_PAGE_SIZE[0] - PDF_MARGIN, y + 22), radius=10, fill="#f5f8fb", outline="#d7e0ea")
    stamp = f"{generated_at}  •  {_report_text('Page', language)} {page_number}"
    _pdf_draw_text(draw, stamp, PDF_PAGE_SIZE[0] - PDF_MARGIN - 18, y + 2, _pdf_font(12), PDF_MUTED, language=language, right=PDF_PAGE_SIZE[0] - PDF_MARGIN - 18)


def _pdf_section(draw: ImageDraw.ImageDraw, title: str, y: int) -> int:
    draw.rounded_rectangle((PDF_MARGIN, y, PDF_MARGIN + 8, y + 32), radius=4, fill=PDF_ACCENT)
    draw.text((PDF_MARGIN + 18, y + 1), title, font=_pdf_font(20, True), fill=PDF_TEXT)
    return y + 44


def _pdf_kv_table(
    draw: ImageDraw.ImageDraw,
    rows: list[tuple[str, Any]],
    x: int,
    y: int,
    width: int,
    row_h: int = 42,
    language: str = "en",
) -> int:
    label_font = _pdf_font(13, True)
    value_font = _pdf_font(13)
    label_w = int(width * 0.35)
    for index, (label, value) in enumerate(rows):
        top = y + index * row_h
        fill = "#f8fafc" if index % 2 == 0 else "white"
        draw.rectangle((x, top, x + width, top + row_h), fill=fill, outline=PDF_BORDER)
        if _report_language(language) == "ar":
            label_text = _report_text(label, language)
            _pdf_draw_text(draw, label_text, x + width - 14, top + 12, label_font, PDF_MUTED, language=language, right=x + width - 14)
            _pdf_draw_wrapped(draw, value, x + 14, top + 10, width - label_w - 28, value_font, max_lines=1, language=language, align="right")
        else:
            draw.text((x + 14, top + 12), label, font=label_font, fill=PDF_MUTED)
            _pdf_draw_wrapped(draw, value, x + label_w, top + 10, width - label_w - 18, value_font, max_lines=1)
    return y + len(rows) * row_h


def _pdf_color(value: Any) -> tuple[int, int, int]:
    try:
        return ImageColor.getrgb(str(value))
    except Exception:
        return (180, 190, 200)


def _decode_map_screenshot(data_url: str) -> Image.Image:
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") and "," in data_url else data_url
    try:
        data = base64.b64decode(raw, validate=False)
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid map screenshot.") from exc
    if image.mode in {"RGBA", "LA"}:
        bg = Image.new("RGB", image.size, "white")
        bg.paste(image, mask=image.getchannel("A"))
        image = bg
    return image.convert("RGB")


def _fit_pdf_image(image: Image.Image, max_w: int, max_h: int, *, upscale: bool = False) -> Image.Image:
    src = image.copy()
    if src.width <= 0 or src.height <= 0:
        return src
    ratio = min(max_w / src.width, max_h / src.height)
    if not upscale:
        ratio = min(ratio, 1.0)
    new_w = max(1, int(round(src.width * ratio)))
    new_h = max(1, int(round(src.height * ratio)))
    if new_w == src.width and new_h == src.height:
        return src
    return src.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _analysis_pdf_label(value: str, language: str = "en") -> str:
    if _report_language(language) == "ar":
        return _report_ar_analysis_label(value)
    labels = {
        "NDVI": "NDVI",
        "NDWI": "NDWI",
        "NDBI": "NDBI",
        "BSI": "BSI",
        "SAVI": "SAVI",
        "OSI_SAR": "OSI-SAR Oil Spill Suspect Index",
        "CHANGE_NDVI": "NDVI Change Detection",
        "CHANGE_NDWI": "NDWI Change Detection",
        "CHANGE_NDBI": "NDBI Change Detection",
        "CHANGE_BSI": "BSI Change Detection",
        "CHANGE_SAVI": "SAVI Change Detection",
        "SUPERVISED_CLASSIFICATION": "Supervised Classification",
        "UNSUPERVISED_CLASSIFICATION": "Unsupervised Classification",
        "supervised_classification": "Supervised Classification",
        "unsupervised_classification": "Unsupervised Classification",
        "oil_spill_suspect_index": "OSI-SAR Oil Spill Suspect Index",
        "change_detection_ndvi": "NDVI Change Detection",
        "change_detection_ndwi": "NDWI Change Detection",
        "change_detection_ndbi": "NDBI Change Detection",
        "change_detection_bsi": "BSI Change Detection",
        "change_detection_savi": "SAVI Change Detection",
    }
    return labels.get(value, value)


def _analysis_pdf_class_label(value: Any, language: str = "en") -> str:
    text = _pdf_text(value)
    if _report_language(language) == "ar":
        return _report_ar_legend_text(text)
    labels = {
        "Absence ou tres faible couverture vegetale": "No or very sparse vegetation cover",
        "Couverture vegetale faible": "Sparse vegetation cover",
        "Couverture vegetale moyenne": "Moderate vegetation cover",
        "Couverture vegetale forte": "Dense vegetation cover",
        "Couverture vegetale tres forte": "Very dense vegetation cover",
        "Absence or very low vegetation cover": "No or very sparse vegetation cover",
        "Low vegetation cover": "Sparse vegetation cover",
        "Medium vegetation cover": "Moderate vegetation cover",
        "High vegetation cover": "Dense vegetation cover",
        "Very high vegetation cover": "Very dense vegetation cover",
    }
    return labels.get(text, text)


def _analysis_pdf_slug(value: str) -> str:
    label = _analysis_pdf_label(value)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
    return slug or "Analysis"


ANALYSIS_SCIENCE_LIBRARY: dict[str, dict[str, str]] = {
    "NDVI": {
        "full_name": "Normalized Difference Vegetation Index (NDVI)",
        "principle": "Computed from the contrast between near-infrared and red reflectance to quantify the presence and vigor of photosynthetically active vegetation.",
        "bands": "Sentinel-2: B8 (NIR) and B4 (Red). Landsat 8/9: SR_B5 (NIR) and SR_B4 (Red).",
        "objective": "Assess vegetation density, vigor, and spatial variability across the study area.",
        "interpretation": "Low values generally indicate bare soil, sparse cover, or non-vegetated surfaces, while high values indicate dense, healthy, or actively growing vegetation.",
        "applications": "Vegetation monitoring, agricultural assessment, ecosystem condition mapping, and drought or degradation analysis.",
    },
    "NDWI": {
        "full_name": "Normalized Difference Water Index (NDWI)",
        "principle": "Uses the green and near-infrared contrast to map continuous surface-water spectral response.",
        "bands": "Sentinel-2: B3 (Green) and B8 (NIR). Landsat 8/9: SR_B3 (Green) and SR_B5 (NIR).",
        "objective": "Highlight pixels with stronger water response while keeping the scientific raster as raw NDWI float values.",
        "interpretation": "Negative values generally indicate dry land or non-water surfaces; positive values are water-compatible but not automatically certain water in every context.",
        "applications": "Surface-water screening, flood monitoring, wetland studies, reservoir mapping, and hydrological change analysis.",
    },
    "NDBI": {
        "full_name": "Normalized Difference Built-up Index (NDBI)",
        "principle": "Computes the floating SWIR-to-NIR normalized difference response; positive values are not automatically built-up in arid landscapes.",
        "bands": "Sentinel-2: B11 (SWIR1, 20 m) and B8 (NIR). Landsat 8/9: SR_B6 (SWIR) and SR_B5 (NIR).",
        "objective": "Map the continuous NDBI spectral response and support built-up interpretation only with complementary evidence.",
        "interpretation": "Positive NDBI response can indicate built-up, impervious, exposed mineral, or bare surfaces; verify with vegetation, water, and bare-soil information before interpreting it as urban.",
        "applications": "Spectral response validation, urban screening, arid-land surface interpretation, and impervious-surface assessment with supporting layers.",
    },
    "BSI": {
        "full_name": "Bare Soil Index (BSI)",
        "principle": "Integrates visible, near-infrared, and short-wave infrared reflectance to separate exposed soil from vegetated or wetter surfaces.",
        "bands": "Sentinel-2: B11, B4, B8, and B2. Landsat 8/9: SR_B6, SR_B4, SR_B5, and SR_B2.",
        "objective": "Highlight exposed soil, dry terrain, sand, and sparsely covered land.",
        "interpretation": "Low values indicate vegetated, moist, or water-influenced surfaces, while high values indicate strong soil exposure or dry bare ground.",
        "applications": "Soil exposure mapping, erosion and degradation studies, mining or construction monitoring, and arid-land assessment.",
    },
    "SAVI": {
        "full_name": "Soil-Adjusted Vegetation Index (SAVI)",
        "principle": "A vegetation index designed to reduce soil background influence by applying a canopy-adjustment factor to the red and near-infrared contrast.",
        "bands": "Sentinel-2: B8 (NIR) and B4 (Red). Landsat 8/9: SR_B5 (NIR) and SR_B4 (Red).",
        "objective": "Measure vegetation cover and vigor in areas where soil reflectance strongly influences NDVI.",
        "interpretation": "Low values indicate sparse vegetation, exposed soil, or weak photosynthetic activity, while high values indicate denser and healthier vegetation cover.",
        "applications": "Semi-arid environments, sparse vegetation mapping, agricultural monitoring, and land degradation studies.",
    },
    "CHANGE_NDVI": {
        "full_name": "NDVI Change Detection",
        "principle": "Compares NDVI between two dates or periods to map directional changes in vegetation vigor and cover.",
        "bands": "Derived from the same NIR and Red bands used for NDVI in both periods.",
        "objective": "Detect vegetation loss, stability, or gain through temporal comparison.",
        "interpretation": "Negative values indicate loss of vegetation cover or vigor, values near zero indicate stability, and positive values indicate vegetation gain or recovery.",
        "applications": "Deforestation monitoring, seasonal change analysis, restoration tracking, and agricultural dynamics.",
    },
    "CHANGE_NDWI": {
        "full_name": "NDWI Change Detection",
        "principle": "Measures temporal variation in NDWI to identify changes in water extent or surface moisture.",
        "bands": "Derived from Green and NIR bands in each compared period.",
        "objective": "Track water gain, water loss, or moisture variation over time.",
        "interpretation": "Negative values suggest drying or water loss, values near zero suggest stable moisture conditions, and positive values suggest increased water presence or wetness.",
        "applications": "Flood change analysis, wetland monitoring, reservoir dynamics, and hydrological observation.",
    },
    "CHANGE_NDBI": {
        "full_name": "NDBI Change Detection",
        "principle": "Applies the validated continuous NDBI pipeline independently to both periods, then computes FLOAT NDBI_P2 minus NDBI_P1.",
        "bands": "Derived from SWIR1 (B11) and NIR (B8) in each period, using the same NDBI formula as the simple analysis.",
        "objective": "Map decrease, stability, or increase of the NDBI spectral response.",
        "interpretation": "Negative values indicate a weaker NDBI response, values near zero indicate stability, and positive values indicate a stronger NDBI response. This is not confirmed new construction, because bare soil can also raise NDBI.",
        "applications": "Urban expansion screening, infrastructure change mapping, and land-use transition studies with independent verification.",
    },
    "CHANGE_BSI": {
        "full_name": "BSI Change Detection",
        "principle": "Compares bare-soil spectral response across two periods to reveal changes in exposed ground.",
        "bands": "Derived from visible, NIR, and SWIR bands in each period.",
        "objective": "Detect increases or decreases in bare soil exposure.",
        "interpretation": "Negative values indicate reduced bare-soil exposure, values near zero indicate stability, and positive values indicate increased soil exposure.",
        "applications": "Land degradation monitoring, construction impact assessment, erosion analysis, and soil exposure studies.",
    },
    "CHANGE_SAVI": {
        "full_name": "SAVI Change Detection",
        "principle": "Compares soil-adjusted vegetation response between two periods to reduce soil background influence in temporal vegetation change analysis.",
        "bands": "Derived from NIR and Red bands in each compared period.",
        "objective": "Detect vegetation loss, stability, or gain in semi-arid or sparsely vegetated environments.",
        "interpretation": "Negative values indicate vegetation decline, values near zero indicate stability, and positive values indicate vegetation recovery or increase.",
        "applications": "Vegetation recovery studies, agricultural change monitoring, and dryland environmental assessment.",
    },
    "SUPERVISED_CLASSIFICATION": {
        "full_name": "Supervised Land-Cover Classification",
        "principle": "Uses labeled training data and spectral predictors to assign each pixel to a predefined thematic class.",
        "bands": "Spectral bands and derived indices selected by the processing pipeline, typically including visible, NIR, SWIR, NDVI, NDWI, NDBI, BSI, and SAVI.",
        "objective": "Generate a thematic land-cover map for the selected area of interest.",
        "interpretation": "Class values are categorical, so interpretation depends on the legend rather than numeric order.",
        "applications": "Land-cover mapping, environmental planning, urban studies, agriculture, and spatial decision support.",
    },
    "UNSUPERVISED_CLASSIFICATION": {
        "full_name": "Unsupervised Land-Cover Classification",
        "principle": "Groups pixels by spectral similarity without prior training labels.",
        "bands": "Spectral bands and derived indices selected by the processing pipeline, typically including visible, NIR, SWIR, NDVI, NDWI, NDBI, BSI, and SAVI.",
        "objective": "Discover dominant spectral patterns and generate exploratory land-cover groupings.",
        "interpretation": "Cluster numbers are internal identifiers; interpretation relies on the legend and thematic behavior of each cluster.",
        "applications": "Exploratory mapping, rapid land-cover reconnaissance, and pre-classification analysis.",
    },
    "OSI_SAR": {
        "full_name": "OSI-SAR Oil Spill Suspect Index",
        "principle": "Analyzes one Sentinel-1 IW VV/VH acquisition in dB. A pixel is an OSI-SAR candidate only if VV < -18 dB AND VH < -25 dB AND local contrast >= 2.5 dB, after incidence and water masks.",
        "bands": "Sentinel-1 VV, VH, and incidence angle, with 500 m local contrast and connected-component filtering.",
        "objective": "Map Potential Oil Slick Candidates / OSI-SAR Oil Spill Suspects for further validation.",
        "interpretation": "Classes are suspicion levels for dark-target candidates, not a confirmed oil spill. Low wind can produce natural dark SAR areas and reduces confidence.",
        "applications": "Maritime surveillance, pollution screening, coastal monitoring, and emergency response support.",
    },
}


def _analysis_scientific_profile_data(value: str, language: str = "en") -> dict[str, str]:
    if _report_language(language) == "ar":
        return _report_ar_analysis_profile(value)
    key = str(value or "").upper()
    base = ANALYSIS_SCIENCE_LIBRARY.get(key)
    if not base and str(value).lower().startswith("change_detection_"):
        base = ANALYSIS_SCIENCE_LIBRARY.get(f"CHANGE_{str(value).replace('change_detection_', '').upper()}")
    if not base:
        return {
            "full_name": "Selected raster analysis",
            "principle": "The report is generated from the selected raster workflow and the available result metadata.",
            "bands": "Bands and derived features depend on the selected analysis pipeline.",
            "objective": "Describe the spatial pattern detected in the current analysis.",
            "interpretation": "Interpretation must rely on the legend, statistics, and map classes provided in the report.",
            "applications": "Operational reporting, decision support, and thematic raster interpretation.",
        }
    return base


def _analysis_scientific_profile(value: str) -> str:
    base = _analysis_scientific_profile_data(value)
    return (
        f"{base['full_name']}. "
        f"Principle: {base['principle']} "
        f"Bands: {base['bands']} "
        f"Objective: {base['objective']} "
        f"Interpretation: {base['interpretation']} "
        f"Applications: {base['applications']}"
    )


def _default_pdf_interpretation(value: str, language: str = "en") -> str:
    if _report_language(language) == "ar":
        return _report_ar_default_interpretation(value)
    key = value.upper()
    if key == "NDVI":
        return "NDVI results describe vegetation cover within the area of interest. High-value classes indicate dense or active vegetation, while low values indicate absent or sparse vegetation cover."
    if key == "NDWI":
        return "NDWI results show a continuous surface-water spectral response. Negative values generally indicate dry or non-water surfaces, while positive values are water-compatible and should be interpreted with context."
    if key == "NDBI":
        return "NDBI results show a continuous SWIR-to-NIR spectral response. Positive values can indicate built-up, impervious, exposed mineral, or bare surfaces and should be checked with supporting indices."
    if key == "BSI":
        return "BSI results indicate bare or strongly exposed soil areas. High values may correspond to dry, sandy, rocky, or sparsely vegetated surfaces."
    if key == "SAVI":
        return "SAVI results evaluate vegetation cover while reducing soil background effects, which is useful in semi-arid or sparse-vegetation areas."
    if key == "OSI_SAR" or value == "oil_spill_suspect_index":
        return "OSI-SAR results map Sentinel-1 SAR dark-target candidates over water. The classes indicate oil-spill suspicion levels and should be validated with wind context, maritime context, and visual evidence when available."
    if key.startswith("CHANGE_") or value.startswith("change_detection_"):
        return "Change Detection compares the selected raster index between two periods on the same area of interest. Negative classes indicate decrease, stable classes indicate limited change, and positive classes indicate increase between period 1 and period 2."
    if key == "SUPERVISED_CLASSIFICATION" or value == "supervised_classification":
        return "Supervised classification produces a land-cover map from the satellite mosaic and training data. It helps distinguish the main thematic classes within the area of interest."
    return "Unsupervised classification automatically groups pixels into spectral clusters. The classes should be interpreted as an exploratory first reading of land-cover patterns."


def _analysis_pdf_description(value: str) -> str:
    profile = _analysis_scientific_profile_data(value)
    return (
        f"{profile['full_name']} is the raster analysis executed for this report. "
        f"It relies on the spectral principle: {profile['principle']} "
        f"Main objective: {profile['objective']} "
        f"Interpretation context: {profile['interpretation']}"
    )


def _analysis_pdf_value_meaning(value: str, language: str = "en") -> str:
    if _report_language(language) == "ar":
        return _report_ar_value_meaning(value)
    key = str(value or "").upper()
    meanings = {
        "NDVI": "Low values indicate bare or sparsely vegetated surfaces, middle values indicate moderate vegetation cover, and high values indicate dense or vigorous vegetation.",
        "NDWI": "Low values indicate negative water response over dry or non-water surfaces, middle values are transitional, and high values indicate stronger water-compatible response.",
        "NDBI": "Low values indicate negative SWIR-to-NIR response, values near zero are mixed, and positive values can represent built-up, impervious, exposed mineral, or bare surfaces.",
        "BSI": "Low values indicate vegetated or wet surfaces, middle values indicate partially exposed soil, and high values indicate strongly exposed bare soil.",
        "SAVI": "Low values indicate sparse or absent vegetation, middle values indicate moderate vegetation cover, and high values indicate dense vegetation while reducing soil background effects.",
        "OSI_SAR": "Class 0 is valid marine water. Class 1 is an oil-spill suspect after VV, VH, local contrast, incidence, water, and connected-pixel filters. This is not a confirmed oil spill.",
        "CHANGE_NDVI": "Negative values indicate vegetation loss, values near zero indicate stability, and positive values indicate vegetation gain.",
        "CHANGE_NDWI": "Negative values indicate moisture or water loss, values near zero indicate stability, and positive values indicate moisture or water gain.",
        "CHANGE_NDBI": "Negative values indicate a weaker NDBI response, values near zero indicate stability, and positive values indicate a stronger NDBI response. This is not confirmed new construction.",
        "CHANGE_BSI": "Negative values indicate reduced bare soil, values near zero indicate stability, and positive values indicate increased soil exposure.",
        "CHANGE_SAVI": "Negative values indicate vegetation loss, values near zero indicate stability, and positive values indicate vegetation gain.",
        "SUPERVISED_CLASSIFICATION": "Class values should be interpreted through the legend; lower values are not inherently weaker, they simply represent a different thematic class.",
        "UNSUPERVISED_CLASSIFICATION": "Class values should be interpreted through the legend; the numeric cluster order is only an internal label and does not express intensity.",
    }
    if key.startswith("CHANGE_"):
        return meanings.get(key, meanings["CHANGE_NDVI"])
    if key == "OSI_SAR" or str(value) == "oil_spill_suspect_index":
        return meanings["OSI_SAR"]
    return meanings.get(key, "Low values, middle values, and high values should be interpreted using the analysis legend and the thematic meaning of the selected index.")


def _is_change_detection_pdf(value: str | None) -> bool:
    text = str(value or "").lower()
    return text.startswith("change_") or text.startswith("change_detection_")


def _change_pdf_base_index(value: str | None) -> str:
    text = str(value or "").upper()
    if text.startswith("CHANGE_DETECTION_"):
        return text.replace("CHANGE_DETECTION_", "", 1)
    if text.startswith("CHANGE_"):
        return text.replace("CHANGE_", "", 1)
    return text


def _dominant_class(classes: list[dict[str, Any]], language: str = "en") -> str:
    if not classes:
        return "-"
    def pct(item: dict[str, Any]) -> float:
        try:
            return float(item.get("pct") or item.get("percentage") or 0)
        except (TypeError, ValueError):
            return 0
    item = max(classes, key=pct)
    return _analysis_pdf_class_label(item.get("name") or item.get("label"), language)


def _pdf_platform_name() -> str:
    settings = _read_platform_settings()
    name = settings.get("platform_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "GeoRasterPortal"


def _pdf_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pdf_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _pdf_result_legend(payload: MapPdfExportRequest) -> list[dict[str, Any]]:
    language = _pdf_payload_language(payload)
    items = payload.classes or payload.legend or []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _analysis_pdf_class_label(item.get("label") or item.get("name") or "Class", language)
        normalized.append(
            {
                "label": label,
                "name": label,
                "meaning": _analysis_pdf_class_label(item.get("meaning") or item.get("description") or "", language),
                "description": _analysis_pdf_class_label(item.get("description") or item.get("meaning") or "", language),
                "color": item.get("color") or "#b8c4d6",
                "surface_ha": item.get("surface_ha") or item.get("surface"),
                "pct": item.get("pct") or item.get("percentage"),
                "pixels": item.get("pixels"),
                "min": item.get("min"),
                "max": item.get("max"),
                "mean_change": item.get("mean_change"),
            }
        )
    return normalized


def _pdf_reference_text_image(payload: MapPdfExportRequest, title: str, subtitle: str, accent: str = PDF_ACCENT) -> Image.Image:
    page = Image.new("RGB", (1600, 1100), "white")
    draw = ImageDraw.Draw(page)
    language = _pdf_payload_language(payload)
    is_ar = language == "ar"
    draw.rounded_rectangle((0, 0, 1599, 1099), radius=24, fill="#f4f8fb", outline="#cbd5e1", width=3)
    draw.rectangle((0, 0, 1599, 150), fill="#0f4c5c")
    if is_ar:
        _pdf_draw_text(draw, title, 1540, 52, _pdf_font(34, True), "white", language=language, right=1540)
        _pdf_draw_text(draw, subtitle, 1540, 100, _pdf_font(18), "#dbeafe", language=language, right=1540)
    else:
        draw.text((60, 52), title, font=_pdf_font(34, True), fill="white")
        draw.text((60, 100), subtitle, font=_pdf_font(18), fill="#dbeafe")

    params = payload.parameters or {}
    geometry = payload.geometry_info or {}
    stats = payload.statistics or {}
    lines = [
        f"{_report_text('Analysis type', language)}: {_analysis_pdf_label(payload.analysis_type, language)}",
        f"{_report_text('Sensor', language)}: {_pdf_text(params.get('sensor'))}",
        f"{_report_text('Analysis period', language)}: {_pdf_period_summary(payload)}",
        f"{_report_text('Study area', language)}: {_report_text(geometry.get('label') or 'Selected area of interest', language)}",
        f"{_report_text('Surface', language)}: {_pdf_number(geometry.get('area_ha') or stats.get('surface_ha') or stats.get('surface'))} {'هكتار' if is_ar else 'ha'}",
    ]
    y = 230
    for line in lines:
        draw.rounded_rectangle((60, y, 720, y + 76), radius=18, fill="white", outline="#d6e4e8", width=2)
        if is_ar:
            _pdf_draw_text(draw, line, 694, y + 25, _pdf_font(16, True), PDF_TEXT, language=language, right=694)
        else:
            draw.text((86, y + 25), line, font=_pdf_font(16, True), fill=PDF_TEXT)
        y += 94
    return page


def _mock_reference_thumbnail(payload: MapPdfExportRequest) -> Image.Image:
    language = _pdf_payload_language(payload)
    return _pdf_reference_text_image(
        payload,
        _report_text("Reference multispectral image", language),
        "معاينة بديلة عند تعذر تحميل المرئية المرجعية." if language == "ar" else "Mock fallback generated when a live GEE thumbnail is unavailable.",
    )


def _mock_result_thumbnail(payload: MapPdfExportRequest) -> Image.Image:
    language = _pdf_payload_language(payload)
    page = _pdf_reference_text_image(
        payload,
        _report_text("Analysis result", language),
        "معاينة بديلة عند تعذر تحميل مرئية النتيجة المصنفة." if language == "ar" else "Mock fallback generated when a live GEE classified image is unavailable.",
        accent="#b45309",
    )
    draw = ImageDraw.Draw(page)
    classes = _pdf_result_legend(payload)[:8]
    if classes:
        x0, y0 = 860, 240
        width = 640
        height = 560
        band_h = max(20, height // len(classes))
        for idx, item in enumerate(classes):
            y = y0 + idx * band_h
            draw.rectangle((x0, y, x0 + width, min(y + band_h, y0 + height)), fill=_pdf_color(item.get("color")))
            if language == "ar":
                _pdf_draw_text(draw, item.get("label"), x0 + width - 18, y + 10, _pdf_font(16, True), "white" if idx < 3 else PDF_TEXT, language=language, right=x0 + width - 18)
            else:
                draw.text((x0 + 18, y + 10), _pdf_text(item.get("label")), font=_pdf_font(16, True), fill="white" if idx < 3 else PDF_TEXT)
    return page


def _download_image_from_url(url: str) -> Image.Image:
    with urllib.request.urlopen(url, timeout=45) as response:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(response.read())))
        if image.mode in {"RGBA", "LA"}:
            bg = Image.new("RGB", image.size, "white")
            bg.paste(image, mask=image.getchannel("A"))
            image = bg
        return image.convert("RGB")


def _image_looks_flat(image: Image.Image) -> bool:
    if image.width <= 1 or image.height <= 1:
        return True
    extrema = image.getextrema()
    if isinstance(extrema, tuple) and extrema and isinstance(extrema[0], tuple):
        return all(lo == hi for lo, hi in extrema)
    if isinstance(extrema, tuple) and len(extrema) == 2:
        return extrema[0] == extrema[1]
    return False


def _tile_template_url(template: str, z: int, x: int, y: int) -> str:
    return template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)).replace("{s}", "a")


def _latlon_to_tile_fraction(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    return x, y


def _estimate_export_zoom(bounds: list[list[float]]) -> int:
    try:
        (south, west), (north, east) = bounds
        span = max(abs(float(north) - float(south)), abs(float(east) - float(west)))
    except Exception:
        return 11
    if span > 8:
        return 7
    if span > 4:
        return 8
    if span > 2:
        return 9
    if span > 1:
        return 10
    if span > 0.5:
        return 11
    if span > 0.25:
        return 12
    if span > 0.1:
        return 13
    return 14


def _tile_mosaic_from_template(
    template: str | None,
    bounds: list[list[float]] | None,
    *,
    target_tile_count: int = 9,
    crop_to_bounds: bool = True,
    max_zoom: int | None = None,
    tile_buffer: int = 1,
) -> Image.Image | None:
    if not template or not bounds or len(bounds) != 2:
        return None
    try:
        south, west = float(bounds[0][0]), float(bounds[0][1])
        north, east = float(bounds[1][0]), float(bounds[1][1])
    except Exception:
        return None

    if max_zoom is None:
        zoom = max(5, min(15, _estimate_export_zoom(bounds)))
    else:
        zoom = max(5, min(18, int(max_zoom)))
    tile_buffer = max(0, min(2, int(tile_buffer)))

    for _ in range(14):
        nw_x, nw_y = _latlon_to_tile_fraction(north, west, zoom)
        se_x, se_y = _latlon_to_tile_fraction(south, east, zoom)
        tile_x0 = max(0, int(math.floor(min(nw_x, se_x))) - tile_buffer)
        tile_x1 = max(tile_x0, int(math.floor(max(nw_x, se_x))) + tile_buffer)
        tile_y0 = max(0, int(math.floor(min(nw_y, se_y))) - tile_buffer)
        tile_y1 = max(tile_y0, int(math.floor(max(nw_y, se_y))) + tile_buffer)
        if (tile_x1 - tile_x0 + 1) * (tile_y1 - tile_y0 + 1) <= target_tile_count:
            break
        if zoom <= 5:
            break
        zoom -= 1

    cols = tile_x1 - tile_x0 + 1
    rows = tile_y1 - tile_y0 + 1
    canvas = Image.new("RGB", (cols * 256, rows * 256), "#eef3f7")

    urls: list[tuple[int, int, str]] = []
    for tx in range(tile_x0, tile_x1 + 1):
        for ty in range(tile_y0, tile_y1 + 1):
            urls.append((tx, ty, _tile_template_url(template, zoom, tx, ty)))

    def load_tile(item: tuple[int, int, str]) -> tuple[int, int, Image.Image | None]:
        tx, ty, url = item
        try:
            return tx, ty, _download_image_from_url(url)
        except Exception:
            return tx, ty, None

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(urls)))) as executor:
        results = list(executor.map(load_tile, urls))

    for tx, ty, image in results:
        if image is None:
            continue
        canvas.paste(image.resize((256, 256)), ((tx - tile_x0) * 256, (ty - tile_y0) * 256))

    if not crop_to_bounds:
        return canvas

    nw_x, nw_y = _latlon_to_tile_fraction(north, west, zoom)
    se_x, se_y = _latlon_to_tile_fraction(south, east, zoom)
    left = int((min(nw_x, se_x) - tile_x0) * 256)
    right = int((max(nw_x, se_x) - tile_x0) * 256)
    top = int((min(nw_y, se_y) - tile_y0) * 256)
    bottom = int((max(nw_y, se_y) - tile_y0) * 256)
    left = max(0, min(left, canvas.width - 1))
    top = max(0, min(top, canvas.height - 1))
    right = max(left + 1, min(right, canvas.width))
    bottom = max(top + 1, min(bottom, canvas.height))
    cropped = canvas.crop((left, top, right, bottom))
    return cropped if cropped.width > 0 and cropped.height > 0 else canvas


def _load_run_result_for_export(run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT result_json FROM runs WHERE id = ?", (run_id,))
        if row:
            return db.json_loads(row["result_json"] or "{}")
        cache_row = db.fetch_one(conn, "SELECT result_json FROM processing_cache WHERE cache_key = ?", (run_id,))
        if cache_row:
            return db.json_loads(cache_row["result_json"] or "{}")
    return None


def _pdf_bounds_from_aoi(aoi: dict[str, Any] | None) -> list[list[float]] | None:
    if not isinstance(aoi, dict):
        return None
    bbox = aoi.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 2:
        try:
            return [
                [float(bbox[0][0]), float(bbox[0][1])],
                [float(bbox[1][0]), float(bbox[1][1])],
            ]
        except Exception:
            pass
    coordinates = (aoi.get("geojson") or {}).get("coordinates", [[[]]])[0]
    if isinstance(coordinates, list) and coordinates:
        lats: list[float] = []
        lons: list[float] = []
        for item in coordinates:
            if isinstance(item, list) and len(item) >= 2:
                with suppress(Exception):
                    lons.append(float(item[0]))
                    lats.append(float(item[1]))
        if lats and lons:
            return [[min(lats), min(lons)], [max(lats), max(lons)]]
    return None


def _result_visual_layer(result: dict[str, Any], layer_key: str | None) -> dict[str, Any]:
    if not layer_key:
        return result
    layer = next(
        (
            item
            for item in result.get("comparison_layers") or []
            if isinstance(item, dict) and item.get("key") == layer_key
        ),
        None,
    )
    if not layer:
        return result
    base_tiles = result.get("tiles") or {}
    layer_tiles = {
        key: value
        for key, value in (layer.get("tiles") or {}).items()
        if value is not None
    }
    return {
        **result,
        "stats": layer.get("stats") or result.get("stats"),
        "histogram": layer.get("histogram") or [],
        "classes": layer.get("classes") or layer.get("legend") or [],
        "palette": layer.get("palette") or result.get("palette"),
        "tiles": {
            **base_tiles,
            **layer_tiles,
        },
        "interpretation": (layer.get("metadata") or {}).get("interpretation") or result.get("interpretation"),
        "active_comparison_layer": layer_key,
    }


def _load_map_pdf_request_from_run(run_id: str, layer_key: str | None = None, language: str = "en") -> MapPdfExportRequest:
    with db.connect() as conn:
        run_row = db.fetch_one(conn, "SELECT id, analysis_id, result_json FROM runs WHERE id = ?", (run_id,))
        if not run_row:
            raise HTTPException(status_code=404, detail="Run not found")
        analysis_row = db.fetch_one(conn, "SELECT * FROM analyses WHERE id = ?", (run_row["analysis_id"],))
        if not analysis_row:
            raise HTTPException(status_code=404, detail="Analysis not found")

    result = _result_visual_layer(db.json_loads(run_row["result_json"] or "{}"), layer_key)
    analysis = _apply_spatial_reference_to_analysis(db.json_loads(analysis_row["payload_json"] or "{}"))
    aoi = analysis.get("aoi") or {}
    bbox = _pdf_bounds_from_aoi(aoi) or (analysis.get("geometry") or {}).get("bbox")
    stats = result.get("stats") or {}
    quality = result.get("quality_summary") or result.get("quality") or result.get("mosaic") or {}
    geometry_info = {
        "label": "Selected area of interest",
        "bounds": bbox,
        "bounds_text": _pdf_text(bbox),
        "area_ha": stats.get("surface_ha") or analysis.get("quality", {}).get("surface_ha") or analysis.get("quality", {}).get("area_ha"),
        "area_km2": quality.get("area_km2") or analysis.get("quality", {}).get("area_km2"),
    }
    parameters = {
        "sensor": analysis.get("sensor"),
        "resolution": analysis.get("resolution"),
        "start_date": analysis.get("date_start"),
        "end_date": analysis.get("date_end"),
        "period_1_start": (analysis.get("period_1") or {}).get("start_date"),
        "period_1_end": (analysis.get("period_1") or {}).get("end_date"),
        "period_2_start": (analysis.get("period_2") or {}).get("start_date"),
        "period_2_end": (analysis.get("period_2") or {}).get("end_date"),
        "cloud_max": analysis.get("max_cloud_pct"),
        "processing_method": analysis.get("image_method") or "median_composite",
        "images_count": quality.get("images_count"),
        "display_mode": result.get("mode") or "mosaic",
        "objective": analysis.get("objective"),
    }
    metadata = {
        "source_data": analysis.get("source"),
        "satellite": analysis.get("sensor"),
        "acquisition_start": analysis.get("date_start"),
        "acquisition_end": analysis.get("date_end"),
        "spatial_resolution": analysis.get("resolution"),
        "extent_coordinates": {
            "south": bbox[0][0] if isinstance(bbox, list) and len(bbox) == 2 and isinstance(bbox[0], list) else None,
            "west": bbox[0][1] if isinstance(bbox, list) and len(bbox) == 2 and isinstance(bbox[0], list) else None,
            "north": bbox[1][0] if isinstance(bbox, list) and len(bbox) == 2 and isinstance(bbox[1], list) else None,
            "east": bbox[1][1] if isinstance(bbox, list) and len(bbox) == 2 and isinstance(bbox[1], list) else None,
        },
        "processing_version": analysis.get("processing_version") or "default-v1",
        "georasterportal_version": REPORT_APP_VERSION,
        "analysis_name": analysis.get("name"),
        "analysis_topic": analysis.get("objective"),
        "layer_key": layer_key,
        "spatial_reference": analysis.get("spatial_reference"),
    }
    return MapPdfExportRequest(
        analysis_id=run_id,
        analysis_type=str(analysis.get("index") or analysis.get("analysis_type") or "NDVI"),
        language=_report_language(language),
        geometry_info=geometry_info,
        parameters=parameters,
        map_screenshot="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+l2kAAAAASUVORK5CYII=",
        legend=result.get("classes") or [],
        statistics=result.get("stats") or {},
        histogram=result.get("histogram") or [],
        classes=result.get("classes") or [],
        quality_summary=quality,
        interpretation=result.get("interpretation"),
        user_name=analysis.get("user") or "local-user",
        metadata=metadata,
    )


def _pdf_export_images(payload: MapPdfExportRequest) -> tuple[Image.Image, Image.Image, Image.Image | None]:
    steps: dict[str, float] = {}
    step_start = time.perf_counter()
    run_id = str(payload.analysis_id or "").strip() or None
    result = _load_run_result_for_export(run_id)
    result = _result_visual_layer(result, (payload.metadata or {}).get("layer_key")) if result else None
    steps["run_fetch"] = time.perf_counter() - step_start
    if not result:
        LOGGER.info("Map PDF export fallback to mock thumbnails: no run result for %s", run_id)
        placeholder = _mock_reference_thumbnail(payload)
        return placeholder, _mock_result_thumbnail(payload), placeholder

    meta_start = time.perf_counter()
    tiles = result.get("tiles") or {}
    reference_tile_url = tiles.get("rgb_tile_url")
    result_tile_url = tiles.get("index_tile_url")
    steps["metadata_fetch"] = time.perf_counter() - meta_start

    reference_fallback = _mock_reference_thumbnail(payload)
    result_fallback = _mock_result_thumbnail(payload)
    images: dict[str, Image.Image | None] = {"reference": reference_fallback, "result": result_fallback}
    bounds = (payload.geometry_info or {}).get("bounds")

    download_start = time.perf_counter()
    def fetch_reference() -> None:
        candidate: Image.Image | None = None
        if reference_tile_url:
            with suppress(Exception):
                candidate = _tile_mosaic_from_template(
                    reference_tile_url,
                    bounds,
                    target_tile_count=16,
                    crop_to_bounds=True,
                    max_zoom=18,
                    tile_buffer=0,
                )
        if candidate is None or _image_looks_flat(candidate):
            with suppress(Exception):
                candidate = _download_image_from_url(create_reference_png_url(result))
        if candidate is not None and not _image_looks_flat(candidate):
            images["reference"] = candidate

    def fetch_result() -> None:
        candidate: Image.Image | None = None
        if result_tile_url:
            with suppress(Exception):
                candidate = _tile_mosaic_from_template(
                    result_tile_url,
                    bounds,
                    target_tile_count=16,
                    crop_to_bounds=True,
                    max_zoom=18,
                    tile_buffer=0,
                )
        if candidate is None or _image_looks_flat(candidate):
            with suppress(Exception):
                candidate = _download_image_from_url(
                    create_index_png_url(result, result.get("active_comparison_layer"))
                )
        if candidate is not None and not _image_looks_flat(candidate):
            images["result"] = candidate

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(fetch_reference), executor.submit(fetch_result)]
        for future in futures:
            future.result()
    steps["image_fetch"] = time.perf_counter() - download_start
    if images["reference"] is None or _image_looks_flat(images["reference"]):
        images["reference"] = reference_fallback
    if images["result"] is None or _image_looks_flat(images["result"]):
        images["result"] = result_fallback
    LOGGER.info(
        "Map PDF asset timings for %s: run=%.3fs meta=%.3fs images=%.3fs",
        run_id or "unknown",
        steps.get("run_fetch", 0.0),
        steps.get("metadata_fetch", 0.0),
        steps.get("image_fetch", 0.0),
    )

    locator = images["reference"] or reference_fallback
    return images["reference"] or reference_fallback, images["result"] or result_fallback, locator


def _pdf_period_summary(payload: MapPdfExportRequest) -> str:
    params = payload.parameters or {}
    language = _pdf_payload_language(payload)
    analysis_type = str(payload.analysis_type or "")
    if analysis_type.startswith("CHANGE_") or analysis_type.startswith("change_detection_"):
        p1s = params.get("period_1_start") or params.get("start_date_1") or params.get("date_start_1")
        p1e = params.get("period_1_end") or params.get("end_date_1") or params.get("date_end_1")
        p2s = params.get("period_2_start") or params.get("start_date_2") or params.get("date_start_2")
        p2e = params.get("period_2_end") or params.get("end_date_2") or params.get("date_end_2")
        if language == "ar":
            return f"الفترة الأولى: {_pdf_text(p1s)} إلى {_pdf_text(p1e)} | الفترة الثانية: {_pdf_text(p2s)} إلى {_pdf_text(p2e)}"
        return f"Period 1: {_pdf_text(p1s)} to {_pdf_text(p1e)} | Period 2: {_pdf_text(p2s)} to {_pdf_text(p2e)}"
    separator = " إلى " if language == "ar" else " to "
    return f"{_pdf_text(params.get('start_date') or params.get('date_start'))}{separator}{_pdf_text(params.get('end_date') or params.get('date_end'))}"


def _pdf_analysis_objective(payload: MapPdfExportRequest) -> str:
    profile = _analysis_scientific_profile_data(payload.analysis_type, _pdf_payload_language(payload))
    return profile["objective"]


def _pdf_analysis_map_title(payload: MapPdfExportRequest) -> str:
    return f"{_analysis_pdf_label(payload.analysis_type)} - Main Result Map"


def _pdf_decode_optional_screenshot(data_url: str | None) -> Image.Image | None:
    if not data_url:
        return None
    with suppress(Exception):
        return _decode_map_screenshot(data_url)
    return None


def _pdf_locator_image(payload: MapPdfExportRequest) -> Image.Image | None:
    return _pdf_decode_optional_screenshot(payload.locator_screenshot) or _pdf_decode_optional_screenshot(payload.map_screenshot)


def _pdf_result_map_image(payload: MapPdfExportRequest) -> Image.Image:
    return _download_layout_source_image(payload)


def _pdf_draw_panel(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    title: str,
    subtitle: str | None = None,
    fill: str = "white",
    language: str = "en",
) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=18, fill=fill, outline=PDF_BORDER, width=2)
    if _report_language(language) == "ar":
        draw.rounded_rectangle((x1 - 22, y0 + 16, x1 - 16, y0 + 48), radius=3, fill=PDF_ACCENT)
        _pdf_draw_text(draw, title, x1 - 32, y0 + 16, _pdf_font(18, True), PDF_TEXT, language=language, right=x1 - 32)
        if subtitle:
            _pdf_draw_text(draw, subtitle, x1 - 32, y0 + 44, _pdf_font(12), PDF_MUTED, language=language, right=x1 - 32)
    else:
        draw.rounded_rectangle((x0 + 16, y0 + 16, x0 + 22, y0 + 48), radius=3, fill=PDF_ACCENT)
        draw.text((x0 + 32, y0 + 16), title, font=_pdf_font(18, True), fill=PDF_TEXT)
        if subtitle:
            draw.text((x0 + 32, y0 + 44), subtitle, font=_pdf_font(12), fill=PDF_MUTED)


def _pdf_paste_center(page: Image.Image, image: Image.Image, rect: tuple[int, int, int, int], padding: int = 18) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    fitted = _fit_pdf_image(image, max(10, x1 - x0 - padding * 2), max(10, y1 - y0 - padding * 2))
    paste_x = x0 + ((x1 - x0) - fitted.width) // 2
    paste_y = y0 + ((y1 - y0) - fitted.height) // 2
    page.paste(fitted, (paste_x, paste_y))
    return paste_x, paste_y, paste_x + fitted.width, paste_y + fitted.height


def _pdf_paste_center_scaled(page: Image.Image, image: Image.Image, rect: tuple[int, int, int, int], padding: int = 18) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    fitted = _fit_pdf_image(image, max(10, x1 - x0 - padding * 2), max(10, y1 - y0 - padding * 2), upscale=True)
    paste_x = x0 + ((x1 - x0) - fitted.width) // 2
    paste_y = y0 + ((y1 - y0) - fitted.height) // 2
    page.paste(fitted, (paste_x, paste_y))
    return paste_x, paste_y, paste_x + fitted.width, paste_y + fitted.height


def _pdf_paste_cover_scaled(page: Image.Image, image: Image.Image, rect: tuple[int, int, int, int], padding: int = 0) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    target_w = max(10, x1 - x0 - padding * 2)
    target_h = max(10, y1 - y0 - padding * 2)
    src = _pdf_trim_empty_image_edges(image)
    if src.width <= 0 or src.height <= 0:
        return x0, y0, x0, y0
    ratio = max(target_w / src.width, target_h / src.height)
    resized = src.resize((max(1, int(round(src.width * ratio))), max(1, int(round(src.height * ratio)))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    fitted = resized.crop((left, top, left + target_w, top + target_h))
    paste_x = x0 + padding
    paste_y = y0 + padding
    page.paste(fitted, (paste_x, paste_y))
    return paste_x, paste_y, paste_x + fitted.width, paste_y + fitted.height


def _pdf_aoi_area_km2(payload: MapPdfExportRequest) -> float | None:
    geometry = payload.geometry_info or {}
    stats = payload.statistics or {}
    area_km2 = _pdf_float(geometry.get("area_km2"))
    if area_km2 is not None and area_km2 >= 0:
        return area_km2
    area_ha = _pdf_float(
        geometry.get("area_ha")
        or stats.get("surface_ha")
        or stats.get("total_area_ha")
        or stats.get("surface")
    )
    if area_ha is None or area_ha < 0:
        return None
    return area_ha / 100.0


def _pdf_adaptive_image_panel(
    slot: tuple[int, int, int, int],
    area_km2: float | None,
) -> tuple[int, int, int, int]:
    """Return a centered report panel sized for the AOI surface."""
    if area_km2 is None or area_km2 >= 100:
        width_ratio, height_ratio = 1.0, 1.0
    elif area_km2 >= 10:
        width_ratio, height_ratio = 0.90, 0.92
    elif area_km2 >= 1:
        width_ratio, height_ratio = 0.78, 0.84
    else:
        width_ratio, height_ratio = 0.62, 0.74

    x0, y0, x1, y1 = slot
    slot_w = x1 - x0
    slot_h = y1 - y0
    panel_w = max(420, int(round(slot_w * width_ratio)))
    panel_h = max(360, int(round(slot_h * height_ratio)))
    panel_x = x0 + (slot_w - panel_w) // 2
    panel_y = y0 + (slot_h - panel_h) // 2
    return panel_x, panel_y, panel_x + panel_w, panel_y + panel_h


def _pdf_paste_adaptive_map(
    page: Image.Image,
    image: Image.Image,
    rect: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Fit the complete AOI inside its report frame without cover-cropping."""
    x0, y0, x1, y1 = rect
    target = (x0 + 18, y0 + 60, x1 - 18, y1 - 24)
    src = _pdf_trim_empty_image_edges(image)
    pasted = _pdf_paste_center_scaled(page, src, target, padding=0)
    draw = ImageDraw.Draw(page)
    draw.rectangle(pasted, outline="#c5cedb", width=1)
    return pasted


def _pdf_trim_empty_image_edges(image: Image.Image) -> Image.Image:
    src = image.convert("RGB")
    if src.width < 20 or src.height < 20:
        return src

    # Remove large neutral margins generated by map/tile fallbacks before fitting in the report panel.
    pixels = src.load()
    samples = [
        pixels[0, 0],
        pixels[src.width - 1, 0],
        pixels[0, src.height - 1],
        pixels[src.width - 1, src.height - 1],
    ]
    bg = tuple(int(sum(channel) / len(samples)) for channel in zip(*samples))
    tolerance = 28

    def is_background(color: tuple[int, int, int]) -> bool:
        return sum(abs(color[idx] - bg[idx]) for idx in range(3)) <= tolerance

    left, right = src.width, -1
    top, bottom = src.height, -1
    step = max(1, min(src.width, src.height) // 700)
    for y in range(0, src.height, step):
        for x in range(0, src.width, step):
            if not is_background(pixels[x, y]):
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)

    if right <= left or bottom <= top:
        return src

    pad = max(2, min(src.width, src.height) // 80)
    crop = (
        max(0, left - pad),
        max(0, top - pad),
        min(src.width, right + pad),
        min(src.height, bottom + pad),
    )
    cropped = src.crop(crop)
    min_area_ratio = 0.015
    if (cropped.width * cropped.height) / float(src.width * src.height) < min_area_ratio:
        return src
    return cropped


def _pdf_draw_metric_card(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], label: str, value: Any, tone: str = "#f7fafc") -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=16, fill=tone, outline=PDF_BORDER, width=2)
    draw.text((x0 + 16, y0 + 14), label, font=_pdf_font(12, True), fill=PDF_MUTED)
    draw.text((x0 + 16, y0 + 42), _pdf_text(value), font=_pdf_font(20, True), fill=PDF_TEXT)


def _pdf_draw_class_area_chart(page: Image.Image, draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], classes: list[dict[str, Any]]) -> None:
    _pdf_draw_panel(draw, rect, "Class Area Distribution", "Horizontal bars scaled by mapped surface")
    chart_classes = classes[:6]
    if not chart_classes:
        draw.text((rect[0] + 22, rect[1] + 82), "No class areas available.", font=_pdf_font(13), fill=PDF_MUTED)
        return
    max_area = max((_pdf_float(item.get("surface_ha")) or 0) for item in chart_classes) or 1
    base_x = rect[0] + 140
    label_x = rect[0] + 22
    top_y = rect[1] + 84
    bar_max_w = rect[2] - base_x - 36
    for idx, item in enumerate(chart_classes):
        y = top_y + idx * 48
        area = _pdf_float(item.get("surface_ha")) or 0
        width = int(bar_max_w * (area / max_area))
        color = _pdf_color(item.get("color"))
        draw.text((label_x, y + 6), _pdf_text(item.get("name") or item.get("label")), font=_pdf_font(12, True), fill=PDF_TEXT)
        draw.rounded_rectangle((base_x, y + 4, base_x + max(width, 4), y + 28), radius=8, fill=color, outline="#7d8796")
        draw.text((base_x + width + 10, y + 6), f"{_pdf_number(area, ' ha')} | {_pdf_number(item.get('pct'), '%')}", font=_pdf_font(12), fill=PDF_MUTED)


def _pdf_draw_histogram_chart(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], histogram: list[dict[str, Any]], title: str) -> None:
    _pdf_draw_panel(draw, rect, title, "Distribution derived from the current analysis result")
    if not histogram:
        draw.text((rect[0] + 22, rect[1] + 82), "No histogram values available.", font=_pdf_font(13), fill=PDF_MUTED)
        return
    chart = histogram[:18]
    max_count = max((_pdf_float(item.get("count")) or 0) for item in chart) or 1
    chart_x0 = rect[0] + 56
    chart_y0 = rect[1] + 220
    chart_x1 = rect[2] - 24
    chart_y1 = rect[3] - 46
    draw.line((chart_x0, chart_y0, chart_x0, chart_y1), fill="#8d99ab", width=2)
    draw.line((chart_x0, chart_y1, chart_x1, chart_y1), fill="#8d99ab", width=2)
    available_w = chart_x1 - chart_x0 - 20
    bar_w = max(8, available_w // max(len(chart), 1) - 6)
    for idx, item in enumerate(chart):
        count = _pdf_float(item.get("count")) or 0
        height = int((chart_y1 - chart_y0 - 24) * (count / max_count))
        x = chart_x0 + 12 + idx * (bar_w + 6)
        y = chart_y1 - height
        draw.rounded_rectangle((x, y, x + bar_w, chart_y1), radius=4, fill=PDF_ACCENT, outline="#2c6f73")
        if idx % 3 == 0:
            label = _pdf_text(item.get("bin"))
            bbox = draw.textbbox((0, 0), label, font=_pdf_font(10))
            draw.text((x + (bar_w - (bbox[2] - bbox[0])) / 2, chart_y1 + 8), label, font=_pdf_font(10), fill=PDF_MUTED)
    draw.text((chart_x0 - 6, chart_y0 - 18), _pdf_number(max_count), font=_pdf_font(10), fill=PDF_MUTED)


def _pdf_draw_change_chart(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], classes: list[dict[str, Any]]) -> None:
    _pdf_draw_panel(draw, rect, "Change Trend by Class", "Mean change values summarized by thematic class")
    items = [item for item in classes if _pdf_float(item.get("mean_change")) is not None][:8]
    if not items:
        draw.text((rect[0] + 22, rect[1] + 82), "No temporal change series available.", font=_pdf_font(13), fill=PDF_MUTED)
        return
    values = [_pdf_float(item.get("mean_change")) or 0 for item in items]
    max_abs = max(max(abs(v) for v in values), 0.01)
    mid_y = (rect[1] + rect[3]) // 2 + 26
    left = rect[0] + 56
    right = rect[2] - 26
    draw.line((left, mid_y, right, mid_y), fill="#8d99ab", width=2)
    bar_space = (right - left - 20) // max(len(items), 1)
    for idx, item in enumerate(items):
        value = _pdf_float(item.get("mean_change")) or 0
        x = left + 10 + idx * bar_space
        bar_h = int((rect[3] - rect[1] - 140) * (abs(value) / max_abs))
        color = "#1f9d55" if value >= 0 else "#d94f41"
        if value >= 0:
            y0, y1 = mid_y - bar_h, mid_y
        else:
            y0, y1 = mid_y, mid_y + bar_h
        draw.rounded_rectangle((x, y0, x + max(20, bar_space - 10), y1), radius=5, fill=color, outline="#7d8796")
        label = _pdf_text(item.get("name") or item.get("label"))
        draw.text((x, rect[3] - 42), label[:12], font=_pdf_font(10), fill=PDF_MUTED)
        draw.text((x, y0 - 18 if value >= 0 else y1 + 4), _pdf_number(value), font=_pdf_font(10), fill=PDF_TEXT)


def _pdf_period_text_from_layer(layer: dict[str, Any], language: str = "en") -> str:
    period = layer.get("period") or {}
    if not isinstance(period, dict):
        return ""
    start = period.get("start_date") or period.get("start") or period.get("date_start")
    end = period.get("end_date") or period.get("end") or period.get("date_end")
    if start or end:
        separator = " إلى " if _report_language(language) == "ar" else " to "
        return f"{_pdf_text(start)}{separator}{_pdf_text(end)}"
    return ""


def _pdf_change_layers_from_result(result: dict[str, Any] | None, payload: MapPdfExportRequest) -> list[dict[str, Any]]:
    if not result:
        return []
    layers = [item for item in result.get("comparison_layers") or [] if isinstance(item, dict)]
    if not layers:
        return []
    base = _change_pdf_base_index(payload.analysis_type).lower()

    def rank(layer: dict[str, Any]) -> int:
        key = str(layer.get("key") or "").lower()
        title = str(layer.get("title") or "").lower()
        if "period_1" in key or "period 1" in title:
            return 0
        if "period_2" in key or "period 2" in title:
            return 1
        if "change" in key or "minus" in title or str(layer.get("index") or "").lower().startswith("change_"):
            return 2
        return 9

    selected = sorted([layer for layer in layers if base in str(layer.get("key") or layer.get("index") or layer.get("title") or "").lower()], key=rank)
    if len(selected) < 3:
        selected = sorted(layers, key=rank)
    ordered: list[dict[str, Any]] = []
    for wanted_rank in (0, 1, 2):
        match = next((layer for layer in selected if rank(layer) == wanted_rank), None)
        if match:
            ordered.append(match)
    for layer in selected:
        if layer not in ordered:
            ordered.append(layer)
        if len(ordered) >= 3:
            break
    return ordered[:3]


def _pdf_change_layer_image(payload: MapPdfExportRequest, layer: dict[str, Any]) -> Image.Image:
    language = _pdf_payload_language(payload)
    bounds = (payload.geometry_info or {}).get("bounds")
    tile_url = ((layer.get("tiles") or {}) if isinstance(layer.get("tiles"), dict) else {}).get("index_tile_url")
    candidate: Image.Image | None = None
    if tile_url:
        with suppress(Exception):
            candidate = _tile_mosaic_from_template(tile_url, bounds, target_tile_count=16, crop_to_bounds=True)
    if candidate is not None and not _image_looks_flat(candidate):
        return candidate
    title = _pdf_text(layer.get("title") or layer.get("index") or ("طبقة كشف التغير" if language == "ar" else "Change detection layer"))
    subtitle = _pdf_period_text_from_layer(layer, language) or _pdf_text(layer.get("topic") or ("معاينة الطبقة غير متاحة" if language == "ar" else "Layer preview unavailable"))
    return _pdf_reference_text_image(payload, title, subtitle)


def _pdf_change_period_interpretation(index_key: str, layer: dict[str, Any], period_label: str, language: str = "en") -> str:
    classes = [item for item in layer.get("classes") or layer.get("legend") or [] if isinstance(item, dict)]
    dominant = _dominant_class(classes, language)
    stats = layer.get("stats") if isinstance(layer.get("stats"), dict) else {}
    mean = _pdf_float(stats.get("mean")) if isinstance(stats, dict) else None
    base = index_key.upper()
    if _report_language(language) == "ar":
        subjects = {
            "NDVI": "كثافة الغطاء النباتي وحيويته",
            "NDWI": "المياه والرطوبة السطحية",
            "NDBI": "الدلائل الطيفية للمناطق المبنية والأسطح غير المنفذة",
            "BSI": "درجة انكشاف التربة العارية",
            "SAVI": "حالة الغطاء النباتي بعد تقليل تأثير خلفية التربة",
        }
        subject = subjects.get(base, "الحالة الموضوعاتية للمؤشر")
        sentence = f"تصف هذه الخريطة المصنفة {subject} خلال {period_label}. ويجب تفسير درجات الفئات وفقاً لمفتاح الخريطة."
        if dominant != "-":
            sentence += f" الفئة السائدة هي {dominant}."
        if mean is not None:
            sentence += f" بلغ المتوسط {_pdf_number(mean)}."
        return sentence
    index_mean = f" The mean value is {_pdf_number(mean)}." if mean is not None else ""
    dominant_text = f" The dominant class is {dominant}." if dominant != "-" else ""
    meanings = {
        "NDVI": "This classified NDVI map describes vegetation cover and vigor during {period}. Higher classes represent denser or healthier vegetation, while lower classes indicate sparse vegetation, bare soil, or non-vegetated surfaces.",
        "NDWI": "This classified NDWI map describes water and surface-moisture conditions during {period}. Higher classes indicate stronger water or moisture response, while lower classes correspond to drier or non-water surfaces.",
        "NDBI": "This classified NDBI map describes built-up and impervious-surface response during {period}. Higher classes indicate stronger artificialized or urban spectral signatures, while lower classes correspond to non-built surfaces.",
        "BSI": "This classified BSI map describes bare-soil exposure during {period}. Higher classes indicate stronger exposed-soil response, while lower classes suggest vegetation, moisture, or covered surfaces.",
        "SAVI": "This classified SAVI map describes soil-adjusted vegetation conditions during {period}. Higher classes indicate stronger vegetation response with reduced soil-background influence, while lower classes indicate sparse cover or exposed soil.",
    }
    sentence = meanings.get(base, "This classified index map describes the thematic condition during {period}. Higher and lower classes must be interpreted according to the legend.")
    return f"{sentence.format(period=period_label)}{dominant_text}{index_mean}"


def _pdf_change_delta_interpretation(index_key: str, layer: dict[str, Any], language: str = "en") -> str:
    classes = [item for item in layer.get("classes") or layer.get("legend") or [] if isinstance(item, dict)]
    dominant = _dominant_class(classes, language)
    stats = layer.get("stats") if isinstance(layer.get("stats"), dict) else {}
    mean = _pdf_float(stats.get("mean")) if isinstance(stats, dict) else None
    base = index_key.upper()
    if _report_language(language) == "ar":
        sentence = _report_ar_default_interpretation(f"CHANGE_{base}")
        if dominant != "-":
            sentence += f" الفئة السائدة على الخريطة هي {dominant}."
        if mean is not None:
            sentence += f" بلغ متوسط الفرق {_pdf_number(mean)} وفق قاعدة الفترة الثانية ناقص الفترة الأولى."
        else:
            sentence += " حُسب الفرق وفق قاعدة الفترة الثانية ناقص الفترة الأولى."
        return sentence
    mean_text = f" The mean delta is {_pdf_number(mean)}, based on period 2 minus period 1." if mean is not None else " The delta follows the current rule: period 2 minus period 1."
    dominant_text = f" The dominant mapped class is {dominant}." if dominant != "-" else ""
    meanings = {
        "NDVI": "The final change map highlights vegetation dynamics. Negative classes represent vegetation loss or reduced vigor, stable classes show limited change, and positive classes indicate vegetation recovery or gain.",
        "NDWI": "The final change map highlights water or moisture dynamics. Negative classes indicate drying or water/moisture loss, stable classes show limited hydrological change, and positive classes indicate increased moisture or probable water appearance.",
        "NDBI": "The final change map highlights built-up dynamics. Negative classes indicate reduced built-up spectral response, stable classes show limited change, and positive classes indicate new artificialization or stronger impervious-surface response.",
        "BSI": "The final change map highlights bare-soil exposure dynamics. Negative classes indicate reduced exposed soil, stable classes show limited change, and positive classes indicate increased exposed soil or dry mineral surfaces.",
        "SAVI": "The final change map highlights vegetation dynamics adjusted for soil background. Negative classes indicate vegetation decline, stable classes show limited change, and positive classes indicate vegetation gain or recovery.",
    }
    return f"{meanings.get(base, _default_pdf_interpretation(f'CHANGE_{base}'))}{dominant_text}{mean_text}"


def _pdf_draw_change_visual_block(
    page: Image.Image,
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    image: Image.Image,
    interpretation: str,
    language: str = "en",
) -> None:
    _pdf_draw_panel(draw, rect, title, subtitle, fill="#fbfdff", language=language)
    x0, y0, x1, y1 = rect
    image_slot = (x0 + 22, y0 + 78, x0 + 592, y1 - 24)
    text_rect = (x0 + 616, y0 + 84, x1 - 24, y1 - 24)
    # Change-detection AOIs may be much taller than the landscape image slot.
    # A cover fit cropped the north and south of those AOIs and made the period
    # maps look as though only a small subsection had been analysed. Fit the
    # complete raster instead and size its visible frame to the image aspect.
    source = _pdf_trim_empty_image_edges(image)
    fitted = _fit_pdf_image(
        source,
        max(10, image_slot[2] - image_slot[0] - 16),
        max(10, image_slot[3] - image_slot[1] - 16),
        upscale=True,
    )
    paste_x = image_slot[0] + ((image_slot[2] - image_slot[0]) - fitted.width) // 2
    paste_y = image_slot[1] + ((image_slot[3] - image_slot[1]) - fitted.height) // 2
    image_frame = (paste_x - 8, paste_y - 8, paste_x + fitted.width + 8, paste_y + fitted.height + 8)
    draw.rounded_rectangle(image_frame, radius=12, fill="white", outline=PDF_BORDER, width=2)
    page.paste(fitted, (paste_x, paste_y))
    interp_label = _report_text("Interpretation", language)
    if _report_language(language) == "ar":
        _pdf_draw_text(draw, interp_label, text_rect[2], text_rect[1], _pdf_font(13, True), PDF_ACCENT, language=language, right=text_rect[2])
    else:
        draw.text((text_rect[0], text_rect[1]), interp_label, font=_pdf_font(13, True), fill=PDF_ACCENT)
    _pdf_draw_wrapped(draw, interpretation, text_rect[0], text_rect[1] + 28, text_rect[2] - text_rect[0], _pdf_font(13), PDF_TEXT, max_lines=7, language=language)


def _pdf_change_detection_visual_page(
    payload: MapPdfExportRequest,
    result: dict[str, Any],
    generated_at: str,
    page_number: int,
) -> Image.Image | None:
    layers = _pdf_change_layers_from_result(result, payload)
    if len(layers) < 3:
        return None
    page, draw = _pdf_page()
    language = _pdf_payload_language(payload)
    is_ar = language == "ar"
    analysis_label = _analysis_pdf_label(payload.analysis_type, language)
    base = _change_pdf_base_index(payload.analysis_type)
    _pdf_draw_header(draw, page, _report_text("Change Detection Visual Results", language), analysis_label, page_number, language)
    if is_ar:
        intro = f"تعرض هذه الصفحة النتيجة الخرائطية لتحليل {analysis_label}. وتشمل خريطة مصنفة للفترة الأولى وخريطة مصنفة للفترة الثانية وخريطة الفرق النهائية المحسوبة وفق قاعدة الفترة الثانية ناقص الفترة الأولى."
    else:
        intro = (
            f"This page expands the cartographic result for {analysis_label}. "
            f"The three maps use the existing comparison layers: classified {base} for period 1, classified {base} for period 2, and the final delta map computed as period 2 minus period 1."
        )
    _pdf_draw_wrapped(draw, intro, PDF_MARGIN, 206, PDF_PAGE_SIZE[0] - PDF_MARGIN * 2, _pdf_font(13), PDF_MUTED, max_lines=3, language=language)
    panel_top = 282
    panel_h = 424
    gap = 18
    panel_w = PDF_PAGE_SIZE[0] - PDF_MARGIN * 2
    labels = (
        [
            (f"5.1 خريطة {base} المصنفة - الفترة الأولى", _report_text("Baseline classified index map", language)),
            (f"5.2 خريطة {base} المصنفة - الفترة الثانية", _report_text("Comparison classified index map", language)),
            (f"5.3 النتيجة النهائية لكشف تغير {base}", _report_text("Delta map: period 2 minus period 1", language)),
        ]
        if is_ar
        else [
            (f"5.1 Classified {base} map - Period 1", "Baseline classified index map"),
            (f"5.2 Classified {base} map - Period 2", "Comparison classified index map"),
            (f"5.3 Final {base} change detection result", "Delta map: period 2 minus period 1"),
        ]
    )
    for idx, layer in enumerate(layers[:3]):
        y0 = panel_top + idx * (panel_h + gap)
        period_text = _pdf_period_text_from_layer(layer, language)
        subtitle = period_text or labels[idx][1]
        image = _pdf_change_layer_image(payload, layer)
        if idx < 2:
            period_label = f"الفترة {'الأولى' if idx == 0 else 'الثانية'}" if is_ar else f"period {idx + 1}"
            interpretation = _pdf_change_period_interpretation(base, layer, period_label, language)
        else:
            interpretation = _pdf_change_delta_interpretation(base, layer, language)
        _pdf_draw_change_visual_block(
            page,
            draw,
            (PDF_MARGIN, y0, PDF_MARGIN + panel_w, y0 + panel_h),
            labels[idx][0],
            subtitle,
            image,
            interpretation,
            language,
        )
    _pdf_draw_footer(draw, generated_at, page_number, language)
    return page


def _pdf_cover_page(payload: MapPdfExportRequest, map_image: Image.Image, generated_at: str) -> Image.Image:
    page, draw = _pdf_page()
    language = _pdf_payload_language(payload)
    is_ar = language == "ar"
    platform_name = _pdf_platform_name()
    analysis_label = _analysis_pdf_label(payload.analysis_type, language)
    profile = _analysis_scientific_profile_data(payload.analysis_type, language)
    params = payload.parameters or {}
    geometry = payload.geometry_info or {}
    stats = payload.statistics or {}
    area_ha = geometry.get("area_ha") or stats.get("surface_ha") or stats.get("total_area_ha") or stats.get("surface")
    draw.rounded_rectangle((0, 0, PDF_PAGE_SIZE[0], 320), radius=0, fill="#0f4c5c")
    draw.rounded_rectangle((PDF_MARGIN, 116, PDF_PAGE_SIZE[0] - PDF_MARGIN, 640), radius=28, fill="#f7fafc", outline="#d6e4e8", width=2)
    logo = _pdf_logo_image()
    if logo:
        logo.thumbnail((140, 88))
        logo_x = PDF_PAGE_SIZE[0] - PDF_MARGIN - 34 - logo.width if is_ar else PDF_MARGIN + 34
        page.paste(logo, (logo_x, 148))
    else:
        logo_x = PDF_PAGE_SIZE[0] - PDF_MARGIN - 156 if is_ar else PDF_MARGIN + 34
        draw.rounded_rectangle((logo_x, 148, logo_x + 122, 236), radius=18, fill="#d7efed", outline="#8ac7c3")
        draw.text((logo_x + 38, 175), "GR", font=_pdf_font(34, True), fill=PDF_ACCENT)
    if is_ar:
        brand_text_right = logo_x - 24
        _pdf_draw_text(draw, platform_name, brand_text_right, 150, _pdf_font(34, True), PDF_TEXT, language=language, right=brand_text_right)
    else:
        draw.text((PDF_MARGIN + 192, 150), platform_name, font=_pdf_font(34, True), fill=PDF_TEXT)
    report_subtitle = _report_text("Professional raster analysis report", language)
    if is_ar:
        _pdf_draw_text(draw, report_subtitle, brand_text_right, 198, _pdf_font(17), PDF_MUTED, language=language, right=brand_text_right)
        _pdf_draw_text(draw, analysis_label, PDF_PAGE_SIZE[0] - PDF_MARGIN - 34, 286, _pdf_font(36, True), PDF_TEXT, language=language, right=PDF_PAGE_SIZE[0] - PDF_MARGIN - 34)
        _pdf_draw_text(draw, profile["full_name"], PDF_PAGE_SIZE[0] - PDF_MARGIN - 34, 342, _pdf_font(16, True), PDF_ACCENT, language=language, right=PDF_PAGE_SIZE[0] - PDF_MARGIN - 34)
    else:
        draw.text((PDF_MARGIN + 192, 198), report_subtitle, font=_pdf_font(17), fill=PDF_MUTED)
        draw.text((PDF_MARGIN + 34, 286), analysis_label, font=_pdf_font(36, True), fill=PDF_TEXT)
        draw.text((PDF_MARGIN + 34, 342), profile["full_name"], font=_pdf_font(16, True), fill=PDF_ACCENT)
    info_rows = [
        ("Execution time", generated_at),
        ("Sensor", params.get("sensor")),
        ("Study area", _report_text(geometry.get("label") or "Selected area of interest", language)),
        ("Analysis period", _pdf_period_summary(payload)),
        ("Surface", _pdf_number(area_ha, " ha")),
        ("GeoRasterPortal version", (payload.metadata or {}).get("georasterportal_version") or REPORT_APP_VERSION),
    ]
    desc_panel = (PDF_MARGIN, 690, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1048)
    desc_title = f"1. {_report_text('Description of the executed analysis', language)}" if is_ar else "1. Description of the executed index"
    desc_subtitle = _report_text("Scientific introduction, principle, interpretation, and context of use", language)
    _pdf_draw_panel(draw, desc_panel, desc_title, desc_subtitle, language=language)
    if is_ar:
        paragraph = (
            f"يمثل {profile['full_name']} التحليل الراستري المنفّذ في هذا التقرير. "
            f"الهدف: {profile['objective']} "
            f"التفسير: {_analysis_pdf_value_meaning(payload.analysis_type, language)}. "
            f"أهم التطبيقات: {profile['applications']}"
        )
    else:
        paragraph = (
            f"{profile['full_name']} is the raster analysis executed in this report. "
            f"It is used to {profile['objective'].rstrip('.').lower()}. "
            f"For interpretation, {_analysis_pdf_value_meaning(payload.analysis_type).rstrip('.')}. "
            f"Typical applications include {profile['applications'].rstrip('.').lower()}."
        )
    text_box = (desc_panel[0] + 18, desc_panel[1] + 72, desc_panel[2] - 18, desc_panel[1] + 186)
    draw.rounded_rectangle(text_box, radius=14, fill="#ffffff", outline=PDF_BORDER)
    _pdf_draw_wrapped(draw, paragraph, text_box[0] + 16, text_box[1] + 16, text_box[2] - text_box[0] - 32, _pdf_font(14), PDF_TEXT, max_lines=6, language=language)
    guide_y = desc_panel[1] + 206
    guide_items = [
        (_report_text("Principle", language), profile["principle"] if is_ar else "Spectral contrast / thematic clustering"),
        (_report_text("Interpretation", language), profile["interpretation"] if is_ar else "Low, medium, and high values by legend"),
        (_report_text("Use case", language), profile["objective"]),
    ]
    guide_w = (desc_panel[2] - desc_panel[0] - 56) // 3
    for idx, (label, value) in enumerate(guide_items):
        x0 = desc_panel[0] + 18 + idx * (guide_w + 8)
        draw.rounded_rectangle((x0, guide_y, x0 + guide_w, guide_y + 84), radius=12, fill="#ffffff", outline=PDF_BORDER)
        if is_ar:
            _pdf_draw_text(draw, label, x0 + guide_w - 12, guide_y + 12, _pdf_font(12, True), PDF_MUTED, language=language, right=x0 + guide_w - 12)
        else:
            draw.text((x0 + 12, guide_y + 12), label, font=_pdf_font(12, True), fill=PDF_MUTED)
        _pdf_draw_wrapped(draw, value, x0 + 12, guide_y + 34, guide_w - 24, _pdf_font(12), PDF_TEXT, max_lines=2, language=language)
    study_panel = (PDF_MARGIN, 1086, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1542)
    _pdf_draw_panel(
        draw,
        study_panel,
        f"2. {_report_text('Study area information', language)}",
        _report_text("Area of interest, sensor, acquisition dates, source, and spatial resolution", language),
        language=language,
    )
    rows_x = study_panel[0] + 22
    rows_y = study_panel[1] + 78
    row_w = (study_panel[2] - study_panel[0] - 52) // 2
    row_h = 56
    study_rows = [
        ("Area name", _report_text(geometry.get("label") or "Selected area of interest", language)),
        ("Surface", f"{_pdf_number(area_ha, ' هكتار' if is_ar else ' ha')}"),
        ("Coordinates / extent", geometry.get("bounds_text") or _pdf_text(geometry.get("bounds") or geometry.get("bbox"))),
        ("Sensor", params.get("sensor")),
        ("Acquisition period", _pdf_period_summary(payload)),
        ("Source data", (payload.metadata or {}).get("source_data") or ("بيانات فضائية معالجة" if is_ar else "Google Earth Engine")),
        ("Spatial resolution", (payload.metadata or {}).get("spatial_resolution") or params.get("resolution")),
        ("Analysis type", analysis_label),
    ]
    for idx, (label, value) in enumerate(study_rows):
        col = idx % 2
        row = idx // 2
        x0 = rows_x + col * (row_w + 8)
        y0 = rows_y + row * (row_h + 8)
        draw.rounded_rectangle((x0, y0, x0 + row_w, y0 + row_h), radius=12, fill="#ffffff", outline=PDF_BORDER)
        translated_label = _report_text(label, language)
        if is_ar:
            _pdf_draw_text(draw, translated_label, x0 + row_w - 12, y0 + 12, _pdf_font(12, True), PDF_MUTED, language=language, right=x0 + row_w - 12)
        else:
            draw.text((x0 + 12, y0 + 12), translated_label, font=_pdf_font(12, True), fill=PDF_MUTED)
        _pdf_draw_wrapped(draw, value, x0 + 12, y0 + 30, row_w - 24, _pdf_font(13), PDF_TEXT, max_lines=1, language=language)
    _pdf_draw_footer(draw, generated_at, 1, language)
    return page


def _pdf_study_area_page(payload: MapPdfExportRequest, reference_image: Image.Image, result_image: Image.Image, generated_at: str) -> Image.Image:
    page, draw = _pdf_page()
    language = _pdf_payload_language(payload)
    analysis_label = _analysis_pdf_label(payload.analysis_type, language)
    area_km2 = _pdf_aoi_area_km2(payload)
    _pdf_draw_header(draw, page, _report_text("Satellite Images", language), analysis_label, 2, language)
    ref_slot = (PDF_MARGIN, 214, PDF_PAGE_SIZE[0] - PDF_MARGIN, 918)
    ref_panel = _pdf_adaptive_image_panel(ref_slot, area_km2)
    _pdf_draw_panel(draw, ref_panel, f"3. {_report_text('Satellite image of reference', language)}", language=language)
    _pdf_paste_adaptive_map(page, reference_image, ref_panel)

    res_slot = (PDF_MARGIN, 950, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1648)
    res_panel = _pdf_adaptive_image_panel(res_slot, area_km2)
    _pdf_draw_panel(draw, res_panel, f"4. {_report_text('Result of the analysis', language)}", language=language)
    _pdf_paste_adaptive_map(page, result_image, res_panel)
    _pdf_draw_footer(draw, generated_at, 2, language)
    return page


def _pdf_result_page(
    payload: MapPdfExportRequest,
    result_image: Image.Image,
    locator_image: Image.Image | None,
    generated_at: str,
    page_number: int = 3,
    section_start: int = 5,
) -> Image.Image:
    page, draw = _pdf_page()
    language = _pdf_payload_language(payload)
    is_ar = language == "ar"
    analysis_label = _analysis_pdf_label(payload.analysis_type, language)
    legend = _pdf_result_legend(payload)
    stats = payload.statistics or {}
    quality = payload.quality_summary or {}
    interpretation = payload.interpretation or _default_pdf_interpretation(payload.analysis_type, language)
    if is_ar and not _pdf_has_arabic(interpretation):
        interpretation = _default_pdf_interpretation(payload.analysis_type, language)
    if legend:
        dominant = _dominant_class(legend, language)
        if dominant != "-":
            if is_ar:
                interpretation = f"{interpretation} الفئة السائدة هي {dominant}، وتمثل النمط المكاني الغالب داخل منطقة الاهتمام."
            else:
                interpretation = f"{interpretation} The dominant class is {dominant}, which describes the prevailing condition across the area of interest."
    _pdf_draw_header(draw, page, _report_text("Statistics and Interpretation", language), analysis_label, page_number, language)
    legend_panel = (PDF_MARGIN, 218, PDF_PAGE_SIZE[0] - PDF_MARGIN, 724)
    _pdf_draw_panel(
        draw,
        legend_panel,
        f"{section_start}. {_report_text('Legend', language)}",
        _report_text("Class colours, surface, and percentage of each class", language),
        language=language,
    )
    col_w = (legend_panel[2] - legend_panel[0] - 70) // 2
    legend_y = legend_panel[1] + 76
    for idx, item in enumerate(legend[:10]):
        if is_ar:
            item_count = max(1, min(len(legend), 10))
            row_gap = 5
            available_height = legend_panel[3] - legend_y - 18
            row_h = min(54, max(34, (available_height - row_gap * (item_count - 1)) // item_count))
            x = legend_panel[0] + 24
            cell_right = legend_panel[2] - 24
            cell_w = cell_right - x
            y = legend_y + idx * (row_h + row_gap)
            draw.rounded_rectangle(
                (x, y, cell_right, y + row_h),
                radius=10,
                fill="#fbfcfe",
                outline=PDF_BORDER,
                width=1,
            )
            square_size = min(28, max(22, row_h - 14))
            square_y = y + (row_h - square_size) // 2
            color_x = cell_right - 16 - square_size
            draw.rounded_rectangle(
                (color_x, square_y, color_x + square_size, square_y + square_size),
                radius=5,
                fill=_pdf_color(item.get("color")),
                outline="#7d8796",
            )
            pct_right = x + int(cell_w * 0.23)
            area_right = x + int(cell_w * 0.52)
            name_left = area_right + 14
            name_right = color_x - 12
            text_y = y + max(7, (row_h - 16) // 2)
            draw.line((pct_right, y + 8, pct_right, y + row_h - 8), fill="#e3e8ef", width=1)
            draw.line((area_right, y + 8, area_right, y + row_h - 8), fill="#e3e8ef", width=1)
            _pdf_draw_wrapped(
                draw,
                item.get("label") or item.get("name"),
                name_left,
                text_y,
                max(40, name_right - name_left),
                _pdf_font(13, True),
                PDF_TEXT,
                max_lines=1,
                language=language,
                align="right",
            )
            area_text = f"المساحة: {_pdf_number(item.get('surface_ha'))} هكتار"
            pct_text = f"النسبة: {_pdf_number(item.get('pct'))}٪"
            _pdf_draw_wrapped(
                draw,
                area_text,
                pct_right + 12,
                text_y,
                max(40, area_right - pct_right - 24),
                _pdf_font(12),
                PDF_MUTED,
                max_lines=1,
                language=language,
                align="right",
            )
            _pdf_draw_wrapped(
                draw,
                pct_text,
                x + 12,
                text_y,
                max(40, pct_right - x - 24),
                _pdf_font(12),
                PDF_MUTED,
                max_lines=1,
                language=language,
                align="right",
            )
        else:
            col = idx % 2
            row = idx // 2
            x = legend_panel[0] + 24 + col * (col_w + 22)
            y = legend_y + row * 54
            draw.rounded_rectangle((x, y + 4, x + 26, y + 28), radius=5, fill=_pdf_color(item.get("color")), outline="#7d8796")
            draw.text((x + 38, y), _pdf_text(item.get("label") or item.get("name")), font=_pdf_font(13, True), fill=PDF_TEXT)
            detail = item.get("meaning") or item.get("description") or ""
            if item.get("pct") not in (None, ""):
                detail = f"{detail} {_pdf_number(item.get('surface_ha'), ' ha')} / {_pdf_number(item.get('pct'), '%')}".strip()
            _pdf_draw_wrapped(draw, detail, x + 38, y + 18, col_w - 52, _pdf_font(11), PDF_MUTED, max_lines=2)

    stats_panel = (PDF_MARGIN, 772, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1228)
    _pdf_draw_panel(
        draw,
        stats_panel,
        f"{section_start + 1}. {_report_text('Statistics', language)}",
        _report_text("Minimum, maximum, mean, standard deviation, pixels, and total mapped area", language),
        language=language,
    )
    area_suffix = " هكتار" if is_ar else " ha"
    stats_rows = [
        ("Minimum", _pdf_text(stats.get("min"))),
        ("Maximum", _pdf_text(stats.get("max"))),
        ("Mean", _pdf_text(stats.get("mean"))),
        ("Std. dev.", _pdf_text(stats.get("std"))),
        ("Pixels", _pdf_number(stats.get("pixels"))),
        ("Total area", _pdf_number((payload.geometry_info or {}).get("area_ha") or stats.get("surface_ha") or stats.get("total_area_ha") or stats.get("surface"), area_suffix)),
        ("Dominant class", _dominant_class(legend, language)),
        ("Analysis type", analysis_label),
    ]
    _pdf_kv_table(draw, stats_rows, stats_panel[0] + 18, stats_panel[1] + 72, stats_panel[2] - stats_panel[0] - 36, row_h=44, language=language)

    interpretation_panel = (PDF_MARGIN, 1260, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1542)
    _pdf_draw_panel(
        draw,
        interpretation_panel,
        f"{section_start + 2}. {_report_text('Detailed interpretation', language)}",
        _report_text("Clear and concise reading of the result", language),
        language=language,
    )
    _pdf_draw_wrapped(draw, interpretation, interpretation_panel[0] + 22, interpretation_panel[1] + 76, interpretation_panel[2] - interpretation_panel[0] - 44, _pdf_font(15), PDF_TEXT, max_lines=6, language=language)
    raw_conclusion = quality.get("message") or quality.get("warning") or quality.get("quality")
    conclusion = _report_ar_quality_conclusion() if is_ar and not _pdf_has_arabic(raw_conclusion) else (raw_conclusion or "The result is consistent with the selected analysis settings and the computed GEE raster.")
    conclusion_label = _report_text("Conclusion", language)
    if is_ar:
        _pdf_draw_text(draw, conclusion_label, interpretation_panel[2] - 22, interpretation_panel[1] + 196, _pdf_font(13, True), PDF_MUTED, language=language, right=interpretation_panel[2] - 22)
        _pdf_draw_wrapped(draw, conclusion, interpretation_panel[0] + 22, interpretation_panel[1] + 222, interpretation_panel[2] - interpretation_panel[0] - 44, _pdf_font(13), PDF_TEXT, max_lines=2, language=language)
    else:
        draw.text((interpretation_panel[0] + 22, interpretation_panel[1] + 196), conclusion_label, font=_pdf_font(13, True), fill=PDF_MUTED)
        _pdf_draw_wrapped(draw, conclusion, interpretation_panel[0] + 120, interpretation_panel[1] + 196, interpretation_panel[2] - interpretation_panel[0] - 142, _pdf_font(13), PDF_TEXT, max_lines=2)
    _pdf_draw_footer(draw, generated_at, page_number, language)
    return page


def _pdf_stats_graphics_page(payload: MapPdfExportRequest, generated_at: str) -> Image.Image:
    page, draw = _pdf_page()
    _pdf_draw_header(draw, page, "Statistics and Graphics", _analysis_pdf_label(payload.analysis_type), 3)
    stats = payload.statistics or {}
    quality = payload.quality_summary or {}
    classes = _pdf_result_legend(payload)
    histogram = payload.histogram or []
    metric_cards = [
        ("Minimum", _pdf_text(stats.get("min"))),
        ("Maximum", _pdf_text(stats.get("max"))),
        ("Mean", _pdf_text(stats.get("mean"))),
        ("Std. dev.", _pdf_text(stats.get("std"))),
        ("Pixels", _pdf_number(stats.get("pixels"))),
        ("Coverage", _pdf_number(quality.get("coverage_percent"), "%")),
        ("Accuracy", _pdf_percent(quality.get("overall_accuracy"))),
        ("Kappa", _pdf_text(quality.get("kappa"))),
    ]
    start_x = PDF_MARGIN
    start_y = 220
    card_w = (PDF_PAGE_SIZE[0] - PDF_MARGIN * 2 - 24) // 4
    for idx, (label, value) in enumerate(metric_cards):
        row = idx // 4
        col = idx % 4
        x0 = start_x + col * (card_w + 8)
        y0 = start_y + row * 88
        _pdf_draw_metric_card(draw, (x0, y0, x0 + card_w, y0 + 72), label, value)

    table_panel = (PDF_MARGIN, 410, PDF_PAGE_SIZE[0] - PDF_MARGIN, 886)
    _pdf_draw_panel(draw, table_panel, "Detailed Statistics", "Professional tabular summary of the generated result")
    rows = [
        ("Analysis type", _analysis_pdf_label(payload.analysis_type)),
        ("Dominant class", _dominant_class(classes)),
        ("Total mapped area", _pdf_number((payload.geometry_info or {}).get("area_ha") or stats.get("surface_ha") or stats.get("total_area_ha") or stats.get("surface"), " ha")),
        ("Detected classes", len(classes)),
        ("Images used", (payload.parameters or {}).get("images_count") or quality.get("images_count") or quality.get("available_images")),
        ("Processing method", (payload.parameters or {}).get("processing_method") or (payload.parameters or {}).get("image_method") or "median_composite"),
        ("Quality note", quality.get("message") or quality.get("warning") or quality.get("quality") or "No additional quality note provided."),
    ]
    _pdf_kv_table(draw, rows, table_panel[0] + 20, table_panel[1] + 70, table_panel[2] - table_panel[0] - 40, row_h=50)

    left_chart = (PDF_MARGIN, 920, PDF_MARGIN + 510, 1540)
    right_chart = (PDF_MARGIN + 536, 920, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1540)
    _pdf_draw_class_area_chart(page, draw, left_chart, classes)
    if any(_pdf_float(item.get("mean_change")) is not None for item in classes):
        _pdf_draw_change_chart(draw, right_chart, classes)
    else:
        _pdf_draw_histogram_chart(draw, right_chart, histogram, "Class Histogram")
    _pdf_draw_footer(draw, generated_at, 3)
    return page


def _pdf_interpretation_metadata_page(payload: MapPdfExportRequest, generated_at: str) -> Image.Image:
    page, draw = _pdf_page()
    _pdf_draw_header(draw, page, "Interpretation and Metadata", _analysis_pdf_label(payload.analysis_type), 4)
    params = payload.parameters or {}
    geometry = payload.geometry_info or {}
    quality = payload.quality_summary or {}
    metadata = payload.metadata or {}
    classes = _pdf_result_legend(payload)
    dominant = _dominant_class(classes)
    interpretation = payload.interpretation or _default_pdf_interpretation(payload.analysis_type)
    if dominant != "-":
        interpretation = f"{interpretation} Dominant mapped class: {dominant}."

    interp_panel = (PDF_MARGIN, 220, PDF_PAGE_SIZE[0] - PDF_MARGIN, 690)
    _pdf_draw_panel(draw, interp_panel, "Automatic Interpretation", "Generated in English for project reporting and stakeholder communication")
    _pdf_draw_wrapped(draw, interpretation, interp_panel[0] + 22, interp_panel[1] + 78, interp_panel[2] - interp_panel[0] - 44, _pdf_font(15), PDF_TEXT, max_lines=10)
    bullet_y = interp_panel[1] + 252
    bullets = [
        f"Dominant class: {dominant}",
        f"Analysis objective: {_pdf_analysis_objective(payload)}",
        f"Sensor and period: {_pdf_text(params.get('sensor'))} | {_pdf_period_summary(payload)}",
        f"Surface analyzed: {_pdf_number(geometry.get('area_ha') or (payload.statistics or {}).get('surface_ha'), ' ha')}",
    ]
    for bullet in bullets:
        draw.rounded_rectangle((interp_panel[0] + 22, bullet_y + 6, interp_panel[0] + 34, bullet_y + 18), radius=4, fill=PDF_ACCENT)
        _pdf_draw_wrapped(draw, bullet, interp_panel[0] + 48, bullet_y, interp_panel[2] - interp_panel[0] - 76, _pdf_font(13), PDF_TEXT, max_lines=2)
        bullet_y += 48

    quality_panel = (PDF_MARGIN, 724, PDF_MARGIN + 510, 1446)
    meta_panel = (PDF_MARGIN + 536, 724, PDF_PAGE_SIZE[0] - PDF_MARGIN, 1446)
    _pdf_draw_panel(draw, quality_panel, "Processing Quality", "Quality and method indicators")
    quality_rows = [
        ("Coverage percent", _pdf_number(quality.get("coverage_percent"), "%")),
        ("Available images", quality.get("images_count") or quality.get("available_images")),
        ("Tiles used", quality.get("tiles_count")),
        ("Classifier / method", quality.get("classifier") or quality.get("cluster_method") or params.get("processing_method")),
        ("Overall accuracy", _pdf_percent(quality.get("overall_accuracy"))),
        ("Kappa", _pdf_text(quality.get("kappa"))),
        ("Quality note", quality.get("message") or quality.get("warning") or quality.get("quality")),
    ]
    _pdf_kv_table(draw, quality_rows, quality_panel[0] + 18, quality_panel[1] + 70, quality_panel[2] - quality_panel[0] - 36, row_h=54)

    _pdf_draw_panel(draw, meta_panel, "Metadata", "Core provenance, spatial context, and processing traceability")
    extent = metadata.get("extent_coordinates") or {}
    bounds = geometry.get("bounds") or geometry.get("bbox")
    meta_rows = [
        ("Source data", metadata.get("source_data") or params.get("source") or "Google Earth Engine"),
        ("Satellite / sensor", metadata.get("satellite") or params.get("sensor")),
        ("Acquisition start", metadata.get("acquisition_start") or params.get("start_date") or params.get("date_start")),
        ("Acquisition end", metadata.get("acquisition_end") or params.get("end_date") or params.get("date_end")),
        ("Spatial resolution", metadata.get("spatial_resolution") or params.get("resolution")),
        ("Study extent", geometry.get("bounds_text") or _pdf_text(bounds)),
        ("South / West", f"{_pdf_text(extent.get('south'))} / {_pdf_text(extent.get('west'))}"),
        ("North / East", f"{_pdf_text(extent.get('north'))} / {_pdf_text(extent.get('east'))}"),
        ("Processing version", metadata.get("processing_version") or params.get("processing_method") or "default-v1"),
        ("GeoRasterPortal version", metadata.get("georasterportal_version") or REPORT_APP_VERSION),
    ]
    _pdf_kv_table(draw, meta_rows, meta_panel[0] + 18, meta_panel[1] + 70, meta_panel[2] - meta_panel[0] - 36, row_h=54)
    _pdf_draw_footer(draw, generated_at, 4)
    return page


def _professional_map_pdf_pages(payload: MapPdfExportRequest, generated_at: str) -> list[Image.Image]:
    reference_image, result_image, locator_image = _pdf_export_images(payload)
    pages = [
        _pdf_cover_page(payload, reference_image, generated_at),
        _pdf_study_area_page(payload, reference_image, result_image, generated_at),
    ]
    if _is_change_detection_pdf(payload.analysis_type):
        result = _load_run_result_for_export(str(payload.analysis_id or "").strip() or None)
        change_page = _pdf_change_detection_visual_page(payload, result or {}, generated_at, 3)
        if change_page is not None:
            pages.append(change_page)
            pages.append(_pdf_result_page(payload, result_image, locator_image, generated_at, page_number=4, section_start=6))
            return pages
    pages.append(_pdf_result_page(payload, result_image, locator_image, generated_at))
    return pages


def _map_pdf_pages(payload: MapPdfExportRequest, screenshot: Image.Image, generated_at: str) -> list[Image.Image]:
    analysis_type = payload.analysis_type
    analysis_label = _analysis_pdf_label(analysis_type)
    params = payload.parameters or {}
    geometry = payload.geometry_info or {}
    stats = payload.statistics or {}
    classes = payload.classes or []
    legend = payload.legend or []
    quality = payload.quality_summary or {}
    interpretation = payload.interpretation or _default_pdf_interpretation(analysis_type)
    bounds = geometry.get("bounds") or geometry.get("bbox") or params.get("bounds")
    bounds_text = geometry.get("bounds_text") or _pdf_text(bounds)
    area_ha = geometry.get("area_ha") or stats.get("surface_ha") or stats.get("total_area_ha") or stats.get("surface")
    area_km2 = geometry.get("area_km2")
    if area_km2 is None and area_ha not in (None, "-"):
        with suppress(Exception):
            area_km2 = float(area_ha) / 100

    pages: list[Image.Image] = []

    page, draw = _pdf_page()
    _pdf_draw_header(draw, page, "Raster Analysis Report", f"Analysis {analysis_label}", 1)
    y = 226
    y = _pdf_section(draw, "Analysis Description", y)
    y = _pdf_draw_wrapped(
        draw,
        _analysis_pdf_description(analysis_type),
        PDF_MARGIN,
        y,
        PDF_PAGE_SIZE[0] - PDF_MARGIN * 2,
        _pdf_font(15),
        PDF_TEXT,
        max_lines=3,
    ) + 34
    draw.text((PDF_MARGIN, y), "GeoRaster", font=_pdf_font(46, True), fill=PDF_ACCENT)
    y += 66
    _pdf_draw_wrapped(draw, f"Professional report generated on {generated_at}", PDF_MARGIN, y, 760, _pdf_font(19), PDF_MUTED)
    y += 70
    if payload.user_name:
        draw.text((PDF_MARGIN, y), f"User: {payload.user_name}", font=_pdf_font(16), fill=PDF_TEXT)
        y += 36
    y = _pdf_section(draw, "General Information", y + 22)
    rows = [
        ("Analysis type", analysis_label),
        ("Area of interest", geometry.get("label") or "Area drawn in the application"),
        ("Surface", f"{_pdf_number(area_ha, ' ha')} / {_pdf_number(area_km2, ' km2')}"),
        ("Coordinates / bounds", bounds_text),
        ("Sensor", params.get("sensor")),
        ("Resolution", params.get("resolution")),
        ("Start date", params.get("start_date") or params.get("date_start")),
        ("End date", params.get("end_date") or params.get("date_end")),
        ("Maximum scene cloud", _pdf_number(params.get("cloud_max") or params.get("max_cloud_pct"), "%")),
        ("Processing method", params.get("processing_method") or params.get("image_method") or "median_composite"),
        ("GEE images used", params.get("images_count") or quality.get("images_count") or quality.get("available_images")),
        ("Display mode", params.get("display_mode") or quality.get("mode") or "catalog/mosaic"),
    ]
    _pdf_kv_table(draw, rows, PDF_MARGIN, y, PDF_PAGE_SIZE[0] - PDF_MARGIN * 2)
    _pdf_draw_footer(draw, generated_at, 1)
    pages.append(page)

    page, draw = _pdf_page()
    _pdf_draw_header(draw, page, "Result Map", f"Analysis {analysis_label}", 2)
    y = 222
    map_img = _fit_pdf_image(screenshot, PDF_PAGE_SIZE[0] - PDF_MARGIN * 2, 860)
    map_x = PDF_MARGIN + ((PDF_PAGE_SIZE[0] - PDF_MARGIN * 2) - map_img.width) // 2
    draw.rectangle((PDF_MARGIN - 2, y - 2, PDF_PAGE_SIZE[0] - PDF_MARGIN + 2, y + map_img.height + 2), outline=PDF_BORDER, width=2)
    page.paste(map_img, (map_x, y))
    y += map_img.height + 46
    y = _pdf_section(draw, "Legend", y)
    item_font = _pdf_font(13)
    for item in legend[:12]:
        color = _pdf_color(item.get("color"))
        draw.rounded_rectangle((PDF_MARGIN, y + 4, PDF_MARGIN + 24, y + 28), radius=4, fill=color, outline="#8a94a6")
        draw.text((PDF_MARGIN + 38, y + 2), _pdf_text(item.get("label") or item.get("name")), font=_pdf_font(13, True), fill=PDF_TEXT)
        y = _pdf_draw_wrapped(draw, item.get("meaning") or item.get("description") or "", PDF_MARGIN + 38, y + 23, 900, item_font, PDF_MUTED, max_lines=2)
        y += 8
        if y > PDF_PAGE_SIZE[1] - 150:
            break
    _pdf_draw_footer(draw, generated_at, 2)
    pages.append(page)

    page, draw = _pdf_page()
    _pdf_draw_header(draw, page, "Statistics and Interpretation", f"Analysis {analysis_label}", 3)
    y = 222
    metric_rows = [
        ("Minimum", stats.get("min")),
        ("Maximum", stats.get("max")),
        ("Mean", stats.get("mean")),
        ("Total area", f"{_pdf_number(area_ha, ' ha')}"),
        ("Dominant class", _dominant_class(classes)),
        ("Overall accuracy", _pdf_percent(quality.get("overall_accuracy") or stats.get("overall_accuracy"))),
        ("Method", quality.get("classifier") or quality.get("cluster_method") or params.get("processing_method")),
    ]
    y = _pdf_kv_table(draw, metric_rows, PDF_MARGIN, y, PDF_PAGE_SIZE[0] - PDF_MARGIN * 2, row_h=40) + 34
    y = _pdf_section(draw, "Class Areas", y)
    header_h = 34
    col_x = [PDF_MARGIN, PDF_MARGIN + 46, PDF_MARGIN + 520, PDF_MARGIN + 704, PDF_MARGIN + 828, PDF_MARGIN + 936]
    draw.rectangle((PDF_MARGIN, y, PDF_PAGE_SIZE[0] - PDF_MARGIN, y + header_h), fill="#edf7f6", outline=PDF_BORDER)
    for x, title in zip(col_x[1:], ["Class", "Surface ha", "%", "Min", "Max"], strict=False):
        draw.text((x, y + 8), title, font=_pdf_font(12, True), fill=PDF_TEXT)
    y += header_h
    for idx, item in enumerate(classes[:14]):
        row_h = 38
        draw.rectangle((PDF_MARGIN, y, PDF_PAGE_SIZE[0] - PDF_MARGIN, y + row_h), fill="#fbfcfe" if idx % 2 == 0 else "white", outline=PDF_BORDER)
        draw.rounded_rectangle((PDF_MARGIN + 12, y + 10, PDF_MARGIN + 32, y + 30), radius=3, fill=_pdf_color(item.get("color")), outline="#8a94a6")
        draw.text((col_x[1], y + 10), _pdf_text(item.get("name") or item.get("label")), font=_pdf_font(12), fill=PDF_TEXT)
        draw.text((col_x[2], y + 10), _pdf_number(item.get("surface_ha") or item.get("surface")), font=_pdf_font(12), fill=PDF_TEXT)
        draw.text((col_x[3], y + 10), _pdf_number(item.get("pct") or item.get("percentage"), "%"), font=_pdf_font(12), fill=PDF_TEXT)
        draw.text((col_x[4], y + 10), _pdf_text(item.get("min")), font=_pdf_font(12), fill=PDF_TEXT)
        draw.text((col_x[5], y + 10), _pdf_text(item.get("max")), font=_pdf_font(12), fill=PDF_TEXT)
        y += row_h
    y += 34
    y = _pdf_section(draw, "Automatic Interpretation", y)
    y = _pdf_draw_wrapped(draw, interpretation, PDF_MARGIN, y, PDF_PAGE_SIZE[0] - PDF_MARGIN * 2, _pdf_font(15), PDF_TEXT, max_lines=7) + 30
    y = _pdf_section(draw, "Processing Quality", y)
    quality_text = quality.get("message") or quality.get("quality") or "The result is based on a Google Earth Engine satellite mosaic. Reliability depends on the selected period, cloud cover, sensor quality, and available imagery."
    _pdf_draw_wrapped(draw, quality_text, PDF_MARGIN, y, PDF_PAGE_SIZE[0] - PDF_MARGIN * 2, _pdf_font(14), PDF_MUTED, max_lines=5)
    _pdf_draw_footer(draw, generated_at, 3)
    pages.append(page)
    return pages


def _map_pdf_bytes(payload: MapPdfExportRequest) -> tuple[str, bytes]:
    timings: dict[str, float] = {}
    total_start = time.perf_counter()
    generated_date = datetime.now(timezone.utc).date().isoformat()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if _pdf_payload_language(payload) == "ar":
        filename = f"GeoRaster_تقرير_{_analysis_pdf_slug(payload.analysis_type)}_{generated_date}.pdf"
    else:
        filename = f"GeoRaster_Report_{_analysis_pdf_slug(payload.analysis_type)}_{generated_date}.pdf"
    pages = _professional_map_pdf_pages(payload, generated_at)
    timings["pdf_generation"] = time.perf_counter() - total_start
    LOGGER.info("Map PDF generated in %.3fs for %s", timings["pdf_generation"], payload.analysis_type)
    buffer = io.BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    timings["pdf_serialization"] = time.perf_counter() - total_start
    LOGGER.info("Map PDF serialized in %.3fs for %s", timings["pdf_serialization"], payload.analysis_type)
    return filename, buffer.getvalue()


MAP_LAYOUT_SIZE = (1800, 1280)


def _load_run_result_for_layout(run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT result_json FROM runs WHERE id = ?", (run_id,))
        if row:
            return db.json_loads(row["result_json"] or "{}")
        cache_row = db.fetch_one(conn, "SELECT result_json FROM processing_cache WHERE cache_key = ?", (run_id,))
        if cache_row:
            return db.json_loads(cache_row["result_json"] or "{}")
    return None


def _bounds_from_layout_payload(payload: MapPdfExportRequest, result: dict[str, Any] | None = None) -> tuple[float, float, float, float] | None:
    bounds = (payload.geometry_info or {}).get("bounds")
    if not bounds:
        bounds = _pdf_bounds_from_aoi(((result or {}).get("analysis") or {}).get("aoi"))
    if isinstance(bounds, list) and len(bounds) == 2:
        try:
            south, west = float(bounds[0][0]), float(bounds[0][1])
            north, east = float(bounds[1][0]), float(bounds[1][1])
            return west, south, east, north
        except Exception:
            pass
    aoi = ((result or {}).get("analysis") or {}).get("aoi") or {}
    bbox = aoi.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 2:
        try:
            south, west = float(bbox[0][0]), float(bbox[0][1])
            north, east = float(bbox[1][0]), float(bbox[1][1])
            return west, south, east, north
        except Exception:
            pass
    coordinates = (aoi.get("geojson") or {}).get("coordinates", [[[]]])[0]
    if isinstance(coordinates, list) and coordinates:
        lons = [float(item[0]) for item in coordinates if isinstance(item, list) and len(item) >= 2]
        lats = [float(item[1]) for item in coordinates if isinstance(item, list) and len(item) >= 2]
        if lons and lats:
            return min(lons), min(lats), max(lons), max(lats)
    return None


def _lonlat_to_tile_pixel(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    scale = 256 * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def _download_tile_image(tile_url: str) -> Image.Image | None:
    try:
        with urllib.request.urlopen(tile_url, timeout=30) as response:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(response.read())))
            return image.convert("RGBA")
    except Exception:
        return None


def _download_layout_tile_mosaic(result: dict[str, Any], payload: MapPdfExportRequest) -> Image.Image | None:
    tiles = result.get("tiles") or {}
    tile_template = tiles.get("index_tile_url") or result.get("index_tile_url") or result.get("tile_url")
    if not tile_template or "{x}" not in tile_template or "{y}" not in tile_template or "{z}" not in tile_template:
        return None
    bounds = _bounds_from_layout_payload(payload, result)
    if not bounds:
        return None
    west, south, east, north = bounds
    if not west < east or not south < north:
        return None

    # 14 is a good balance for report exports: detailed enough for AOIs, but avoids large tile bursts.
    zoom = 14
    west_px, north_px = _lonlat_to_tile_pixel(west, north, zoom)
    east_px, south_px = _lonlat_to_tile_pixel(east, south, zoom)
    min_tile_x, max_tile_x = int(math.floor(west_px / 256)), int(math.floor((east_px - 1) / 256))
    min_tile_y, max_tile_y = int(math.floor(north_px / 256)), int(math.floor((south_px - 1) / 256))
    tile_count = (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)
    if tile_count <= 0 or tile_count > 80:
        return None

    mosaic = Image.new("RGBA", ((max_tile_x - min_tile_x + 1) * 256, (max_tile_y - min_tile_y + 1) * 256), (238, 245, 248, 255))
    downloaded = 0
    for tx in range(min_tile_x, max_tile_x + 1):
        for ty in range(min_tile_y, max_tile_y + 1):
            tile_url = tile_template.replace("{z}", str(zoom)).replace("{x}", str(tx)).replace("{y}", str(ty))
            tile = _download_tile_image(tile_url)
            if tile is None:
                continue
            mosaic.paste(tile, ((tx - min_tile_x) * 256, (ty - min_tile_y) * 256), tile)
            downloaded += 1
    if downloaded == 0:
        return None

    left = int(round(west_px - (min_tile_x * 256)))
    top = int(round(north_px - (min_tile_y * 256)))
    right = int(round(east_px - (min_tile_x * 256)))
    bottom = int(round(south_px - (min_tile_y * 256)))
    cropped = mosaic.crop((left, top, max(left + 1, right), max(top + 1, bottom)))
    background = Image.new("RGB", cropped.size, "#eef5f8")
    background.paste(cropped, mask=cropped.getchannel("A"))
    return background


def _download_layout_source_image(payload: MapPdfExportRequest) -> Image.Image:
    run_id = str(payload.analysis_id or "").strip() or None
    result = _load_run_result_for_layout(run_id)
    if not result:
        return _decode_map_screenshot(payload.map_screenshot)
    layer_key = (payload.metadata or {}).get("layer_key")
    result = _result_visual_layer(result, layer_key)
    try:
        image_url = create_index_png_url(result, layer_key=layer_key)
        with urllib.request.urlopen(image_url, timeout=60) as response:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(response.read())))
            if image.mode in {"RGBA", "LA"}:
                bg = Image.new("RGB", image.size, "white")
                bg.paste(image, mask=image.getchannel("A"))
                return bg
            return image.convert("RGB")
    except Exception:
        tile_mosaic = _download_layout_tile_mosaic(result, payload)
        if tile_mosaic is not None:
            return tile_mosaic
        return _decode_map_screenshot(payload.map_screenshot)


def _layout_period_text(payload: MapPdfExportRequest) -> str:
    params = payload.parameters or {}
    analysis_type = str(payload.analysis_type or "")
    if analysis_type.startswith("CHANGE_") or analysis_type.startswith("change_detection_"):
        p1s = params.get("period_1_start")
        p1e = params.get("period_1_end")
        p2s = params.get("period_2_start")
        p2e = params.get("period_2_end")
        return f"Period 1: {_pdf_text(p1s)} -> {_pdf_text(p1e)}    Period 2: {_pdf_text(p2s)} -> {_pdf_text(p2e)}"
    return f"Period: {_pdf_text(params.get('start_date'))} -> {_pdf_text(params.get('end_date'))}"


def _draw_layout_north_arrow(draw: ImageDraw.ImageDraw, center_x: int, top_y: int) -> None:
    draw.text((center_x - 10, top_y), "N", font=_pdf_font(28, True), fill=PDF_TEXT)
    shaft_top = top_y + 38
    shaft_bottom = shaft_top + 88
    draw.line((center_x, shaft_top + 10, center_x, shaft_bottom), fill=PDF_TEXT, width=7)
    draw.polygon(
        [
            (center_x, shaft_top - 10),
            (center_x - 24, shaft_top + 28),
            (center_x + 24, shaft_top + 28),
        ],
        fill=PDF_ACCENT,
        outline=PDF_TEXT,
    )
    draw.polygon(
        [
            (center_x, shaft_bottom + 18),
            (center_x - 16, shaft_bottom - 12),
            (center_x + 16, shaft_bottom - 12),
        ],
        fill="white",
        outline=PDF_TEXT,
    )


def _format_degree(value: float, axis: str) -> str:
    hemi = "N" if axis == "lat" and value >= 0 else "S" if axis == "lat" else "E" if value >= 0 else "W"
    return f"{abs(value):.4f}{hemi}"


def _draw_layout_scale(draw: ImageDraw.ImageDraw, x: int, y: int, width: int) -> None:
    width = max(120, int(width))
    seg = max(24, width // 4)
    width = seg * 4
    draw.rectangle((x, y, x + width, y + 22), outline=PDF_TEXT, width=2, fill="white")
    for idx in range(4):
        fill = PDF_TEXT if idx % 2 == 0 else "white"
        draw.rectangle((x + idx * seg, y, x + (idx + 1) * seg, y + 22), outline=PDF_TEXT, width=1, fill=fill)
    draw.text((x, y + 30), "0", font=_pdf_font(12), fill=PDF_TEXT)
    draw.text((x + seg - 8, y + 30), "250 m", font=_pdf_font(12), fill=PDF_TEXT)
    draw.text((x + seg * 2 - 8, y + 30), "500 m", font=_pdf_font(12), fill=PDF_TEXT)
    draw.text((x + seg * 4 - 18, y + 30), "1 km", font=_pdf_font(12), fill=PDF_TEXT)


def _draw_layout_map_frame(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], bounds: Any = None) -> None:
    draw.rectangle(rect, outline="#111827", width=5)


def _draw_layout_aoi_locator(draw: ImageDraw.ImageDraw, page: Image.Image, rect: tuple[int, int, int, int], locator_image: Image.Image | None) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=10, outline=PDF_TEXT, width=2, fill="white")
    draw.text((x0 + 14, y0 + 10), "AOI locator", font=_pdf_font(14, True), fill=PDF_TEXT)
    inner = (x0 + 18, y0 + 42, x1 - 18, y1 - 18)
    draw.rectangle(inner, outline="#9aa7bd", width=2, fill="#eef3f7")
    if locator_image is None:
        return
    fitted = locator_image.copy()
    fitted.thumbnail((inner[2] - inner[0], inner[3] - inner[1]))
    img_x = inner[0] + ((inner[2] - inner[0]) - fitted.width) // 2
    img_y = inner[1] + ((inner[3] - inner[1]) - fitted.height) // 2
    page.paste(fitted, (img_x, img_y))
    draw.rectangle((img_x, img_y, img_x + fitted.width, img_y + fitted.height), outline="#9aa7bd", width=2)


def _map_layout_image(payload: MapPdfExportRequest, map_image: Image.Image, generated_at: str) -> Image.Image:
    page = Image.new("RGB", MAP_LAYOUT_SIZE, "white")
    draw = ImageDraw.Draw(page)
    language = _pdf_payload_language(payload)
    is_ar = language == "ar"
    # Official analysis names and acronyms intentionally remain unchanged.
    analysis_label = _analysis_pdf_label(payload.analysis_type)
    geometry = payload.geometry_info or {}
    legend = _pdf_result_legend(payload) if is_ar else (payload.legend or payload.classes or [])

    page_margin = 72
    draw.rounded_rectangle(
        (page_margin, page_margin, MAP_LAYOUT_SIZE[0] - page_margin, MAP_LAYOUT_SIZE[1] - page_margin),
        radius=22,
        outline=PDF_BORDER,
        width=3,
    )

    title = f"الخريطة المصنفة لتحليل {analysis_label}" if is_ar else f"Classified Map of the {analysis_label} Analysis"
    title_font = _pdf_font(38, True)
    rendered_title = _pdf_display_text(title, language)
    title_bbox = draw.textbbox((0, 0), rendered_title, font=title_font)
    title_x = (MAP_LAYOUT_SIZE[0] - (title_bbox[2] - title_bbox[0])) // 2
    draw.text((title_x, 112), rendered_title, font=title_font, fill=PDF_TEXT)
    draw.line((page_margin + 40, 178, MAP_LAYOUT_SIZE[0] - page_margin - 40, 178), fill=PDF_BORDER, width=2)

    map_panel = (118, 224, 1264, 1136)
    legend_panel = (1304, 224, 1682, 1136)

    draw.rounded_rectangle(map_panel, radius=16, outline=PDF_BORDER, width=3, fill="#fbfcfe")
    draw.rounded_rectangle(legend_panel, radius=16, outline=PDF_BORDER, width=3, fill="#fbfcfe")
    if is_ar:
        _pdf_draw_text(
            draw,
            "مفتاح الخريطة",
            legend_panel[2] - 24,
            legend_panel[1] + 22,
            _pdf_font(22, True),
            PDF_TEXT,
            language=language,
            right=legend_panel[2] - 24,
        )
    else:
        draw.text((legend_panel[0] + 24, legend_panel[1] + 22), "Legend", font=_pdf_font(22, True), fill=PDF_TEXT)

    map_inner_margin_x = 34
    map_inner_top = 54
    map_bottom_reserved = 114
    map_inner_width = map_panel[2] - map_panel[0] - (map_inner_margin_x * 2)
    map_inner_height = map_panel[3] - map_panel[1] - map_inner_top - map_bottom_reserved
    map_img = _fit_pdf_image(map_image, map_inner_width, map_inner_height, upscale=True)
    map_x = map_panel[0] + map_inner_margin_x + (map_inner_width - map_img.width) // 2
    map_y = map_panel[1] + map_inner_top + (map_inner_height - map_img.height) // 2
    frame_rect = (map_x - 4, map_y - 4, map_x + map_img.width + 4, map_y + map_img.height + 4)
    page.paste(map_img, (map_x, map_y))
    _draw_layout_map_frame(draw, frame_rect, geometry.get("bounds"))
    _draw_layout_scale(draw, map_x + 10, map_y + map_img.height + 34, min(300, map_img.width - 20))
    _draw_layout_north_arrow(draw, map_panel[2] - 64, map_panel[1] + 30)

    legend_y = legend_panel[1] + 76
    for item in legend[:10]:
        color = _pdf_color(item.get("color"))
        if is_ar:
            color_left = legend_panel[2] - 56
            draw.rounded_rectangle((color_left, legend_y, legend_panel[2] - 24, legend_y + 28), radius=6, fill=color, outline="#8a94a6")
            text_right = color_left - 14
            text_left = legend_panel[0] + 24
            text_width = max(40, text_right - text_left)
            _pdf_draw_wrapped(
                draw,
                _pdf_text(item.get("label") or item.get("name")),
                text_left,
                legend_y - 1,
                text_width,
                _pdf_font(15, True),
                PDF_TEXT,
                max_lines=1,
                language=language,
                align="right",
            )
        else:
            draw.rounded_rectangle((legend_panel[0] + 24, legend_y, legend_panel[0] + 56, legend_y + 28), radius=6, fill=color, outline="#8a94a6")
            draw.text((legend_panel[0] + 72, legend_y - 1), _pdf_text(item.get("label") or item.get("name")), font=_pdf_font(15, True), fill=PDF_TEXT)
        details = item.get("meaning") or item.get("description") or ""
        if is_ar:
            value_parts: list[str] = []
            if item.get("surface_ha") not in (None, ""):
                value_parts.append(f"المساحة: {_pdf_number(item.get('surface_ha'))} هكتار")
            if item.get("pct") not in (None, ""):
                value_parts.append(f"النسبة: {_pdf_number(item.get('pct'))}٪")
            if value_parts:
                details = "  |  ".join(value_parts)
        elif item.get("pct") not in (None, ""):
            details = f"{details} {_pdf_number(item.get('pct'), '%')} / {_pdf_number(item.get('surface_ha'), ' ha')}".strip()
        if is_ar:
            legend_y = _pdf_draw_wrapped(
                draw,
                details,
                text_left,
                legend_y + 24,
                text_width,
                _pdf_font(13),
                PDF_MUTED,
                max_lines=1,
                language=language,
                align="right",
            )
        else:
            legend_y = _pdf_draw_wrapped(draw, details, legend_panel[0] + 72, legend_y + 24, legend_panel[2] - legend_panel[0] - 96, _pdf_font(13), PDF_MUTED, max_lines=2)
        legend_y += 16
        if legend_y > legend_panel[3] - 72:
            break

    return page


def _map_layout_png_bytes(payload: MapPdfExportRequest) -> tuple[str, bytes]:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    map_image = _download_layout_source_image(payload)
    image = _map_layout_image(payload, map_image, generated_at)
    generated_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    if _pdf_payload_language(payload) == "ar":
        filename = f"GeoRaster_خريطة_{_analysis_pdf_slug(payload.analysis_type)}_{generated_stamp}.png"
    else:
        filename = f"GeoRaster_Map_{_analysis_pdf_slug(payload.analysis_type)}_{generated_stamp}.png"
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return filename, buffer.getvalue()


def _persist_classification_artifacts(conn: Any, analysis: dict[str, Any], run_id: str, result: dict[str, Any], cache_key: str) -> None:
    analysis_type = str(result.get("analysis_type") or "")
    if analysis_type != "supervised_classification":
        return
    model_id = str(uuid.uuid4())
    result_id = str(uuid.uuid4())
    metric_id = str(uuid.uuid4())
    created_at = now_iso()
    quality = result.get("quality_summary") or {}
    accuracy = result.get("accuracy") or {}
    model_metadata = {
        "algorithm_label": quality.get("classifier"),
        "training_split": quality.get("training_split"),
        "sample_source": quality.get("sample_source"),
        "validation_split_mode": quality.get("validation_split_mode"),
        "reference": quality.get("reference"),
        "warning": quality.get("warning"),
    }
    with suppress(Exception):
        conn.execute(
            """
            INSERT OR IGNORE INTO classification_models (
              id, project_id, name, algorithm, algorithm_params_json, input_bands_json,
              samples_hash, aoi_hash, cache_key, gee_asset_id, model_metadata_json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                quality.get("project_id") or "default",
                analysis.get("name") or "Supervised classification model",
                quality.get("algorithm") or "random_forest",
                db.json_dumps(quality.get("algorithm_params") or {}),
                db.json_dumps(["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "NDBI", "BSI", "SAVI"]),
                cache_key,
                result_context_key_for_analysis(analysis),
                cache_key,
                None,
                db.json_dumps(model_metadata),
                "trained",
                created_at,
            ),
        )
    row = db.fetch_one(conn, "SELECT id FROM classification_models WHERE cache_key = ?", (cache_key,))
    persisted_model_id = row["id"] if row else model_id
    conn.execute(
        """
        INSERT INTO classification_results (
          id, project_id, model_id, run_id, aoi_json, classified_tile_url, classified_asset_id,
          palette_json, class_stats_json, mode, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result_id,
            quality.get("project_id") or "default",
            persisted_model_id,
            run_id,
            db.json_dumps(analysis.get("aoi") or {}),
            (result.get("tiles") or {}).get("index_tile_url"),
            None,
            db.json_dumps(result.get("palette") or []),
            db.json_dumps(result.get("classes") or []),
            result.get("mode") or "gee",
            "completed",
            created_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO validation_metrics (
          id, result_id, model_id, confusion_matrix_json, overall_accuracy, kappa,
          producer_accuracy_json, user_accuracy_json, omission_error_json, commission_error_json,
          validation_samples_count, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric_id,
            result_id,
            persisted_model_id,
            db.json_dumps(accuracy.get("confusion_matrix") or []),
            accuracy.get("overall_accuracy"),
            accuracy.get("kappa"),
            db.json_dumps(accuracy.get("producer_accuracy") or []),
            db.json_dumps(accuracy.get("user_accuracy") or []),
            db.json_dumps([item.get("omission_error") for item in accuracy.get("class_metrics") or []]),
            db.json_dumps([item.get("commission_error") for item in accuracy.get("class_metrics") or []]),
            int((result.get("stats") or {}).get("validation_samples_count") or 0),
            created_at,
        ),
    )

def analysis_to_history(item: dict[str, Any]) -> dict[str, Any]:
    quality = item.get("quality") or item.get("mosaic") or {}
    return {
        "id": item["id"],
        "name": item["name"],
        "date": item["created_at"][:10],
        "user": item.get("user") or "local-user",
        "image": item.get("image_id") or "Sentinel-2 Surface Reflectance",
        "source": item.get("source", "S2_SR_HARMONIZED"),
        "index": item.get("index", "NDVI"),
        "method": item.get("image_method", "least_cloudy"),
        "period": f"{item.get('date_start', '-')} -> {item.get('date_end', '-')}",
        "area": f"{area_from_bbox_ha(item.get('aoi') or {})} ha",
        "area_km2": quality.get("area_km2"),
        "images_count": quality.get("images_count"),
        "tiles_count": quality.get("tiles_count"),
        "quality": quality.get("quality"),
        "coverage_percent": quality.get("coverage_percent"),
        "status": item.get("display_status", "En cours"),
        "exports": item.get("exports", []),
    }


def _history_analysis_label(index_id: str) -> str:
    labels = {
        "NDVI": "NDVI Analysis",
        "NDWI": "NDWI Analysis",
        "NDBI": "NDBI Analysis",
        "BSI": "BSI Analysis",
        "SAVI": "SAVI Analysis",
        "OSI_SAR": "OSI-SAR Analysis",
        "CHANGE_NDVI": "NDVI Change Detection",
        "CHANGE_NDWI": "NDWI Change Detection",
        "CHANGE_NDBI": "NDBI Change Detection",
        "CHANGE_BSI": "BSI Change Detection",
        "CHANGE_SAVI": "SAVI Change Detection",
        "SUPERVISED_CLASSIFICATION": "Supervised Classification",
        "UNSUPERVISED_CLASSIFICATION": "Unsupervised Classification",
    }
    return labels.get(index_id, f"{index_id} Analysis")


def _history_study_area_name(analysis: dict[str, Any]) -> str:
    for key in ("study_area_name", "area_name", "zone_name", "region_name"):
        value = str(analysis.get(key) or "").strip()
        if value and value.upper() != "AOI":
            return value
    bbox = (analysis.get("aoi") or {}).get("bbox")
    if isinstance(bbox, list) and len(bbox) == 2:
        try:
            south, west = float(bbox[0][0]), float(bbox[0][1])
            north, east = float(bbox[1][0]), float(bbox[1][1])
            return f"Study area {((south + north) / 2):.4f}, {((west + east) / 2):.4f}"
        except Exception:
            pass
    return "Selected study area"


def _history_period(analysis: dict[str, Any]) -> str:
    if str(analysis.get("index") or "").startswith("CHANGE_"):
        period_1 = analysis.get("period_1") or {}
        period_2 = analysis.get("period_2") or {}
        return f"{period_1.get('start_date', '-')} -> {period_1.get('end_date', '-')} / {period_2.get('start_date', '-')} -> {period_2.get('end_date', '-')}"
    return f"{analysis.get('date_start') or analysis.get('start_date') or '-'} -> {analysis.get('date_end') or analysis.get('end_date') or '-'}"


def _history_sensor_label(sensor: Any) -> str:
    labels = {
        "sentinel-2": "Sentinel-2",
        "landsat-8-9": "Landsat 8/9",
        "sentinel-1": "Sentinel-1 SAR",
        "dynamic-world": "Dynamic World",
        "esa-worldcover": "ESA WorldCover",
    }
    return labels.get(str(sensor or ""), _pdf_text(sensor or "Unknown sensor"))


def _history_item_from_run(row: Any, exports: list[dict[str, Any]]) -> dict[str, Any]:
    # The history list must stay fast and must not refresh GEE tiles for every row.
    # Full visual refresh is reserved for opening a specific run from History.
    result = _synchronize_result_visual_metadata(db.json_loads(row["result_json"] or "{}"))
    analysis = _apply_spatial_reference_to_analysis(result.get("analysis") or db.json_loads(row["payload_json"] or "{}"))
    index_id = analysis_kind(analysis)
    stats = result.get("stats") or {}
    quality = result.get("quality_summary") or result.get("quality") or result.get("mosaic") or {}
    cache_key = None
    with suppress(Exception):
        cache_key = cache_key_for_analysis(analysis)
    surface_ha = stats.get("surface_ha") or stats.get("total_area_ha") or stats.get("surface") or area_from_bbox_ha(analysis.get("aoi") or {})
    export_types = [str(item.get("kind") or "").replace("_", " ").upper() for item in exports if item.get("kind")]
    return {
        "id": row["id"],
        "run_id": row["id"],
        "analysis_id": row["analysis_id"],
        "name": _history_analysis_label(index_id),
        "study_area_name": _history_study_area_name(analysis),
        "date": str(row["created_at"])[:10],
        "executed_at": row["created_at"],
        "updated_at": row["updated_at"],
        "period": _history_period(analysis),
        "sensor": _history_sensor_label(analysis.get("sensor")),
        "sensor_id": analysis.get("sensor"),
        "resolution": analysis.get("resolution"),
        "index": index_id,
        "status": row["status"],
        "surface_ha": surface_ha,
        "area": _pdf_number(surface_ha, " ha"),
        "exports": exports,
        "export_types": export_types,
        "export_summary": ", ".join(export_types) if export_types else "No export yet",
        "classes": result.get("classes") or [],
        "legend": result.get("classes") or [],
        "stats": stats,
        "statistics": stats,
        "histogram": result.get("histogram") or [],
        "tiles": result.get("tiles") or {},
        "tile_url": (result.get("tiles") or {}).get("index_tile_url"),
        "aoi": analysis.get("aoi"),
        "analysis": analysis,
        "quality_summary": quality,
        "quality": quality.get("quality") or quality.get("message"),
        "coverage_percent": quality.get("coverage_percent"),
        "cache_key": cache_key,
        "mode": result.get("mode"),
        "metadata": {
            "source": analysis.get("source") or quality.get("source"),
            "image_id": analysis.get("image_id"),
            "processing_version": analysis.get("processing_version"),
            "spatial_reference": analysis.get("spatial_reference"),
        },
        "backend": True,
    }


app = FastAPI(title="GeoRaster Backend (MVP)", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ai_raster_router)
app.include_router(ai_inference_router)
app.include_router(ai_postprocessing_router)
app.include_router(ai_vectorization_router)
app.include_router(ai_results_router)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    ensure_default_landcover_classes()
    purge_incompatible_processing_cache()
    _fail_interrupted_async_jobs()
    warm_gee_connection()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "georaster-backend", "time": now_iso(), "mvp": "Sentinel-2 NDVI/NDWI/NDBI/BSI/SAVI/Change Detection/Supervised/Unsupervised Classification"}


@app.get("/api/gee/status")
def get_gee_status() -> dict[str, Any]:
    # Keep status snappy; background warm-up + frontend retry cover slower first connects.
    return {"item": gee_status(wait_seconds=25)}


@app.get("/api/settings/platform")
def get_platform_settings() -> dict[str, Any]:
    settings = _clean_platform_settings(_read_platform_settings())
    return {
        **settings,
        "coordinate_reference": {
            "web_map_crs": CRS_CATALOG["EPSG:3857"],
            "analysis_choices": [CRS_CATALOG[code] for code in ("EPSG:9332", "EPSG:9333", "EPSG:9356", "EPSG:9357", "EPSG:9358", "EPSG:9359", "EPSG:9360")],
            "simulation_3d": CRS_CATALOG["EPSG:9332"],
            "effective": _effective_spatial_reference(None, settings=settings),
        },
    }


@app.put("/api/settings/platform")
async def update_platform_settings(request: Request) -> dict[str, Any]:
    payload = await request.json()
    settings = _write_platform_settings(_clean_platform_settings(payload if isinstance(payload, dict) else {}))
    return {
        **settings,
        "coordinate_reference": {
            "web_map_crs": CRS_CATALOG["EPSG:3857"],
            "analysis_choices": [CRS_CATALOG[code] for code in ("EPSG:9332", "EPSG:9333", "EPSG:9356", "EPSG:9357", "EPSG:9358", "EPSG:9359", "EPSG:9360")],
            "effective": _effective_spatial_reference(None, settings=settings),
        },
    }


@app.post("/api/settings/logo")
async def upload_platform_logo(request: Request, x_user_role: str | None = Header(default="admin")) -> dict[str, Any]:
    _assert_admin(x_user_role)
    content_type = (request.headers.get("content-type") or "").split(";")[0].lower()

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Aucun fichier logo recu.")
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="Le logo ne doit pas depasser 2 MB.")
    extension = _logo_extension_for_upload(content_type, data)

    PLATFORM_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _clear_platform_logos()
    logo_path = PLATFORM_UPLOAD_DIR / f"logo.{extension}"
    logo_path.write_bytes(data)
    logo_url = f"/uploads/platform/logo.{extension}?v={int(datetime.now(timezone.utc).timestamp())}"
    settings = _write_platform_settings({"platform_name": "GeoRaster", "logo_url": logo_url})
    return {"success": True, "logo_url": settings["logo_url"], "message": "Logo updated successfully"}


@app.post("/api/settings/logo/reset")
def reset_platform_logo(x_user_role: str | None = Header(default="admin")) -> dict[str, Any]:
    _assert_admin(x_user_role)
    _clear_platform_logos()
    settings = _write_platform_settings({"platform_name": "GeoRaster", "logo_url": None})
    return {"success": True, "logo_url": settings["logo_url"], "message": "Default logo restored"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    with db.connect() as conn:
        analysis_count = db.fetch_one(conn, "SELECT COUNT(*) AS n FROM analyses")["n"]
        export_count = db.fetch_one(conn, "SELECT COUNT(*) AS n FROM exports")["n"]
        rows = db.fetch_all(conn, "SELECT payload_json FROM analyses ORDER BY created_at DESC LIMIT 5")
    return {
        "stats": {
            "images": len(IMAGES),
            "analyses": analysis_count,
            "indices": len([i for i in INDICES if i.get("enabled")]),
            "exports": export_count,
        },
        "recent_analyses": [analysis_to_history(db.json_loads(r["payload_json"])) for r in rows],
        "indices": INDICES,
    }


@app.get("/api/catalog/sources")
def list_sources() -> dict[str, Any]:
    return {"items": SOURCES}


@app.get("/api/catalog/indices")
def list_indices(enabled_only: bool = Query(default=False)) -> dict[str, Any]:
    items = [i for i in INDICES if i.get("enabled")] if enabled_only else INDICES
    return {"items": items}


@app.get("/api/catalog/images")
def list_catalog_images(
    sensor: str = Query(default="all"),
    region: str = Query(default="all"),
    max_cloud: int = Query(default=100, ge=0, le=100),
    q: str = Query(default=""),
) -> dict[str, Any]:
    del sensor, region, max_cloud, q
    return {
        "items": [],
        "source": "map_search",
        "message": "Live satellite scenes are searched from Map & Analysis with an AOI. This catalog does not return mock images.",
    }


@app.get("/api/classification/classes")
def list_landcover_classes(project_id: str = Query(default="default")) -> dict[str, Any]:
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT id, project_id, code, name, description, color, sort_order, is_active, created_at
            FROM landcover_classes
            WHERE project_id = ? OR project_id = 'default'
            ORDER BY sort_order, code
            """,
            (project_id,),
        )
    return {"items": [dict(row) for row in rows]}


@app.post("/api/classification/classes")
async def create_landcover_class(request: Request) -> dict[str, Any]:
    payload = await request.json()
    created_at = now_iso()
    project_id = str(payload.get("project_id") or "default")
    code = int(payload.get("code") or 0)
    if code <= 0:
        raise HTTPException(status_code=422, detail="Class code must be a positive integer")
    item = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "code": code,
        "name": str(payload.get("name") or "").strip(),
        "description": payload.get("description"),
        "color": str(payload.get("color") or "#bdbdbd"),
        "sort_order": int(payload.get("sort_order") or payload.get("code") or 0),
        "is_active": 1 if payload.get("is_active", True) else 0,
        "created_at": created_at,
    }
    if not item["name"]:
        raise HTTPException(status_code=422, detail="Class name is required")
    with db.connect() as conn:
        duplicate = db.fetch_one(
            conn,
            "SELECT id FROM landcover_classes WHERE project_id = ? AND (code = ? OR lower(name) = lower(?))",
            (project_id, code, item["name"]),
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="A class with this code or name already exists")
        conn.execute(
            """
            INSERT INTO landcover_classes (id, project_id, code, name, description, color, sort_order, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                item["project_id"],
                item["code"],
                item["name"],
                item["description"],
                item["color"],
                item["sort_order"],
                item["is_active"],
                item["created_at"],
            ),
        )
    return {"item": item}


def _normalize_training_sample_geometry(geometry: Any) -> dict[str, Any]:
    if not isinstance(geometry, dict):
        raise HTTPException(status_code=422, detail="Sample geometry must be a GeoJSON object")
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates")

    def coordinate_pair(value: Any) -> list[float]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            raise HTTPException(status_code=422, detail="Invalid sample coordinate")
        try:
            longitude = float(value[0])
            latitude = float(value[1])
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid sample coordinate")
        if not math.isfinite(longitude) or not math.isfinite(latitude):
            raise HTTPException(status_code=422, detail="Sample coordinates must be finite")
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise HTTPException(status_code=422, detail="Sample coordinates are outside longitude/latitude bounds")
        return [longitude, latitude]

    if geometry_type == "Point":
        return {**geometry, "type": "Point", "coordinates": coordinate_pair(coordinates)}
    if geometry_type == "Polygon":
        if not isinstance(coordinates, (list, tuple)) or not coordinates or not isinstance(coordinates[0], (list, tuple)):
            raise HTTPException(status_code=422, detail="Polygon sample must contain a linear ring")
        ring = [coordinate_pair(value) for value in coordinates[0]]
        if len({(value[0], value[1]) for value in ring}) < 3:
            raise HTTPException(status_code=422, detail="Polygon sample requires at least three distinct vertices")
        if ring[0] != ring[-1]:
            ring.append(list(ring[0]))
        return {**geometry, "type": "Polygon", "coordinates": [ring]}
    raise HTTPException(status_code=422, detail="Only Point and Polygon training samples are supported")


@app.get("/api/classification/samples")
def list_training_samples(project_id: str = Query(default="default")) -> dict[str, Any]:
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT id, project_id, class_id, user_id, geometry_json, geometry_type, usage, quality_status, source, properties_json, created_at
            FROM training_samples
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,),
        )
    items = []
    for row in rows:
        item = dict(row)
        item["geometry"] = db.json_loads(item.pop("geometry_json"))
        item["properties"] = db.json_loads(item.pop("properties_json") or "{}")
        items.append(item)
    return {"items": items}


@app.post("/api/classification/samples")
async def create_training_sample(request: Request) -> dict[str, Any]:
    payload = await request.json()
    geometry = _normalize_training_sample_geometry(payload.get("geometry"))
    project_id = str(payload.get("project_id") or "default")
    class_id = str(payload.get("class_id") or "").strip()
    if not class_id:
        raise HTTPException(status_code=422, detail="A land-cover class is required")
    usage = str(payload.get("usage") or "training").lower()
    if usage not in {"training", "validation"}:
        raise HTTPException(status_code=422, detail="Sample usage must be training or validation")
    created_at = now_iso()
    item = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "class_id": class_id,
        "user_id": payload.get("user_id") or "local-user",
        "geometry": geometry,
        "geometry_type": geometry["type"],
        "usage": usage,
        "quality_status": payload.get("quality_status") or "valid",
        "source": payload.get("source") or "manual",
        "properties": payload.get("properties") or {},
        "created_at": created_at,
    }
    with db.connect() as conn:
        class_row = db.fetch_one(
            conn,
            "SELECT id FROM landcover_classes WHERE id = ? AND (project_id = ? OR project_id = 'default') AND is_active = 1",
            (class_id, project_id),
        )
        if not class_row:
            raise HTTPException(status_code=422, detail="The selected land-cover class does not exist or is inactive")
        conn.execute(
            """
            INSERT INTO training_samples (id, project_id, class_id, user_id, geometry_json, geometry_type, usage, quality_status, source, properties_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                item["project_id"],
                item["class_id"],
                item["user_id"],
                db.json_dumps(item["geometry"]),
                item["geometry_type"],
                item["usage"],
                item["quality_status"],
                item["source"],
                db.json_dumps(item["properties"]),
                item["created_at"],
            ),
        )
    return {"item": item}


@app.put("/api/classification/samples/{sample_id}")
async def update_training_sample(sample_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    with db.connect() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT id, project_id, class_id, user_id, geometry_json, geometry_type, usage,
                   quality_status, source, properties_json, created_at
            FROM training_samples
            WHERE id = ?
            """,
            (sample_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Training sample not found")
        item = dict(row)
        project_id = str(item.get("project_id") or "default")
        class_id = str(payload.get("class_id") or item.get("class_id") or "").strip()
        usage = str(payload.get("usage") or item.get("usage") or "training").lower()
        if usage not in {"training", "validation"}:
            raise HTTPException(status_code=422, detail="Sample usage must be training or validation")
        class_row = db.fetch_one(
            conn,
            "SELECT id FROM landcover_classes WHERE id = ? AND (project_id = ? OR project_id = 'default') AND is_active = 1",
            (class_id, project_id),
        )
        if not class_row:
            raise HTTPException(status_code=422, detail="The selected land-cover class does not exist or is inactive")
        conn.execute(
            "UPDATE training_samples SET class_id = ?, usage = ? WHERE id = ?",
            (class_id, usage, sample_id),
        )
    item["class_id"] = class_id
    item["usage"] = usage
    item["geometry"] = db.json_loads(item.pop("geometry_json"))
    item["properties"] = db.json_loads(item.pop("properties_json") or "{}")
    return {"item": item}


@app.delete("/api/classification/samples/{sample_id}")
def delete_training_sample(sample_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT id FROM training_samples WHERE id = ?", (sample_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Training sample not found")
        conn.execute("DELETE FROM training_samples WHERE id = ?", (sample_id,))
    return {"deleted": True, "id": sample_id}


@app.delete("/api/classification/classes/{class_id}/samples")
def delete_training_samples_for_class(
    class_id: str,
    project_id: str = Query(default="default"),
) -> dict[str, Any]:
    with db.connect() as conn:
        cursor = conn.execute(
            "DELETE FROM training_samples WHERE class_id = ? AND project_id = ?",
            (class_id, project_id),
        )
        deleted = max(int(cursor.rowcount or 0), 0)
    return {"deleted": True, "class_id": class_id, "samples_deleted": deleted}


@app.post("/api/catalog/images/search")
def search_catalog_images(payload: PreviewRequest, limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    return search_sentinel2(payload.model_dump(), limit=limit)


@app.post("/api/gee/jobs/catalog")
def create_gee_catalog_job(payload: PreviewRequest, limit: int = Query(default=12, ge=1, le=50)) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    created_at = now_iso()
    queued = {
        "job_id": job_id,
        "status": "queued",
        "progress_percent": 0,
        "current_step": "queued",
        "status_message": "Requete en attente",
        "message": "Requete en attente",
        "result": None,
        "error": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    with GEE_CATALOG_JOBS_LOCK:
        GEE_CATALOG_JOBS[job_id] = queued
    _persist_async_job(ASYNC_JOB_KIND_CATALOG, job_id, queued)
    thread = threading.Thread(
        target=_run_gee_catalog_job,
        args=(job_id, payload.model_dump(), limit),
        daemon=True,
    )
    thread.start()
    return {
        "job_id": job_id,
        "status": "queued",
        "progress_percent": 0,
        "current_step": "queued",
        "status_message": "Requete en attente",
        "message": "Requete en attente",
    }


@app.get("/api/gee/jobs/{job_id}/status")
def get_gee_catalog_job_status(job_id: str) -> dict[str, Any]:
    job = _get_gee_catalog_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job GEE introuvable")
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "progress_percent": job.get("progress_percent", 0),
        "current_step": job.get("current_step"),
        "status_message": job.get("status_message"),
        "message": job.get("message"),
        "error": job.get("error"),
        "result": job.get("result") if job.get("status") == "completed" else None,
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


@app.get("/api/images")
def list_images() -> dict[str, Any]:
    return {"items": IMAGES}


@app.post("/api/gee/preview")
def gee_preview(payload: PreviewRequest) -> dict[str, Any]:
    return {"item": preview_sentinel2(payload.model_dump())}


@app.post("/api/aoi/split")
async def split_aoi(request: Request) -> dict[str, Any]:
    """Split an imported AOI into N parts of equivalent area."""
    payload = await request.json()
    geometry = payload.get("geometry")
    if not isinstance(geometry, dict):
        aoi = payload.get("aoi")
        geometry = aoi.get("geojson") if isinstance(aoi, dict) else None
    if not isinstance(geometry, dict):
        raise HTTPException(status_code=422, detail="geometry ou aoi.geojson est requis (Polygon ou MultiPolygon).")

    cells_along_length = CELLS_ALONG_LENGTH
    if payload.get("cells_along_length") is not None:
        try:
            cells_along_length = int(payload["cells_along_length"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="cells_along_length doit etre un entier.") from None

    requested = payload.get("parts")
    automatic = requested is None or (isinstance(requested, str) and requested.strip().lower() == "auto")
    try:
        items = split_aoi_grid(geometry, requested, cells_along_length)
    except AoiSplitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "parts": len(items),
        "mode": "auto" if automatic else "manual",
        "cells_along_length": cells_along_length,
        "grid": {
            "rows": max((item["row"] for item in items), default=0),
            "columns": max((item["column"] for item in items), default=0),
        },
        "total_area_km2": round(sum(item["area_km2"] for item in items), 6),
        "items": items,
    }


@app.post("/api/analyses")
def create_analysis(payload: AnalysisCreate) -> dict[str, Any]:
    created_at = now_iso()
    item = Analysis(id=str(uuid.uuid4()), created_at=created_at, updated_at=created_at, **payload.model_dump())
    stored = _apply_spatial_reference_to_analysis(item.model_dump())
    stored["display_status"] = "En cours"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO analyses (id, created_at, updated_at, payload_json) VALUES (?, ?, ?, ?)",
            (item.id, item.created_at, item.updated_at, db.json_dumps(stored)),
        )
    return {"item": stored}


@app.get("/api/analyses")
def list_analyses() -> dict[str, Any]:
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT payload_json FROM analyses ORDER BY created_at DESC")
    return {"items": [_apply_spatial_reference_to_analysis(db.json_loads(r["payload_json"])) for r in rows]}


@app.get("/api/history")
def history() -> dict[str, Any]:
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT r.id, r.analysis_id, r.created_at, r.updated_at, r.status, r.message, r.result_json, a.payload_json
            FROM runs r
            JOIN analyses a ON a.id = r.analysis_id
            ORDER BY r.created_at DESC
            """,
        )
        export_rows = db.fetch_all(
            conn,
            "SELECT id, run_id, kind, filename, content_type, file_path, created_at FROM exports ORDER BY created_at DESC",
        )
    exports_by_run: dict[str, list[dict[str, Any]]] = {}
    for export in export_rows:
        item = dict(export)
        exports_by_run.setdefault(str(item.get("run_id")), []).append(item)
    return {"items": [_history_item_from_run(row, exports_by_run.get(row["id"], [])) for row in rows]}


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT payload_json FROM analyses WHERE id = ?", (analysis_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"item": _apply_spatial_reference_to_analysis(db.json_loads(row["payload_json"]))}


@app.put("/api/analyses/{analysis_id}")
def update_analysis(analysis_id: str, payload: AnalysisCreate) -> dict[str, Any]:
    updated_at = now_iso()
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT payload_json FROM analyses WHERE id = ?", (analysis_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Analysis not found")
        current = db.json_loads(row["payload_json"])
        merged = _apply_spatial_reference_to_analysis({**current, **payload.model_dump(), "id": analysis_id, "updated_at": updated_at})
        conn.execute(
            "UPDATE analyses SET updated_at = ?, payload_json = ? WHERE id = ?",
            (updated_at, db.json_dumps(merged), analysis_id),
        )
    return {"item": merged}


@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        run_rows = db.fetch_all(conn, "SELECT id, result_json FROM runs WHERE analysis_id = ?", (analysis_id,))
        run_ids = [str(row["id"]) for row in run_rows]
        if not run_ids:
            exists = db.fetch_one(conn, "SELECT id FROM analyses WHERE id = ?", (analysis_id,))
            if not exists:
                raise HTTPException(status_code=404, detail="Analysis not found")
        cache_keys_to_delete: set[str] = set()
        cache_rows = db.fetch_all(conn, "SELECT cache_key, params_json, result_json FROM processing_cache")
        for cache_row in cache_rows:
            with suppress(Exception):
                params = db.json_loads(cache_row["params_json"] or "{}")
                result = db.json_loads(cache_row["result_json"] or "{}")
                if params.get("id") == analysis_id or result.get("latest_run_id") in run_ids:
                    cache_keys_to_delete.add(cache_row["cache_key"])
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            export_rows = db.fetch_all(conn, f"SELECT file_path FROM exports WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM exports WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM classification_results WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids)
            for export_row in export_rows:
                _safe_unlink_export_file(str(export_row["file_path"] or ""))
        for cache_key in cache_keys_to_delete:
            conn.execute("DELETE FROM processing_cache WHERE cache_key = ?", (cache_key,))
        cur = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Analysis not found")
    return {"deleted": True, "id": analysis_id, "runs_deleted": len(run_ids), "cache_deleted": len(cache_keys_to_delete)}


def _is_deferred_statistics_flag(value: Any) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().lower()
    return text in {"deferred_for_first_map", "deferred"} or text.startswith("deferred")


def _result_has_deferred_statistics(result: dict[str, Any]) -> bool:
    stats = result.get("stats") if isinstance(result.get("stats"), dict) else {}
    quality = result.get("quality_summary") if isinstance(result.get("quality_summary"), dict) else {}
    performance = result.get("performance") if isinstance(result.get("performance"), dict) else {}
    return bool(
        performance.get("stats_deferred") is True
        or stats.get("statistics_deferred") is True
        or _is_deferred_statistics_flag(stats.get("statistics_status"))
        or _is_deferred_statistics_flag(quality.get("statistics_status"))
    )


def _attach_run_context(result: dict[str, Any], analysis: dict[str, Any], run_id: str) -> dict[str, Any]:
    result["analysis"] = analysis
    result["spatial_reference"] = analysis.get("spatial_reference")
    if isinstance(result.get("quality_summary"), dict):
        result["quality_summary"] = {**result["quality_summary"], "spatial_reference": analysis.get("spatial_reference")}
    if analysis_kind(analysis) == "OSI_SAR":
        result["quality"] = result.get("quality_summary") or result.get("mosaic")
    else:
        result["quality"] = result.get("mosaic") or preview_sentinel2(
            {
                "source": analysis.get("source", "S2_SR_HARMONIZED"),
                "date_start": analysis.get("date_start"),
                "date_end": analysis.get("date_end"),
                "max_cloud_pct": analysis.get("max_cloud_pct", 20),
                "image_method": analysis.get("image_method", "least_cloudy"),
                "aoi": analysis.get("aoi"),
            }
        )["quality"]
    result["latest_run_id"] = run_id
    return result


def _complete_deferred_run_statistics(
    run_id: str,
    analysis_id: str,
    analysis: dict[str, Any],
    cache_key: str,
    surface_ha: int,
) -> None:
    started = time.perf_counter()
    try:
        LOGGER.info("Deferred GEE statistics started for run %s", run_id)
        completed_at = now_iso()
        full_result = compute_sentinel2_index(
            analysis,
            surface_ha=surface_ha,
            first_map_priority=False,
        )
        full_result["cached"] = False
        _attach_run_context(full_result, analysis, run_id)
        with db.connect() as conn:
            _persist_classification_artifacts(conn, analysis, run_id, full_result, cache_key)
            serialized = db.json_dumps(full_result)
            conn.execute(
                "UPDATE runs SET updated_at = ?, result_json = ? WHERE id = ? AND analysis_id = ?",
                (completed_at, serialized, run_id, analysis_id),
            )
            conn.execute(
                "UPDATE processing_cache SET updated_at = ?, result_json = ? WHERE cache_key = ?",
                (completed_at, serialized, cache_key),
            )
            analysis["display_status"] = "Termine"
            analysis["updated_at"] = completed_at
            analysis["quality"] = full_result.get("quality")
            analysis["mosaic"] = full_result.get("mosaic")
            conn.execute(
                "UPDATE analyses SET updated_at = ?, payload_json = ? WHERE id = ?",
                (completed_at, db.json_dumps(analysis), analysis_id),
            )
        LOGGER.info(
            "Deferred GEE statistics completed in %.3fs for run %s",
            time.perf_counter() - started,
            run_id,
        )
    except Exception:
        LOGGER.exception("Deferred GEE statistics failed for run %s", run_id)


@app.post("/api/analyses/{analysis_id}/run")
def run_analysis(analysis_id: str, force: bool = Query(default=False)) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT payload_json FROM analyses WHERE id = ?", (analysis_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Analysis not found")
        analysis = _apply_spatial_reference_to_analysis(db.json_loads(row["payload_json"]))
        if analysis_kind(analysis) == "OSI_SAR":
            try:
                analysis = prepare_osi_sar_analysis(analysis)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        analysis["processing_version"] = processing_version_for_analysis(analysis)
        if analysis_kind(analysis) == "OSI_SAR":
            conn.execute(
                "UPDATE analyses SET updated_at = ?, payload_json = ? WHERE id = ?",
                (now_iso(), db.json_dumps(analysis), analysis_id),
            )

        run_id = str(uuid.uuid4())
        created_at = now_iso()
        surface_ha = area_from_bbox_ha(analysis.get("aoi") or {})
        cache_key = cache_key_for_analysis(analysis)
        cached = None if force else db.fetch_one(conn, "SELECT updated_at, result_json FROM processing_cache WHERE cache_key = ?", (cache_key,))
        if cached and not cache_timestamp_is_fresh(cached["updated_at"], ANALYSIS_CACHE_TTL_SECONDS):
            conn.execute("DELETE FROM processing_cache WHERE cache_key = ?", (cache_key,))
            cached = None
        if cached:
            result = db.json_loads(cached["result_json"])
            if _should_reuse_cached_result(result, gee_enabled=bool(gee_status().get("enabled"))):
                result["cached"] = True
            else:
                cached = None
        if not cached:
            if not gee_status().get("enabled"):
                raise HTTPException(status_code=503, detail=MOCK_ANALYSIS_UNAVAILABLE)
            try:
                # Small AOIs stay atomic. Very large spectral / change analyses
                # return map tiles first; deferred stats already overwrite the run.
                result = compute_sentinel2_index(
                    analysis,
                    surface_ha=surface_ha,
                    first_map_priority=should_prioritize_first_map(
                        analysis_kind(analysis),
                        surface_ha / 100.0,
                    ),
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except Exception as exc:
                message = str(exc)
                if "Quota" in message or "quota" in message:
                    detail = "Quota GEE atteint. Solution: relancer plus tard ou reduire la zone."
                elif "timed out" in message.lower() or "timeout" in message.lower():
                    detail = "Timeout GEE. Solution: reduire l'AOI, elargir la periode ou utiliser median composite."
                else:
                    detail = f"Erreur GEE pendant le calcul {analysis.get('index', 'NDVI')}: {message}"
                raise HTTPException(status_code=502, detail=detail) from exc
            if _is_mock_result(result):
                raise HTTPException(status_code=503, detail=MOCK_ANALYSIS_UNAVAILABLE)
            result["cached"] = False
            conn.execute(
                "INSERT OR REPLACE INTO processing_cache (cache_key, created_at, updated_at, params_json, result_json) VALUES (?, ?, ?, ?, ?)",
                (cache_key, created_at, created_at, db.json_dumps(analysis), db.json_dumps(result)),
            )
        _attach_run_context(result, analysis, run_id)
        should_complete_deferred_statistics = (
            not cached
            and str(result.get("mode") or "").lower() == "gee"
            and _result_has_deferred_statistics(result)
        )

        _persist_classification_artifacts(conn, analysis, run_id, result, cache_key)

        run = Run(
            id=run_id,
            analysis_id=analysis_id,
            status="succeeded",
            message="Analyse MVP terminee avec GEE." if result.get("mode") == "gee" else "Analyse MVP terminee en mode mock.",
            created_at=created_at,
            updated_at=created_at,
        )

        conn.execute(
            "INSERT INTO runs (id, analysis_id, created_at, updated_at, status, message, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run.id, analysis_id, run.created_at, run.updated_at, run.status, run.message, db.json_dumps(result)),
        )
        conn.execute(
            "UPDATE processing_cache SET updated_at = ?, result_json = ? WHERE cache_key = ?",
            (created_at, db.json_dumps(result), cache_key),
        )
        analysis["display_status"] = "Termine"
        analysis["updated_at"] = created_at
        analysis["quality"] = result.get("quality")
        analysis["mosaic"] = result.get("mosaic")
        conn.execute(
            "UPDATE analyses SET updated_at = ?, payload_json = ? WHERE id = ?",
            (created_at, db.json_dumps(analysis), analysis_id),
        )

    if should_complete_deferred_statistics:
        threading.Thread(
            target=_complete_deferred_run_statistics,
            args=(run_id, analysis_id, copy.deepcopy(analysis), cache_key, surface_ha),
            daemon=True,
        ).start()

    return {"item": run.model_dump()}


def _set_analysis_job(job_id: str, **updates: Any) -> None:
    with ANALYSIS_JOBS_LOCK:
        job = ANALYSIS_JOBS.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = now_iso()
        snapshot = dict(job)
    _persist_async_job(ASYNC_JOB_KIND_ANALYSIS, job_id, snapshot)


def _get_analysis_job(job_id: str) -> dict[str, Any] | None:
    with ANALYSIS_JOBS_LOCK:
        job = ANALYSIS_JOBS.get(job_id)
        if job:
            return dict(job)
    stored = _read_async_job(ASYNC_JOB_KIND_ANALYSIS, job_id)
    if not stored:
        return None
    with ANALYSIS_JOBS_LOCK:
        ANALYSIS_JOBS.setdefault(job_id, stored)
    return dict(stored)


def _run_analysis_job(job_id: str, analysis_id: str, force: bool) -> None:
    _set_analysis_job(job_id, status="processing", progress_percent=10, message="Preparation...")

    def _progress(percent: int, message: str) -> None:
        clamped = max(10, min(int(percent), 95))
        _set_analysis_job(job_id, status="processing", progress_percent=clamped, message=message)

    set_classification_progress_hook(_progress)
    try:
        run = run_analysis(analysis_id, force=force)["item"]
        _set_analysis_job(
            job_id,
            status="completed",
            progress_percent=100,
            message="Analyse terminee",
            run=run,
            run_id=run.get("id"),
        )
    except HTTPException as exc:
        _set_analysis_job(job_id, status="failed", progress_percent=100, message=str(exc.detail), error=str(exc.detail))
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        _set_analysis_job(job_id, status="failed", progress_percent=100, message=str(exc), error=str(exc))
    finally:
        set_classification_progress_hook(None)


@app.post("/api/jobs/analyses")
def create_analysis_job(
    analysis_id: str = Query(...),
    force: bool = Query(default=False),
) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT payload_json FROM analyses WHERE id = ?", (analysis_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis = db.json_loads(row["payload_json"])
    area_km2 = area_from_bbox_ha(analysis.get("aoi") or {}) / 100.0
    policy = surface_policy(area_km2, 30 if analysis.get("sensor") == "landsat-8-9" else 10)
    job_id = str(uuid.uuid4())
    created_at = now_iso()
    queued = {
        "job_id": job_id,
        "analysis_id": analysis_id,
        "status": "queued",
        "progress_percent": 0,
        "message": "Analyse ajoutee a la file",
        "error": None,
        "run": None,
        "run_id": None,
        "processing_policy": policy,
        "created_at": created_at,
        "updated_at": created_at,
    }
    with ANALYSIS_JOBS_LOCK:
        ANALYSIS_JOBS[job_id] = queued
    _persist_async_job(ASYNC_JOB_KIND_ANALYSIS, job_id, queued)
    threading.Thread(target=_run_analysis_job, args=(job_id, analysis_id, force), daemon=True).start()
    stored = _get_analysis_job(job_id)
    return dict(stored or queued)


@app.get("/api/jobs/analyses/{job_id}")
def get_analysis_job(job_id: str) -> dict[str, Any]:
    result = _get_analysis_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return result


@app.post("/api/analysis/change-detection")
async def run_change_detection_endpoint(request: Request) -> dict[str, Any]:
    payload = await request.json()
    analysis_type = str(payload.get("analysis_type") or "").lower()
    change_map = {
        "change_detection_ndvi": ("CHANGE_NDVI", "NDVI Change Detection"),
        "change_detection_ndwi": ("CHANGE_NDWI", "NDWI Change Detection"),
        "change_detection_ndbi": ("CHANGE_NDBI", "NDBI Change Detection"),
        "change_detection_bsi": ("CHANGE_BSI", "BSI Change Detection"),
        "change_detection_savi": ("CHANGE_SAVI", "SAVI Change Detection"),
    }
    if analysis_type not in change_map:
        raise HTTPException(status_code=422, detail="analysis_type doit etre change_detection_ndvi, change_detection_ndwi, change_detection_ndbi, change_detection_bsi ou change_detection_savi.")

    period_1 = payload.get("period_1") or {}
    period_2 = payload.get("period_2") or {}
    if not period_1.get("start_date") or not period_1.get("end_date") or not period_2.get("start_date") or not period_2.get("end_date"):
        raise HTTPException(status_code=422, detail="period_1 et period_2 doivent contenir start_date et end_date.")

    index_id, label = change_map[analysis_type]
    analysis_payload = dict(payload)
    analysis_payload["name"] = payload.get("name") or label
    analysis_payload["index"] = index_id
    analysis_payload["analysis_type"] = analysis_type
    analysis_payload["start_date"] = payload.get("start_date") or period_2.get("start_date")
    analysis_payload["end_date"] = payload.get("end_date") or period_2.get("end_date")
    analysis_payload["date_start"] = payload.get("date_start") or analysis_payload["start_date"]
    analysis_payload["date_end"] = payload.get("date_end") or analysis_payload["end_date"]
    analysis_payload["period_1"] = period_1
    analysis_payload["period_2"] = period_2

    created = create_analysis(AnalysisCreate(**analysis_payload))
    analysis_id = created["item"]["id"]
    run = run_analysis(analysis_id, force=bool(payload.get("force", False)))["item"]
    result_item = get_run_result(run["id"])["item"]
    tiles = result_item.get("tiles") or {}
    classes = result_item.get("classes") or []
    return {
        "success": True,
        "analysis_id": analysis_id,
        "run_id": run["id"],
        "analysis_type": analysis_type,
        "tile_url": tiles.get("index_tile_url"),
        "legend": classes,
        "classes": classes,
        "statistics": result_item.get("stats") or {},
        "quality_summary": result_item.get("quality_summary") or result_item.get("quality") or {},
        "interpretation": result_item.get("interpretation"),
        "from_cache": bool(result_item.get("cached")),
    }


@app.post("/api/result-cache/search")
def search_result_cache(payload: AnalysisCreate) -> dict[str, Any]:
    analysis = payload.model_dump()
    context_key = result_context_key_for_analysis(analysis)
    wanted_key = cache_key_for_analysis(analysis)
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT cache_key, created_at, updated_at, params_json, result_json FROM processing_cache ORDER BY updated_at DESC")
    items = []
    selected = None
    for row in rows:
        if not cache_timestamp_is_fresh(row["updated_at"], ANALYSIS_CACHE_TTL_SECONDS):
            continue
        params = db.json_loads(row["params_json"])
        if result_context_key_for_analysis(params) != context_key:
            continue
        if not is_cache_row_compatible(params):
            continue
        layer = cache_row_to_layer(row)
        items.append(layer)
        if row["cache_key"] == wanted_key:
            selected = layer
    return {"items": items, "item": selected, "context_key": context_key, "cache_key": wanted_key}


@app.delete("/api/result-cache/{cache_key}")
def delete_result_cache(cache_key: str) -> dict[str, Any]:
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM processing_cache WHERE cache_key = ?", (cache_key,))
        deleted = cur.rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Cached result not found")
    return {"deleted": True, "cache_key": cache_key}


@app.get("/api/runs")
def list_runs() -> dict[str, Any]:
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT id, analysis_id, created_at, updated_at, status, message FROM runs ORDER BY created_at DESC")
    return {"items": [dict(r) for r in rows]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(
            conn,
            "SELECT id, analysis_id, created_at, updated_at, status, message FROM runs WHERE id = ?",
            (run_id,),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    run = Run(**dict(row))
    return {"item": run.model_dump()}


@app.get("/api/runs/{run_id}/result")
def get_run_result(run_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(
            conn,
            "SELECT id, analysis_id, created_at, updated_at, status, message, result_json FROM runs WHERE id = ?",
            (run_id,),
        )
        export_rows = db.fetch_all(
            conn,
            "SELECT id, run_id, kind, filename, content_type, file_path, created_at FROM exports WHERE run_id = ? ORDER BY created_at DESC",
            (run_id,),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    run = Run(
        id=row["id"],
        analysis_id=row["analysis_id"],
        status=row["status"],
        message=row["message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    result = _synchronize_result_visual_metadata(db.json_loads(row["result_json"] or "{}"))
    analysis = _apply_spatial_reference_to_analysis(result.get("analysis") or {})
    result["analysis"] = analysis
    payload = RunResult(
        run=run,
        stats=result.get("stats"),
        histogram=result.get("histogram"),
        classes=result.get("classes"),
        tiles=result.get("tiles"),
    )
    cache_key = None
    with suppress(Exception):
        if analysis:
            cache_key = cache_key_for_analysis(analysis)
    return {
        "item": {
            **payload.model_dump(),
            "run_id": row["id"],
            "analysis_id": row["analysis_id"],
            "quality": result.get("quality"),
            "mosaic": result.get("mosaic"),
            "cached": result.get("cached"),
            "palette": result.get("palette"),
            "analysis_type": result.get("analysis_type"),
            "accuracy": result.get("accuracy"),
            "quality_summary": result.get("quality_summary"),
            "performance": result.get("performance"),
            "mode": result.get("mode"),
            "gee": result.get("gee"),
            "algorithm_comparison": result.get("algorithm_comparison"),
            "interpretation": result.get("interpretation"),
            "cluster_interpretation": result.get("cluster_interpretation"),
            "comparison_layers": result.get("comparison_layers") or [],
            "active_comparison_layer": result.get("active_comparison_layer"),
            "analysis": analysis,
            "spatial_reference": analysis.get("spatial_reference"),
            "exports": [dict(row) for row in export_rows],
            "cache_key": cache_key,
        }
    }


def _refresh_result_visuals(result: dict[str, Any]) -> dict[str, Any]:
    refreshed = dict(result or {})
    analysis = refreshed.get("analysis") or {}
    if refreshed.get("mode") != "gee" or str(analysis.get("index", "")).upper() != "NDVI":
        return refreshed

    try:
        index_image, geom, cfg, index_id, image, _sensor = _analysis_index_context(analysis)
        scale = int(cfg.get("scale", 10))
        surface_ha = int((refreshed.get("stats") or {}).get("surface_ha") or 0)
        if surface_ha:
            refreshed["classes"] = _compute_classes(index_image, geom, cfg, surface_ha, scale=scale)
        classified_image, classified_vis = _classified_index_image(index_image, cfg, index_id)
        tiles = dict(refreshed.get("tiles") or {})
        tiles["index_tile_url"] = _tile_url(classified_image, classified_vis)
        tiles["rgb_tile_url"] = tiles.get("rgb_tile_url") or _tile_url(
            image.clip(geom),
            _analysis_rgb_vis_for_sensor(_sensor_id(analysis)),
        )
        refreshed["tiles"] = tiles
        refreshed["palette"] = [item[3] for item in cfg.get("classes") or []]
    except Exception:
        return refreshed

    return refreshed


def _update_unsupervised_cluster_metadata(
    result: dict[str, Any],
    cluster_code: int,
    *,
    name: str | None = None,
    color: str | None = None,
) -> bool:
    if color is not None and not result.get("tile_source_palette"):
        current_classes = [item for item in (result.get("classes") or []) if isinstance(item, dict)]
        ordered_current_classes = sorted(current_classes, key=lambda item: int(item.get("code") or 0))
        current_palette = [str(item.get("color") or "") for item in ordered_current_classes]
        if current_palette and all(re.fullmatch(r"#[0-9a-fA-F]{6}", item) for item in current_palette):
            # The current tile still contains this palette. Keep it separate
            # from the user palette so the browser can recolor pixels locally.
            result["tile_source_palette"] = current_palette

    found = False
    for collection_name in ("classes", "cluster_interpretation"):
        for item in result.get(collection_name) or []:
            if int(item.get("code") or -1) != int(cluster_code):
                continue
            if name is not None:
                item["name"] = name
            if color is not None:
                item["color"] = color
            found = True

    if found and color is not None:
        classes = [item for item in (result.get("classes") or []) if isinstance(item, dict)]
        ordered_classes = sorted(classes, key=lambda item: int(item.get("code") or 0))
        result["palette"] = [str(item.get("color") or "") for item in ordered_classes]
    return found


@app.post("/api/runs/{run_id}/clusters/{cluster_code}/rename")
async def rename_unsupervised_cluster(run_id: str, cluster_code: int, request: Request) -> dict[str, Any]:
    payload = await request.json()
    has_name = "name" in payload
    has_color = "color" in payload
    name = str(payload.get("name") or "").strip() if has_name else None
    color = str(payload.get("color") or "").strip().lower() if has_color else None
    if not has_name and not has_color:
        raise HTTPException(status_code=422, detail="Cluster name or color is required")
    if has_name and not name:
        raise HTTPException(status_code=422, detail="Cluster name is required")
    if has_color and not re.fullmatch(r"#[0-9a-f]{6}", color or ""):
        raise HTTPException(status_code=422, detail="Cluster color must use the #RRGGBB format")

    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT result_json FROM runs WHERE id = ?", (run_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        result = normalize_unsupervised_result_order(db.json_loads(row["result_json"] or "{}"))
        if result.get("analysis_type") != "unsupervised_classification":
            raise HTTPException(status_code=422, detail="Cluster customization is only available for unsupervised classification results")

        if not _update_unsupervised_cluster_metadata(result, cluster_code, name=name, color=color):
            raise HTTPException(status_code=404, detail="Cluster not found")

        serialized = db.json_dumps(result)
        conn.execute("UPDATE runs SET result_json = ?, updated_at = ? WHERE id = ?", (serialized, now_iso(), run_id))
        cache_rows = db.fetch_all(conn, "SELECT cache_key, result_json FROM processing_cache")
        for cache_row in cache_rows:
            cached_result = db.json_loads(cache_row["result_json"] or "{}")
            if cached_result.get("latest_run_id") == run_id:
                cached_result["classes"] = result.get("classes")
                cached_result["cluster_interpretation"] = result.get("cluster_interpretation")
                cached_result["palette"] = result.get("palette")
                cached_result["tile_source_palette"] = result.get("tile_source_palette")
                conn.execute(
                    "UPDATE processing_cache SET result_json = ?, updated_at = ? WHERE cache_key = ?",
                    (db.json_dumps(cached_result), now_iso(), cache_row["cache_key"]),
                )
        with suppress(Exception):
            conn.execute(
                "UPDATE classification_results SET palette_json = ?, class_stats_json = ? WHERE run_id = ?",
                (db.json_dumps(result.get("palette") or []), db.json_dumps(result.get("classes") or []), run_id),
            )
    return {"item": result}


@app.get("/api/runs/{run_id}/tiles")
def get_run_tiles(
    run_id: str,
    refresh: bool = Query(False),
    include_rgb: bool = Query(True),
) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT result_json FROM runs WHERE id = ?", (run_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    result = _synchronize_result_visual_metadata(db.json_loads(row["result_json"] or "{}"))
    tiles = dict(result.get("tiles") or {})
    source = "stored"
    refresh_error = None

    if not refresh or result.get("mode") != "gee":
        return {"item": {"run_id": run_id, **tiles, "comparison_layers": result.get("comparison_layers") or [], "tile_source_palette": result.get("tile_source_palette"), "opacity": 0.85, "mode": result.get("mode"), "source": source, "refreshed": False, "refresh_error": None}}

    try:
        fresh_tiles = create_run_tile_urls(result, include_rgb=include_rgb)
        fresh_comparison_layers = fresh_tiles.pop("comparison_layers", None)
        if fresh_tiles.get("index_tile_url"):
            tiles["index_tile_url"] = fresh_tiles["index_tile_url"]
        if include_rgb and fresh_tiles.get("rgb_tile_url"):
            tiles["rgb_tile_url"] = fresh_tiles["rgb_tile_url"]
        _set_cached_run_tiles(run_id, tiles)
        result["tiles"] = tiles
        if result.get("analysis_type") == "unsupervised_classification":
            # A freshly generated GEE tile already embeds the current user
            # palette. Future color edits can therefore remain browser-local.
            result["tile_source_palette"] = list(result.get("palette") or [])
        if isinstance(fresh_comparison_layers, list) and fresh_comparison_layers:
            fresh_by_key = {item.get("key"): item for item in fresh_comparison_layers if isinstance(item, dict)}
            merged_layers = []
            for layer in result.get("comparison_layers") or []:
                if not isinstance(layer, dict):
                    continue
                fresh_layer = fresh_by_key.get(layer.get("key"))
                if fresh_layer:
                    layer = {
                        **layer,
                        "tiles": {
                            **(layer.get("tiles") or {}),
                            **(fresh_layer.get("tiles") or {}),
                        },
                    }
                merged_layers.append(layer)
            if merged_layers:
                result["comparison_layers"] = merged_layers
        with db.connect() as conn:
            conn.execute(
                "UPDATE runs SET result_json = ?, updated_at = ? WHERE id = ?",
                (db.json_dumps(result), now_iso(), run_id),
            )
            with suppress(Exception):
                analysis = result.get("analysis") or {}
                cache_key = cache_key_for_analysis(analysis) if analysis else None
                if cache_key:
                    cached_row = db.fetch_one(conn, "SELECT result_json FROM processing_cache WHERE cache_key = ?", (cache_key,))
                    if cached_row:
                        cached_result = db.json_loads(cached_row["result_json"] or "{}")
                        cached_result["tiles"] = tiles
                        if result.get("tile_source_palette"):
                            cached_result["tile_source_palette"] = result.get("tile_source_palette")
                        if result.get("comparison_layers"):
                            cached_result["comparison_layers"] = result.get("comparison_layers")
                        conn.execute(
                            "UPDATE processing_cache SET result_json = ?, updated_at = ? WHERE cache_key = ?",
                            (db.json_dumps(cached_result), now_iso(), cache_key),
                        )
        source = "gee_refresh"
    except Exception as exc:
        source = "stored_fallback"
        refresh_error = str(exc) or "Unable to refresh GEE map tiles."
        LOGGER.warning("GEE tile refresh failed for run %s: %s", run_id, refresh_error)
        _invalidate_stale_tile_cache(run_id, result)
    return {"item": {"run_id": run_id, **tiles, "comparison_layers": result.get("comparison_layers") or [], "tile_source_palette": result.get("tile_source_palette"), "opacity": 0.85, "mode": result.get("mode"), "source": source, "refreshed": source == "gee_refresh", "refresh_error": refresh_error}}


def _invalidate_stale_tile_cache(run_id: str, result: dict[str, Any]) -> None:
    """Stop reusing cached GEE results whose map tiles can no longer be refreshed."""
    result["tiles_stale"] = True
    analysis = result.get("analysis") if isinstance(result.get("analysis"), dict) else {}
    cache_key = cache_key_for_analysis(analysis) if analysis else None
    with db.connect() as conn:
        conn.execute(
            "UPDATE runs SET result_json = ?, updated_at = ? WHERE id = ?",
            (db.json_dumps(result), now_iso(), run_id),
        )
        if cache_key:
            cached_row = db.fetch_one(conn, "SELECT result_json FROM processing_cache WHERE cache_key = ?", (cache_key,))
            if cached_row:
                cached_result = db.json_loads(cached_row["result_json"] or "{}")
                if isinstance(cached_result, dict):
                    cached_result["tiles_stale"] = True
                    conn.execute(
                        "UPDATE processing_cache SET result_json = ?, updated_at = ? WHERE cache_key = ?",
                        (db.json_dumps(cached_result), now_iso(), cache_key),
                    )


@app.post("/api/runs/{run_id}/export")
def create_export(run_id: str, payload: ExportCreate) -> dict[str, Any]:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT result_json FROM runs WHERE id = ?", (run_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    result = db.json_loads(row["result_json"] or "{}")
    export_result = _result_visual_layer(result, payload.layer_key)
    language = _report_language(payload.language)

    export_id = str(uuid.uuid4())
    created_at = now_iso()

    try:
        filename = _export_download_filename(payload.kind, run_id, export_result, language)
        if payload.kind == "stats_json":
            content_type = "application/json; charset=utf-8"
            localized_result = _localize_result_export(export_result, language)
            bytes_ = db.json_dumps(localized_result).encode("utf-8")
        elif payload.kind == "stats_csv":
            content_type = "text/csv; charset=utf-8"
            bytes_ = _csv_export_bytes(export_result, language)
        elif payload.kind == "map_png":
            content_type = "application/vnd.google-earth-engine.url"
            bytes_ = _call_with_timeout(
                lambda: create_index_png_url(result, layer_key=payload.layer_key).encode("utf-8"),
                GEE_EXPORT_URL_TIMEOUT_SECONDS,
                "Timeout GEE pendant la generation de l'URL PNG.",
            )
        elif payload.kind == "geotiff":
            content_type = "application/vnd.google-earth-engine.url"
            is_unsupervised_export = (
                str(result.get("analysis_type") or "").lower() == "unsupervised_classification"
                or str((result.get("analysis") or {}).get("index") or "").upper()
                == "UNSUPERVISED_CLASSIFICATION"
            )
            bytes_ = _call_with_timeout(
                lambda: create_index_geotiff_url(result, layer_key=payload.layer_key).encode("utf-8"),
                (
                    GEE_UNSUPERVISED_EXPORT_URL_TIMEOUT_SECONDS
                    if is_unsupervised_export
                    else GEE_EXPORT_URL_TIMEOUT_SECONDS
                ),
                "Timeout GEE pendant la generation de l'URL GeoTIFF.",
            )
        else:
            content_type = "application/pdf"
            report_payload = _load_map_pdf_request_from_run(run_id, layer_key=payload.layer_key, language=language)
            filename, bytes_ = _map_pdf_bytes(report_payload)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Export {payload.kind} impossible: {exc}") from exc

    file_path = _export_file_path(payload.kind, _export_storage_filename(filename, content_type))
    file_path.write_bytes(bytes_)

    with db.connect() as conn:
        conn.execute(
            "INSERT INTO exports (id, run_id, created_at, kind, filename, content_type, file_path, bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (export_id, run_id, created_at, payload.kind, filename, content_type, str(file_path), bytes_),
        )

    ref = ExportRef(id=export_id, run_id=run_id, kind=payload.kind, filename=filename, content_type=content_type, created_at=created_at)
    return {"item": ref.model_dump()}


@app.post("/api/export/map-pdf")
def create_map_pdf_export(payload: MapPdfExportRequest) -> dict[str, Any]:
    filename, pdf_bytes = _map_pdf_bytes(payload)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / filename
    report_path.write_bytes(pdf_bytes)
    return {
        "success": True,
        "pdf_url": f"/exports/reports/{filename}",
        "filename": filename,
        "message": "تم إنشاء تقرير PDF بنجاح" if _pdf_payload_language(payload) == "ar" else "PDF report generated successfully",
    }


@app.get("/api/runs/{run_id}/export/map-pdf")
def download_map_pdf_for_run(
    run_id: str,
    layer_key: str | None = Query(default=None),
    language: str = Query(default="en", pattern="^(en|ar)$"),
) -> Response:
    payload = _load_map_pdf_request_from_run(run_id, layer_key=layer_key, language=language)
    filename, pdf_bytes = _map_pdf_bytes(payload)
    report_path = REPORTS_DIR / filename
    report_path.write_bytes(pdf_bytes)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@app.post("/api/export/map-layout-png")
def create_map_layout_png_export(payload: MapPdfExportRequest) -> dict[str, Any]:
    filename, image_bytes = _map_layout_png_bytes(payload)
    MAP_LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
    image_path = MAP_LAYOUTS_DIR / filename
    image_path.write_bytes(image_bytes)
    return {
        "success": True,
        "image_url": f"/exports/map-layouts/{filename}",
        "filename": filename,
        "message": "تم إنشاء الإخراج الخرائطي بصيغة PNG بنجاح" if _pdf_payload_language(payload) == "ar" else "Cartographic PNG layout generated successfully",
    }


@app.get("/api/exports")
def list_exports() -> dict[str, Any]:
    with db.connect() as conn:
        rows = db.fetch_all(conn, "SELECT id, run_id, kind, filename, content_type, file_path, created_at FROM exports ORDER BY created_at DESC")
    return {"items": [dict(r) for r in rows]}


@app.get("/api/exports/{export_id}/download")
def download_export(export_id: str) -> Response:
    with db.connect() as conn:
        row = db.fetch_one(conn, "SELECT filename, content_type, bytes, file_path FROM exports WHERE id = ?", (export_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Export not found")
    filename = str(row["filename"])
    content_type = str(row["content_type"])
    if content_type == "application/vnd.google-earth-engine.url":
        source_url = row["bytes"].decode("utf-8")
        try:
            upstream = urllib.request.urlopen(source_url, timeout=GEE_EXPORT_DOWNLOAD_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail="Timeout GEE pendant le telechargement de l'export.",
            ) from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc).lower():
                raise HTTPException(
                    status_code=504,
                    detail="Timeout GEE pendant le telechargement de l'export.",
                ) from exc
            # Preserve the previous download behavior if the upstream stream
            # cannot be opened by the API server.
            return RedirectResponse(url=source_url, status_code=307)
        except Exception:
            return RedirectResponse(url=source_url, status_code=307)

        def stream_upstream() -> Any:
            try:
                while True:
                    chunk = upstream.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                upstream.close()

        media_type = "image/tiff" if filename.lower().endswith((".tif", ".tiff")) else "image/png"
        return StreamingResponse(
            stream_upstream(),
            media_type=media_type,
            headers={"Content-Disposition": _content_disposition(filename)},
        )
    stored_file_path = _safe_export_file_path(str(row["file_path"] or ""))
    if stored_file_path is not None and stored_file_path.is_file():
        return Response(
            content=stored_file_path.read_bytes(),
            media_type=content_type,
            headers={"Content-Disposition": _content_disposition(filename)},
        )
    return Response(
        content=row["bytes"],
        media_type=content_type,
        headers={"Content-Disposition": _content_disposition(filename)},
    )
