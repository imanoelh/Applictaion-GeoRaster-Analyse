from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[1] / "data" / "ground_truth" / "buildings" / "maxar_2025"
ALLOWED_STATUSES = {"NOT_ANNOTATED", "IN_PROGRESS", "ANNOTATED", "VALIDATED"}
EXPECTED_CRS = "EPSG:32637"


def _raster_info(path: Path) -> dict[str, Any]:
    executable = shutil.which("gdalinfo")
    if executable is None:
        candidate = Path(sys.executable).parent / "Library" / "bin" / "gdalinfo.exe"
        if candidate.is_file():
            executable = str(candidate)
    if executable is None:
        raise RuntimeError("gdalinfo non disponible (activez un environnement GDAL)")
    env = os.environ.copy()
    library_bin = str(Path(executable).resolve().parent)
    env["PATH"] = library_bin + os.pathsep + env.get("PATH", "")
    result = subprocess.run([executable, "-json", str(path)], capture_output=True, text=True, env=env, check=True)
    return json.loads(result.stdout)


def _crs_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        props = value.get("properties", {})
        name = props.get("name") if isinstance(props, dict) else None
        if isinstance(name, str):
            match = re.search(r"(?:EPSG[:/]+|EPSG::)(\d+)$", name, flags=re.IGNORECASE)
            return f"EPSG:{match.group(1)}" if match else name
        return None
    return None


def validate_dataset(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    metadata_dir = root / "metadata"
    annotations_dir = root / "annotations"
    images_dir = root / "images"

    for metadata_path in sorted(metadata_dir.glob("*.json")):
        zone_id = metadata_path.stem
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{metadata_path.name}: metadata illlisible ({exc})")
            continue

        status = metadata.get("annotation_status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{zone_id}: annotation_status invalide ({status!r})")
        raster_path = images_dir / f"{zone_id}.tif"
        geojson_path = annotations_dir / f"{zone_id}.geojson"
        if not raster_path.is_file():
            errors.append(f"{zone_id}: raster manquant")
            continue
        if not geojson_path.is_file():
            errors.append(f"{zone_id}: GeoJSON manquant")
            continue

        try:
            raster = _raster_info(raster_path)
            raster_width, raster_height = raster["size"]
            transform = raster["geoTransform"]
            raster_resolution = (abs(transform[1]), abs(transform[5]))
            raster_bounds = (
                transform[0],
                transform[3] + raster_height * transform[5],
                transform[0] + raster_width * transform[1],
                transform[3],
            )
            epsg = (raster.get("stac") or {}).get("proj:epsg")
            raster_crs = f"EPSG:{epsg}" if epsg is not None else None
        except Exception as exc:  # pragma: no cover - reports rasterio driver errors
            errors.append(f"{zone_id}: GeoTIFF illlisible ({exc})")
            continue

        if raster_crs != EXPECTED_CRS or metadata.get("crs") != EXPECTED_CRS:
            errors.append(f"{zone_id}: CRS attendu {EXPECTED_CRS}, raster={raster_crs}, metadata={metadata.get('crs')}")
        if (raster_width, raster_height) != (metadata.get("pixel_width"), metadata.get("pixel_height")):
            errors.append(f"{zone_id}: dimensions raster/metadata différentes")
        if any(abs(a - b) > 1e-8 for a, b in zip(raster_resolution, metadata.get("resolution", []))):
            errors.append(f"{zone_id}: résolution raster/metadata différente")
        actual_bounds = list(raster_bounds)
        recorded_bounds = metadata.get("bounds", {})
        expected_bounds = [recorded_bounds.get(k) for k in ("left", "bottom", "right", "top")]
        if any(v is None for v in expected_bounds) or any(abs(a - b) > 1e-5 for a, b in zip(actual_bounds, expected_bounds)):
            errors.append(f"{zone_id}: bounds raster/metadata différents")

        try:
            document = json.loads(geojson_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{zone_id}: GeoJSON invalide ({exc})")
            continue
        if document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
            errors.append(f"{zone_id}: document non FeatureCollection")
            continue
        geojson_crs = _crs_name(document.get("crs"))
        if geojson_crs != EXPECTED_CRS:
            errors.append(f"{zone_id}: CRS GeoJSON absent ou différent ({geojson_crs})")

        features = document["features"]
        if not features and status == "NOT_ANNOTATED":
            warnings.append(f"{zone_id}: NOT_ANNOTATED; FeatureCollection vide, non assimilée à ANNOTATED_EMPTY")
        elif not features and status in {"ANNOTATED", "VALIDATED"}:
            if status == "ANNOTATED" and metadata.get("empty_annotation_confirmed") is True:
                pass
            else:
                errors.append(f"{zone_id}: collection vide incompatible avec le statut {status}")

        geometry_area = 0.0
        for index, feature in enumerate(features):
            properties = feature.get("properties") or {}
            building_id = properties.get("building_id")
            feature_zone = properties.get("zone_id")
            if not isinstance(building_id, str) or not building_id.strip():
                errors.append(f"{zone_id} feature {index}: building_id absent")
            elif building_id in seen_ids:
                errors.append(f"{zone_id} feature {index}: building_id dupliqué ({building_id})")
            else:
                seen_ids.add(building_id)
            if feature_zone != zone_id:
                errors.append(f"{zone_id} feature {index}: zone_id différent ({feature_zone!r})")
            if properties.get("annotation_status") != "manual":
                errors.append(f"{zone_id} feature {index}: annotation_status doit être 'manual'")
            if properties.get("source") != "Maxar 2025-07-28":
                errors.append(f"{zone_id} feature {index}: source inattendue")
            geometry_json = feature.get("geometry")
            if not geometry_json:
                errors.append(f"{zone_id} feature {index}: géométrie absente/vide")
                continue
            try:
                geom = shape(geometry_json)
            except Exception as exc:
                errors.append(f"{zone_id} feature {index}: géométrie illlisible ({exc})")
                continue
            if geom.is_empty:
                errors.append(f"{zone_id} feature {index}: géométrie vide")
            if geom.geom_type not in {"Polygon", "MultiPolygon"}:
                errors.append(f"{zone_id} feature {index}: type interdit ({geom.geom_type})")
            if not geom.is_valid:
                errors.append(f"{zone_id} feature {index}: géométrie invalide/auto-intersection")
            if geom.area <= 0:
                errors.append(f"{zone_id} feature {index}: surface non positive")
            if not geom.is_empty and not (
                geom.bounds[0] >= raster_bounds[0] - 1e-7
                and geom.bounds[1] >= raster_bounds[1] - 1e-7
                and geom.bounds[2] <= raster_bounds[2] + 1e-7
                and geom.bounds[3] <= raster_bounds[3] + 1e-7
            ):
                errors.append(f"{zone_id} feature {index}: géométrie hors des bounds du patch")
            geometry_area += geom.area

        if status == "NOT_ANNOTATED":
            if metadata.get("building_count") is not None or metadata.get("annotated_area_m2") is not None:
                errors.append(f"{zone_id}: annotation statistics must remain null while NOT_ANNOTATED")
        else:
            if metadata.get("building_count") != len(features):
                errors.append(f"{zone_id}: building_count does not match the feature count")
            recorded_area = metadata.get("annotated_area_m2")
            if recorded_area is None or abs(float(recorded_area) - geometry_area) > max(1e-6, geometry_area * 1e-8):
                errors.append(f"{zone_id}: annotated_area_m2 does not match geometries")

    if not list(metadata_dir.glob("*.json")):
        errors.append("aucun metadata de zone trouvé")
    return errors, warnings


if __name__ == "__main__":
    issues, notices = validate_dataset()
    for notice in notices:
        print(f"WARNING: {notice}")
    for issue in issues:
        print(f"ERROR: {issue}")
    if issues:
        raise SystemExit(1)
    print(f"VALID: package structure valid; {len(notices)} zone(s) remain NOT_ANNOTATED")
