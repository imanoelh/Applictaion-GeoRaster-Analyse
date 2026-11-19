# ÉTAPE 14A.1D2 — Final remaining Ground Truth errors QA

Le GeoPackage réellement utilisé par `14A1C_ground_truth_FIX_REBUILT_V2.qgz` est :

`backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/ground_truth_layers_14A1C_WORKING.gpkg`

Les comptes sont conformes : 25 features pour `14A_001_residential_ground_truth`, 22 pour `14A_003_dense_urban_ground_truth`, soit 47 au total.

La QA montre que les cinq corrections annoncées ne sont pas toutes présentes dans le fichier actuellement lu. Les erreurs restantes réelles sont :

- `14A_001` bâtiments 24 et 25 hors bounds ;
- `14A_003` bâtiments 12 et 20 hors bounds ;
- `14A_003` bâtiments 3 et 15 encore invalides avec auto-intersection.

Le bâtiment 25 est géométriquement valide mais reste hors bounds. Les bâtiments 12 et 20 sont également valides mais hors bounds. Les masques ont été régénérés en 512×512 avec valeurs `{0,1}`. L’alignement RGB ↔ masque GT corrigé ↔ sorties MODEL_C est validé sur les deux patches.

Les 36 features précédemment valides restent WKB-identiques. Aucun changement automatique de géométrie n’a été effectué et aucun statut VALIDATED n’a été appliqué.

Artefacts :

- `qa/14A1D2_geometry_qa.json`
- `qa/14A1D2_corrected_gt_summary.json`
- `masks/ground_truth_corrected/14A_001_residential.tif`
- `masks/ground_truth_corrected/14A_003_dense_urban.tif`

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

OUT OF BOUNDS :
4

EMPTY GEOMETRIES :
0

ZERO AREA :
0

EXACT DUPLICATES :
0

TARGET 14A_001 BUILDING 25 :
VALID

TARGET 14A_003 BUILDING 3 :
INVALID

TARGET 14A_003 BUILDING 15 :
INVALID

TARGET 14A_003 BUILDING 12 :
VALID

TARGET 14A_003 BUILDING 20 :
VALID

UNCHANGED VALID FEATURES :
YES

GT MASKS :
2 / 2

MASK ALIGNMENT :
VALIDATED

PATCHES VALIDATED :
0 / 2

ANNOTATION WORKFLOW :
FAILED

MODEL_C :
UNCHANGED

MODEL_C RE-RUN :
NO

READY_FOR_MODEL_C_REBENCHMARK :
NO

NEXT STEP :
CORRECT REMAINING ERRORS
