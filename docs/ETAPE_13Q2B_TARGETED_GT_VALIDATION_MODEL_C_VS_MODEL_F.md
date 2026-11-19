# ÉTAPE 13Q.2B — Targeted Ground Truth Validation MODEL_C vs MODEL_F

## Périmètre

Validation ciblée sur les six patches TEST 13M déjà réparés et contrôlés. Les images et les masques GT n'ont pas été modifiés. La vérité terrain est `APPROXIMATE_EVALUATION_GROUND_TRUTH`; les scores servent à guider la R&D, pas à annoncer une précision de production.

Les prédictions proviennent des sorties strictement reproductibles de 13Q.1 : même RGB, même grille 512×512, seuil 0,50, et aucun réglage de seuil par catégorie.

## Résultats par contexte

| Contexte | MODEL_C IoU | MODEL_F IoU | MODEL_C rappel | MODEL_F rappel | meilleur |
|---|---:|---:|---:|---:|---|
| Difficult (2 patches) | 0,388 | **0,494** | 0,589 | **0,785** | MODEL_F |
| Industrial (2 patches) | **0,811** | 0,376 | **0,960** | 0,468 | MODEL_C |
| Residential (2 patches) | 0,145 | **0,501** | 0,171 | **0,647** | MODEL_F |
| Global (6 patches) | 0,448 | **0,457** | 0,573 | **0,634** | MODEL_F léger |

MODEL_C conserve la meilleure précision globale (0,586 contre 0,547) et domine nettement les deux patches industriels. MODEL_F améliore le rappel, le Dice et l'IoU global, avec un gain très marqué sur les scènes résidentielles et difficiles. Cette différence de comportement par contexte empêche de conclure à un remplacement universel.

## Détail par patch

Les six lignes détaillées sont conservées dans `backend/data/models/building/experimental/benchmark_13Q1_FINAL/patch_metrics.json`. MODEL_F gagne sur `2024_difficult`, `2024_residential`, `2025_difficult` et `2025_residential`; MODEL_C gagne sur les deux patches industriels.

## Contrôles spatiaux

Les masques et les sorties GeoTIFF gardent la même taille, transform, CRS et bounds que chaque RGB. Aucun décalage pixel n'a été observé. Les sorties sont des overlays d'inspection R&D et ne sont pas injectées dans GeoRaster production.

## Décision

MODEL_F est confirmé comme candidat expérimental intéressant pour les scènes résidentielles et difficiles, mais il n'est pas validé comme modèle universel : sa dégradation industrielle et sa précision globale inférieure imposent un test supplémentaire avec davantage de patches industriels et une revue manuelle des faux positifs. MODEL_C reste le modèle production par défaut.

MODEL_C :
PRODUCTION BASELINE — VALIDATED

MODEL_F :
EXPERIMENTAL CANDIDATE — TARGETED VALIDATION PARTIAL

GROUND TRUTH :
6 APPROXIMATE TEST PATCHES

MODEL_C GLOBAL IOU :
0.448

MODEL_F GLOBAL IOU :
0.457

MODEL_C GLOBAL RECALL :
0.573

MODEL_F GLOBAL RECALL :
0.634

MODEL_C GLOBAL PRECISION :
0.586

MODEL_F GLOBAL PRECISION :
0.547

BEST DIFFICULT / RESIDENTIAL :
MODEL_F

BEST INDUSTRIAL :
MODEL_C

BEST OVERALL :
MODEL_F SLIGHTLY, CONTEXT-DEPENDENT

MODEL_F PRODUCTION :
NO

MODEL_C DEFAULT :
YES

NEXT STEP :
ADDITIONAL MODEL_F INDUSTRIAL/BOUNDARY VALIDATION
