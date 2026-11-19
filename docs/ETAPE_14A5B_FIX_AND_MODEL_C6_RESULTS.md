# ÉTAPE 14A.5B-FIX → 14A.6

La source originale `14A5A_new_patch_expansion_gt.gpkg` a été conservée. Une copie corrigée a été créée dans `annotations/14A5B_new_patch_expansion_gt_FIXED.gpkg`.

Les 24 géométries hors emprise ont été intersectées strictement avec l’emprise de leur raster. Les 10 géométries invalides ont reçu `MakeValid` uniquement avant cette intersection. Aucun buffer, déplacement, simplification ou fusion arbitraire n’a été appliqué. Les 85 identifiants ont été conservés et complétés avec `patch_id`, `annotation_source=MANUAL` et `review_status=VALIDATED`.

La QA finale donne 0 géométrie invalide, 0 hors emprise, 0 géométrie vide, 0 surface nulle et 0 doublon. Les cinq masques binaires alignés ont été générés dans `14A5B_fixed_masks`. Les splits historiques restent inchangés et les patches de test verrouillés sont exclus.

Le manifeste enrichi est `14A6_enriched_manifest.json`. MODEL_C6 a été initialisé avec le checkpoint MODEL_C3, entraîné deux epochs sur 16 tuiles 256×256 des quatre patches d’entraînement de la nouvelle série, en CPU. Le checkpoint expérimental est `backend/data/models/model_c6_experimental/best_model_c6.pth`. Aucun fichier de production n’a été modifié.

Le benchmark strict objet C3/C6 sur les patches verrouillés n’a pas été exécuté dans ce cycle : le harness de matching polygonal reproductible n’est pas disponible dans l’environnement courant. Les métriques C3 conservées sont celles du benchmark verrouillé historique. MODEL_C6 reste expérimental et n’est pas promu.

TOTAL ORIGINAL GT :
85

INVALID BEFORE :
10

INVALID AFTER :
0

OUT OF BOUNDS BEFORE :
24

OUT OF BOUNDS AFTER :
0

INCOMPLETE ATTRIBUTES BEFORE :
85

INCOMPLETE ATTRIBUTES AFTER :
0

NON TARGET GEOMETRIES CHANGED :
0

VALIDATED BUILDINGS :
85

REVIEW REQUIRED :
0

QA GEOMETRY :
PASS

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

READY FOR TRAINING :
YES

MODEL_C6 TRAINING COMPLETED :
YES

MODEL_C6 BEST EPOCH :
2

MODEL_C6 OBJECT RECALL :
NOT_RUN

MODEL_C6 OBJECT F1 :
NOT_RUN

MODEL_C6 FALSE POSITIVES :
NOT_RUN

MODEL_C6 MISSED :
NOT_RUN

MODEL_C6 BOUNDARY F1 :
NOT_RUN

MODEL_C6 ONNX :
SKIPPED

PRODUCTION :
UNCHANGED

FINAL DECISION :
MODEL_C6_TRAINED_EXPERIMENTAL_PENDING_STRICT_LOCKED_BENCHMARK

NEXT STEP :
RUN_STRICT_C3_C6_LOCKED_POLYGON_BENCHMARK_BEFORE_ANY_PROMOTION
