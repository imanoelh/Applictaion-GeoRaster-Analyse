# ÉTAPE 14A.3E2-FINAL2 — Final Targeted Positive QA

## Résultat de l’audit

Les couches persistées `TARGET_GT` ont été relues dans `balanced_dataset_14A3E/target_ground_truth_14A3E.gpkg`. Elles contiennent 33 features : 2 dans `14A2_2024_11`, 6 dans `14A2_2025_12`, 17 dans `14A2_2024_14` et 8 dans `14A2_2025_15`.

Les géométries sont non vides, valides et sans doublon exact. Cinq features sont toutefois hors des bounds du raster correspondant ; elles ne peuvent pas être incluses dans un dataset d’entraînement sans correction manuelle. Les 13 annotations au-delà des 20 cibles initiales ont été conservées dans l’audit : 10 sont géométriquement exploitables après contrôle spatial et 3 restent ambiguës à cause de leur emplacement hors bounds.

Le fichier de revue des négatifs ne contient aucune décision humaine persistée : les 44 lignes sont toujours `UNREVIEWED`. Aucun négatif n’a donc été converti automatiquement en `VALID_NEGATIVE`, et aucun n’a été utilisé pour le dataset final. Les conflits positif/négatif ne peuvent être déclarés résolus tant que la revue n’est pas enregistrée.

Conséquence : `BALANCED_DATASET_READY = NO`. Aucun entraînement n’a été lancé et MODEL_C, MODEL_C2, MODEL_C3 et MODEL_C4 restent inchangés.

TOTAL TARGET_GT FEATURES :
33

TARGETED POSITIVES :
20

EXTRA VALID BUILDINGS :
10

AMBIGUOUS EXTRAS :
3

INVALID GEOMETRIES :
0

SELF INTERSECTIONS :
0

OUT OF BOUNDS :
5

DUPLICATES :
0

VALID NEGATIVES :
0

REJECTED NEGATIVES :
0

UNREVIEWED NEGATIVES :
44

QA CONFLICT NEGATIVES :
0

FINAL POSITIVE CROPS :
226

FINAL NEGATIVE CROPS :
0

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

POSITIVE GEOMETRY QA :
FAIL

BALANCED_DATASET_READY :
NO

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

NEXT STEP :
14A.3F MODEL_C5 BALANCED FINE-TUNING /
FIX TARGETED DATA
