"""Prepare a locked, prediction-free 6-patch test annotation package.

Copies the existing Maxar TEST images byte-for-byte. It never reads model outputs,
never modifies the source annotations/metadata, and never writes any labels or masks.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path

# Prefer the backend venv's bundled spatial databases for this process only.
# The machine currently exposes an incompatible PostgreSQL PROJ database.
ROOT = Path(__file__).resolve().parents[1]
VENV_SPATIAL = ROOT / "backend/.venv/Lib/site-packages/rasterio"
if (VENV_SPATIAL / "proj_data/proj.db").is_file():
    os.environ["PROJ_LIB"] = str(VENV_SPATIAL / "proj_data")
    os.environ["PROJ_DATA"] = str(VENV_SPATIAL / "proj_data")
if (VENV_SPATIAL / "gdal_data").is_dir():
    os.environ["GDAL_DATA"] = str(VENV_SPATIAL / "gdal_data")

import rasterio
from PIL import Image, ImageDraw

SOURCE = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
DEST = SOURCE / "benchmark_13M_test"
EXPECTED_TEST_IDS = {
    "GT_2024_difficult_02", "GT_2024_industrial_02", "GT_2024_residential_02",
    "GT_2025_difficult_02", "GT_2025_industrial_02", "GT_2025_residential_02",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def main() -> int:
    with (SOURCE / "metadata/patch_index.csv").open(encoding="utf-8-sig", newline="") as f:
        records = {r["patch_id"]: r for r in csv.DictReader(f) if r["split"] == "test"}
    actual = set(records)
    if actual != EXPECTED_TEST_IDS:
        raise RuntimeError(f"TEST set changed: expected {sorted(EXPECTED_TEST_IDS)}, got {sorted(actual)}")
    if (DEST / "metadata/manifest.json").exists():
        raise RuntimeError(f"Refusing to overwrite existing annotation package: {DEST}")

    for sub in ("images", "annotations", "metadata", "overlays", "qgis"):
        (DEST / sub).mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    contact_items = []
    for patch_id in sorted(EXPECTED_TEST_IDS):
        row = records[patch_id]
        source_meta_path = SOURCE / "metadata" / f"{patch_id}.json"
        source_meta = json.loads(source_meta_path.read_text(encoding="utf-8"))
        if source_meta.get("split") != "test" or source_meta.get("annotation_status") != "NOT_ANNOTATED":
            raise RuntimeError(f"{patch_id} must still be an unannotated TEST patch")
        original = SOURCE / source_meta["image"]
        image_out = DEST / "images" / f"{patch_id}.tif"
        shutil.copyfile(original, image_out)
        source_sha, copied_sha = sha256(original), sha256(image_out)
        if source_sha != copied_sha:
            raise RuntimeError(f"Byte-for-byte image copy failed for {patch_id}")

        with rasterio.open(image_out) as src:
            if (src.width, src.height, src.count) != (512, 512, 3):
                raise RuntimeError(f"{patch_id}: expected RGB 512x512 raster")
            transform = list(src.transform)[:6]
            crs = "EPSG:32637"
            bounds = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]
            rgb = Image.fromarray(src.read((1, 2, 3)).transpose(1, 2, 0))
            if src.crs.to_epsg() != 32637:
                raise RuntimeError(f"{patch_id}: unexpected CRS {src.crs}")

        empty_fc = {
            "type": "FeatureCollection", "name": patch_id,
            "crs": {"type": "name", "properties": {"name": crs}},
            "metadata": {
                "patch_id": patch_id, "split": "TEST_LOCKED", "annotation_status": "NOT_ANNOTATED",
                "annotator": None, "training_use_prohibited": True,
                "evaluation_only": True, "source_image_sha256": source_sha,
                "properties_schema": ["building_ref_id", "patch_id", "date", "source",
                                      "annotation_status", "annotator", "notes"],
                "instruction": "Empty human-label template. Do not copy predictions into this file.",
            },
            "features": [],
        }
        (DEST / "annotations" / f"{patch_id}.geojson").write_text(
            json.dumps(empty_fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        md = {
            "patch_id": patch_id, "split": "TEST_LOCKED", "original_split": "test",
            "evaluation_only": True, "training_use_prohibited": True,
            "annotation_status": "NOT_ANNOTATED", "annotator": None, "reviewer": None,
            "source_date": source_meta["source_date"], "source_raster": source_meta["source_raster"],
            "source_image_sha256": source_sha, "image": f"images/{patch_id}.tif",
            "annotation": f"annotations/{patch_id}.geojson", "overlay_template": f"overlays/{patch_id}_blank.png",
            "width": 512, "height": 512, "bands": 3, "crs": crs,
            "transform": transform, "bounds": bounds, "resolution_m": 0.35,
            "building_count": None, "mask": None,
            "annotation_note": "Null count means not reviewed; do not infer an empty/no-building scene.",
        }
        (DEST / "metadata" / f"{patch_id}.json").write_text(
            json.dumps(md, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        template = rgb.copy()
        draw = ImageDraw.Draw(template)
        draw.rectangle((0, 0, 511, 28), fill=(10, 10, 10))
        draw.text((8, 7), f"{patch_id} | BLANK HUMAN GROUND TRUTH TEMPLATE | NO MODEL PREDICTIONS", fill=(255, 255, 255))
        template.save(DEST / "overlays" / f"{patch_id}_blank.png")
        contact_items.append((patch_id, rgb.copy(), template.copy()))
        manifest_rows.append({"patch_id": patch_id, "original_split": "test", "locked_split": "TEST_LOCKED",
                              "source_image_sha256": source_sha, "copy_sha256": copied_sha,
                              "annotation_status": "NOT_ANNOTATED", "features": 0, "mask": None})

    # Six rows: untouched RGB and explicitly empty annotation template.
    cell, top, label = 240, 30, 22
    sheet = Image.new("RGB", (2 * cell, 6 * (cell + label)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (pid, rgb, template) in enumerate(contact_items):
        y = i * (cell + label)
        draw.text((4, y + 4), f"{pid} | RGB", fill="black")
        draw.text((cell + 4, y + 4), f"{pid} | blank annotation", fill="black")
        sheet.paste(rgb.resize((cell, cell)), (0, y + label))
        sheet.paste(template.resize((cell, cell)), (cell, y + label))
    sheet.save(DEST / "overlays/contact_sheet_test_blank.jpg", quality=92)

    manifest = {
        "stage": "13M", "purpose": "independent held-out model evaluation",
        "locked_split": "TEST_LOCKED", "patch_count": 6, "patch_ids": sorted(EXPECTED_TEST_IDS),
        "human_annotations_validated": 0, "human_buildings_annotated": None,
        "training_use_prohibited": True, "augmentation_training_prohibited": True,
        "model_predictions_included_in_annotation_layers": False,
        "model_outputs_location": "separate benchmark_13L outputs; not copied here",
        "source_images_byte_identical": all(x["source_image_sha256"] == x["copy_sha256"] for x in manifest_rows),
        "patches": manifest_rows,
    }
    (DEST / "metadata/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    instructions = """# 13M - QGIS annotation guide (locked TEST holdout)

This package contains only the six TEST RGB images and blank human annotation templates. Do not add model predictions to the annotation layer. Do not move these patches to TRAIN or use them for training, fine-tuning, or training augmentation.

## Open in QGIS

1. Add `images/<patch_id>.tif` as the background. Confirm the layer reports EPSG:32637 and 512x512.
2. Add the matching `annotations/<patch_id>.geojson`. It is intentionally empty; an empty layer means NOT_ANNOTATED, not "no buildings".
3. Before drawing the first polygon, open the annotation layer's attribute table, toggle editing, and add these text fields: `building_ref_id`, `patch_id`, `date`, `source`, `annotation_status`, `annotator`, `notes`. The empty GeoJSON intentionally has no feature-property schema. If QGIS will not add fields to it, create a new Polygon GeoJSON layer in EPSG:32637 with those fields and save it over the matching annotation file.
4. Digitize each clearly visible roof boundary. Include small, large, complex, and adjacent roofs. Exclude roads, vehicles, vegetation, shadows, bare ground, and ambiguous objects. Do not use model proposals as labels.
5. Assign a unique building ID such as `<patch_id>_B001`; set `annotation_status=ANNOTATED` while drawing. After a complete second visual review, set all features and patch metadata to `VALIDATED`, and record annotator/reviewer. A truly empty scene can be validated as empty only after a human has checked the whole patch and documented that review.
6. Save the layer. Validate geometry and exact alignment against the image before rasterizing. The final mask must be 512x512 uint8 `{0,1}` with the exact image CRS/transform/bounds.

## Patch set

The six IDs are fixed by `metadata/manifest.json`. The manifest records source and copied image SHA256 values. `overlays/contact_sheet_test_blank.jpg` shows RGB and blank templates only; no model predictions are included.
"""
    (DEST / "qgis/README.md").write_text(instructions, encoding="utf-8")
    print(json.dumps({"destination": str(DEST), "patch_count": len(manifest_rows),
                      "source_images_byte_identical": manifest["source_images_byte_identical"],
                      "annotations_created": 6, "features_added": 0,
                      "masks_created": 0, "model_predictions_copied": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
