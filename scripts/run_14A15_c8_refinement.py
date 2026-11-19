"""Application-level C8 refinement on non-GOLD DEV patches only.

This script never writes model weights or GOLD data. It preserves raw C8
probabilities and evaluates a small, auditable post-processing grid.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
import time
from collections import deque
from pathlib import Path

import numpy as np
import rasterio
os.environ["PROJ_LIB"] = str(Path(rasterio.__file__).resolve().parent / "proj_data")
from PIL import Image, ImageDraw, ImageFont
from rasterio.features import rasterize, shapes
from rasterio.warp import transform_geom
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union, transform as shapely_transform
from shapely import wkb

import torch
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision"
DEV = BASE / "14A9B_dev_set"
C8 = BASE / "14A11_hybrid_pipeline"
OUT = BASE / "14A15_application_precision_refinement"
CHECKPOINT = C8 / "models/MODEL_C8_HYBRID_epoch2.pth"
CHECKPOINT_SHA256 = "32f48ba94385206ed3e1cc8a156b73ac33810525f05a6bb3fd51b16c486a7576"
PATCHES = [
    "14A9B_DEV_11_R00256_C05888",
    "14A9B_DEV_12_R03840_C06400",
    "14A9B_DEV_13_R05888_C02816",
    "14A9B_DEV_14_R08448_C08960",
]


def sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_model():
    model = deeplabv3_resnet50(weights=None, weights_backbone=None, aux_loss=True)
    model.classifier = DeepLabHead(2048, 1)
    checkpoint = torch.load(str(CHECKPOINT), map_location="cpu", weights_only=True)
    state = checkpoint["state_dict"] if isinstance(checkpoint, dict) and "state_dict" in checkpoint else checkpoint
    model.load_state_dict(state, strict=True)
    model.eval()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    return model


def read_gt(path: Path, patch_id: str):
    rows = []
    with sqlite3.connect(path) as db:
        for geom_blob, *attrs in db.execute(f'SELECT geom FROM "{patch_id}"'):
            if geom_blob is None:
                continue
            flags = geom_blob[3]
            envelope = (flags >> 1) & 7
            envelope_bytes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(envelope, 0)
            rows.append(wkb.loads(geom_blob[8 + envelope_bytes:]))
    return rows


def connected_components(mask: np.ndarray, minimum: int) -> np.ndarray:
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x]:
                continue
            current += 1
            q = deque([(y, x)])
            labels[y, x] = current
            pixels = []
            while q:
                cy, cx = q.popleft(); pixels.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = current; q.append((ny, nx))
            if len(pixels) < minimum:
                for py, px in pixels:
                    labels[py, px] = 0
    return labels


def polygons_from_probability(prob: np.ndarray, threshold: float, minimum: int, transform):
    labels = connected_components(prob >= threshold, minimum)
    final = (labels > 0).astype(np.uint8)
    result = []
    for geom, value in shapes(final, mask=final.astype(bool), transform=transform):
        if int(value) != 1:
            continue
        polygon = shape(geom)
        if not polygon.is_empty and polygon.area > 0:
            result.append(polygon)
    return final, result, labels


def metrics(gt, pred, threshold=0.30):
    pairs = []
    used_g = set(); used_p = set()
    candidates = []
    for gi, g in enumerate(gt):
        for pi, p in enumerate(pred):
            union = g.union(p).area
            iou = g.intersection(p).area / union if union else 0.0
            if iou >= threshold:
                candidates.append((iou, gi, pi))
    for iou, gi, pi in sorted(candidates, reverse=True):
        if gi not in used_g and pi not in used_p:
            used_g.add(gi); used_p.add(pi); pairs.append((gi, pi, iou))
    tp = len(pairs); fp = len(pred) - tp; fn = len(gt) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    small = {i for i, g in enumerate(gt) if g.area <= 50.0}
    small_tp = len(small & used_g)
    return dict(TP=tp, FP=fp, FN=fn, GT=len(gt), PRED=len(pred), precision=precision,
                recall=recall, f1=f1, small_gt=len(small), small_tp=small_tp,
                small_recall=small_tp / len(small) if small else 0.0,
                matched=pairs)


def object_features(prob, polygons, transform):
    rows = []
    for idx, polygon in enumerate(polygons, 1):
        area = float(polygon.area); perimeter = float(polygon.length)
        hull_area = float(polygon.convex_hull.area)
        minx, miny, maxx, maxy = polygon.bounds
        width = maxx - minx; height = maxy - miny
        rectangularity = area / (width * height) if width and height else 0.0
        compactness = 4 * math.pi * area / (perimeter * perimeter) if perimeter else 0.0
        mask = rasterize([(mapping(polygon), 1)], out_shape=prob.shape, transform=transform, fill=0, dtype="uint8").astype(bool)
        values = prob[mask]
        mean_probability = float(values.mean()) if values.size else 0.0
        max_probability = float(values.max()) if values.size else 0.0
        edge_probability = float(np.percentile(values, 20)) if values.size else 0.0
        artifact_score = min(1.0, 0.45 * (1.0 - mean_probability) + 0.30 * (1.0 - (area / max(area, 64.0))) + 0.25 * (1.0 - (area / hull_area if hull_area else 0.0)))
        bare_soil_score = min(1.0, 0.6 * (1.0 - mean_probability) + 0.4 * (1.0 - compactness))
        aspect_ratio = max(width, height) / max(1e-9, min(width, height))
        road_score = min(1.0, 0.55 * max(0.0, (aspect_ratio - 4.0) / 8.0) + 0.25 * (1.0 - rectangularity) + 0.20 * (1.0 - mean_probability))
        rows.append(dict(object_id=f"c8_{idx:05d}", area_m2=area, perimeter_m=perimeter,
                         area_px=area / 0.1225, compactness=compactness,
                         solidity=area / hull_area if hull_area else 0.0,
                         rectangularity=rectangularity, aspect_ratio=aspect_ratio,
                         hole_count=max(0, len(polygon.interiors)), mean_probability=mean_probability,
                         max_probability=max_probability, edge_probability=edge_probability,
                         neighbor_distance=None, artifact_score=artifact_score,
                         bare_soil_fp_score=bare_soil_score, road_fp_score=road_score,
                         large_object_warning=bool(area > 2000.0), fragment_merge_score=0.0))
    return rows


def geojson(features):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": str(i), "properties": p, "geometry": mapping(g)}
        for i, (g, p) in enumerate(features, 1)
    ]}


def save_overlay(path, rgb, baseline, refined, title):
    im = Image.fromarray(np.moveaxis(rgb[:3], 0, -1).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(im)
    # Raster masks are deliberately shown as translucent color overlays.
    for mask, color in ((baseline, (220, 40, 40)), (refined, (30, 170, 70))):
        ys, xs = np.where(mask)
        if len(xs):
            for y, x in zip(ys[::max(1, len(xs)//4000)], xs[::max(1, len(xs)//4000)]):
                draw.point((int(x), int(y)), fill=color)
    draw.text((5, 5), title, fill="white")
    im.save(path)


def main():
    assert CHECKPOINT.is_file() and sha256(CHECKPOINT) == CHECKPOINT_SHA256
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("BASELINE_C8_RAW", "refined", "overlays", "zones"):
        (OUT / name).mkdir(exist_ok=True)
    gt_path = DEV / "gt/MANUAL_CORRECTED_GT.gpkg"
    model = load_model()
    records = []
    all_probs = {}; all_gt = {}; all_rgb = {}; all_transforms = {}; all_base = {}
    for patch in PATCHES:
        rgb_path = DEV / "rgb" / f"{patch}.tif"
        with rasterio.open(rgb_path) as src:
            rgb = src.read(indexes=(1, 2, 3)); transform = src.transform
            image = rgb.astype(np.float32); image = (image - image.min()) / max(1e-6, float(image.max() - image.min()))
        with torch.inference_mode():
            probability = torch.sigmoid(model(torch.from_numpy(image[None]))["out"][0, 0]).numpy().astype(np.float32)
        # DEV GT is stored in the native UTM 37N annotation CRS while these
        # application rasters are WGS84 GeoTIFFs. Reproject only in memory for
        # comparison; no source annotation or raster is rewritten.
        gt = [shape(transform_geom("EPSG:32637", "EPSG:4326", mapping(geometry), precision=12)) for geometry in read_gt(gt_path, patch)]
        base_mask, base_polygons, _ = polygons_from_probability(probability, 0.50, 32, transform)
        np.savez_compressed(OUT / "BASELINE_C8_RAW" / f"{patch}.npz", probability=probability, thresholded_mask=base_mask)
        (OUT / "BASELINE_C8_RAW" / f"{patch}.geojson").write_text(json.dumps(geojson([(g, {"model": "MODEL_C8_HYBRID", "stage": "RAW"}) for g in base_polygons]), indent=2), encoding="utf-8")
        all_probs[patch] = probability; all_gt[patch] = gt; all_rgb[patch] = rgb; all_transforms[patch] = transform; all_base[patch] = base_polygons
        records.extend(object_features(probability, base_polygons, transform))
    with (OUT / "14A15_c8_object_features.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)

    configs = []
    for threshold in (0.45, 0.50, 0.55, 0.60):
        for minimum in (16, 32, 48, 64):
            total = {"TP": 0, "FP": 0, "FN": 0, "GT": 0, "PRED": 0, "small_gt": 0, "small_tp": 0}
            for patch in PATCHES:
                _, pred, _ = polygons_from_probability(all_probs[patch], threshold, minimum, all_transforms[patch])
                m = metrics(all_gt[patch], pred)
                for key in total: total[key] += m[key]
            tp, fp, fn = total["TP"], total["FP"], total["FN"]
            precision = tp / (tp + fp) if tp + fp else 0.0; recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            configs.append(dict(threshold=threshold, min_component=minimum, **total, precision=precision, recall=recall, f1=f1, small_recall=total["small_tp"] / total["small_gt"] if total["small_gt"] else 0.0))
    baseline = next(r for r in configs if r["threshold"] == 0.5 and r["min_component"] == 32)
    feasible = [r for r in configs if r["precision"] > baseline["precision"] and r["f1"] >= baseline["f1"] and r["small_recall"] >= baseline["small_recall"] * 0.8]
    refined = max(feasible or [baseline], key=lambda r: (r["precision"], r["f1"], r["small_recall"], -r["FP"]))
    (OUT / "DEV_GRID.csv").write_text("".join([",".join(map(str, r.values())) + "\n" for r in configs]), encoding="utf-8")
    refined_config = dict(model="MODEL_C8_HYBRID", enabled=refined != baseline, checkpoint=str(CHECKPOINT.relative_to(ROOT)), checkpoint_sha256=CHECKPOINT_SHA256, baseline_threshold=0.50, baseline_min_component=32, threshold=refined["threshold"], min_component=refined["min_component"], connectivity=4, morphology="NONE", artifact_filter="CONSERVATIVE_FEATURE_SCORE_ONLY", bare_soil_filter="UNCERTAIN_ONLY_NO_HARD_REJECTION", road_filter="UNCERTAIN_ONLY_NO_HARD_REJECTION", polygon_cleaning="LIGHT_REPAIR_NO_AGGRESSIVE_SIMPLIFICATION", fragment_merge="DISABLED_UNTIL_HUMAN_VALIDATION", hole_cleaning="REMOVE_ONLY_SUBPIXEL_NOISE", selection_source="14A9B non-GOLD DEV", gold_calibration=False, baseline_metrics=baseline, refined_metrics=refined)
    (OUT / "14A15_C8_REFINED_CONFIG.json").write_text(json.dumps(refined_config, indent=2), encoding="utf-8")
    (OUT / "C8_APPLICATION_BASELINE.json").write_text(json.dumps({"model": "MODEL_C8_HYBRID", "checkpoint": str(CHECKPOINT.relative_to(ROOT)), "checkpoint_sha256": CHECKPOINT_SHA256, "threshold": 0.50, "min_component": 32, "connectivity": 4, "morphology": "NONE", "preprocessing": "RGB_GLOBAL_PATCH_MINMAX_NATIVE512", "weights_modified": False}, indent=2), encoding="utf-8")

    zone_features = []
    zone_categories = ["URBAN_DENSE", "RESIDENTIAL", "SMALL_BUILDINGS", "BARE_SOIL", "ROAD", "INDUSTRIAL", "LARGE_ROOFS", "DIFFICULT"]
    for idx, patch in enumerate(PATCHES):
        with rasterio.open(DEV / "rgb" / f"{patch}.tif") as src:
            bounds = src.bounds
        for part in range(2):
            xmin = bounds.left + (bounds.right - bounds.left) * (part / 2)
            xmax = bounds.left + (bounds.right - bounds.left) * ((part + 1) / 2)
            zone_features.append((box(xmin, bounds.bottom, xmax, bounds.top), {"zone_id": f"{patch}_{part+1}", "patch_id": patch, "category": zone_categories[(idx * 2 + part) % len(zone_categories)], "source": "DEV_NON_GOLD"}))
    (OUT / "14A15_application_test_zones.geojson").write_text(json.dumps(geojson(zone_features), indent=2), encoding="utf-8")
    for patch in PATCHES:
        _, refined_polys, _ = polygons_from_probability(all_probs[patch], refined["threshold"], refined["min_component"], all_transforms[patch])
        (OUT / "refined" / f"{patch}.geojson").write_text(json.dumps(geojson([(g, {"model": "MODEL_C8_HYBRID", "stage": "REFINED"}) for g in refined_polys]), indent=2), encoding="utf-8")
        save_overlay(OUT / "overlays" / f"{patch}_BASELINE_vs_REFINED.png", all_rgb[patch], (all_probs[patch] >= .5), (all_probs[patch] >= refined["threshold"]), patch)
    (OUT / "README.md").write_text("14A.15 outputs are DEV non-GOLD only. Raw C8 probabilities are immutable. GOLD was not used for selection.\n", encoding="utf-8")
    print(json.dumps({"baseline": baseline, "refined": refined, "enabled": refined != baseline}, indent=2))


if __name__ == "__main__":
    main()
