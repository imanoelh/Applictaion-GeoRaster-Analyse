"""Exploratory C/D hybrid benchmark for the locked six-patch 13M TEST set.

Uses archived 13M1B predictions only. Never writes to source imagery, archived
model outputs, the human ground-truth GeoPackage, or production configuration.
Run with the QGIS Python environment (GDAL/OGR, NumPy, SciPy, Pillow).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr
from PIL import Image, ImageDraw
from scipy import ndimage

gdal.UseExceptions()
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test"
ARCH = ROOT / "backend/data/models/building/experimental/benchmark_13M1B/outputs"
OUT = ROOT / "backend/data/models/building/experimental/benchmark_13N/outputs"
PATCHES = [
    "GT_2024_difficult_02", "GT_2024_industrial_02", "GT_2024_residential_02",
    "GT_2025_difficult_02", "GT_2025_industrial_02", "GT_2025_residential_02",
]
VARIANTS = ["MODEL_C_ONLY", "MODEL_D_ONLY", "HYBRID_UNION", "HYBRID_INTERSECTION",
            "FUSION_50_50", "FUSION_C25_D75", "FUSION_C75_D25",
            "HYBRID_D_OBJECT_COVERAGE", "HYBRID_C_BOUNDARY_D_COVERAGE"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def raster(path):
    ds = gdal.Open(str(path))
    if ds is None:
        raise RuntimeError(f"Cannot open {path}")
    return ds, ds.ReadAsArray(), (ds.RasterXSize, ds.RasterYSize, ds.GetProjection(), ds.GetGeoTransform())


def same_grid(a, b):
    return a[0:2] == b[0:2] and a[2] == b[2] and np.allclose(a[3], b[3], rtol=0, atol=1e-9)


def write_mask(path, arr, ref_ds):
    path.parent.mkdir(parents=True, exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), ref_ds.RasterXSize, ref_ds.RasterYSize, 1, gdal.GDT_Byte,
                       options=["COMPRESS=DEFLATE", "PREDICTOR=2"])
    ds.SetGeoTransform(ref_ds.GetGeoTransform()); ds.SetProjection(ref_ds.GetProjection())
    b = ds.GetRasterBand(1); b.WriteArray(arr.astype(np.uint8)); b.SetNoDataValue(0); b.FlushCache()
    ds.FlushCache(); ds = None


def components(mask):
    labels, n = ndimage.label(mask.astype(bool), structure=np.ones((3, 3), np.uint8))
    return labels, int(n)


def pixel_metrics(pred, gt):
    p, g = pred.astype(bool), gt.astype(bool)
    tp = int(np.count_nonzero(p & g)); fp = int(np.count_nonzero(p & ~g)); fn = int(np.count_nonzero(~p & g))
    iou = tp / (tp + fp + fn) if tp + fp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    dice = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0
    return {"iou": iou, "dice": dice, "precision": precision, "recall": recall, "f1": dice,
            "tp": tp, "fp": fp, "fn": fn, "tn": int(p.size - tp - fp - fn)}


def boundaries(mask):
    mask = mask.astype(bool)
    return mask & ~ndimage.binary_erosion(mask, structure=np.ones((3, 3)), border_value=0)


def boundary_metrics(pred, gt):
    pb, gb = boundaries(pred), boundaries(gt)
    if not pb.any() or not gb.any():
        return 0.0, float("nan")
    dg = ndimage.distance_transform_edt(~gb); dp = ndimage.distance_transform_edt(~pb)
    p_recall = float(np.mean(dg[pb] <= 1.0)); g_recall = float(np.mean(dp[gb] <= 1.0))
    bf1 = 2 * p_recall * g_recall / (p_recall + g_recall) if p_recall + g_recall else 0.0
    mbd = float((np.mean(dg[pb]) + np.mean(dp[gb])) / 2)
    return bf1, mbd


def gt_feature_masks(gpkg, patch_id, ref_ds):
    src = ogr.Open(str(gpkg), 0)
    layer_name = patch_id + "_ground_truth"
    layer = src.GetLayerByName(layer_name)
    if layer is None:
        raise RuntimeError(f"Cannot find repaired GT layer {layer_name}")
    fields = [layer.GetLayerDefn().GetFieldDefn(i).GetName() for i in range(layer.GetLayerDefn().GetFieldCount())]
    georef = ref_ds.GetGeoTransform(); proj = ref_ds.GetProjection()
    srs = osr.SpatialReference(); srs.ImportFromWkt(proj)
    features = []
    mem_drv = ogr.GetDriverByName("Memory")
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is None or geom.IsEmpty():
            continue
        mds = gdal.GetDriverByName("MEM").Create("", ref_ds.RasterXSize, ref_ds.RasterYSize, 1, gdal.GDT_Byte)
        mds.SetGeoTransform(georef); mds.SetProjection(proj); mds.GetRasterBand(1).Fill(0)
        vds = mem_drv.CreateDataSource(""); vl = vds.CreateLayer("gt", srs=srs, geom_type=ogr.wkbUnknown)
        vf = ogr.Feature(vl.GetLayerDefn()); vf.SetGeometry(geom.Clone()); vl.CreateFeature(vf)
        gdal.RasterizeLayer(mds, [1], vl, burn_values=[1])
        fm = mds.GetRasterBand(1).ReadAsArray().astype(bool)
        if fm.any(): features.append(fm)
        vf = None; vl = None; vds = None; mds = None
    src = None
    return features


def match_components(cmask, dmask, threshold=0.10):
    cl, nc = components(cmask); dl, nd = components(dmask)
    # Single documented rule, greedy one-to-one by descending pixel IoU.
    pairs = []
    for di in range(1, nd + 1):
        dm = dl == di
        touched, counts = np.unique(cl[dm], return_counts=True)
        for ci, inter in zip(touched.tolist(), counts.tolist()):
            if ci == 0: continue
            union = int(dm.sum()) + int((cl == ci).sum()) - inter
            iou = inter / union if union else 0.0
            if iou > threshold:
                pairs.append((iou, ci, di))
    used_c, used_d, matched = set(), set(), {}
    for iou, ci, di in sorted(pairs, reverse=True):
        if ci not in used_c and di not in used_d:
            used_c.add(ci); used_d.add(di); matched[di] = ci
    return cl, dl, matched


def object_metrics(pred, gt_features):
    labels, n = components(pred)
    pairs = []
    for gi, gm in enumerate(gt_features):
        touched, counts = np.unique(labels[gm], return_counts=True)
        for pi, inter in zip(touched.tolist(), counts.tolist()):
            if pi == 0: continue
            pm = labels == pi
            union = int(gm.sum()) + int(pm.sum()) - int(inter)
            iou = inter / union if union else 0.0
            if iou >= 0.50: pairs.append((iou, gi, pi))
    ug, up, detected = set(), set(), 0
    for iou, gi, pi in sorted(pairs, reverse=True):
        if gi not in ug and pi not in up:
            ug.add(gi); up.add(pi); detected += 1
    return {"gt_buildings": len(gt_features), "predicted_components": n,
            "detected_gt_objects": detected, "missed_gt_objects": len(gt_features) - detected,
            "extra_components": n - len(up)}


def rgb_image(arr):
    rgb = np.moveaxis(arr[:3], 0, -1).astype(np.uint8)
    return Image.fromarray(rgb, "RGB")


def render_mask(rgb, mask, color=(255, 0, 0), alpha=100):
    base = rgb.convert("RGBA"); ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ar = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
    ar[mask.astype(bool)] = (*color, alpha)
    ov = Image.fromarray(ar, "RGBA")
    return Image.alpha_composite(base, ov).convert("RGB")


def main():
    manifest = json.loads((BASE / "metadata/manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((ARCH / "benchmark_provenance.json").read_text(encoding="utf-8"))
    if provenance.get("fresh_inference_performed") is not False:
        raise RuntimeError("Unexpected archive provenance: must reuse earlier outputs")
    checks, loaded = [], {}
    for pid in PATCHES:
        entry = next(x for x in manifest["patches"] if x["patch_id"] == pid)
        ipath = BASE / "images" / f"{pid}.tif"
        src_path = ROOT / "backend/data/fine_tuning/buildings/maxar_v1/images" / f"{pid}.tif"
        ids, rgb, grid = raster(ipath); ssha = sha(ipath)
        if ssha != entry["source_image_sha256"] or sha(src_path) != ssha:
            raise RuntimeError(f"{pid}: source SHA mismatch; stopping before fusion")
        item = {"patch_id": pid, "source_sha256": ssha, "shape": [ids.RasterYSize, ids.RasterXSize],
                "projection": grid[2], "geotransform": list(grid[3]), "grid_verified": True}
        for model, pband in (("model_c", 1), ("model_d", 2)):
            for kind in ("probability", "binary"):
                path = ARCH / model / kind / f"{pid}.tif"
                ds, a, g = raster(path)
                if not same_grid(grid, g): raise RuntimeError(f"{pid} {model}/{kind}: grid mismatch")
                if kind == "probability":
                    if a.ndim == 3:
                        if a.shape[0] < pband: raise RuntimeError(f"{pid}: missing probability class band {pband}")
                        a = a[pband - 1]
                    a = a.astype(np.float32)
                    if not np.isfinite(a).all() or a.min() < -1e-6 or a.max() > 1.000001:
                        raise RuntimeError(f"{pid} {model}: probabilities outside [0,1]")
                else:
                    if a.ndim == 3: a = a[0]
                    if not set(np.unique(a).tolist()).issubset({0, 1}):
                        raise RuntimeError(f"{pid} {model}: non-binary mask values")
                    a = a.astype(np.uint8)
                loaded.setdefault(pid, {}).setdefault(model, {})[kind] = a
                item[f"{model}_{kind}_grid_verified"] = True
            if not np.array_equal(loaded[pid][model]["binary"],
                                  (loaded[pid][model]["probability"] >= 0.5).astype(np.uint8)):
                raise RuntimeError(f"{pid} {model}: probability threshold does not reproduce archived binary mask")
        checks.append(item)

    # Archive validation passed: derived products go to an isolated new directory.
    for folder in ("masks", "overlays", "variants", "comparison"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    repaired = ARCH / "ground_truth/ground_truth_benchmark_repaired.gpkg"
    if not repaired.exists(): raise RuntimeError("Missing repaired evaluation Ground Truth")
    summary, per_patch, obj_csv, fusion_seconds = {}, [], [], 0.0
    component_csv = []
    best_candidates = ["HYBRID_INTERSECTION", "FUSION_C25_D75", "FUSION_50_50", "FUSION_C75_D25",
                       "HYBRID_C_BOUNDARY_D_COVERAGE", "HYBRID_D_OBJECT_COVERAGE", "HYBRID_UNION"]
    for pid in PATCHES:
        img_ds, rgb_arr, _ = raster(BASE / "images" / f"{pid}.tif")
        c = loaded[pid]["model_c"]["binary"].astype(bool); d = loaded[pid]["model_d"]["binary"].astype(bool)
        cp = loaded[pid]["model_c"]["probability"]; dp = loaded[pid]["model_d"]["probability"]
        gt_ds, gt_arr, _ = raster(ARCH / "ground_truth/masks" / f"{pid}.tif")
        if gt_arr.ndim == 3: gt_arr = gt_arr[0]
        gt = gt_arr.astype(bool)
        gtf = gt_feature_masks(repaired, pid, img_ds)
        cl, dl, matched = match_components(c, d, 0.10)
        # D-primary candidate/component bookkeeping; all D-only objects remain.
        d_cov = np.zeros_like(d, dtype=bool)
        c_bound = np.zeros_like(d, dtype=bool)
        for di in range(1, int(dl.max()) + 1):
            dm = dl == di
            ci = matched.get(di)
            d_cov |= dm
            if ci is not None:
                c_bound |= (cl == ci)
            else:
                c_bound |= dm
            points = np.argwhere(dm)
            cy, cx = points.mean(axis=0) if len(points) else (float("nan"), float("nan"))
            dist = float("nan")
            if ci is not None:
                cpts = np.argwhere(cl == ci)
                dist = float(np.sqrt(((cpts.mean(axis=0) - np.array([cy, cx])) ** 2).sum()))
            scores = dp[dm]
            component_csv.append({"patch_id": pid, "model_d_component_id": di,
                "classification": "SUPPORTED_BY_C" if ci is not None else "D_ONLY",
                "matched_model_c_component_id": ci or "", "matched_component_iou_gt_0_10": next((x[0] for x in []), ""),
                "area_pixels": int(dm.sum()), "mean_probability_d": float(scores.mean()),
                "max_probability_d": float(scores.max()), "centroid_distance_to_matched_c_px": dist})
        # record matching IoU and component label counts for the CSV.
        for row in component_csv:
            if row["patch_id"] == pid and row["matched_model_c_component_id"]:
                ci = row["matched_model_c_component_id"]; di = row["model_d_component_id"]
                inter = int(np.count_nonzero((cl == ci) & (dl == di)))
                row["matched_component_iou_gt_0_10"] = inter / (int(np.count_nonzero(cl == ci)) + int(np.count_nonzero(dl == di)) - inter)
        variants = {
            "MODEL_C_ONLY": c,
            "MODEL_D_ONLY": d,
            "HYBRID_UNION": c | d,
            "HYBRID_INTERSECTION": c & d,
        }
        t0 = time.perf_counter()
        for name, wc in (("FUSION_50_50", .50), ("FUSION_C25_D75", .25), ("FUSION_C75_D25", .75)):
            variants[name] = (wc * cp + (1.0 - wc) * dp) >= .50
        variants["HYBRID_D_OBJECT_COVERAGE"] = d_cov
        variants["HYBRID_C_BOUNDARY_D_COVERAGE"] = c_bound
        fusion_seconds += time.perf_counter() - t0
        for name, mask in variants.items():
            write_mask(OUT / "masks" / name / f"{pid}.tif", mask.astype(np.uint8), img_ds)
            for j in range(1, 4):
                (OUT / "masks" / name).mkdir(parents=True, exist_ok=True)
            pm = pixel_metrics(mask, gt); bf1, mbd = boundary_metrics(mask, gt); om = object_metrics(mask, gtf)
            row = {"patch_id": pid, "variant": name, **pm, "boundary_f1_1px": bf1,
                   "mean_boundary_distance_px": mbd, "component_count_8conn": components(mask)[1], **om}
            per_patch.append(row)
            if name not in summary: summary[name] = {k: 0 for k in ("tp", "fp", "fn", "tn")}
            for k in ("tp", "fp", "fn", "tn"): summary[name][k] += pm[k]
            summary[name].setdefault("detected_gt_objects", 0); summary[name]["detected_gt_objects"] += om["detected_gt_objects"]
            summary[name].setdefault("missed_gt_objects", 0); summary[name]["missed_gt_objects"] += om["missed_gt_objects"]
            summary[name].setdefault("extra_components", 0); summary[name]["extra_components"] += om["extra_components"]
            summary[name].setdefault("components", 0); summary[name]["components"] += row["component_count_8conn"]
            summary[name].setdefault("boundary_f1_sum", 0.0); summary[name]["boundary_f1_sum"] += bf1
            summary[name].setdefault("mbd_sum", 0.0); summary[name]["mbd_sum"] += mbd
            # individual overlays; RGB plus candidate contour (red).
            ov = render_mask(rgb_image(rgb_arr), mask, (255, 30, 30), 115)
            ov.save(OUT / "overlays" / f"{pid}_{name}.png")
        obj_csv.append({"patch_id": pid, "gt_features": len(gtf),
                        "model_c_components": int(cl.max()), "model_d_components": int(dl.max()),
                        "cd_matched_pairs_iou_gt_0_10": len(matched),
                        "d_supported_by_c": len(matched), "d_only_kept": int(dl.max()) - len(matched)})
        img_ds = gt_ds = None
    for name, x in summary.items():
        tp, fp, fn = x["tp"], x["fp"], x["fn"]
        x.update({"iou": tp / (tp + fp + fn) if tp + fp + fn else 1,
                  "dice": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1,
                  "precision": tp/(tp+fp) if tp+fp else 0,
                  "recall": tp/(tp+fn) if tp+fn else 0,
                  "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1,
                  "boundary_f1_1px_macro": x.pop("boundary_f1_sum") / 6,
                  "mean_boundary_distance_px_macro": x.pop("mbd_sum") / 6,
                  "mean_components_per_patch": x["components"] / 6})
    # A best hybrid must reach D IoU and improve D precision or clearly reduce extra components.
    dmet = summary["MODEL_D_ONLY"]
    eligible = [n for n in best_candidates if summary[n]["iou"] >= dmet["iou"] and
                (summary[n]["precision"] > dmet["precision"] or summary[n]["extra_components"] < dmet["extra_components"])]
    # If none meets success criteria, report the strongest hybrid IoU without implying a win.
    best = max(eligible, key=lambda n: (summary[n]["iou"], summary[n]["precision"], -summary[n]["extra_components"])) if eligible else max(best_candidates, key=lambda n: (summary[n]["iou"], summary[n]["precision"], -summary[n]["extra_components"]))
    # Polygonize the selected experimental mask only; archived C/D GeoJSON files remain untouched.
    poly_dir = OUT / "polygons" / best
    poly_dir.mkdir(parents=True, exist_ok=True)
    for pid in PATCHES:
        mask_ds = gdal.Open(str(OUT / "masks" / best / f"{pid}.tif"))
        drv = ogr.GetDriverByName("GeoJSON")
        poly_path = poly_dir / f"{pid}.geojson"
        if poly_path.exists(): poly_path.unlink()
        vds = drv.CreateDataSource(str(poly_path))
        srs = osr.SpatialReference(); srs.ImportFromWkt(mask_ds.GetProjection())
        layer = vds.CreateLayer("buildings", srs=srs, geom_type=ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn("value", ogr.OFTInteger))
        gdal.Polygonize(mask_ds.GetRasterBand(1), mask_ds.GetRasterBand(1), layer, 0, [], callback=None)
        vds = None; mask_ds = None
    # Save grid provenance and derived metrics.
    (OUT / "grid_validation.json").write_text(json.dumps({"patches": checks, "archive_provenance": provenance,
        "validation": "PASS; all source hashes and grids match; C/D archived binary masks reproduce from probability >= 0.5",
        "d_probability_band": 2, "matching_rule": "Greedy one-to-one component matching, IoU > 0.10"}, indent=2), encoding="utf-8")
    (OUT / "metrics_summary.json").write_text(json.dumps({"evaluation":"APPROXIMATE / ENGINEERING ONLY",
        "threshold":0.5,"matching_rule":"greedy one-to-one MODEL_C/MODEL_D 8-connected component IoU > 0.10; GT object match IoU >=0.50",
        "variants":summary,"best_hybrid":best,"best_hybrid_meets_success_criteria":best in eligible,
        "fusion_postprocess_seconds_total":fusion_seconds,"fusion_postprocess_seconds_per_patch":fusion_seconds/6,
        "timing_scope":"construction of the three weighted probability masks and hybrid boolean arrays; excludes C/D component matching, image/model inference, raster I/O and output rendering",
        "archived_inference_estimate":{"model_c_seconds":19.085338899982162,"model_d_geoai_seconds":18.784773399995174,
        "combined_plus_measured_fusion_seconds":19.085338899982162+18.784773399995174+fusion_seconds,
        "note":"Separate archived timer scopes; estimate indicates two passes are slower than one model."}}, indent=2), encoding="utf-8")
    for fname, rows in (("metrics_per_patch.csv", per_patch), ("object_matching_summary.csv", obj_csv),
                        ("d_component_classification.csv", component_csv)):
        with open(OUT / fname, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    # Contact sheet: RGB, approximate GT, C, D, best hybrid.
    cols = ["RGB", "GT APPROX", "MODEL C", "MODEL D", best]
    thumb = 256; margin = 14; title_h = 28
    sheet = Image.new("RGB", (margin + len(cols)*(thumb+margin), margin + len(PATCHES)*(thumb+title_h+margin)), "white")
    draw = ImageDraw.Draw(sheet)
    for r, pid in enumerate(PATCHES):
        y = margin + r*(thumb+title_h+margin)
        rgbds, rgbarr, _ = raster(BASE / "images" / f"{pid}.tif")
        masks = {"GT APPROX": raster(ARCH / "ground_truth/masks" / f"{pid}.tif")[1],
                 "MODEL C": loaded[pid]["model_c"]["binary"], "MODEL D": loaded[pid]["model_d"]["binary"],
                 best: np.asarray(gdal.Open(str(OUT/"masks"/best/f"{pid}.tif")).ReadAsArray())}
        if masks["GT APPROX"].ndim == 3: masks["GT APPROX"] = masks["GT APPROX"][0]
        imgs = {"RGB": rgb_image(rgbarr)}
        for col, color in (("GT APPROX", (255,0,0)), ("MODEL C", (0,220,50)), ("MODEL D", (0,100,255)), (best,(255,30,30))):
            imgs[col] = render_mask(imgs.get("RGB", rgb_image(rgbarr)), masks[col], color, 125)
        for c, name in enumerate(cols):
            x = margin + c*(thumb+margin); tile = imgs[name].resize((thumb,thumb), Image.Resampling.NEAREST)
            sheet.paste(tile, (x,y+title_h)); draw.text((x,y), f"{pid} | {name}", fill="black")
        rgbds = None
    sheet.save(OUT / "comparison/contact_sheet_13N.png")
    # Overlay panel with all masks and each candidate model visible distinctly.
    legend_h = 42
    overlays = Image.new("RGB", (3*thumb+4*margin, legend_h + 2*(thumb+title_h+margin)), "white")
    draw = ImageDraw.Draw(overlays)
    draw.text((margin, 10), "Overlay colors: approximate GT = red | MODEL_C = green | MODEL_D = blue | best hybrid = yellow", fill="black")
    for i,pid in enumerate(PATCHES):
        r,c = divmod(i,3); x=margin+c*(thumb+margin); y=legend_h+margin+r*(thumb+title_h+margin)
        rgbds, rgbarr, _ = raster(BASE / "images" / f"{pid}.tif")
        canvas=rgb_image(rgbarr).convert("RGBA")
        for m,color in ((raster(ARCH/"ground_truth/masks"/f"{pid}.tif")[1],(255,0,0)),
                        (loaded[pid]["model_c"]["binary"],(0,255,0)),(loaded[pid]["model_d"]["binary"],(0,100,255)),
                        (np.asarray(gdal.Open(str(OUT/"masks"/best/f"{pid}.tif")).ReadAsArray()),(255,255,0))):
            if m.ndim==3: m=m[0]
            ar=np.zeros((512,512,4),np.uint8); ar[m.astype(bool)]=(*color,80); canvas=Image.alpha_composite(canvas,Image.fromarray(ar,"RGBA"))
        overlays.paste(canvas.convert("RGB").resize((thumb,thumb),Image.Resampling.NEAREST),(x,y+title_h))
        draw.text((x,y),pid,fill="black"); rgbds=None
    overlays.save(OUT/"comparison/contact_sheet_13N_overlays.png")
    (OUT/"comparison/best_hybrid.txt").write_text(best+"\n",encoding="utf-8")
    print(json.dumps({"output":str(OUT),"best_hybrid":best,"eligible_hybrids":eligible,
                      "fusion_seconds":fusion_seconds,"variants":summary},indent=2))


if __name__ == "__main__": main()
