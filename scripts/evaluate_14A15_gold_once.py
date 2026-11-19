"""One-shot post-freeze GOLD check for 14A.15; never selects parameters."""
from __future__ import annotations
import csv, json, os, sqlite3
import sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import shapes, rasterize
from rasterio.warp import transform_geom
from shapely.geometry import shape, mapping
from shapely import wkb
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_14A15_c8_refinement import BASE, C8, OUT, CHECKPOINT_SHA256, PATCHES, connected_components, metrics, polygons_from_probability, read_gt

ROOT = Path(__file__).resolve().parents[1]
GOLD = BASE / "14A7_gold_set/gt/14A7_GOLD_SET_GT_FIXED.gpkg"
GOLD_PATCHES = [
    "14A7_VAL_2025_RESIDENTIAL_02", "14A7_VAL_2025_DENSE_04",
    "14A7_VAL_2025_INDUSTRIAL_10", "14A7_VAL_2025_DIFFICULT_11",
]


def load_gt(patch):
    with sqlite3.connect(GOLD) as db:
        rows = []
        for (blob,) in db.execute('SELECT geom FROM buildings_gt WHERE patch_id = ?', (patch,)):
            flags = blob[3]; env = (flags >> 1) & 7
            rows.append(wkb.loads(blob[8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(env, 0):]))
    return rows


def boundary_f1(pred_mask: np.ndarray, gt_mask: np.ndarray) -> float:
    def boundary(mask):
        up = np.zeros_like(mask); up[1:] = mask[:-1]
        down = np.zeros_like(mask); down[:-1] = mask[1:]
        left = np.zeros_like(mask); left[:, 1:] = mask[:, :-1]
        right = np.zeros_like(mask); right[:, :-1] = mask[:, 1:]
        return mask & ~(up & down & left & right)
    def dilate(mask):
        out = mask.copy()
        out[1:] |= mask[:-1]; out[:-1] |= mask[1:]
        out[:, 1:] |= mask[:, :-1]; out[:, :-1] |= mask[:, 1:]
        return out
    pb, gb = boundary(pred_mask), boundary(gt_mask)
    p = float((pb & dilate(gb)).sum()) / max(1, int(pb.sum()))
    r = float((gb & dilate(pb)).sum()) / max(1, int(gb.sum()))
    return 2 * p * r / (p + r) if p + r else 0.0


def main():
    config = json.loads((OUT / "14A15_C8_REFINED_CONFIG.json").read_text(encoding="utf-8"))
    threshold = float(config["threshold"]); minimum = int(config["min_component"])
    rows=[]; total={"TP":0,"FP":0,"FN":0,"GT":0,"PRED":0,"small_gt":0,"small_tp":0}; boundary_scores=[]
    for patch in GOLD_PATCHES:
        with rasterio.open(BASE / "14A7_validation_expansion/rgb" / f"{patch}.tif") as src:
            transform = src.transform
        with np.load(C8 / "gold_evaluation" / f"{patch}.npz") as z:
            prob = z["probability"]
        native_gt = load_gt(patch)
        gt = [shape(transform_geom("EPSG:32637", "EPSG:4326", mapping(g), precision=12)) for g in native_gt]
        _, pred, _ = polygons_from_probability(prob, threshold, minimum, transform)
        m = metrics(gt, pred)
        matched_small = sum(1 for gi, _pi, _iou in m["matched"] if native_gt[gi].area <= 50.0)
        m["small_gt"] = sum(1 for geometry in native_gt if geometry.area <= 50.0)
        m["small_tp"] = matched_small
        pred_mask = (prob >= threshold)
        gt_mask = rasterize([(mapping(g), 1) for g in gt], out_shape=pred_mask.shape, transform=transform, fill=0, dtype="uint8").astype(bool)
        boundary_scores.append(boundary_f1(pred_mask, gt_mask))
        for key in total: total[key] += m[key]
        for gi, pi, iou in m["matched"]:
            rows.append({"patch_id":patch,"gt_id":gi,"prediction_id":pi,"iou":iou,"matched":True})
        matched_gt={x[0] for x in m["matched"]}
        rows.extend({"patch_id":patch,"gt_id":gi,"prediction_id":"","iou":0.0,"matched":False} for gi in range(len(gt)) if gi not in matched_gt)
    tp,fp,fn=total["TP"],total["FP"],total["FN"]
    precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
    result={"model":"MODEL_C8_HYBRID","weights_modified":False,"gold_used_for_selection":False,"gold_attempts":1,"threshold":threshold,"min_component":minimum,**total,"object_precision":precision,"object_recall":recall,"object_f1":2*precision*recall/(precision+recall) if precision+recall else 0.0,"small_recall":total["small_tp"]/total["small_gt"] if total["small_gt"] else 0.0,"boundary_f1":float(np.mean(boundary_scores)),"baseline_f1":0.421875,"baseline_precision":0.5934065934065934,"baseline_recall":0.32727272727272727,"baseline_fp":37,"baseline_small_recall":3/38,"baseline_boundary_f1":0.33643356301335414}
    (OUT/"GOLD_ONE_SHOT_RESULT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    with (OUT/"GOLD_ONE_SHOT_MATCHING.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result,indent=2))

if __name__ == "__main__": main()
