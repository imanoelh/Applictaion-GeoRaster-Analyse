# ÉTAPE 13Q.1 — Final Deep Benchmark of Building Footprint Models

## Exécution

Benchmark R&D isolé sur les six patches TEST 13M, sans modification du registre, des adapters, du frontend, des rasters sources ou de MODEL_C. Les sorties sont sous `backend/data/models/building/experimental/benchmark_13Q1_FINAL/`.

Environnement : Python backend avec `transformers 4.46.3` ajouté uniquement dans `.venv_13q1`, PyTorch CPU existant, ONNX Runtime CPU. Aucun `requirements.txt` de production n'a été modifié.

## Validation des candidats

### MODEL_F

Le checkpoint est un SegFormer B0 (`hidden_sizes=[32,64,160,256]`, quatre stages, tête binaire). Le prétraitement utilisé est RGB `/255`, conformément au pipeline SpaceNet documenté. Le chargement strict a réussi avec `missing_keys=0`, `unexpected_keys=0`. La sortie native 128×128 a été remise à 512×512 par interpolation bilinéaire uniquement pour comparer la grille source.

### MODEL_G

Le graphe ONNX est chargeable et produit `[1,3,256,256]`. La documentation officielle décrit une probabilité bâtiment, mais n'identifie pas la sémantique de chacun des trois canaux. L'inspection du graphe et de ses métadonnées ne permet pas de déterminer de façon reproductible le canal bâtiment ni la transformation (sigmoid, softmax ou autre). MODEL_G est donc **FAILED pour le benchmark qualité**, sans appliquer d'activation arbitraire.

### MODEL_H

Le même checkpoint, preprocessing et tiling validés en 13Q ont été réutilisés sans réglage supplémentaire.

## Résultats pixel à seuil 0,50

| Modèle | IoU | Dice/F1 | Précision | Rappel |
|---|---:|---:|---:|---:|
| MODEL_C | 0,448 | 0,557 | **0,586** | 0,573 |
| MODEL_F | **0,457** | **0,582** | 0,547 | **0,634** |
| MODEL_G | — | — | — | — |
| MODEL_H | 0,310 | 0,420 | 0,344 | 0,556 |

Ces métriques utilisent `APPROXIMATE_EVALUATION_GROUND_TRUTH`; elles sont exploratoires et ne constituent pas une validation scientifique finale. MODEL_F améliore légèrement IoU, Dice et rappel de C, avec une baisse de précision. Les métriques de contour et objet doivent être recalculées avec le canal G officiellement documenté avant toute décision de production.

## Sorties

Pour C, F et H : cartes de probabilité, masques binaires et overlays par patch. Pour G : diagnostics logits par tuile, sans conversion en masque. Une planche de comparaison est disponible dans le dossier expérimental.

## Décision R&D

MODEL_F est le **primary finalist provisoire** sur le critère combiné IoU/rappel/Dice. MODEL_C est le **secondary finalist de référence** car il reste le modèle production stable. MODEL_H est écarté de cette sélection pour résultats pixel inférieurs et couverture très bruitée. MODEL_G est bloqué techniquement jusqu'à clarification officielle des trois canaux.

---

MODEL_C :
VALIDATED

MODEL_F :
VALIDATED

MODEL_G :
FAILED

MODEL_H :
VALIDATED

MODEL_F ARCHITECTURE :
SegFormer B0, backbone MiT-B0, tête binaire, RGB /255, sortie native 128×128

MODEL_G OUTPUT SEMANTICS :
UNRESOLVED — 3 logits [1,3,256,256], canal bâtiment et activation non documentés

MODEL_C IOU :
0.448 exploratory

MODEL_F IOU :
0.457 exploratory

MODEL_G IOU :
NOT COMPUTED — FAILED SEMANTICS

MODEL_H IOU :
0.310 exploratory

MODEL_C RECALL :
0.573 exploratory

MODEL_F RECALL :
0.634 exploratory

MODEL_G RECALL :
NOT COMPUTED

MODEL_H RECALL :
0.556 exploratory

MODEL_C PRECISION :
0.586 exploratory

MODEL_F PRECISION :
0.547 exploratory

MODEL_G PRECISION :
NOT COMPUTED

MODEL_H PRECISION :
0.344 exploratory

BEST BUILDING DETECTION :
MODEL_F (provisional, higher recall)

BEST BUILDING LOCATION :
MODEL_F (provisional visual/pixel assessment)

BEST SMALL BUILDINGS :
NOT DETERMINED — object matching not finalized

BEST DENSE URBAN :
MODEL_F provisional

BEST BUILDING SEPARATION :
NOT DETERMINED

BEST LARGE ROOFS :
MODEL_F provisional

BEST COMPLEX ROOFS :
NOT DETERMINED

BEST BOUNDARY ALIGNMENT :
NOT DETERMINED — approximate GT and G semantics blocker

LOWEST FALSE POSITIVES :
MODEL_C (highest precision)

LOWEST MISSED BUILDINGS :
MODEL_F (highest recall)

BEST OBJECT-LEVEL RESULT :
NOT DETERMINED

BEST OVERALL BUILDING FOOTPRINT QUALITY :
MODEL_F PROVISIONAL

PRIMARY FINALIST :
MODEL_F

SECONDARY FINALIST :
MODEL_C

PRODUCTION MODIFIED :
NO

MODEL_C DEFAULT :
YES

4096 TEST :
NOT_RUN

FULL RASTER :
NOT_RUN

NEXT STEP :
13Q.2 FINALIST REAL ORTHOPHOTO 2048/4096 TEST
