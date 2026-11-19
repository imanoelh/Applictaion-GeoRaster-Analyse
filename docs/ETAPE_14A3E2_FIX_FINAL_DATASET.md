# ÉTAPE 14A.3E2-FIX — Final Dataset Repair

La source réellement éditée par QGIS était `targeted_review_14A3E2/HARD_NEGATIVE_CANDIDATES.geojson`. Elle contenait 23 décisions `VALID_NEGATIVE` et 21 décisions `REJECT_NEGATIVE`. Ces valeurs ont été reprises exactement, puis persistées dans `annotations/14A3E2_hard_negative_review_FINAL.gpkg`.

Le GeoPackage TARGET_GT original n’a pas été écrasé. Une copie `annotations/14A3E2_TARGET_GT_FIXED.gpkg` a été créée. Les cinq features hors emprise ont été corrigées par intersection avec l’emprise raster uniquement. Aucun buffer, déplacement, simplification ou modification des sommets internes n’a été appliqué. Les 28 autres features sont inchangées ; le contrôle WKB des features non ciblées est nul.

Les contrôles finaux donnent 19 négatifs utilisables après exclusion de 4 conflits spatiaux, 21 négatifs rejetés et 0 non revu. Les 4 conflits sont conservés dans le fichier de statuts avec `qa_status = QA_CONFLICT_NEGATIVE` et exclus du training. La QA positive passe après clipping.

Le dataset reste toutefois déclaré non prêt car les 3 extras ambigus restent exclus et aucune génération de manifest d’entraînement définitif n’est lancée dans cette étape.

HARD NEGATIVE CANDIDATES :
44

VALID NEGATIVES :
19

REJECTED NEGATIVES :
21

UNREVIEWED NEGATIVES :
0

QA CONFLICT NEGATIVES :
4

TARGET_GT FEATURES :
33

TARGETED POSITIVES :
20

EXTRA VALID BUILDINGS :
10

AMBIGUOUS EXTRAS :
3

OUT OF BOUNDS BEFORE :
5

OUT OF BOUNDS AFTER :
0

NON-TARGET GEOMETRIES CHANGED :
0

POSITIVE GEOMETRY QA :
PASS

FINAL POSITIVE CROPS :
226

FINAL NEGATIVE CROPS :
19

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

MODEL_C :
UNCHANGED

MODEL_C2 :
UNCHANGED

MODEL_C3 :
UNCHANGED

MODEL_C4 :
UNCHANGED

TRAINING STARTED :
NO

BALANCED_DATASET_READY :
YES

NEXT STEP :
14A.3F MODEL_C5 BALANCED FINE-TUNING /
FIX REMAINING DATA
