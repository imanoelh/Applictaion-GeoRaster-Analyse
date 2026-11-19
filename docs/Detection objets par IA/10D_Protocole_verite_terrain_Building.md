# Étape 10D — Protocole de vérité terrain Building Maxar

Date : 14 octobre 2026  
Portée : préparer une annotation humaine reproductible et les outils d’évaluation du modèle Building actuel.  
Décisions respectées : aucun fine-tuning, aucun changement de checkpoint, aucun changement de seuil/post-processing, aucune modification du pipeline IA, aucun module Building Change Detection.

## 1. État des données

L’audit de `test-data/`, `test-data/validation-results/` et des données fournies ne trouve aucun SHP, GeoPackage ou GeoJSON de bâtiments de référence. Les GeoJSON existants sont des sorties IA de diagnostic ou des données de test générales ; ils ne sont pas utilisés comme vérité terrain.

```text
GROUND_TRUTH_SOURCE = MANUAL_ANNOTATION_REQUIRED
GROUND_TRUTH = À ANNOTER
```

Les références visuelles officielles pour l’annotation sont uniquement les GeoTIFF géoréférencés Maxar RGB `p2–p98` :

- `test-data/validation-results/maxar_rgb_derivatives/maxar_2024_rgb_p2p98.tif` ;
- `test-data/validation-results/maxar_rgb_derivatives/maxar_2025_rgb_p2p98.tif`.

Les PNG quicklook et les polygones IA ne sont jamais la source géographique ni la vérité terrain.

## 2. Patches préparés

Le script `backend/scripts/prepare_building_ground_truth.py` crée 8 patches par date, soit 16 au total. Chaque patch fait 512 × 512 pixels à 0,35 m, donc environ 179,2 × 179,2 m, en EPSG:32637. Les fenêtres sont extraites sans reprojeter ni dupliquer le COG original complet.

| Date | Patches | TRAIN | VALIDATION | TEST |
|---|---:|---:|---:|---:|
| 2024 | 8 | 3 | 2 | 3 |
| 2025 | 8 | 3 | 2 | 3 |

Contextes proposés, à vérifier visuellement par l’annotateur :

- `urban_dense` : tissu urbain dense ;
- `residential` : bâtiments résidentiels plus isolés ;
- `industrial` : grands bâtiments, hangars ou installations ;
- `difficult_context` : sol nu, routes, ombres, végétation ou surfaces ambiguës.

Les groupes sont disjoints spatialement et ne sont pas créés par tirage aléatoire de tuiles adjacentes. Le catalogue conserve `patch_id`, date, contexte proposé, split, fenêtre raster, bounds, CRS, résolution, largeur, hauteur et source.

Catalogue : `test-data/building-ground-truth/patch_catalog.json`.

## 3. Format et schéma

Le format de travail retenu est GeoJSON en EPSG:32637, car Fiona/OGR n’est pas nécessaire sur cette machine et QGIS/ArcGIS l’ouvrent directement. Un GeoPackage pourra être exporté après annotation si l’environnement SIG l’exige.

Chaque objet doit être `Polygon` ou `MultiPolygon` avec uniquement le schéma minimal :

```text
building_ref_id : string, unique dans tout le dataset
patch_id        : string
date            : string (2024 ou 2025)
source          : string
annotation_status : string
annotator       : string
notes           : string
```

Les 16 fichiers GeoJSON générés sont des `FeatureCollection` vides. Aucun polygone n’a été inventé.

## 4. Règles d’annotation

L’annotateur travaille d’abord sur l’orthophoto, sans prédictions IA visibles comme guide principal, afin de préserver les faux négatifs mesurables.

- dessiner l’empreinte visible de la toiture/bâtiment ;
- séparer deux bâtiments seulement si une séparation physique est observable ;
- garder une empreinte unique pour un ensemble contigu indissociable et le noter ;
- inclure annexes et petits abris clairement bâtis ;
- exclure routes, véhicules, conteneurs temporaires, tas, sols nus et ombres seules ;
- pour une partie occultée, dessiner seulement la partie certaine et noter `OCCLUDED` ;
- pour une construction en cours, annoter la partie construite et noter `UNDER_CONSTRUCTION` ;
- annoter 2024 et 2025 séparément, sans copier automatiquement les géométries d’une date à l’autre.

Guide détaillé QGIS/ArcGIS : `test-data/building-ground-truth/README_ANNOTATION.md`.

## 5. Contrôle qualité

Le validateur `backend/scripts/validate_building_ground_truth.py` vérifie :

- FeatureCollection et CRS EPSG:32637 ;
- propriétés requises et cohérence `patch_id/date` ;
- IDs uniques ;
- géométries Polygon/MultiPolygon non vides et valides ;
- absence de self-intersection ;
- géométries contenues dans l’emprise du patch ;
- absence de doublons structurels.

Commande :

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\validate_building_ground_truth.py
```

Résultat actuel : `VALID`, 16 patches contrôlés, 0 feature contrôlée, 0 bâtiment, 16 avertissements « annotation humaine requise ». `VALID` signifie que les templates sont corrects ; cela ne signifie pas que le ground truth existe.

## 6. Outil d’évaluation prêt après annotation

`backend/scripts/building_ground_truth_metrics.py` fournit :

- TP, FP, FN, TN pixels ;
- Precision, Recall, F1 et IoU avec divisions par zéro gérées ;
- IoU d’objets ;
- matching one-to-one déterministe : tri par IoU décroissant puis index prédiction/référence ;
- TP/FP/FN objets ;
- compteurs `MERGED_DETECTION` et `SPLIT_DETECTION` ;
- classes de taille provisoires (`small <25 m²`, `medium <100 m²`, `large ≥100 m²`) explicitement non définitives.

`backend/scripts/evaluate_building_ground_truth.py` rasterise prédictions et référence dans la grille du GeoTIFF, reprojette les géométries dans le CRS du raster, puis calcule les métriques. Il refuse de produire des scores lorsque le GeoJSON de référence est vide :

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\evaluate_building_ground_truth.py `
  --prediction <prediction.geojson> `
  --reference <GT_patch.geojson> `
  --raster <maxar_rgb_p2p98.tif>
```

Les résultats futurs devront être ventilés par `urban_dense`, `residential`, `industrial`, `difficult_context`, puis par classes de taille. Les seuils d’IoU (initialement 0,50) et de taille sont des paramètres de rapport, non des règles métier figées.

## 7. Baseline et séparation future

Avant toute optimisation, le baseline à conserver est :

```text
MODEL          = unet_best.pt
RGB            = Maxar bands 5/3/2
STRETCH        = p2–p98 par canal
THRESHOLD      = 0.50
POSTPROCESSING = configuration actuelle
```

Le TEST restera indépendant. Le choix futur du seuil, de `min_object_pixels`, de la morphologie, des epochs ou du learning rate se fera sur TRAIN/VALIDATION uniquement. Aucune métrique baseline n’est disponible aujourd’hui : aucun bâtiment humain n’est annoté.

## 8. Décision scientifique actuelle

L’étape 10C suggère un domain gap, mais cette hypothèse reste à mesurer. Il est interdit de déclarer le fine-tuning scientifiquement nécessaire avant le baseline annoté. Il est également interdit de lancer Building Change Detection avant une validation mono-date suffisante sur 2024 et 2025.

## 9. Tests

- tests spécifiques 10D métriques/validation : 7 passed ;
- backend complet après ajout des outils : 209 passed, 0 failed ;
- aucun composant de production IA ou frontend modifié.

ÉTAPE 10D — STATUT :
BLOQUÉE PAR ANNOTATION

GROUND TRUTH :
À ANNOTER

ANNOTATION PROTOCOL :
VALIDÉ

TRAIN SPLIT :
NON PRÊT

VALIDATION SPLIT :
NON PRÊT

TEST SPLIT :
NON PRÊT

BASELINE METRICS :
NON DISPONIBLES

MODEL DOMAIN GAP :
À MESURER

PRÊT POUR FINE-TUNING :
NON

PRÊT POUR BUILDING CHANGE DETECTION :
NON
