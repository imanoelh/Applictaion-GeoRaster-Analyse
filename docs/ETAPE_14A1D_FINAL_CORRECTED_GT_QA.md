# ÉTAPE 14A.1D — Final corrected Ground Truth QA

## Source audité

Le projet `14A1C_ground_truth_FIX_REBUILT_V2.qgz` référence bien :

`backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/ground_truth_layers_14A1C_WORKING.gpkg`

Layers contrôlés : `14A_001_residential_ground_truth` et `14A_003_dense_urban_ground_truth`, en EPSG:32637. Les comptes restent 25 et 22, soit 47 features.

## Résultat géométrique

La correction manuelle a supprimé la majorité des erreurs, mais la QA réelle n’est pas encore validée :

- 14A_001 : bâtiment 25 encore hors bounds ;
- 14A_003 : bâtiments 3 et 15 encore invalides avec auto-intersection ; bâtiments 12 et 20 encore hors bounds ;
- géométries vides : 0 ; surfaces nulles : 0 ; doublons exacts : 0.

Les 11 features ciblées par 14A.1C ont changé par rapport au GeoPackage original ; les 36 features valides non ciblées sont WKB-identiques. Le GeoPackage original n’a pas été modifié.

## Masques et alignement

Les deux masques corrigés ont été générés dans `masks/ground_truth_corrected/`, en 512×512, valeurs `{0,1}`, avec le transform, CRS, bounds et résolution des RGB correspondants. L’alignement RGB ↔ GT mask ↔ MODEL_C mask ↔ MODEL_C probability est validé pour les deux patches.

Les statuts `annotation_status=VALIDATED` et `review_status=REVIEWED` n’ont pas été appliqués, car des erreurs persistent.

Artefacts :

- `qa/14A1D_geometry_qa.json`
- `qa/14A1D_corrected_gt_summary.json`
- `qa/14A1D_remaining_errors.csv`
- `qa/14A1D_corrected_contact_sheet.png`

MODEL_C n’a pas été relancé. Aucun benchmark ni fine-tuning n’a été exécuté.

PATCH 14A_001 FEATURES :
25

PATCH 14A_003 FEATURES :
22

TOTAL GT FEATURES :
47

INVALID GEOMETRIES :
2

SELF INTERSECTIONS :
2

EMPTY GEOMETRIES :
0

ZERO AREA :
0

OUT OF BOUNDS :
3

EXACT DUPLICATES :
0

CORRECTED FEATURES :
11

UNCHANGED VALID FEATURES :
YES

CORRECTED GT MASKS :
2 / 2

MASK ALIGNMENT :
VALIDATED

PATCHES VALIDATED :
0 / 2

ANNOTATION WORKFLOW :
FAILED

ORIGINAL GT MODIFIED :
NO

MODEL_C :
UNCHANGED

MODEL_C RE-RUN :
NO

READY_FOR_MODEL_C_REBENCHMARK :
NO

READY_FOR_BATCH_EXPANSION :
NO

NEXT STEP :
CORRECT REMAINING GT ERRORS
