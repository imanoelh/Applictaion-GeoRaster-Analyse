"""Prepare an isolated SpaceNet building dataset for future MODEL_C9 training.

This module intentionally has no imports from GeoRaster API, registry, or model
code.  It reads source imagery and footprints file-by-file and writes aligned
512px GeoTIFF tiles, masks, manifests, and rejection diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, bounds as window_bounds
from rasterio.warp import transform_geom
from shapely.geometry import box, shape
from shapely.ops import unary_union

LOGGER = logging.getLogger("georaster.spacenet_dataset")
DEFAULT_TILE_SIZE = 512
DEFAULT_SEED = 42
DEFAULT_RGB_LOW_PERCENTILE = 2.0
DEFAULT_RGB_HIGH_PERCENTILE = 98.0


@dataclass(frozen=True)
class Pair:
    imagery: Path
    labels: Path
    source_id: str


_SPACENET_SAMPLE_RE = re.compile(r"(AOI[_-][A-Za-z0-9]+[_-][A-Za-z0-9]+[_-]img[0-9]+)", re.IGNORECASE)


def extract_spacenet_sample_id(path_or_filename: str | Path) -> str:
    """Return the collision-safe SpaceNet sample id from an image or label name.

    Examples: ``RGB-PanSharpen_AOI_5_Khartoum_img1.tif`` and
    ``buildings_AOI_5_Khartoum_img1.geojson`` both become
    ``AOI_5_Khartoum_img1``.  The complete AOI/city/img token is retained so
    ``img1``, ``img10`` and the same image number in another AOI never collide.
    """
    name = Path(path_or_filename).name
    match = _SPACENET_SAMPLE_RE.search(Path(name).stem)
    if match:
        return re.sub(r"-", "_", match.group(1))
    stem = Path(name).stem
    stem = re.sub(r"^(?:RGB[-_]PanSharpen|RGB|MUL|PAN|buildings?|footprints?|labels?)[-_]", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[-_]?(?:RGB|MUL|PAN|buildings?|footprints?|labels?)$", "", stem, flags=re.IGNORECASE)
    return re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower()


def discover_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def uint16_to_uint8_percentile(
    rgb: np.ndarray, *, low_percentile: float = DEFAULT_RGB_LOW_PERCENTILE,
    high_percentile: float = DEFAULT_RGB_HIGH_PERCENTILE,
) -> np.ndarray:
    """Convert band-first RGB data to uint8 using deterministic per-band clipping."""
    if rgb.ndim != 3 or rgb.shape[0] < 3:
        raise ValueError("RGB array must have shape (bands, height, width) with at least 3 bands")
    if not 0 <= low_percentile < high_percentile <= 100:
        raise ValueError("percentiles must satisfy 0 <= low < high <= 100")
    source = np.asarray(rgb[:3])
    output = np.empty(source.shape, dtype=np.uint8)
    for band_index in range(3):
        band = source[band_index].astype(np.float32, copy=False)
        low, high = np.percentile(band, [low_percentile, high_percentile])
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            output[band_index] = np.clip(band, 0, 255).astype(np.uint8)
            continue
        scaled = (np.clip(band, low, high) - low) * (255.0 / (high - low))
        output[band_index] = np.rint(scaled).astype(np.uint8)
    return output


def discover_pairs(imagery_dir: Path, labels_dir: Path, *, limit: int | None = None) -> tuple[list[Pair], list[dict[str, str]]]:
    images = discover_files(imagery_dir, (".tif", ".tiff", ".jp2", ".png", ".jpg", ".jpeg"))
    labels = discover_files(labels_dir, (".geojson", ".json", ".shp", ".gpkg"))
    label_by_key: dict[str, list[Path]] = {}
    for label in labels:
        label_by_key.setdefault(extract_spacenet_sample_id(label), []).append(label)
    image_by_key: dict[str, list[Path]] = {}
    for image in images:
        image_by_key.setdefault(extract_spacenet_sample_id(image), []).append(image)
    pairs: list[Pair] = []
    rejected: list[dict[str, str]] = []
    for image in images:
        key = extract_spacenet_sample_id(image)
        if len(image_by_key[key]) > 1:
            rejected.append({"source_image": str(image), "canonical_sample_id": key, "reason": "DUPLICATE_IMAGE_CANONICAL_ID"})
            continue
        candidates = label_by_key.get(key, [])
        if not candidates:
            rejected.append({"source_image": str(image), "canonical_sample_id": key, "reason": "NO_MATCHING_LABEL"})
            continue
        if len(candidates) > 1:
            rejected.append({"source_image": str(image), "canonical_sample_id": key, "reason": "DUPLICATE_LABEL_CANONICAL_ID", "labels": ";".join(str(p) for p in candidates)})
            continue
        pairs.append(Pair(image, candidates[0], key))
        if limit and len(pairs) >= limit:
            break
    return pairs, rejected


def _read_features(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if path.suffix.lower() in {".geojson", ".json"}:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("type") == "FeatureCollection":
            return list(payload.get("features", [])), payload.get("crs", {}).get("properties", {}).get("name") if isinstance(payload.get("crs"), dict) else None
        if payload.get("type") == "Feature":
            return [payload], None
        raise ValueError("JSON label must be a FeatureCollection or Feature")
    try:
        import fiona  # optional dependency for shapefile/GPKG sources
    except ImportError as exc:
        raise RuntimeError(f"Fiona is required for vector source {path.name}") from exc
    with fiona.open(path) as source:
        crs = source.crs_wkt or (source.crs.to_string() if source.crs else None)
        return [{"type": "Feature", "geometry": item["geometry"], "properties": dict(item.get("properties") or {})} for item in source], crs


def _source_crs(value: str | None, raster: rasterio.DatasetReader) -> Any:
    if value:
        return value
    return raster.crs


def load_geometries(label_path: Path, raster: rasterio.DatasetReader) -> list[Any]:
    features, label_crs = _read_features(label_path)
    source_crs = _source_crs(label_crs, raster)
    target_crs = raster.crs
    raster_bounds = box(*raster.bounds)
    output: list[Any] = []
    for index, feature in enumerate(features, start=1):
        geometry = feature.get("geometry")
        if not geometry:
            LOGGER.warning("Skipping null geometry %s feature %s", label_path.name, index)
            continue
        geom = shape(geometry)
        if geom.is_empty:
            continue
        if not geom.is_valid:
            repaired = geom.buffer(0)
            if repaired.is_empty or not repaired.is_valid:
                raise ValueError(f"INVALID_GEOMETRY:{label_path.name}:{index}")
            geom = repaired
        # SpaceNet GeoJSON uses the OGC CRS84 spelling (lon/lat), while some
        # GDAL builds expose the same geographic raster CRS as a verbose WKT.
        # Treat these as equivalent rather than asking an incompatible PROJ
        # database to transform an already-aligned footprint.
        crs84_equivalent = bool(
            label_crs and "CRS84" in str(label_crs).upper() and target_crs and target_crs.is_geographic
        )
        if source_crs and target_crs and str(source_crs) != str(target_crs) and not crs84_equivalent:
            geom = shape(transform_geom(source_crs, target_crs, geom.__geo_interface__))
        geom = geom.intersection(raster_bounds)
        if not geom.is_empty and geom.is_valid:
            output.append(geom)
    return output


def assign_splits(pairs: list[Pair], *, seed: int, train_ratio: float, val_ratio: float, test_ratio: float) -> dict[str, str]:
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError("train/val/test ratios must sum to 1")
    ids = sorted({pair.source_id for pair in pairs})
    random.Random(seed).shuffle(ids)
    n = len(ids)
    train_end = int(round(n * train_ratio))
    val_end = train_end + int(round(n * val_ratio))
    if n >= 3:
        train_end = max(1, min(train_end, n - 2))
        val_end = max(train_end + 1, min(val_end, n - 1))
    return {source_id: ("train" if i < train_end else "val" if i < val_end else "test") for i, source_id in enumerate(ids)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tile_positions(width: int, height: int, tile_size: int, stride: int) -> Iterable[tuple[int, int]]:
    rows = list(range(0, max(1, height - tile_size + 1), stride))
    cols = list(range(0, max(1, width - tile_size + 1), stride))
    if rows[-1] + tile_size < height:
        rows.append(max(0, height - tile_size))
    if cols[-1] + tile_size < width:
        cols.append(max(0, width - tile_size))
    for row in rows:
        for col in cols:
            yield row, col


def prepare_dataset(
    *, imagery: Path, labels: Path, output: Path, tile_size: int = DEFAULT_TILE_SIZE,
    stride: int | None = None, seed: int = DEFAULT_SEED, train_ratio: float = .70,
    val_ratio: float = .15, test_ratio: float = .15, keep_empty_tiles: bool = True,
    max_empty_tile_ratio: float = .35, nodata_threshold: float = .50,
    dry_run: bool = False, limit: int | None = None,
    rgb_low_percentile: float = DEFAULT_RGB_LOW_PERCENTILE,
    rgb_high_percentile: float = DEFAULT_RGB_HIGH_PERCENTILE,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    if tile_size <= 0 or (stride is not None and stride <= 0):
        raise ValueError("tile-size and stride must be positive")
    stride = stride or tile_size
    all_pairs, discovery_rejections = discover_pairs(imagery, labels)
    # ``limit`` limits work/examples, not the pairing audit itself.  This keeps
    # the dry-run honest for large datasets while still allowing a quick sample.
    pairs = all_pairs[:limit] if limit is not None else all_pairs
    split_by_source = assign_splits(pairs, seed=seed, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio) if pairs else {}
    summary: dict[str, Any] = {"images_detected": len(discover_files(imagery, (".tif", ".tiff", ".jp2", ".png", ".jpg", ".jpeg"))), "labels_detected": len(discover_files(labels, (".geojson", ".json", ".shp", ".gpkg"))), "pairs": len(all_pairs), "pairs_sampled": len(pairs), "dry_run": dry_run, "seed": seed}
    if dry_run:
        examples: list[dict[str, Any]] = []
        for pair in pairs[:10]:
            item: dict[str, Any] = {"imagery": str(pair.imagery), "labels": str(pair.labels), "canonical_sample_id": pair.source_id, "source_id": pair.source_id, "split": split_by_source.get(pair.source_id)}
            try:
                with rasterio.open(pair.imagery) as raster:
                    geometries = load_geometries(pair.labels, raster)
                    item.update({"width": raster.width, "height": raster.height, "bands": raster.count, "dtype": raster.dtypes[0], "crs": raster.crs.to_string() if raster.crs else None, "transform": list(raster.transform), "footprints_after_clip": len(geometries)})
            except Exception as exc:
                item["error"] = f"{type(exc).__name__}:{exc}"
            examples.append(item)
        summary["pair_examples"] = examples
        summary["unmatched"] = discovery_rejections
        return summary

    for split in ("train", "val", "test"):
        (output / split / "images").mkdir(parents=True, exist_ok=True)
        (output / split / "masks").mkdir(parents=True, exist_ok=True)
    (output / "metadata" / "previews").mkdir(parents=True, exist_ok=True)
    rejected: list[dict[str, Any]] = list(discovery_rejections)
    records: list[dict[str, Any]] = []
    source_metadata: list[dict[str, Any]] = []
    candidates_empty: list[dict[str, Any]] = []
    positive_count = 0
    for pair in pairs:
        split = split_by_source[pair.source_id]
        try:
            with rasterio.open(pair.imagery) as raster:
                if raster.count < 3 or raster.crs is None:
                    raise ValueError("RASTER_MISSING_RGB_OR_CRS")
                geoms = load_geometries(pair.labels, raster)
                output_crs = "+proj=longlat +datum=WGS84 +no_defs" if raster.crs and raster.crs.is_geographic else raster.crs
                source_metadata.append({"source_id": pair.source_id, "imagery": str(pair.imagery), "labels": str(pair.labels), "width": raster.width, "height": raster.height, "crs": raster.crs.to_string(), "transform": list(raster.transform), "split": split, "geometry_count": len(geoms)})
                for row, col in _tile_positions(raster.width, raster.height, tile_size, stride):
                    window = Window(col, row, tile_size, tile_size)
                    tile_id = f"{pair.source_id}__r{row:06d}_c{col:06d}"
                    try:
                        rgb_uint16 = raster.read((1, 2, 3), window=window, boundless=True, fill_value=0)
                        rgb = uint16_to_uint8_percentile(rgb_uint16, low_percentile=rgb_low_percentile, high_percentile=rgb_high_percentile)
                        masks = raster.read_masks(1, window=window, boundless=True)
                        valid = masks > 0
                        tile_box = box(*window_bounds(window, raster.transform))
                        clipped = [geom for geom in geoms if geom.intersects(tile_box)]
                        mask = rasterize(((geom, 255) for geom in clipped), out_shape=(tile_size, tile_size), transform=raster.window_transform(window), fill=0, dtype="uint8")
                        mask[~valid] = 0
                        nodata_ratio = 1.0 - (float(valid.sum()) / float(tile_size * tile_size))
                        building_pixels = int(np.count_nonzero(mask == 255))
                        empty = building_pixels == 0
                        item = {"tile_id": tile_id, "row": row, "col": col, "split": split, "source_raster": str(pair.imagery), "source_label": str(pair.labels), "width": tile_size, "height": tile_size, "building_pixel_count": building_pixels, "building_pixel_ratio": building_pixels / float(tile_size * tile_size), "nodata_pixel_ratio": nodata_ratio, "empty_tile": empty, "crs": str(output_crs), "source_bounds": list(window_bounds(window, raster.transform))}
                        if nodata_ratio > nodata_threshold:
                            rejected.append({**item, "reason": "TOO_MUCH_NODATA"})
                            continue
                        if empty and (not keep_empty_tiles):
                            rejected.append({**item, "reason": "EMPTY_TILE_DISABLED"})
                            continue
                        if empty:
                            candidates_empty.append({"item": item, "rgb": rgb, "mask": mask, "transform": raster.window_transform(window)})
                        else:
                            positive_count += 1
                            records.append(item)
                            image_path = output / split / "images" / f"{tile_id}.tif"
                            mask_path = output / split / "masks" / f"{tile_id}_mask.tif"
                            profile = raster.profile.copy(); profile.pop("blockxsize", None); profile.pop("blockysize", None); profile.update(driver="GTiff", width=tile_size, height=tile_size, count=3, dtype=str(rgb.dtype), crs=output_crs, transform=raster.window_transform(window), compress="deflate")
                            with rasterio.open(image_path, "w", **profile) as dst: dst.write(rgb)
                            mask_profile = profile.copy(); mask_profile.update(count=1, dtype="uint8", nodata=0)
                            with rasterio.open(mask_path, "w", **mask_profile) as dst: dst.write(mask, 1)
                            item.update({"image_path": str(image_path.relative_to(output)), "mask_path": str(mask_path.relative_to(output)), "rgb_sha256": _sha256(image_path), "mask_sha256": _sha256(mask_path)})
                    except Exception as exc:
                        rejected.append({"tile_id": tile_id, "source_image": str(pair.imagery), "source_label": str(pair.labels), "reason": f"TILE_ERROR:{type(exc).__name__}:{exc}"})
        except Exception as exc:
            rejected.append({"source_image": str(pair.imagery), "source_label": str(pair.labels), "reason": f"SOURCE_ERROR:{type(exc).__name__}:{exc}"})
    random.Random(seed).shuffle(candidates_empty)
    max_empty = int((max_empty_tile_ratio / max(1e-9, 1.0 - max_empty_tile_ratio)) * positive_count) if positive_count else len(candidates_empty)
    for entry in candidates_empty[:max_empty]:
        item, rgb, mask, transform = entry["item"], entry["rgb"], entry["mask"], entry["transform"]
        image_path = output / item["split"] / "images" / f"{item['tile_id']}.tif"; mask_path = output / item["split"] / "masks" / f"{item['tile_id']}_mask.tif"
        profile = {"driver": "GTiff", "width": tile_size, "height": tile_size, "count": 3, "dtype": str(rgb.dtype), "crs": item["crs"], "transform": transform, "compress": "deflate"}
        with rasterio.open(image_path, "w", **profile) as dst: dst.write(rgb)
        profile.update(count=1, dtype="uint8", nodata=0)
        with rasterio.open(mask_path, "w", **profile) as dst: dst.write(mask, 1)
        item.update({"image_path": str(image_path.relative_to(output)), "mask_path": str(mask_path.relative_to(output)), "rgb_sha256": _sha256(image_path), "mask_sha256": _sha256(mask_path)})
        records.append(item)
    for entry in candidates_empty[max_empty:]:
        rejected.append({**entry["item"], "reason": "EMPTY_TILE_RATIO_LIMIT"})
    records.sort(key=lambda item: item["tile_id"])
    building_pixels = sum(i["building_pixel_count"] for i in records)
    total_pixels = max(1, len(records) * tile_size * tile_size)
    statistics = {"total_tiles": len(records), "train_count": sum(i["split"] == "train" for i in records), "validation_count": sum(i["split"] == "val" for i in records), "test_count": sum(i["split"] == "test" for i in records), "positive_tiles": sum(not i["empty_tile"] for i in records), "negative_tiles": sum(i["empty_tile"] for i in records), "rejected_tiles": len(rejected), "total_building_pixels": building_pixels, "building_pixel_ratio": building_pixels / total_pixels, "background_pixel_ratio": 1.0 - (building_pixels / total_pixels), "source_rasters": len(source_metadata), "footprints_total": sum(i["geometry_count"] for i in source_metadata), "seed": seed, "tile_size": tile_size, "stride": stride, "rgb_profile": "spacenet_rgb_percentile_uint8_v1", "rgb_low_percentile": rgb_low_percentile, "rgb_high_percentile": rgb_high_percentile, "input_dtype": "uint16", "output_rgb_dtype": "uint8", "mask_dtype": "uint8", "mask_values": [0, 255], "processing_seconds": time.perf_counter() - started_at}
    metadata = output / "metadata"
    (metadata / "dataset_manifest.json").write_text(json.dumps({"schema_version": "georaster_building_v1", "mask_convention": {"background": 0, "building": 255}, "records": records}, indent=2), encoding="utf-8")
    (metadata / "dataset_statistics.json").write_text(json.dumps(statistics, indent=2), encoding="utf-8")
    (metadata / "rejected_tiles.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    (metadata / "source_metadata.json").write_text(json.dumps(source_metadata, indent=2), encoding="utf-8")
    disk_usage_bytes = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    statistics["disk_usage_bytes"] = disk_usage_bytes
    statistics["disk_usage_mib"] = disk_usage_bytes / (1024 * 1024)
    (metadata / "dataset_statistics.json").write_text(json.dumps(statistics, indent=2), encoding="utf-8")
    summary.update(statistics); summary["unmatched"] = discovery_rejections
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imagery", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=DEFAULT_TILE_SIZE)
    parser.add_argument("--stride", type=int)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--train-ratio", type=float, default=.70)
    parser.add_argument("--val-ratio", type=float, default=.15)
    parser.add_argument("--test-ratio", type=float, default=.15)
    parser.add_argument("--keep-empty-tiles", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-empty-tile-ratio", type=float, default=.35)
    parser.add_argument("--nodata-threshold", type=float, default=.50)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rgb-low-percentile", type=float, default=DEFAULT_RGB_LOW_PERCENTILE)
    parser.add_argument("--rgb-high-percentile", type=float, default=DEFAULT_RGB_HIGH_PERCENTILE)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    values = vars(args).copy(); values.pop("log_level", None)
    summary = prepare_dataset(**values)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
