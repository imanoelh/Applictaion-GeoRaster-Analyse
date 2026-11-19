# ÉTAPE 14A.2B2-FIX — Surgical Seed Ground Truth Repair

La réparation a été réalisée sur une copie du GeoPackage original. Le fichier source `14A2B1_manual_seed_ground_truth.gpkg` n'a pas été écrasé.

## Contrôles effectués

- 100 géométries lues et leurs SHA256 WKB conservés dans `qa/14A2B2_wkb_before_<patch>.json`.
- Les attributs des 100 entités ont été complétés avec le patch exact, `MANUAL`, `MANUAL`.
- Les IDs existants valides ont été conservés. Les valeurs absentes ou dupliquées ont reçu un identifiant déterministe basé sur le patch et la séquence.
- Les 22 entités hors emprise ont été corrigées par intersection stricte avec l'emprise du raster correspondant.
- L'unique auto-intersection (`14A2_2025_13`, bâtiment `17`) a été réparée par GEOS `MakeValid`. Le diagnostic GEOS indique une auto-intersection au point `(582227.06421969063, 2367497.7033499405)`; la réparation produit une géométrie polygonale valide sans revue manuelle requise.
- Les 77 géométries non ciblées sont restées byte-identiques en WKB.
- Cinq masques 512x512 ont été régénérés avec le transform, le CRS et la résolution des rasters RGB.

Les fichiers produits sont dans `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/` : GeoPackage candidat, masques corrigés, CSV de QA, résumé JSON et planche de contrôle.

TOTAL GT FEATURES :
100

ATTRIBUTES FIXED :
100 / 100

INCOMPLETE ATTRIBUTES :
0

OUT OF BOUNDS BEFORE :
22

OUT OF BOUNDS AFTER :
0

SELF INTERSECTIONS BEFORE :
1

SELF INTERSECTIONS AFTER :
0

INVALID GEOMETRIES :
0

DUPLICATES :
0

EMPTY GEOMETRIES :
0

ZERO AREA :
0

TARGET GEOMETRIES MODIFIED :
23

NON-TARGET GEOMETRIES CHANGED :
0

GT MASKS :
5 / 5

MASK ALIGNMENT :
VALIDATED

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

MANUAL REVIEW REQUIRED :
NO

PATCHES VALIDATED :
5 / 5

FINAL SEED GT :
APPROVED

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

TRAINING STARTED :
NO

READY_FOR_FINE_TUNING :
YES

NEXT STEP :
14A.3 MODEL_C2 EXPERIMENTAL FINE-TUNING /
14A.2B2-FIX MANUAL REVIEW
