# ÉTAPE 14A.2 — HIGH-PRECISION BUILDING TRAINING DATASET EXPANSION

## Scope

Created an isolated expansion under `14A2_expansion` from the existing Maxar RGB mosaics. The expansion contains 20 new 512×512 RGB patches (16 train, 4 val), matching MODEL_C pseudo-probability maps, binary masks, GeoJSON preannotations and RGB overlays. No production model, raster source, historical index, or locked test data was modified.

## Dataset and QA

- Train/validation split: 16/4, with no TEST patches copied into either split.
- Ground-truth layers: 20 empty editable Polygon layers in `annotations/ground_truth_layers_14A2.gpkg`, EPSG:32637, with fields `building_id`, `patch_id`, `annotation_status`, `review_status`, `annotator`, and `source`.
- Pseudo-labels: 20/20 masks, 20/20 probability rasters, 20/20 GeoJSON files and 20 overlays. They remain `MODEL_C_PSEUDO_LABEL` / `PENDING` and are not ground truth.
- Leakage QA uses positive-area intersection, so adjacent grid cells sharing an edge are not falsely reported as leakage. Legacy leakage: 0/20; pilot leakage: 0/20.
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
0 / 20
PILOT VALIDATION LEAKAGE :
0 / 20
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
