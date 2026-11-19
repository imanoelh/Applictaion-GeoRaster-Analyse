"""Controlled live-GEE experiments for the unsupervised-classification axes.

This module is deliberately outside the API path.  It reuses one mosaic and a
fixed validation sample so K, sampling, predictors, standardisation and the
Sentinel composite can be compared one variable at a time.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import gee_client as gc
from app.scalability import classification_cost_policy


PROFILE_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12", "NDVI", "NDWI", "NDBI", "BSI"]
SPECTRAL_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
FEATURES = {
    "F0_current": SPECTRAL_BANDS + ["NDVI", "NDWI", "NDBI", "BSI", "SAVI"],
    "F1_spectral": SPECTRAL_BANDS,
    "F2_spectral_ndvi": SPECTRAL_BANDS + ["NDVI"],
    "F3_spectral_ndvi_ndwi": SPECTRAL_BANDS + ["NDVI", "NDWI"],
}


def _aoi(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    return {
        "bbox": [south, west, north, east],
        "geojson": {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
    }


def _area_km2(aoi: dict[str, Any]) -> float:
    south, west, north, east = aoi["bbox"]
    mean_lat = math.radians((south + north) / 2)
    return abs(east - west) * 111.32 * max(math.cos(mean_lat), 0.25) * abs(north - south) * 110.57


def _analysis(aoi: dict[str, Any], *, method: str = "median_composite") -> dict[str, Any]:
    return {
        "sensor": "sentinel-2",
        "source": "gee",
        "date_start": "2024-06-01",
        "date_end": "2024-06-30",
        "max_cloud_pct": 40,
        "image_method": method,
        "analysis_type": "unsupervised_classification",
        "index": "UNSUPERVISED_CLASSIFICATION",
        "aoi": aoi,
    }


def _sample(stack: Any, bands: list[str], geom: Any, *, count: int, scale: int, seed: int) -> Any:
    return stack.select(bands).sample(
        region=geom,
        scale=scale,
        numPixels=count,
        seed=seed,
        geometries=False,
        tileScale=8,
        dropNulls=True,
    )


def _grid_sample(
    stack: Any,
    bands: list[str],
    geom: Any,
    bbox: list[float],
    *,
    count: int,
    scale: int,
    seed: int,
    rows: int = 4,
    columns: int = 4,
) -> Any:
    south, west, north, east = bbox
    per_cell = max(1, math.ceil(count / (rows * columns)))
    grid_band = gc.ee.Image.constant(-1).rename("grid_cell").toInt16()
    for row in range(rows):
        cell_south = south + (north - south) * row / rows
        cell_north = south + (north - south) * (row + 1) / rows
        for column in range(columns):
            cell_west = west + (east - west) * column / columns
            cell_east = west + (east - west) * (column + 1) / columns
            cell = gc.ee.Geometry.Rectangle([cell_west, cell_south, cell_east, cell_north])
            grid_band = grid_band.paint(cell, row * columns + column)
    # One server-side aggregation, with a bounded equal quota per grid cell.
    # This avoids the GEE "Too many concurrent aggregations" failure caused by
    # merging one independent sample() request per cell.
    return (
        stack.select(bands)
        .addBands(grid_band.updateMask(grid_band.gte(0)))
        .stratifiedSample(
            numPoints=per_cell,
            classBand="grid_cell",
            region=geom,
            scale=scale,
            seed=seed,
            dropNulls=True,
            tileScale=8,
            geometries=False,
        )
        .limit(count)
    )


def _standardize(samples: Any, bands: list[str]) -> tuple[Any, dict[str, float], dict[str, float]]:
    reducer = gc.ee.Reducer.mean().repeat(len(bands)).combine(
        reducer2=gc.ee.Reducer.stdDev().repeat(len(bands)),
        sharedInputs=True,
    )
    raw = samples.reduceColumns(reducer=reducer, selectors=bands).getInfo() or {}
    means = [float(value) for value in (raw.get("mean") or [])]
    deviations = [max(float(value or 0), 1e-6) for value in (raw.get("stdDev") or [])]
    if len(means) != len(bands) or len(deviations) != len(bands):
        raise RuntimeError("Incomplete z-score statistics")
    mean_by_band = dict(zip(bands, means))
    deviation_by_band = dict(zip(bands, deviations))

    def transform(feature: Any) -> Any:
        return gc.ee.Feature(feature).set(
            {
                band: gc.ee.Number(feature.get(band)).subtract(mean_by_band[band]).divide(deviation_by_band[band])
                for band in bands
            }
        )

    return samples.map(transform), mean_by_band, deviation_by_band


def _apply_standardization(samples: Any, bands: list[str], means: dict[str, float], deviations: dict[str, float]) -> Any:
    def transform(feature: Any) -> Any:
        return gc.ee.Feature(feature).set(
            {
                band: gc.ee.Number(feature.get(band)).subtract(means[band]).divide(deviations[band])
                for band in bands
            }
        )

    return samples.map(transform)


def _ndvi_distribution(samples: Any) -> dict[str, Any]:
    filters = {
        "lt_0": gc.ee.Filter.lt("NDVI", 0),
        "0_0.1": gc.ee.Filter.And(gc.ee.Filter.gte("NDVI", 0), gc.ee.Filter.lt("NDVI", 0.1)),
        "0.1_0.2": gc.ee.Filter.And(gc.ee.Filter.gte("NDVI", 0.1), gc.ee.Filter.lt("NDVI", 0.2)),
        "0.2_0.3": gc.ee.Filter.And(gc.ee.Filter.gte("NDVI", 0.2), gc.ee.Filter.lt("NDVI", 0.3)),
        "0.3_0.5": gc.ee.Filter.And(gc.ee.Filter.gte("NDVI", 0.3), gc.ee.Filter.lt("NDVI", 0.5)),
        "gte_0.5": gc.ee.Filter.gte("NDVI", 0.5),
    }
    payload = gc.ee.Dictionary({"total": samples.size(), **{name: samples.filter(rule).size() for name, rule in filters.items()}}).getInfo()
    total = int(payload.get("total") or 0)
    return {
        name: {"count": int(payload.get(name) or 0), "pct": round(100 * int(payload.get(name) or 0) / total, 3) if total else 0}
        for name in filters
    }


def _cluster_profiles(clustered: Any, area_km2: float) -> list[dict[str, Any]]:
    histogram = clustered.aggregate_histogram("cluster").getInfo() or {}
    reducer = gc.ee.Reducer.mean().repeat(len(PROFILE_BANDS)).group(
        groupField=len(PROFILE_BANDS),
        groupName="cluster",
    )
    raw = clustered.reduceColumns(reducer=reducer, selectors=PROFILE_BANDS + ["cluster"]).getInfo() or {}
    total = sum(int(value) for value in histogram.values())
    means_by_cluster = {
        int(group["cluster"]): dict(zip(PROFILE_BANDS, (float(value) for value in group.get("mean") or [])))
        for group in raw.get("groups") or []
    }
    rows = []
    for key, value in sorted(histogram.items(), key=lambda item: int(item[0])):
        cluster = int(key)
        count = int(value)
        pct = (100 * count / total) if total else 0
        means = means_by_cluster.get(cluster, {})
        rows.append(
            {
                "cluster": cluster,
                "validation_pixels": count,
                "pct_valid": round(pct, 3),
                "estimated_surface_km2": round(area_km2 * pct / 100, 2),
                "means": {band: round(float(means.get(band) or 0), 6) for band in PROFILE_BANDS},
            }
        )
    return rows


def _run_variant(
    label: str,
    training: Any,
    validation: Any,
    bands: list[str],
    *,
    clusters: int,
    seed: int,
    area_km2: float,
    standardization: str = "none",
    training_count_hint: int | None = None,
) -> dict[str, Any]:
    print(f"START_VARIANT {label}", file=sys.stderr, flush=True)
    started = time.perf_counter()
    training_for_cluster = training.select(bands)
    validation_for_cluster = validation
    if standardization == "zscore":
        training_for_cluster, means, deviations = _standardize(training_for_cluster, bands)
        validation_for_cluster = _apply_standardization(validation, bands, means, deviations)
    clusterer = gc.ee.Clusterer.wekaKMeans(
        nClusters=clusters,
        init=1,
        preserveOrder=True,
        seed=seed,
    ).train(features=training_for_cluster, inputProperties=bands, subsamplingSeed=seed)
    clustered = validation_for_cluster.cluster(clusterer, "cluster")
    profiles = _cluster_profiles(clustered, area_km2)
    ndvis = [float(row["means"]["NDVI"]) for row in profiles]
    result = {
        "label": label,
        "k": clusters,
        "seed": seed,
        "features": bands,
        "normalization": standardization,
        "training_count": int(training_count_hint if training_count_hint is not None else (training.size().getInfo() or 0)),
        "validation_count": sum(int(row["validation_pixels"]) for row in profiles),
        "ndvi_separation": round(max(ndvis) - min(ndvis), 6) if ndvis else 0,
        "clusters": profiles,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    print(
        "END_VARIANT " + json.dumps(
            {
                "label": label,
                "elapsed_ms": result["elapsed_ms"],
                "ndvi_separation": result["ndvi_separation"],
                "cluster_pcts": [row["pct_valid"] for row in profiles],
                "cluster_ndvi": [row["means"]["NDVI"] for row in profiles],
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
        flush=True,
    )
    return result


def _scene_diagnostics(collection: Any) -> dict[str, Any]:
    raw = gc.ee.Dictionary(
        {
            "scene_count": collection.size(),
            "earliest_ms": collection.aggregate_min("system:time_start"),
            "latest_ms": collection.aggregate_max("system:time_start"),
            "tiles": collection.aggregate_array("MGRS_TILE").distinct().sort(),
            "cloud_mean": collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE"),
        }
    ).getInfo() or {}
    earliest = gc._format_date(raw.get("earliest_ms"))
    latest = gc._format_date(raw.get("latest_ms"))
    return {
        "collection": gc.S2_COLLECTION,
        "scene_count": int(raw.get("scene_count") or 0),
        "earliest": earliest,
        "latest": latest,
        "temporal_span_days": (
            (gc.datetime.fromisoformat(latest) - gc.datetime.fromisoformat(earliest)).days
            if earliest and latest
            else None
        ),
        "sentinel_tiles": raw.get("tiles") or [],
        "sentinel_tiles_count": len(raw.get("tiles") or []),
        "mean_cloud_pct": round(float(raw.get("cloud_mean") or 0), 3),
    }


SCENARIOS = {
    "small": _aoi(24.70, 46.60, 24.78, 46.70),
    "medium": _aoi(24.40, 46.20, 24.90, 46.90),
    "large": _aoi(23.60, 45.40, 25.40, 47.60),
}


def run(
    axis: str,
    *,
    scenario: str = "medium",
    sample_count_override: int | None = None,
    validation_count: int = 3_000,
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    if not gc._ensure_gee():
        raise RuntimeError(f"GEE unavailable: {gc.gee_status()}")
    aoi = SCENARIOS[scenario]
    area_km2 = _area_km2(aoi)
    analysis = _analysis(aoi)
    mosaic = gc._build_analysis_mosaic(analysis)
    stack, _ = gc._unsupervised_feature_stack(mosaic["image"], "sentinel-2")
    geom = mosaic["geom"]
    policy = classification_cost_policy(area_km2, 10)
    sample_count = int(sample_count_override or policy["max_unsupervised_samples"])
    sample_scale = int(policy["sample_scale_m"])
    all_bands = FEATURES["F0_current"]
    # A bounded, independent validation sample is enough for controlled axis
    # comparisons and avoids re-evaluating a 12k-point graph for every K.
    validation = _sample(stack, all_bands, geom, count=validation_count, scale=max(sample_scale, 60), seed=913)
    baseline_training = _sample(stack, all_bands, geom, count=sample_count, scale=sample_scale, seed=91)
    collection = gc._prepared_collection(analysis, geom)
    report: dict[str, Any] = {
        "aoi": aoi,
        "area_km2": round(area_km2, 2),
        "policy": policy,
        "mosaic": gc._mosaic_quality_payload(mosaic),
        "scenes": _scene_diagnostics(collection),
        "baseline_training_count": int(baseline_training.size().getInfo() or 0),
        "baseline_ndvi_distribution": _ndvi_distribution(baseline_training),
        "axis": axis,
        "scenario": scenario,
        "results": [],
    }
    print(
        "PREPARED " + json.dumps(
            {
                "scenario": scenario,
                "area_km2": round(area_km2, 2),
                "sample_count": report["baseline_training_count"],
                "validation_requested": validation_count,
                "scenes": report["scenes"],
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
        flush=True,
    )

    if axis in {"k", "all"}:
        for k in (k_values or [2, 3, 4, 5, 6, 8]):
            report["results"].append(_run_variant(f"K{k}", baseline_training, validation, all_bands, clusters=k, seed=91, area_km2=area_km2, training_count_hint=report["baseline_training_count"]))

    if axis in {"sampling", "all"}:
        for multiplier in [1, 2, 3]:
            count = min(20_000, sample_count * multiplier)
            training = _sample(stack, all_bands, geom, count=count, scale=sample_scale, seed=91)
            report["results"].append(_run_variant(f"random_{count}", training, validation, all_bands, clusters=4, seed=91, area_km2=area_km2, training_count_hint=count))
    if axis in {"sampling", "grid", "all"}:
        grid = _grid_sample(stack, all_bands, geom, aoi["bbox"], count=sample_count, scale=sample_scale, seed=91)
        report["grid_ndvi_distribution"] = _ndvi_distribution(grid)
        grid_count = int(grid.size().getInfo() or 0)
        report["results"].append(_run_variant("grid_4x4", grid, validation, all_bands, clusters=4, seed=91, area_km2=area_km2, training_count_hint=grid_count))

    if axis in {"features", "all"}:
        for label, bands in FEATURES.items():
            report["results"].append(_run_variant(label, baseline_training, validation, bands, clusters=4, seed=91, area_km2=area_km2, training_count_hint=report["baseline_training_count"]))

    if axis in {"normalization", "all"}:
        bands = FEATURES["F2_spectral_ndvi"]
        for method in ["none", "zscore"]:
            report["results"].append(_run_variant(f"normalization_{method}", baseline_training, validation, bands, clusters=4, seed=91, area_km2=area_km2, standardization=method, training_count_hint=report["baseline_training_count"]))

    if axis in {"composite", "all"}:
        bands = FEATURES["F2_spectral_ndvi"]
        report["results"].append(_run_variant("adaptive_tile_median", baseline_training, validation, bands, clusters=4, seed=91, area_km2=area_km2, standardization="zscore", training_count_hint=report["baseline_training_count"]))
        global_image = collection.median().clip(geom)
        global_stack, _ = gc._unsupervised_feature_stack(global_image, "sentinel-2")
        global_training = _grid_sample(global_stack, all_bands, geom, aoi["bbox"], count=sample_count, scale=sample_scale, seed=91)
        global_validation = _sample(global_stack, all_bands, geom, count=validation_count, scale=max(sample_scale, 60), seed=913)
        report["results"].append(_run_variant("global_median", global_training, global_validation, bands, clusters=4, seed=91, area_km2=area_km2, standardization="zscore", training_count_hint=sample_count))

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axis", choices=["k", "sampling", "grid", "features", "normalization", "composite", "all"], required=True)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="medium")
    parser.add_argument("--sample-count", type=int)
    parser.add_argument("--validation-count", type=int, default=3_000)
    parser.add_argument("--k-values", default="2,3,4,5,6,8")
    args = parser.parse_args()
    started = time.perf_counter()
    k_values = [int(value) for value in args.k_values.split(",") if value.strip()]
    report = run(
        args.axis,
        scenario=args.scenario,
        sample_count_override=args.sample_count,
        validation_count=args.validation_count,
        k_values=k_values,
    )
    report["total_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
