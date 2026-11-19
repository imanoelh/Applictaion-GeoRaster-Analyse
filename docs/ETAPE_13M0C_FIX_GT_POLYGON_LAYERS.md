# ÉTAPE 13M.0C — Couches Ground Truth polygonales éditables

Date : 2026-10-22  
QGIS utilisé pour l'audit et les validations hors interface : **3.40.14-Bratislava**. Aucun modèle, raster, split TEST ni prédiction n'a été modifié ou exécuté. Les anciennes Polygon Annotations n'ont pas été converties ni utilisées.

## Audit des six couches source

Le projet initial `benchmark_13M_test/qgis/13M_locked_test_ground_truth.qgz` contient les six couches nommées `HUMAN_GROUND_TRUTH_EMPTY_<patch_id>`. QGIS 3.40.14 les a toutes ouvertes avec ces propriétés :

| Provider | Geometry type | WKB type | CRS | Editable avant fix | Features |
|---|---|---|---|---|---:|
| OGR | No geometry | NoGeometry | vide/non défini | Non | 0 |

Cela confirme la cause du bouton `Add Record` : les sources sont des GeoJSON vides sans géométrie polygonale déclarée.

## Nouvelles couches

Un GeoPackage UTF-8 a été créé :

`backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/annotations/ground_truth_layers.gpkg`

Il contient les six couches polygonales suivantes, toutes vides au départ :

| Patch | Nom de couche | Geometry/WKB | CRS | Champs |
|---|---|---|---|---|
| 01 — `GT_2024_difficult_02` | `GT_2024_difficult_02_ground_truth` | Polygon | EPSG:32637 | `building_id`, `annotation_status`, `review_status`, `annotator` |
| 02 — `GT_2024_industrial_02` | `GT_2024_industrial_02_ground_truth` | Polygon | EPSG:32637 | mêmes champs |
| 03 — `GT_2024_residential_02` | `GT_2024_residential_02_ground_truth` | Polygon | EPSG:32637 | mêmes champs |
| 04 — `GT_2025_difficult_02` | `GT_2025_difficult_02_ground_truth` | Polygon | EPSG:32637 | mêmes champs |
| 05 — `GT_2025_industrial_02` | `GT_2025_industrial_02_ground_truth` | Polygon | EPSG:32637 | mêmes champs |
| 06 — `GT_2025_residential_02` | `GT_2025_residential_02_ground_truth` | Polygon | EPSG:32637 | mêmes champs |

Les valeurs par défaut du formulaire QGIS sont configurées dans le projet pour les nouvelles entités : `annotation_status = ANNOTATED` et `review_status = NOT_REVIEWED`. Aucun bâtiment n'a été ajouté aux couches réelles.

## Projet QGIS

Le projet dérivé est :

`backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/qgis/13M_locked_test_ground_truth_polygon_layers.qgz`

Il remplace seulement les six couches Ground Truth par leurs nouvelles sources GPKG et conserve les six groupes, l'ordre 01–06, les six rasters RGB, le CRS de projet et les six bookmarks. Le projet source reste disponible séparément. Les fichiers GeoJSON vides sont conservés en tant que templates et n'ont pas été écrasés.

QGIS 3.40.14 a relu le projet dérivé : les six couches sont valides, de type Polygon, en EPSG:32637, ont zéro feature, et les six couches RGB sont toujours présentes. La capacité OGR `AddFeatures` est disponible et `startEditing()` fonctionne pour chacune.

### Vérification de persistance

Dans un GeoPackage temporaire distinct du dataset réel, le test QGIS a donné :

- avant édition : 0 feature ;
- ajout d'un polygone test et `commitChanges()` ;
- fermeture/réouverture de la couche : 1 feature persistée dans le fichier ;
- suppression de cette feature, commit, puis nouvelle réouverture : 0 feature.

Le GeoPackage temporaire a été retiré. Les six couches Ground Truth réelles restent vides.

### Vérification de la barre d'outils

La géométrie Polygon et l'édition ont été confirmées avec l'API de QGIS 3.40.14. La vérification visuelle du libellé `Add Polygon Feature` dans la barre d'outils n'a pas été terminée : l'automatisation de l'interface s'est arrêtée lorsque la touche Échap physique a été détectée. Le projet dérivé n'a pas été ouvert dans l'interface durant la suite de ce contrôle. À son ouverture, sélectionner une couche `*_ground_truth` pour activer les outils de numérisation polygonale.

## État final

OLD LAYER GEOMETRY TYPE :
NoGeometry / Unknown; OGR; CRS non défini; non éditable; 0 feature pour les 6 couches

NEW LAYER GEOMETRY TYPE :
POLYGON

CRS :
EPSG:32637

QGIS ADD POLYGON FEATURE :
AVAILABLE — géométrie Polygon et capacité d'ajout confirmées via QGIS API; libellé visuel non observé

TEST FEATURE PERSISTENCE :
VALIDATED — 0 → 1 après réouverture → 0 après suppression et réouverture, sur couche temporaire

GROUND TRUTH LAYERS :
6

MODEL_C :
UNCHANGED

MODEL_D :
UNCHANGED

TEST SPLIT :
UNCHANGED

READY_FOR_MANUAL_DIGITIZING :
YES — ouvrir `13M_locked_test_ground_truth_polygon_layers.qgz` et sélectionner la couche Ground Truth du patch voulu
