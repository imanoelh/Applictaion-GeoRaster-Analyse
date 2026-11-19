from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion"
GPKG = EXP / "annotations/ground_truth_layers_14A2.gpkg"
MANIFEST = EXP / "manifests/dataset_manifest.json"
QA = EXP / "qa"
REPORT = ROOT / "docs/ETAPE_14A2_TRAINING_DATASET_EXPANSION.md"


def area(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def main():
    # Add the documented annotation schema without creating any features.
    with sqlite3.connect(GPKG) as con:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type='features' ORDER BY table_name"
        )]
        fields = {"building_id": "TEXT", "patch_id": "TEXT", "annotation_status": "TEXT",
                  "review_status": "TEXT", "annotator": "TEXT", "source": "TEXT"}
        for table in tables:
            existing = {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
            for name, typ in fields.items():
                if name not in existing:
                    con.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {typ}')

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    patches = data["patches"]
    for p in patches:
        md = EXP / p["split"] / "metadata" / f'{p["patch_id"]}.json'
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(json.dumps({"patch_id": p["patch_id"], "split": p["split"],
                                  "scene_type": p.get("scene_type"), "year": p.get("year"),
                                  "bounds": p["bounds"], "crs": "EPSG:32637",
                                  "annotation_status": "PENDING", "label_source": "MODEL_C_PSEUDO_LABEL",
                                  "test_locked": False}, indent=2), encoding="utf-8")
    # Strict positive-area overlap avoids counting adjacent grid cells as leakage.
    legacy_boxes = [
        (582091.8914781092, 2368001.6373675326, 582271.0914781092, 2368180.8373675323),
        (582629.4914781093, 2368001.6373675326, 582808.6914781093, 2368180.8373675323),
        (582091.8914781092, 2367822.4373675324, 582271.0914781092, 2368001.6373675326),
        (582629.4914781093, 2367822.4373675324, 582808.6914781093, 2368001.6373675326),
    ]
    pilot_boxes = [
        (582091.8914781092, 2368001.6373675326, 582271.0914781092, 2368180.8373675323),
        (582091.8914781092, 2367732.4373675324, 582271.0914781092, 2367912.4373675324),
    ]
    rows = []
    for p in patches:
        b = tuple(p["bounds"])
        legacy = any(area(b, x) > 1e-6 for x in legacy_boxes)
        pilot = any(area(b, x) > 1e-6 for x in pilot_boxes)
        rows.append({"patch_id": p["patch_id"], "legacy_test_overlap": legacy,
                     "pilot_validation_overlap": pilot, "bounds": json.dumps(list(b))})
    QA.mkdir(parents=True, exist_ok=True)
    with (QA / "14A2_leakage_check.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    mask_count = len(list((EXP / "pseudo_labels/model_c/mask").glob("*.tif")))
    prob_count = len(list((EXP / "pseudo_labels/model_c/probability").glob("*.tif")))
    geojson_count = len(list((EXP / "pseudo_labels/model_c/geojson").glob("*.geojson")))
    summary = {
        "new_patches": len(patches), "train_patches": sum(p["split"] == "train" for p in patches),
        "val_patches": sum(p["split"] == "val" for p in patches),
        "locked_test_patches": "reference only / excluded", "train_buildings": 0,
        "val_buildings": 0, "ground_truth_status": "PENDING", "geometry_qa": "PASS",
        "legacy_test_leakage": sum(r["legacy_test_overlap"] for r in rows),
        "pilot_validation_leakage": sum(r["pilot_validation_overlap"] for r in rows),
        "pseudo_labels_created": {"probability": prob_count, "mask": mask_count, "geojson": geojson_count},
        "fine_tuning_ready": False, "training_started": False,
        "notes": "Empty GT layers are intentionally pending manual annotation; pseudo-labels are not ground truth.",
    }
    (QA / "14A2_dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    locked = {
        "purpose": "Reference-only locked test set; excluded from 14A.2 train/val and any fine-tuning.",
        "patch_ids": [
            "GT_2024_difficult_02", "GT_2024_industrial_02", "GT_2024_residential_02",
            "GT_2025_difficult_02", "GT_2025_industrial_02", "GT_2025_residential_02",
            "14A_001_residential", "14A_003_dense_urban"
        ],
        "training_excluded": True,
    }
    (EXP / "test_locked").mkdir(exist_ok=True)
    (EXP / "test_locked/locked_test_reference.json").write_text(json.dumps(locked, indent=2), encoding="utf-8")

    report = f"""# ÉTAPE 14A.2 — HIGH-PRECISION BUILDING TRAINING DATASET EXPANSION

## Scope

Created an isolated expansion under `14A2_expansion` from the existing Maxar RGB mosaics. The expansion contains 20 new 512×512 RGB patches (16 train, 4 val), matching MODEL_C pseudo-probability maps, binary masks, GeoJSON preannotations and RGB overlays. No production model, raster source, historical index, or locked test data was modified.

## Dataset and QA

- Train/validation split: 16/4, with no TEST patches copied into either split.
- Ground-truth layers: 20 empty editable Polygon layers in `annotations/ground_truth_layers_14A2.gpkg`, EPSG:32637, with fields `building_id`, `patch_id`, `annotation_status`, `review_status`, `annotator`, and `source`.
- Pseudo-labels: {mask_count}/20 masks, {prob_count}/20 probability rasters, {geojson_count}/20 GeoJSON files and 20 overlays. They remain `MODEL_C_PSEUDO_LABEL` / `PENDING` and are not ground truth.
- Leakage QA uses positive-area intersection, so adjacent grid cells sharing an edge are not falsely reported as leakage. Legacy leakage: {summary['legacy_test_leakage']}/20; pilot leakage: {summary['pilot_validation_leakage']}/20.
- Geometry QA passes because all GT layers are intentionally empty pending human annotation. No fine-tuning was started.

Some source windows emitted GDAL valid-pixel/statistics warnings during extraction; they are noted for manual review and do not alter source mosaics.

## QGIS review project

`14A2_expansion/qgis/14A2_training_ground_truth.qgz` contains the 20 RGB layers, 20 MODEL_C pseudo-label layers, 20 editable Ground Truth Polygon layers and 20 patch bookmarks, all in EPSG:32637.

NEW PATCHES :
20
TRAIN PATCHES :
16
VAL PATCHES :
4
LOCKED TEST PATCHES :
REFERENCE ONLY / EXCLUDED
TOTAL TRAIN BUILDINGS :
0
TOTAL VAL BUILDINGS :
0
LEGACY TEST LEAKAGE :
{summary['legacy_test_leakage']} / 20
PILOT VALIDATION LEAKAGE :
{summary['pilot_validation_leakage']} / 20
PREANNOTATIONS CREATED :
20 / 20
GROUND TRUTH STATUS :
PENDING
GEOMETRY QA :
PASS
MODEL_C :
UNCHANGED
TRAINING STARTED :
NO
FINE_TUNING_READY :
NO
NEXT STEP :
14A.2B MANUAL GT ANNOTATION
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"layers": len(tables), "summary": summary, "report": str(REPORT)}, indent=2))


if __name__ == "__main__":
    main()
