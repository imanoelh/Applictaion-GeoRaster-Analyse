# ÉTAPE 13M.0D — CLEAN QGIS ANNOTATIONS

## Résultat

Une copie propre du projet polygonal a été créée à partir de `13M_locked_test_ground_truth_polygon_layers.qgz`. Le projet source n’a pas été écrasé. L’audit QGIS 3.40.14 a identifié 35 objets dans la couche système `Annotations`, tous de type `polygon`. Seuls ces objets graphiques ont été retirés de la copie.

## Vérifications de la copie CLEAN

- Réouverture avec l’API QGIS 3.40.14 réussie; couche système `Annotations` vide (0 objet).
- Six couches `*_ground_truth` valides, type Polygon, EPSG:32637, 0 feature chacune. Les six couches peuvent entrer en mode édition via l’API QGIS; l’essai a été annulé sans création de feature.
- Six rasters `RGB_TEST_LOCKED_GT_*` valides et visibles dans l’arbre de couches. Aucun raster n’a été écrit ou modifié.
- Six groupes de patches et six bookmarks conservés.
- Aucun modèle ni split TEST touché; aucune inférence effectuée.

Le projet CLEAN a été lancé dans QGIS Desktop 3.40.14. L’interface graphique n’est pas exposée à cette session d’automatisation; l’affichage visuel sans polygones roses et le libellé exact `Add Polygon Feature` n’ont donc pas pu être confirmés à l’écran. La validation des annotations, couches, rasters et capacité d’édition a été faite par l’API QGIS.

## Fichiers

- Copie propre : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth_CLEAN.qgz`
- Projet d’origine conservé : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth_polygon_layers.qgz`
- GeoPackage Ground Truth conservé sans feature : `backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/annotations/ground_truth_layers.gpkg`

OLD GRAPHIC ANNOTATIONS BEFORE : 35 (polygon)

OLD GRAPHIC ANNOTATIONS AFTER : 0

GROUND TRUTH LAYERS : 6

GROUND TRUTH FEATURES : 0

RGB LAYERS : 6

GROUND TRUTH GEOMETRY : POLYGON

CRS : EPSG:32637

CLEAN PROJECT : backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth_CLEAN.qgz

READY_FOR_MANUAL_GROUND_TRUTH : YES (API validation; visual toolbar label requires desktop confirmation)

MODEL_C : UNCHANGED

MODEL_D : UNCHANGED

TEST SPLIT : UNCHANGED
