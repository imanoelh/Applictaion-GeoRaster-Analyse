# Étape 10G — Audit ground truth et préparation du fine-tuning

Date : 14 octobre 2026

## Décision immédiate

Le répertoire `test-data/building-ground-truth/` contient bien les supports de validation, mais aucune annotation humaine exploitable. Les 16 fichiers GeoJSON sont des `FeatureCollection` vides : 8 patches 2024 et 8 patches 2025. Aucun entraînement, fine-tuning, choix de seuil ou comparaison scientifique n’a donc été lancé.

## Inventaire

| Élément | Résultat |
|---|---:|
| Patches catalogue | 16 |
| Patches 2024 | 8 |
| Patches 2025 | 8 |
| Patches TRAIN proposés | 8 |
| Patches VALIDATION proposés | 4 |
| Patches TEST proposés | 4 |
| GeoTIFF 512 × 512 présents | 16 |
| GeoJSON présents | 16 |
| Fichiers d’annotation non vides | 0 |
| Bâtiments annotés | 0 |
| Polygones invalides détectés | 0 (aucune géométrie à contrôler) |
| IDs dupliqués | 0 |
| Fichiers manquants | 0 |

Le catalogue déclare `status=EMPTY_TEMPLATES_ONLY`, `ground_truth_source=MANUAL_ANNOTATION_REQUIRED`, CRS `EPSG:32637` et résolution `0,35 m`. Les contextes proposés sont `urban_dense`, `residential`, `industrial` et `difficult_context`.

Validation exécutée par `backend/scripts/validate_building_ground_truth.py` : statut structurel `VALID`, `checked_features=0`, `building_count=0`, avec un avertissement d’annotation humaine requise pour chacun des 16 patches.

## Conséquence scientifique

Le dataset n’est pas suffisant pour un fine-tuning : il ne contient actuellement aucune vérité terrain. Les splits TRAIN/VALIDATION/TEST présents dans le catalogue sont uniquement des propositions géographiques ; ils ne peuvent pas être utilisés pour mesurer le modèle tant que les annotations ne sont pas remplies et contrôlées.

Il est interdit de convertir les 13/22 candidats produits par l’IA en vérité terrain. Aucune précision, rappel, F1, IoU pixel ou métrique objet n’est calculée, afin de ne pas fabriquer de résultats scientifiques.

## Préparation recommandée après annotation

1. Annoter les bâtiments visibles dans les 16 patches avec des Polygon/MultiPolygon dans `EPSG:32637`.
2. Renseigner au minimum `building_ref_id`, `patch_id`, `date` et `source` pour chaque feature.
3. Contrôler validité, géométrie vide, doublons, emprise et cohérence date/image.
4. Conserver les zones géographiques TEST intactes et ne jamais les utiliser pour choisir epochs, loss, augmentations ou threshold.
5. Recalculer le manifest, rasteriser les masques sur la grille exacte, puis seulement exécuter la baseline `unet_best.pt`.
6. Décider ensuite, avec les métriques VALIDATION, si un fine-tuning prudent est justifié.

Aucun fichier frontend, LocalRasterSource, TilingService, checkpoint de production, export ou analyse historique n’a été modifié. Aucun modèle n’a été entraîné et `unet_best.pt` reste le modèle de production.

## ÉTAPE 10G — STATUT :
BLOQUÉE

GROUND TRUTH :
ABSENTE

DATASET :
NON PRÊT

BASELINE EVALUATION :
NON RÉALISÉE

TRAINING :
NON RÉALISÉ

BASELINE MODEL :
unet_best.pt

FINE-TUNED MODEL :
AUCUN

BEST THRESHOLD :
NON DISPONIBLE

PIXEL PRECISION BEFORE :
NON DISPONIBLE — aucune vérité terrain

PIXEL RECALL BEFORE :
NON DISPONIBLE — aucune vérité terrain

PIXEL F1 BEFORE :
NON DISPONIBLE — aucune vérité terrain

PIXEL IOU BEFORE :
NON DISPONIBLE — aucune vérité terrain

PIXEL PRECISION AFTER :
NON DISPONIBLE — aucun entraînement

PIXEL RECALL AFTER :
NON DISPONIBLE — aucun entraînement

PIXEL F1 AFTER :
NON DISPONIBLE — aucun entraînement

PIXEL IOU AFTER :
NON DISPONIBLE — aucun entraînement

OBJECT PRECISION BEFORE :
NON DISPONIBLE — aucune vérité terrain

OBJECT RECALL BEFORE :
NON DISPONIBLE — aucune vérité terrain

OBJECT F1 BEFORE :
NON DISPONIBLE — aucune vérité terrain

OBJECT PRECISION AFTER :
NON DISPONIBLE — aucun entraînement

OBJECT RECALL AFTER :
NON DISPONIBLE — aucun entraînement

OBJECT F1 AFTER :
NON DISPONIBLE — aucun entraînement

MODEL DOMAIN GAP :
NON CONFIRMÉ — hypothèse technique non mesurable sans annotations

MODEL PROMOTION :
NON RECOMMANDÉE

PRODUCTION MODEL CHANGED :
NON

BACKEND REGRESSION :
AUCUNE

PRÊT POUR BUILDING CHANGE DETECTION :
NON
