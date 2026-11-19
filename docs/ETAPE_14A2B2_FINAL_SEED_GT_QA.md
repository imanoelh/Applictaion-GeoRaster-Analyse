# ÉTAPE 14A.2B2 — FINAL SEED GROUND TRUTH QA

La QA a contrôlé les 5 couches manuelles et a généré les masques 512x512 dans `masks/seed_gt_final/`, la contact sheet et le fichier d'erreurs. Les géométries n'ont pas été corrigées automatiquement.

Résultat : 100 bâtiments sur les 5 patches. Les masques sont alignés sur les RGB (512x512, valeurs 0/1). La QA détecte cependant 1 géométrie invalide avec auto-intersection, 22 géométries hors emprise raster et 100 features avec attributs incomplets : `patch_id`, `annotation_source` et `review_status` sont nuls. Le seed ne peut donc pas être approuvé pour le fine-tuning.

Les erreurs détaillées sont dans `qa/14A2B2_seed_gt_errors.csv`. Aucun manifest FINAL_SEED_GT approuvé n'est créé tant que ces erreurs ne sont pas corrigées manuellement.

SEED PATCHES :
5

TOTAL GT FEATURES :
100

PATCH 14A2_2025_13 :
22 features; 1 invalid/self-intersection; 3 out-of-bounds; 22 attribute errors

PATCH 14A2_2024_13 :
34 features; 10 out-of-bounds; 34 attribute errors

PATCH 14A2_2024_15 :
10 features; 2 out-of-bounds; 10 attribute errors

PATCH 14A2_2025_14 :
24 features; 6 out-of-bounds; 24 attribute errors

PATCH 14A2_2024_12 :
10 features; 1 out-of-bounds; 10 attribute errors

INVALID GEOMETRIES :
1

SELF INTERSECTIONS :
1

OUT OF BOUNDS :
22

DUPLICATES :
0

EMPTY GEOMETRIES :
0

ZERO AREA :
0

GT MASKS :
5 / 5

MASK ALIGNMENT :
VALIDATED

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

PATCHES VALIDATED :
0 / 5

FINAL SEED GT :
REJECTED

MODEL_C :
UNCHANGED

TRAINING STARTED :
NO

READY_FOR_FINE_TUNING :
NO

NEXT STEP :
14A.2B2 CORRECT GT ERRORS AND RERUN QA
