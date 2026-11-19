"""Prepare, validate, rasterize validated human labels, and create QA sheets.

No model predictions are read. Masks are written only for metadata status VALIDATED.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.features import rasterize
from shapely.geometry import shape, box
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
SPLITS = {"train": "TRAIN", "val": "VALIDATION", "test": "TEST"}
ALLOWED_STATUS = {"NOT_ANNOTATED", "IN_PROGRESS", "ANNOTATED", "VALIDATED"}
FIELDS = ["building_ref_id", "patch_id", "date", "source", "annotation_status", "annotator", "notes"]


def load_rows():
    rows = []
    for mp in sorted((DATA / "metadata").glob("*.json")):
        m = json.loads(mp.read_text(encoding="utf-8"))
        if "patch_id" not in m:
            continue
        m.setdefault("annotation_status", "NOT_ANNOTATED")
        m.setdefault("annotator", None)
        m.setdefault("building_count", None)
        m.setdefault("annotated_area_m2", None)
        m["geojson"] = f"annotations/{m['patch_id']}.geojson"
        gp = DATA / m["geojson"]
        if not gp.exists():
            fc = {
                "type": "FeatureCollection",
                "name": m["patch_id"],
                "crs": {"type": "name", "properties": {"name": m["crs"]}},
                "metadata": {"patch_id": m["patch_id"], "date": m["source_date"],
                             "source": m["source_raster"], "annotation_status": m["annotation_status"],
                             "annotator": None, "properties_schema": FIELDS,
                             "instructions": "Manual roof polygons only. No model predictions as labels."},
                "features": [],
            }
            gp.parent.mkdir(parents=True, exist_ok=True)
            gp.write_text(json.dumps(fc, indent=2) + "\n", encoding="utf-8")
        mp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        rows.append((mp, m))
    return rows


def feature_collection(meta):
    path = DATA / meta["geojson"]
    fc = json.loads(path.read_text(encoding="utf-8"))
    crs_name = fc.get("crs", {}).get("properties", {}).get("name")
    if not crs_name or rasterio.crs.CRS.from_string(crs_name) != rasterio.crs.CRS.from_string(meta["crs"]):
        raise ValueError(f"{meta['patch_id']}: GeoJSON CRS mismatch")
    return fc


def validate(rows):
    errors, global_ids, output = [], set(), {}
    spatial_splits, spatial_bounds = {}, []
    for mp, m in rows:
        patch_error_start = len(errors)
        pid = m["patch_id"]
        status = m["annotation_status"]
        if status not in ALLOWED_STATUS:
            errors.append(f"{pid}: unknown annotation_status {status}")
            continue
        img_path = DATA / m["image"]
        try:
            with rasterio.open(img_path) as im:
                if (im.width, im.height, im.count) != (512, 512, 3):
                    errors.append(f"{pid}: image dimensions/bands must be 512x512 RGB")
                if any(dtype != "uint8" for dtype in im.dtypes):
                    errors.append(f"{pid}: image must be uint8")
                if im.colorinterp[:3] != (rasterio.enums.ColorInterp.red, rasterio.enums.ColorInterp.green,
                                          rasterio.enums.ColorInterp.blue):
                    errors.append(f"{pid}: image bands are not marked RGB")
                if not im.crs or im.crs.to_string() != m["crs"]:
                    errors.append(f"{pid}: image CRS mismatch")
                if not np.allclose(im.bounds, m["bounds"], atol=1e-7):
                    errors.append(f"{pid}: image bounds mismatch")
                transform, width, height, crs, bounds = im.transform, im.width, im.height, im.crs, im.bounds
        except Exception as exc:
            errors.append(f"{pid}: image open/metadata failure: {exc}")
            continue
        try:
            fc = feature_collection(m)
        except Exception as exc:
            errors.append(str(exc))
            continue
        patch_box = box(*bounds)
        group = m.get("spatial_group", pid)
        previous_split = spatial_splits.setdefault(group, m["split"])
        if previous_split != m["split"]:
            errors.append(f"{pid}: same spatial group appears in multiple splits")
        spatial_bounds.append((pid, m["split"], patch_box))
        geometries = []
        for index, feature in enumerate(fc.get("features", [])):
            try:
                geom = shape(feature["geometry"])
                props = feature.get("properties") or {}
                ref = props.get("building_ref_id")
                required = ("building_ref_id", "patch_id", "date", "source", "annotation_status", "annotator")
                missing = [key for key in required if not props.get(key)]
                if missing:
                    errors.append(f"{pid}: feature {index} missing properties: {', '.join(missing)}")
                if geom.geom_type not in ("Polygon", "MultiPolygon"):
                    errors.append(f"{pid}: feature {index} is not Polygon/MultiPolygon")
                if geom.is_empty or not geom.is_valid or geom.area <= 0:
                    errors.append(f"{pid}: feature {index} is empty, invalid, or has zero area")
                if not patch_box.covers(geom):
                    errors.append(f"{pid}: feature {index} lies outside patch bounds")
                if not ref or ref in global_ids:
                    errors.append(f"{pid}: missing or duplicate building_ref_id on feature {index}")
                else:
                    global_ids.add(ref)
                if props.get("patch_id") != pid:
                    errors.append(f"{pid}: feature {index} patch_id mismatch")
                if props.get("date") != m["source_date"] or props.get("source") != m["source_raster"]:
                    errors.append(f"{pid}: feature {index} date/source metadata mismatch")
                if props.get("annotation_status") not in ALLOWED_STATUS or props.get("annotation_status") != status:
                    errors.append(f"{pid}: feature {index} annotation_status must match patch metadata")
                geometries.append(geom)
            except Exception as exc:
                errors.append(f"{pid}: malformed feature {index}: {exc}")
        if status in ("ANNOTATED", "VALIDATED") and not m.get("annotator"):
            errors.append(f"{pid}: {status} requires annotator in patch metadata")
        if status == "ANNOTATED" and not geometries:
            errors.append(f"{pid}: ANNOTATED requires at least one building; use VALIDATED for reviewed empty patches")
        if status == "VALIDATED" and len(errors) == patch_error_start:
            if not m.get("annotator"):
                errors.append(f"{pid}: VALIDATED requires annotator/reviewer")
            masks = [(geom, 1) for geom in geometries]
            array = rasterize(masks, out_shape=(height, width), transform=transform,
                              fill=0, all_touched=False, dtype="uint8")
            mask_path = DATA / "masks" / f"{pid}.tif"
            with rasterio.open(img_path) as im:
                profile = im.profile.copy()
            profile.update(driver="GTiff", count=1, dtype="uint8", nodata=None,
                           compress="deflate", predictor=2)
            mask_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(mask_path, "w", **profile) as dst:
                dst.write(array, 1)
                dst.set_band_description(1, "binary_building_mask (0=background, 1=building)")
            area = float(unary_union(geometries).area) if geometries else 0.0
            m["mask"] = f"masks/{pid}.tif"
            m["building_count"] = len(geometries)
            m["annotated_area_m2"] = area
            with rasterio.open(mask_path) as mask, rasterio.open(img_path) as im:
                if (mask.width, mask.height) != (im.width, im.height) or mask.crs != im.crs or mask.transform != im.transform:
                    errors.append(f"{pid}: generated mask/image alignment mismatch")
                if not set(np.unique(mask.read(1)).tolist()).issubset({0, 1}):
                    errors.append(f"{pid}: generated mask is not binary")
        elif status == "VALIDATED":
            m["mask"] = None
        else:
            m["mask"] = None
            m["building_count"] = len(geometries) if status == "ANNOTATED" else None
            m["annotated_area_m2"] = float(unary_union(geometries).area) if geometries else None
        fc.setdefault("metadata", {})["annotation_status"] = status
        fc["metadata"]["annotator"] = m.get("annotator")
        (DATA / m["geojson"]).write_text(json.dumps(fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        mp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        output[pid] = {"meta": m, "transform": transform, "crs": crs, "geometries": geometries}
    for i, (pid, split, a) in enumerate(spatial_bounds):
        for pid2, split2, b in spatial_bounds[i + 1:]:
            if split != split2 and a.intersection(b).area > 0:
                errors.append(f"spatial overlap across splits: {pid} / {pid2}")
    return errors, output


def write_index(rows):
    path = DATA / "metadata/patch_index.csv"
    fields = ["filename", "patch_id", "width", "height", "bands", "dtype", "CRS", "transform", "bounds", "split",
              "source_raster", "source_date", "resolution", "annotation_status", "annotator", "building_count", "annotated_area_m2"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for _, m in rows:
            with rasterio.open(DATA / m["image"]) as ds:
                writer.writerow({"filename": Path(m["image"]).name, "patch_id": m["patch_id"], "width": ds.width,
                                 "height": ds.height, "bands": ds.count, "dtype": ",".join(ds.dtypes),
                                 "CRS": ds.crs.to_string(), "transform": ";".join(map(str, ds.transform[:6])),
                                 "bounds": ";".join(map(str, ds.bounds)),
                                 "split": m["split"], "source_raster": m["source_raster"],
                                 "source_date": m["source_date"], "resolution": m["resolution"],
                                 "annotation_status": m["annotation_status"], "annotator": m.get("annotator"),
                                 "building_count": m.get("building_count"), "annotated_area_m2": m.get("annotated_area_m2")})
    return path


def contact_sheets(output):
    qa = DATA / "metadata/visual_qa_13k1"
    qa.mkdir(parents=True, exist_ok=True)
    for split, title in SPLITS.items():
        records = [x for x in output.values() if x["meta"]["split"] == split]
        cell_w, cell_h, top_h, label_h = 180, 180, 28, 38
        page = Image.new("RGB", (cell_w * 3, top_h + len(records) * (cell_h + label_h)), "white")
        draw = ImageDraw.Draw(page)
        draw.text((4, 8), "RGB image", fill="black")
        draw.text((cell_w + 4, 8), "Human annotation", fill="black")
        draw.text((2 * cell_w + 4, 8), "Validated mask overlay", fill="black")
        for row, record in enumerate(sorted(records, key=lambda x: x["meta"]["patch_id"])):
            m, transform, geometries = record["meta"], record["transform"], record["geometries"]
            y = top_h + row * (cell_h + label_h)
            with rasterio.open(DATA / m["image"]) as ds:
                rgb = np.moveaxis(ds.read((1, 2, 3)), 0, -1)
            im = Image.fromarray(rgb).resize((cell_w, cell_h))
            page.paste(im, (0, y))
            ann = im.copy()
            if geometries:
                arr = rasterize([(g, 1) for g in geometries], out_shape=(512, 512), transform=transform,
                                fill=0, all_touched=False, dtype="uint8")
                overlay = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
                overlay.putdata([(255, 50, 40, 100 if v else 0) for v in arr.reshape(-1)])
                ann = Image.alpha_composite(Image.fromarray(rgb).convert("RGBA"), overlay).convert("RGB").resize((cell_w, cell_h))
            page.paste(ann, (cell_w, y))
            mask_image = im.copy()
            mask_path = DATA / m["mask"] if m.get("mask") else None
            if mask_path and mask_path.exists():
                with rasterio.open(mask_path) as ds:
                    arr = ds.read(1)
                overlay = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
                overlay.putdata([(0, 255, 70, 110 if v else 0) for v in arr.reshape(-1)])
                mask_image = Image.alpha_composite(Image.fromarray(rgb).convert("RGBA"), overlay).convert("RGB").resize((cell_w, cell_h))
            page.paste(mask_image, (2 * cell_w, y))
            draw.text((4, y + cell_h + 3), f"{m['patch_id']} | {m['annotation_status']}", fill="black")
        page.save(qa / f"{split}_annotation_mask_contact_sheet.jpg", quality=92)


def main():
    global DATA
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, default=DATA)
    args = ap.parse_args()
    DATA = args.dataset.resolve()
    rows = load_rows()
    index_path = write_index(rows)
    errors, output = validate(rows)
    contact_sheets(output)
    statuses = {status: sum(m["annotation_status"] == status for _, m in rows) for status in ALLOWED_STATUS}
    # Default mode still emits masks for VALIDATED items; the explicit switch is a clear opt-in.
    # Validation never synthesizes an empty label for an unreviewed patch.
    summary = {"patches": len(rows), "statuses": statuses, "validated_patches": statuses["VALIDATED"],
               "masks": sum(1 for _, m in rows if m.get("mask")), "index": str(index_path),
               "geojson_validation": "FAILED" if errors else "VALIDATED",
               "spatial_leakage": "YES" if any("spatial" in e for e in errors) else "NO", "errors": errors,
               "ready_for_fine_tuning": len(rows) == 16 and statuses["VALIDATED"] == 16 and not errors and all(m.get("mask") for _, m in rows)}
    (DATA / "metadata/annotation_validation_report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
