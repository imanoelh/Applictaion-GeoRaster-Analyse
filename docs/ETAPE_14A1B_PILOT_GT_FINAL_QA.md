# ÉTAPE 14A.1B — FINAL PILOT GROUND TRUTH QA

Les deux couches Ground Truth ont été relues directement dans `annotations/ground_truth_14A.gpkg`. MODEL_C n’a pas été relancé. Les masques GT et les overlays QA ont été générés dans `masks/ground_truth/` et `qa/pilot_overlays/`.

## Résultats par patch
### 14A_001_residential
- Couche : `14A_001_residential_ground_truth`
- Features : 25
- Géométrie invalide : 1
- Géométries vides : 0
- Auto-intersections : 1
- Hors bounds : 3
- Doublons exacts : 0
- MODEL_C IoU : 0.0816
- MODEL_C Dice : 0.1509
- Boundary F1 @1 px : 0.0456
- Boundary F1 @2 px : 0.0776
- Alignement : VALIDATED

### 14A_003_dense_urban
- Couche : `14A_003_dense_urban_ground_truth`
- Features : 22
- Géométrie invalide : 5
- Géométries vides : 0
- Auto-intersections : 5
- Hors bounds : 3
- Doublons exacts : 0
- MODEL_C IoU : 0.1794
- MODEL_C Dice : 0.3042
- Boundary F1 @1 px : 0.0607
- Boundary F1 @2 px : 0.0993
- Alignement : VALIDATED

## Méthode
- Rasterisation GT avec le transform exact du RGB, 512 × 512, sans resampling.
- Matching objet par IoU ≥ 0,30.
- Boundary tolerance : 1 px et 2 px. Pixel size : 0,35 m.
- Mean / P95 / Hausdorff calculés sur les pixels de contour GT et prédits.

PATCH 14A_001 FEATURES : 25
PATCH 14A_003 FEATURES : 22
TOTAL GT FEATURES : 47
INVALID GEOMETRIES : 6
EMPTY GEOMETRIES : 0
SELF INTERSECTIONS : 6
OUT OF BOUNDS : 6
EXACT DUPLICATES : 0
GT MASKS : 2 / 2
MASK ALIGNMENT : FAILED
MODEL_C GLOBAL IOU : 0.1296
MODEL_C GLOBAL DICE : 0.2295
MODEL_C GLOBAL PRECISION : 0.5571
MODEL_C GLOBAL RECALL : 0.1445
MODEL_C BOUNDARY F1 @1PX : 0.0532
MODEL_C BOUNDARY F1 @2PX : 0.0885
MEAN BOUNDARY DISTANCE : 43.4548 px / 15.2092 m
GT BUILDINGS : 47
DETECTED BUILDINGS : 34
MISSED BUILDINGS : 40
FALSE POSITIVE OBJECTS : 27
MERGED BUILDINGS : 0
FRAGMENTED BUILDINGS : 0
DOMINANT MODEL_C ERROR : BOUNDARY_ERROR
PATCHES VALIDATED : 0 / 2
ANNOTATION WORKFLOW : FAILED
LEGACY TEST LEAKAGE : 0
PRODUCTION MODIFIED : NO
MODEL_C : UNCHANGED
READY_FOR_BATCH_EXPANSION : NO
NEXT STEP : CORRECT PILOT GROUND TRUTH