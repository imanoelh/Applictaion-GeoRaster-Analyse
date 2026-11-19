"""Generate MODEL_C proposals only; keep them separate from human ground truth."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask, shapes
from shapely.geometry import mapping, shape


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
BACKEND = ROOT / "backend"
CHECKPOINT = BACKEND / "data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth"
EXPECTED_CHECKPOINT_SHA256 = "170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555"
MODEL_ID = "spacenet2_deeplab"
THRESHOLD = 0.50


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    from app.ai.models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
    from app.ai.services.tiling_service import TilingService

    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("MODEL_C checkpoint SHA256 does not match the audited artifact; refusing inference.")
    adapter = SpaceNet2DeepLabAdapter(CHECKPOINT, expected_sha256=EXPECTED_CHECKPOINT_SHA256, engine="onnxruntime")
    adapter.load()
    runtime = str(adapter.get_model_info().get("runtime", "")).lower()
    if runtime != "onnxruntime":
        raise RuntimeError(f"Expected ONNX Runtime CPU, got {runtime}.")

    rows = []
    started_all = time.perf_counter()
    try:
        for meta_path in sorted((DATA / "metadata").glob("*.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if "patch_id" not in meta:
                continue
            patch_id = meta["patch_id"]
            meta.setdefault("review_status", "NOT_REVIEWED")
            meta.setdefault("reviewer", None)
            meta.setdefault("reviewed_at", None)
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            image_path = DATA / meta["image"]
            with rasterio.open(image_path) as src:
                tiles = TilingService().iter_tiles(
                    image_path,
                    raster_id=f"preannotation-{patch_id}",
                    tile_size=512,
                    overlap_ratio=0.0,
                    min_valid_pixel_ratio=0.05,
                    preprocessing_profile="rgb_orthophoto_uint8_v1",
                    band_indexes=(1, 2, 3),
                )
                prepared = list(adapter.prepare_inference_tiles(
                    tiles, image_path, raster_id=f"preannotation-{patch_id}", band_indexes=(1, 2, 3)
                ))
                if len(prepared) != 1:
                    raise RuntimeError(f"{patch_id}: expected one 512x512 input tile, got {len(prepared)}")
                tile = prepared[0]
                output = adapter.predict(tile)
                probability = output.probability_map
                positive = np.logical_and(probability >= THRESHOLD, tile.valid_mask)
                binary = positive.astype(np.uint8)
                transform, crs, bounds = src.transform, src.crs, src.bounds

            features = []
            for geom_mapping, value in shapes(binary, mask=positive, transform=transform, connectivity=8):
                geom = shape(geom_mapping)
                pixel_region = geometry_mask([geom_mapping], out_shape=(512, 512), transform=transform,
                                             all_touched=False, invert=True)
                scores = probability[pixel_region & positive]
                if scores.size == 0:
                    continue
                mean_score, max_score = float(scores.mean()), float(scores.max())
                confidence_class = "HIGH_CONFIDENCE" if mean_score >= 0.80 else (
                    "MEDIUM_CONFIDENCE" if mean_score >= 0.60 else "LOW_CONFIDENCE"
                )
                area_pixels = int(scores.size)
                index = len(features) + 1
                properties = {
                    "building_id": f"{patch_id}_MC{index:04d}",
                    "patch_id": patch_id,
                    "date": str(meta["source_date"]),
                    "source": "MODEL_C_PREANNOTATION",
                    "source_raster": meta["source_raster"],
                    "model_id": MODEL_ID,
                    "engine": "ONNX_RUNTIME_CPU",
                    "threshold": THRESHOLD,
                    "review_status": "NOT_REVIEWED",
                    "confidence_mean": mean_score,
                    "confidence_max": max_score,
                    "confidence_class": confidence_class,
                    "area_pixels": area_pixels,
                    "area_m2": float(geom.area),
                    "annotator": None,
                }
                features.append({"type": "Feature", "geometry": geom_mapping, "properties": properties})

            feature_collection = {
                "type": "FeatureCollection",
                "name": f"{patch_id}_model_c_preannotation",
                "crs": {"type": "name", "properties": {"name": crs.to_string()}},
                "metadata": {
                    "patch_id": patch_id,
                    "source": "MODEL_C_PREANNOTATION",
                    "model_id": MODEL_ID,
                    "engine": "ONNX_RUNTIME_CPU",
                    "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
                    "onnx_sha256": sha256(adapter.onnx_path),
                    "threshold": THRESHOLD,
                    "review_status": "NOT_REVIEWED",
                    "human_validation_required": True,
                    "automatically_validated": False,
                },
                "features": features,
            }
            out_path = DATA / "pre_annotations" / f"{patch_id}_model_c.geojson"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Do not overwrite an existing edited review layer; model proposals are reproducible.
            out_path.write_text(json.dumps(feature_collection, indent=2) + "\n", encoding="utf-8")

            review_path = DATA / "review" / f"{patch_id}_review.geojson"
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_created = not review_path.exists()
            if review_created:
                review_fc = json.loads(json.dumps(feature_collection))
                review_fc["name"] = f"{patch_id}_manual_review"
                review_fc["metadata"]["review_layer"] = True
                review_path.write_text(json.dumps(review_fc, indent=2) + "\n", encoding="utf-8")
            low_count = sum(f["properties"]["confidence_class"] == "LOW_CONFIDENCE" for f in features)
            area_total = float(sum(f["properties"]["area_m2"] for f in features))
            vertices = sum(len(shape(f["geometry"]).exterior.coords) if shape(f["geometry"]).geom_type == "Polygon" else
                           sum(len(poly.exterior.coords) for poly in shape(f["geometry"]).geoms)
                           for f in features)
            rows.append({
                "patch_id": patch_id,
                "split": meta["split"],
                "source_date": meta["source_date"],
                "candidate_count": len(features),
                "low_confidence_count": low_count,
                "low_confidence_ratio": low_count / len(features) if features else 0.0,
                "fragmentation_candidates_per_m2": len(features) / area_total if area_total else 0.0,
                "total_candidate_area_m2": area_total,
                "mean_candidate_area_m2": area_total / len(features) if features else 0.0,
                "vertex_count": vertices,
                "inference_ms": float(output.inference_time_ms),
                "preannotation_geojson": str(out_path.relative_to(DATA)).replace("\\", "/"),
                "review_geojson": str(review_path.relative_to(DATA)).replace("\\", "/"),
                "review_file_created": review_created,
                "review_status": "NOT_REVIEWED",
            })
            print(f"{patch_id}: {len(features)} candidates, {output.inference_time_ms:.1f} ms")
    finally:
        adapter.close()

    rows.sort(key=lambda r: (r["low_confidence_count"], r["candidate_count"],
                             r["fragmentation_candidates_per_m2"], r["total_candidate_area_m2"],
                             r["vertex_count"]), reverse=True)
    priority_path = DATA / "metadata/review_priority.csv"
    priority_path.parent.mkdir(parents=True, exist_ok=True)
    with priority_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    time_path = DATA / "metadata/review_time_log.csv"
    if not time_path.exists():
        with time_path.open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["patch_id", "manual_from_scratch_minutes", "assisted_review_minutes", "reviewer", "notes"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows[:3]:
                writer.writerow({"patch_id": row["patch_id"], "manual_from_scratch_minutes": "",
                                 "assisted_review_minutes": "", "reviewer": "", "notes": "Human time study pending"})

    manifest = {
        "model_id": MODEL_ID, "engine": "ONNX_RUNTIME_CPU", "threshold": THRESHOLD,
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256, "onnx_sha256": sha256(adapter.onnx_path),
        "preprocessing_profile": "full_raster_global_rgb_minmax_v1",
        "human_validation_required": True, "auto_validation": False,
        "patches": len(rows), "candidate_count_total": sum(r["candidate_count"] for r in rows),
        "inference_wall_time_seconds": round(time.perf_counter() - started_all, 3),
        "review_files_preserved_on_rerun": True,
    }
    (DATA / "metadata/preannotation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
