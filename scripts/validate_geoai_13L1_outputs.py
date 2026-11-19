"""Validate the derived 13L.1 outputs and summarize identical-patch timings."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import rasterio
import numpy as np
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
OUT = ROOT / "backend/data/models/building/experimental/benchmark_13L1/outputs/whu_geoai"
BASE = ROOT / "backend/data/models/building/experimental/benchmark_13L/outputs"


def main() -> None:
    results = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    alignment_errors: list[str] = []
    invalid_geojson: list[str] = []
    mask_differences_from_13L: list[str] = []
    total_geoai_polygons = 0
    for item in results:
        pid = item["patch_id"]
        meta = json.loads((DATA / "metadata" / f"{pid}.json").read_text(encoding="utf-8"))
        with rasterio.open(DATA / meta["image"]) as src, \
             rasterio.open(OUT / "binary" / f"{pid}.tif") as mask, \
             rasterio.open(OUT / "probability" / f"{pid}.tif") as prob:
            for derived in (mask, prob):
                if (src.width, src.height, src.transform, src.crs) != \
                   (derived.width, derived.height, derived.transform, derived.crs):
                    alignment_errors.append(pid)
            if mask.count != 1 or prob.count != 2:
                alignment_errors.append(pid)
            current_mask = mask.read(1)
        with rasterio.open(BASE / "whu_unetplusplus_efficientnetb4/binary" / f"{pid}.tif") as prior:
            if not np.array_equal(current_mask, prior.read(1)):
                mask_differences_from_13L.append(pid)
        fc = json.loads((OUT / "raw_polygons" / f"{pid}.geojson").read_text(encoding="utf-8"))
        total_geoai_polygons += len(fc["features"])
        if any(not shape(f["geometry"]).is_valid for f in fc["features"]):
            invalid_geojson.append(pid)

    base_rows = list(csv.DictReader((BASE / "benchmark_results_13L.csv").open(encoding="utf-8-sig")))
    report = {
        "patches": len(results),
        "mask_and_probability_exactly_match_source_grid": not alignment_errors,
        "alignment_errors": sorted(set(alignment_errors)),
        "all_raw_geojson_geometries_valid": not invalid_geojson,
        "invalid_geojson_patches": invalid_geojson,
        "geoai_masks_identical_to_13l_whu_masks": not mask_differences_from_13L,
        "mask_differences_from_13l": mask_differences_from_13L,
        "geoai_whu_total_connected_components": total_geoai_polygons,
        "geoai_whu_seconds_mean_including_model_load": statistics.mean(
            x["geoai_whu_seconds_including_model_load"] for x in results
        ),
        "geoai_whu_seconds_mean_excluding_first_cold_patch": statistics.mean(
            x["geoai_whu_seconds_including_model_load"] for x in results[1:]
        ),
        "model_c_13l_seconds_mean": statistics.mean(float(x["model_c_seconds"]) for x in base_rows),
        "whu_manual_13l_seconds_mean": statistics.mean(float(x["whu_seconds"]) for x in base_rows),
        "model_c_13l_components": sum(int(x["model_c_polygons"]) for x in base_rows),
        "whu_manual_13l_components": sum(int(x["whu_polygons"]) for x in base_rows),
    }
    (OUT.parent / "validation_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
