from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import torch
from PIL import Image, ImageDraw
from rasterio.enums import ColorInterp
from rasterio.windows import Window, transform as window_transform

from app.ai.config.ai_model_config import BuildingModelConfig
from app.ai.models.building_model_adapter import BuildingModelAdapter
from app.ai.models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
from app.ai.registry.model_registry import ModelRegistry
from app.ai.services.building_polygonization_service import (
    BuildingPolygonizationService,
    PolygonizationConfig,
)
from app.ai.services.building_results_service import BuildingResultsService
from app.ai.services.inference_service import InferenceService
from app.ai.services.postprocessing_service import (
    PostProcessingConfig,
    PostProcessingService,
    RasterGrid,
)
from app.ai.services.preprocessing_profiles import RGBOrthophotoProfile
from app.ai.services.tiling_service import TilingService


ROOT = Path(__file__).resolve().parents[2]
SOURCE_RGB = ROOT / "test-data" / "validation-results" / "maxar_rgb_derivatives" / "maxar_2025_rgb_p2p98.tif"
ORIGINAL_MAXAR = ROOT / "test-data" / "Jul 28, 2025" / "25JUL28115945-S3DS-200009702745_01_P001_COG.tif"
PATCH_CATALOG = ROOT / "test-data" / "building-ground-truth" / "patch_catalog.json"
GROUND_TRUTH_README = ROOT / "test-data" / "building-ground-truth" / "README_ANNOTATION.md"
OUTPUT = ROOT / "backend" / "data" / "benchmarks" / "building" / "model_a_vs_model_c"
EXPECTED_MODEL_A = "6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987"
EXPECTED_MODEL_C = "170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555"
ZONES = (
    ("zone_1_residential", "GT_2025_residential_01"),
    ("zone_2_mixed_sparse", "GT_2025_difficult_02"),
)
MODEL_A_TILE_SIZE = 640
MODEL_C_TILE_SIZE = 512
OVERLAP_RATIO = 0.20
THRESHOLD = 0.50


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def raster_metadata(path: Path) -> dict[str, Any]:
    with rasterio.open(path) as dataset:
        return {
            "filename": path.name,
            "path": str(path.relative_to(ROOT)),
            "file_size_bytes": path.stat().st_size,
            "width": dataset.width,
            "height": dataset.height,
            "bands": dataset.count,
            "dtype": list(dataset.dtypes),
            "crs": dataset.crs.to_string() if dataset.crs else None,
            "transform": list(dataset.transform),
            "resolution": [dataset.res[0], dataset.res[1]],
            "bounds": {
                "left": dataset.bounds.left,
                "bottom": dataset.bounds.bottom,
                "right": dataset.bounds.right,
                "top": dataset.bounds.top,
            },
            "nodata": dataset.nodata,
            "colorinterp": [value.name for value in dataset.colorinterp],
        }


def materialize_zone(source_path: Path, catalog_entry: dict[str, Any], zone_id: str) -> Path:
    destination = OUTPUT / "subzones" / f"{zone_id}.tif"
    destination.parent.mkdir(parents=True, exist_ok=True)
    window_info = catalog_entry["window"]
    window = Window(
        int(window_info["col_off"]),
        int(window_info["row_off"]),
        int(window_info["width"]),
        int(window_info["height"]),
    )
    with rasterio.open(source_path) as source:
        profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            width=int(window.width),
            height=int(window.height),
            count=3,
            dtype="uint8",
            crs=source.crs,
            transform=window_transform(window, source.transform),
            nodata=source.nodata,
            compress="deflate",
            tiled=True,
        )
        data = source.read((1, 2, 3), window=window)
        with rasterio.open(destination, "w", **profile) as target:
            target.write(data)
            target.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
            target.descriptions = ("R", "G", "B")
            target.update_tags(
                benchmark_zone=zone_id,
                source_raster=source_path.name,
                source_window=json.dumps(window_info, sort_keys=True),
            )
    return destination


def make_grid(path: Path, raster_id: str) -> RasterGrid:
    with rasterio.open(path) as dataset:
        bounds = dataset.bounds
        return RasterGrid(
            raster_id=raster_id,
            width=dataset.width,
            height=dataset.height,
            crs=dataset.crs.to_string() if dataset.crs else "",
            transform=tuple(float(value) for value in dataset.transform),
            bounds={
                "left": float(bounds.left),
                "bottom": float(bounds.bottom),
                "right": float(bounds.right),
                "top": float(bounds.top),
            },
        )


def write_diagnostics(mask_result: Any, out_dir: Path, grid: RasterGrid) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": rasterio.Affine(*grid.transform[:6]),
        "compress": "deflate",
    }
    for name, array, dtype in (
        ("probability.tif", mask_result.global_probability_map, "float32"),
        ("binary_mask.tif", mask_result.global_binary_mask, "uint8"),
        ("valid_mask.tif", mask_result.global_valid_mask.astype(np.uint8), "uint8"),
    ):
        with rasterio.open(out_dir / name, "w", dtype=dtype, **profile) as dataset:
            dataset.write(np.asarray(array, dtype=dtype), 1)


def draw_overlay(image_path: Path, vector_result: Any, output_path: Path, color: tuple[int, int, int]) -> Image.Image:
    with rasterio.open(image_path) as dataset:
        rgb = dataset.read((1, 2, 3)).transpose(1, 2, 0)
        affine_inverse = ~dataset.transform
    canvas = Image.fromarray(rgb, mode="RGB").convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    def draw_ring(coords: Any) -> None:
        points = []
        for x, y in coords:
            col, row = affine_inverse * (float(x), float(y))
            points.append((int(round(col)), int(round(row))))
        if len(points) > 1:
            draw.line(points, fill=(*color, 255), width=2, joint="curve")

    for feature in vector_result.building_features:
        geometry = feature.geometry
        polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
        for polygon in polygons:
            draw_ring(polygon.exterior.coords)
            for interior in polygon.interiors:
                draw_ring(interior.coords)
    canvas.convert("RGB").save(output_path)
    return canvas.convert("RGB")


def run_zone(
    adapter: BuildingModelAdapter | SpaceNet2DeepLabAdapter,
    *,
    model_key: str,
    zone_id: str,
    raster_path: Path,
    c_stats: tuple[float, float],
) -> tuple[dict[str, Any], list[dict[str, Any]], Any, Any, Any]:
    registry = ModelRegistry()
    registry.register("building", lambda: adapter)
    inference = InferenceService(registry)
    source_id = f"13c-{model_key}-{zone_id}"
    tile_size = MODEL_A_TILE_SIZE if model_key == "model_a" else MODEL_C_TILE_SIZE
    started = time.perf_counter()
    tiles = list(
        TilingService().iter_tiles(
            raster_path,
            raster_id=source_id,
            tile_size=tile_size,
            overlap_ratio=OVERLAP_RATIO,
            preprocessing_profile=RGBOrthophotoProfile.name,
            band_indexes=(1, 2, 3),
        )
    )
    if isinstance(adapter, SpaceNet2DeepLabAdapter):
        tiles = [adapter.normalize_tile(tile, image_min=c_stats[0], image_max=c_stats[1]) for tile in tiles]
    predictions = list(
        inference.iter_predictions(
            tiles,
            object_type="building",
            probability_threshold=THRESHOLD,
            inference_mode="standard",
        )
    )
    grid = make_grid(raster_path, source_id)
    mask_result = PostProcessingService().process(
        predictions,
        grid=grid,
        config=PostProcessingConfig(probability_threshold=THRESHOLD),
    )
    vector_result = BuildingPolygonizationService().polygonize(
        mask_result,
        config=PolygonizationConfig(),
    )
    analysis_result = BuildingResultsService().build(vector_result)
    elapsed = time.perf_counter() - started
    info = adapter.get_model_info()
    inference_ms = sum(prediction.metadata.inference_time_ms for prediction in predictions)
    stats = analysis_result.statistics.model_dump(mode="json")
    zone_metrics = {
        "zone_id": zone_id,
        "input_raster": str(raster_path.relative_to(ROOT)),
        "crs": grid.crs,
        "bounds": grid.bounds,
        "tile_size": tile_size,
        "overlap_ratio": OVERLAP_RATIO,
        "tile_count": len(predictions),
        "threshold": THRESHOLD,
        "load_time_ms": float(info["model_load_time_ms"]),
        "inference_time_ms": inference_ms,
        "seconds_per_tile": inference_ms / 1000.0 / len(predictions) if predictions else None,
        "total_pipeline_time_seconds": elapsed,
        "positive_pixel_count_after_fusion": int(mask_result.positive_pixel_count),
        "valid_pixel_count": int(mask_result.valid_pixel_count),
        "positive_pixel_ratio_after_fusion": float(mask_result.positive_pixel_ratio),
        **stats,
        "model_name": info["model_name"],
        "model_version": info["model_version"],
        "model_architecture": info.get("model_architecture"),
        "model_mode": info["model_mode"],
        "device": info["device"],
    }
    return zone_metrics, [feature.model_dump(mode="json") for feature in analysis_result.feature_collection.features], mask_result, vector_result, grid


def main() -> None:
    torch.set_num_threads(2)
    if not SOURCE_RGB.is_file() or not ORIGINAL_MAXAR.is_file():
        raise FileNotFoundError("Le raster Maxar réel requis pour le benchmark est absent.")

    config = BuildingModelConfig.from_env()
    if config.checkpoint_path is None or sha256(config.checkpoint_path) != EXPECTED_MODEL_A:
        raise RuntimeError("MODEL_A n'est pas le checkpoint production validé attendu.")
    model_c_path = ROOT / "backend" / "data" / "models" / "building" / "experimental" / "spacenet2-deeplab" / "best_deeplab.pth"
    if sha256(model_c_path) != EXPECTED_MODEL_C:
        raise RuntimeError("MODEL_C n'est pas le checkpoint expérimental validé attendu.")

    catalog = json.loads(PATCH_CATALOG.read_text(encoding="utf-8"))
    entries = {entry["patch_id"]: entry for entry in catalog["dates"]["2025"]["patches"]}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    zone_paths = {
        zone_id: materialize_zone(SOURCE_RGB, entries[patch_id], zone_id)
        for zone_id, patch_id in ZONES
    }
    model_a = BuildingModelAdapter(config)
    model_c = SpaceNet2DeepLabAdapter(model_c_path, expected_sha256=EXPECTED_MODEL_C)
    model_a.load()
    model_c.load()
    c_stats = model_c._image_minmax(SOURCE_RGB, raster_id="maxar-2025-full-scene", band_indexes=(1, 2, 3))

    metadata = {
        "benchmark": "STEP_13C_REAL_MODEL_A_VS_MODEL_C",
        "created_at_local": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "image_type": "Real Maxar orthorectified imagery; p2-p98 RGB derivative",
        "acquisition_datetime": "2025-07-28T11:59:45.105760Z",
        "original_image": raster_metadata(ORIGINAL_MAXAR),
        "common_rgb_source": raster_metadata(SOURCE_RGB),
        "rgb_mapping_from_original_maxar": {"R": 5, "G": 3, "B": 2},
        "zones": [
            {
                "zone_id": zone_id,
                "catalog_patch_id": patch_id,
                "context_proposal_only": entries[patch_id]["context"],
                "annotation_status": entries[patch_id]["annotation_status"],
                "window": entries[patch_id]["window"],
                "bounds": entries[patch_id]["bounds"],
                "raster": raster_metadata(zone_paths[zone_id]),
            }
            for zone_id, patch_id in ZONES
        ],
        "ground_truth": "ABSENT; annotation GeoJSON files are empty templates and README says MANUAL_ANNOTATION_REQUIRED.",
        "model_a": {
            "checkpoint": str(config.checkpoint_path.relative_to(ROOT)),
            "sha256": EXPECTED_MODEL_A,
            "architecture": config.model_architecture,
            "preprocessing": "Production path: RGB uint8 /255 profile then existing per-channel z-score in adapter.",
            "mode": "PRODUCTION",
        },
        "model_c": {
            "checkpoint": str(model_c_path.relative_to(ROOT)),
            "sha256": EXPECTED_MODEL_C,
            "architecture": "torchvision DeepLabV3 / ResNet-50",
            "preprocessing": "One scalar min/max over the full common RGB scene, valid source pixels; normalize then 512x512 patches; sigmoid(out).",
            "full_scene_scalar_min": c_stats[0],
            "full_scene_scalar_max": c_stats[1],
            "mode": "EXPERIMENTAL ONLY",
        },
        "inference": {
            "threshold_model_a": THRESHOLD,
            "threshold_model_c": THRESHOLD,
            "tile_size_model_a": MODEL_A_TILE_SIZE,
            "tile_size_model_c": MODEL_C_TILE_SIZE,
            "overlap_ratio_both_models": OVERLAP_RATIO,
            "inference_mode": "standard",
            "postprocessing": PostProcessingConfig(probability_threshold=THRESHOLD).public_summary(),
            "polygonization": PolygonizationConfig().public_summary(),
        },
        "limitation": "Qualitative/exploratory only; no precision, recall, F1, IoU or scientific ranking without reviewed labels.",
    }
    write_json(OUTPUT / "benchmark_metadata.json", metadata)

    model_outputs: dict[str, dict[str, Any]] = {}
    full_scene_outputs: dict[str, dict[str, Any]] = {}
    for key, adapter in (("model_a", model_a), ("model_c", model_c)):
        zone_metrics: list[dict[str, Any]] = []
        all_features: list[dict[str, Any]] = []
        zone_area_values: list[float] = []
        for zone_id, _patch_id in ZONES:
            metrics, features, mask, vectors, grid = run_zone(
                adapter,
                model_key=key,
                zone_id=zone_id,
                raster_path=zone_paths[zone_id],
                c_stats=c_stats,
            )
            zone_metrics.append(metrics)
            for feature in features:
                feature["properties"]["benchmark_zone_id"] = zone_id
                all_features.append(feature)
            zone_area_values.extend(
                [float(feature.area_m2) for feature in vectors.building_features if feature.area_m2 is not None]
            )
            diag_dir = OUTPUT / key / zone_id
            write_diagnostics(mask, diag_dir, grid)
            color = (0, 220, 255) if key == "model_a" else (255, 165, 0)
            draw_overlay(zone_paths[zone_id], vectors, diag_dir / "overlay.png", color)
            mask.cleanup()
        total_candidates = len(zone_area_values)
        total_area = sum(zone_area_values)
        aggregate = {
            "zone_count": len(zone_metrics),
            "tile_count": sum(item["tile_count"] for item in zone_metrics),
            "load_time_ms": zone_metrics[0]["load_time_ms"],
            "inference_time_ms": sum(item["inference_time_ms"] for item in zone_metrics),
            "seconds_per_tile": (
                sum(item["inference_time_ms"] for item in zone_metrics)
                / 1000.0
                / sum(item["tile_count"] for item in zone_metrics)
            ),
            "total_pipeline_time_seconds": sum(item["total_pipeline_time_seconds"] for item in zone_metrics),
            "positive_pixel_count_after_fusion": sum(item["positive_pixel_count_after_fusion"] for item in zone_metrics),
            "candidate_count": total_candidates,
            "total_area_m2": total_area,
            "mean_area_m2": total_area / total_candidates if total_candidates else None,
            "median_area_m2": float(np.median(zone_area_values)) if zone_area_values else None,
            "min_area_m2": min(zone_area_values) if zone_area_values else None,
            "max_area_m2": max(zone_area_values) if zone_area_values else None,
        }
        model_dir = OUTPUT / key
        model_dir.mkdir(parents=True, exist_ok=True)
        write_json(model_dir / "result.geojson", {"type": "FeatureCollection", "features": all_features})
        full_metrics, full_features, full_mask, full_vectors, full_grid = run_zone(
            adapter,
            model_key=key,
            zone_id="full_scene_2025",
            raster_path=SOURCE_RGB,
            c_stats=c_stats,
        )
        full_dir = model_dir / "full_scene_2025"
        write_diagnostics(full_mask, full_dir, full_grid)
        draw_overlay(
            SOURCE_RGB,
            full_vectors,
            full_dir / "overlay.png",
            (0, 220, 255) if key == "model_a" else (255, 165, 0),
        )
        write_json(full_dir / "result.geojson", {"type": "FeatureCollection", "features": full_features})
        write_json(full_dir / "metrics.json", full_metrics)
        full_scene_outputs[key] = full_metrics
        full_mask.cleanup()
        model_outputs[key] = {"aggregate": aggregate, "zones": zone_metrics}
        write_json(model_dir / "metrics.json", model_outputs[key])
        adapter.close()

    comparison_dir = OUTPUT / "comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    comparison_inputs = [(zone_id, zone_paths[zone_id]) for zone_id, _ in ZONES]
    comparison_inputs.append(("full_scene_2025", SOURCE_RGB))
    for zone_id, image_path in comparison_inputs:
        base = Image.open(image_path).convert("RGB").resize((512, 512))
        a_overlay = Image.open(OUTPUT / "model_a" / zone_id / "overlay.png").convert("RGB").resize((512, 512))
        c_overlay = Image.open(OUTPUT / "model_c" / zone_id / "overlay.png").convert("RGB").resize((512, 512))
        both = Image.blend(a_overlay, c_overlay, 0.5)
        panel = Image.new("RGB", (1024, 1056), "white")
        draw = ImageDraw.Draw(panel)
        for title, image, x, y in (
            ("Orthophoto", base, 0, 32),
            ("MODEL_A candidates (cyan)", a_overlay, 512, 32),
            ("MODEL_C candidates (orange)", c_overlay, 0, 544),
            ("A + C overlay", both, 512, 544),
        ):
            draw.text((x + 5, y - 22), title, fill="black")
            panel.paste(image, (x, y))
        panel.save(comparison_dir / f"{zone_id}_comparison.png")

    summary = {
        "benchmark_conclusion": "BENCHMARK_INCONCLUSIVE",
        "ground_truth": "ABSENT",
        "qualitative_only": True,
        "visual_review": {
            "building_coverage": "MODEL_C shows outlines over substantially more visible roofs; MODEL_A is sparse and returns no candidates in the two sampled subzones.",
            "apparent_false_positives": "UNCLEAR without independent labels; some small MODEL_C candidates may correspond to rooftop structures or bright ground details.",
            "apparent_false_negatives": "MODEL_A appears to miss more visibly built roof area in these samples; descriptive only.",
            "boundary_quality": "UNCLEAR without reviewed roof footprints.",
            "fragmentation": "UNCLEAR; small MODEL_C polygons may be separate rooftop structures or fragments.",
            "roads_bare_soil_vegetation_shadows": "The mixed sparse zone includes roads, bare lots, and vegetation; no independent labels are available to classify each candidate.",
        },
        "models": model_outputs,
        "geographic_alignment": {
            "same_source_rgb": str(SOURCE_RGB.relative_to(ROOT)),
            "same_zone_bounds_for_both_models": True,
            "same_threshold": THRESHOLD,
            "same_postprocessing_and_polygonization": True,
        },
        "full_scene_benchmark": {
            "status": "RUN",
            "scope": "The available full RGB scene is 2048x2048 (4.19 MP), not a massive raster.",
            "models": full_scene_outputs,
        },
        "next_step": "OBTAIN REPRESENTATIVE DATA OR GROUND TRUTH",
    }
    write_json(comparison_dir / "summary.json", summary)
    model_a.close()
    model_c.close()
    print(json.dumps({"output": str(OUTPUT), "summary": summary}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
