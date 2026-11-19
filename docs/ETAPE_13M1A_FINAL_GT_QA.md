# ÉTAPE 13M.1A — FINAL HUMAN GROUND TRUTH QA

Audit effectué le 2026-10-22 avec QGIS/GDAL sur `benchmark_13M_test/annotations/ground_truth_layers.gpkg`. Aucune géométrie, feature, raster, statut ou métadonnée de split n’a été corrigé durant cette QA. MODEL_C, MODEL_D et le fine-tuning n’ont pas été exécutés.

## Résumé par couche

| Patch | Features | Aire totale m² | Moyenne m² | Min m² | Max m² | Géométries invalides | Features hors emprise | Résultat |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| GT_2024_difficult_02 | 16 | 5 654.772 | 353.423 | 48.467 | 1 939.374 | 5 | 3 | NEEDS_CORRECTION |
| GT_2024_industrial_02 | 1 | 322.074 | 322.074 | 322.074 | 322.074 | 0 | 1 | NEEDS_CORRECTION |
| GT_2024_residential_02 | 20 | 10 166.922 | 508.346 | 12.339 | 2 094.286 | 2 | 5 | NEEDS_CORRECTION |
| GT_2025_difficult_02 | 19 | 5 856.453 | 308.234 | 55.800 | 1 841.550 | 4 | 3 | NEEDS_CORRECTION |
| GT_2025_industrial_02 | 1 | 393.101 | 393.101 | 393.101 | 393.101 | 0 | 1 | NEEDS_CORRECTION |
| GT_2025_residential_02 | 11 | 5 760.018 | 523.638 | 197.780 | 988.218 | 1 | 1 | NEEDS_CORRECTION |

Total : 68 features; aire totale 28 153.340 m². Toutes les couches sont des Polygon EPSG:32637. La date de modification du GeoPackage est 2026-10-22 18:20:17; aucune date de modification par couche n’est enregistrée.

## Anomalies géométriques à corriger manuellement

Toutes les 68 géométries ont une aire positive; aucune géométrie vide et aucun doublon exact n’ont été trouvés. 56 géométries sont valides selon GEOS et 12 présentent une auto-intersection :

- `GT_2024_difficult_02`: building_id 3, 4, 6, 11, 12 — Self-intersection.
- `GT_2024_residential_02`: building_id 2, 7 — Self-intersection.
- `GT_2025_difficult_02`: building_id 2, 5, 6, 7 — Self-intersection.
- `GT_2025_residential_02`: building_id 6 — Self-intersection.

14 features dépassent les bounds de leur raster; leurs sommets doivent être corrigés manuellement ou les géométries doivent être redessinées entièrement dans le patch :

- `GT_2024_difficult_02`: building_id 10, 15, 16.
- `GT_2024_industrial_02`: building_id 1.
- `GT_2024_residential_02`: building_id 4, 6, 7, 13, 15.
- `GT_2025_difficult_02`: building_id 3, 10, 19.
- `GT_2025_industrial_02`: building_id 1.
- `GT_2025_residential_02`: building_id 7.

Le feature `GT_2024_residential_02 / building_id 7` est à la fois auto-intersecté et hors bounds. Les patches industriels échouent uniquement à cause d’un feature hors bounds, malgré la validité GEOS de ces géométries.

## Alignement et livrables QA

Les six rasters sont 512×512, 3 bandes, EPSG:32637, avec résolution 0,35 m et géotransform identique aux métadonnées. Pour chaque masque, le raster a été créé directement sur la même grille GDAL sans reprojection ni resampling; taille, geotransform, CRS et bounds sont identiques, et les seules valeurs sont 0 et 1. Les masques et overlays des six couches sont des livrables QA provisoires: les features hors bounds sont coupées par le raster et les géométries invalides ne sont pas réparées. Les planches de contours et de masques couvrent les six patches.

Dossier QA : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qa_13M1A/`

- Masques : `masks/GT_*_ground_truth_mask.tif` (6)
- Overlays contours : `overlays/GT_*_gt_contours.png` (6)
- Overlays masque semi-transparent : `overlays/GT_*_gt_mask_overlay.png` (6)
- Planche contours : `contact_sheets/six_patches_gt_contours_contact_sheet.png`
- Planche masque : `contact_sheets/six_patches_gt_mask_contact_sheet.png`

Aucune couche ne passe tous les contrôles. Les attributs restent `annotation_status=ANNOTATED` et `review_status=NOT_REVIEWED`; aucune validation n’a été appliquée.

## Intégrité du split et écart de métadonnées

Le manifeste confirme les six IDs en `TEST_LOCKED`, `training_use_prohibited=true`, `augmentation_training_prohibited=true`, et les hashes source/copie identiques. Le split reste verrouillé.

Le manifeste et les six JSON de metadata sont toutefois obsolètes par rapport au GeoPackage : ils indiquent `human_annotations_validated=0`, `features=0`, `NOT_ANNOTATED`/compte null, alors que le GeoPackage contient 68 features avec statut `ANNOTATED`. Ces métadonnées n’ont pas été modifiées puisque les couches doivent d’abord être corrigées et validées.

PATCH 01 BUILDINGS : 16 — NEEDS_CORRECTION (5 invalides, 3 hors bounds)

PATCH 02 BUILDINGS : 1 — NEEDS_CORRECTION (1 hors bounds)

PATCH 03 BUILDINGS : 20 — NEEDS_CORRECTION (2 invalides, 5 hors bounds)

PATCH 04 BUILDINGS : 19 — NEEDS_CORRECTION (4 invalides, 3 hors bounds)

PATCH 05 BUILDINGS : 1 — NEEDS_CORRECTION (1 hors bounds)

PATCH 06 BUILDINGS : 11 — NEEDS_CORRECTION (1 invalide, 1 hors bounds)

TOTAL GT BUILDINGS : 68

VALID GEOMETRIES : 56 / 68

INVALID GEOMETRIES : 12

OUT_OF_BOUNDS : 14

DUPLICATES : 0

GROUND TRUTH MASKS : 6 / 6 (QA provisoire)

MASK ALIGNMENT : VALIDATED (grille exacte; features hors bounds et géométries invalides bloquent la validation GT)

CONTACT SHEETS : CREATED

VALIDATED PATCHES : 0 / 6

TEST SPLIT LOCKED : YES

MODEL_C : NOT RUN

MODEL_D : NOT RUN

FINE TUNING : NOT RUN

READY_FOR_MODEL_C_VS_MODEL_D_BENCHMARK : NO

NEXT STEP : CORRECT GROUND TRUTH
