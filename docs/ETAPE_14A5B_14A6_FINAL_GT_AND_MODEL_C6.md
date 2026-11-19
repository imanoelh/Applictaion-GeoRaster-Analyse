# GeoRaster — ÉTAPE 14A.5B–14A.6 : FINAL GT QA + ACCELERATED HIGH-PRECISION TRAINING

## Résultat QA

Les annotations ont été lues directement depuis `annotations/14A5A_new_patch_expansion_gt.gpkg`. Le total est de 85 polygones : 46, 11, 7, 7 et 14 par patch.

La QA géométrique bloque la suite : 10 géométries sont invalides et 24 features dépassent les limites de leur raster. Aucun doublon exact ni géométrie vide n’a été détecté. Les champs `patch_id`, `annotation_source` et `review_status` sont vides sur les features persistées ; la complétude attributaire échoue donc également.

Aucune correction automatique n’a été appliquée. Les géométries invalides et hors limites nécessitent une copie de sauvegarde, une correction contrôlée (`MakeValid`/intersection) et une vérification visuelle humaine. La couverture complète des bâtiments visibles n’est pas démontrable automatiquement à partir des seules couches ; elle reste à revoir.

## Décision

Le dataset TRAIN enrichi n’est pas construit et aucun entraînement MODEL_C6 n’a démarré. MODEL_C3/C4/C5, MODEL_C production, API, frontend, registry et anciens datasets restent inchangés.

TOTAL NEW GT BUILDINGS :
85

GT GEOMETRY QA :
FAIL

GT COMPLETENESS REVIEW :
REVIEW_REQUIRED

OUT OF BOUNDS AFTER :
24

INVALID GEOMETRIES AFTER :
10

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

TRAIN DATASET READY :
NO

MODEL_C6 TRAINED :
NO

MODEL_C6 BEST EPOCH :
NOT_RUN

MODEL_C3 OBJECT RECALL :
0.2190

MODEL_C6 OBJECT RECALL :
NOT_RUN

MODEL_C3 OBJECT F1 :
0.2585

MODEL_C6 OBJECT F1 :
NOT_RUN

MODEL_C3 FALSE POSITIVES :
14

MODEL_C6 FALSE POSITIVES :
NOT_RUN

MODEL_C3 MISSED :
37

MODEL_C6 MISSED :
NOT_RUN

MODEL_C6 PIXEL IOU :
NOT_RUN

MODEL_C6 BOUNDARY F1 @1PX :
NOT_RUN

MODEL_C6 CPU INFERENCE :
NOT_RUN

MODEL_C6 ONNX :
SKIPPED

PRODUCTION :
UNCHANGED

DECISION :
TRAINING_BLOCKED_BY_QA

NEXT STEP :
CORRECT_10_INVALID_24_OUT_OF_BOUNDS_AND_COMPLETE_ANNOTATION_ATTRIBUTES
