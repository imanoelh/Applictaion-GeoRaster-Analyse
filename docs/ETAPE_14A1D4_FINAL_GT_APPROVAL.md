# ÉTAPE 14A.1D4 — Final visual Ground Truth approval

La revue visuelle humaine des six corrections a été déclarée `APPROVED`. La QA finale a été exécutée sur le Candidate GPKG uniquement :

`backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/ground_truth_layers_14A1D3_CANDIDATE.gpkg`

Les 47 features sont valides, non vides, de surface positive, sans auto-intersection, entièrement dans les bounds RGB et sans doublon exact. Les six features ciblées ont été contrôlées individuellement ; leurs superficies et centroïdes sont enregistrés dans `qa/14A1D4_final_gt_geometry_qa.json`.

Les 41 features non ciblées sont WKB-identiques au dataset antérieur. Le WORKING GT et l’original sont inchangés.

Les deux masques finaux ont été régénérés dans `masks/ground_truth_final/`, en 512×512, valeurs `{0,1}`. L’alignement RGB ↔ polygones Candidate ↔ masques finaux ↔ masques/probabilités MODEL_C est validé sans décalage.

Une référence de provenance explicite a été créée dans `manifests/14A1D4_final_gt_reference.json`. Aucun benchmark ni calcul de métriques MODEL_C n’a été lancé.

PATCH 14A_001 FEATURES :
25

PATCH 14A_003 FEATURES :
22

TOTAL GT FEATURES :
47

INVALID GEOMETRIES :
0

SELF INTERSECTIONS :
0

OUT OF BOUNDS :
0

EMPTY GEOMETRIES :
0

ZERO AREA :
0

EXACT DUPLICATES :
0

TARGET FEATURES VALID :
6 / 6

NON-TARGET FEATURES CHANGED :
0

FINAL GT MASKS :
2 / 2

MASK ALIGNMENT :
VALIDATED

VISUAL APPROVAL :
APPROVED

PATCHES VALIDATED :
2 / 2

ANNOTATION WORKFLOW :
VALIDATED

FINAL GT :
APPROVED

MODEL_C :
UNCHANGED

MODEL_C RE-RUN :
NO

READY_FOR_MODEL_C_REBENCHMARK :
YES

READY_FOR_BATCH_EXPANSION :
NO

NEXT STEP :
14A.1E MODEL_C HIGH-PRECISION REBENCHMARK
