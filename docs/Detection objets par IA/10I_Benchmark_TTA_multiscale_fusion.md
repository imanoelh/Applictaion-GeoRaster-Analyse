# Étape 10I — Benchmark TTA, multi-scale et fusion probabiliste

Date : 14 octobre 2026

## Cadre expérimental

Le checkpoint `unet_best.pt`, le preprocessing Maxar RGB p2-p98, le tilage `640` avec overlap `20 %`, le post-traitement et le threshold `0,50` sont restés inchangés. Les quatre modes ont été exécutés sur les mêmes dérivés 2024/2025 et la même emprise. Aucune vérité terrain n’étant disponible, les nombres ci-dessous sont des observations techniques et qualitatives, pas des mesures de précision.

- STANDARD : une prédiction par tuile.
- TTA : original, flip horizontal, flip vertical, rotation 90°, puis moyenne des quatre probability maps après inversion.
- MULTI_SCALE : échelles 0,75, 1,00, 1,25, remises sur la grille 640 × 640 puis moyenne probabiliste.
- ENHANCED : TTA complet à l’échelle 1,00 + original aux échelles 0,75 et 1,25. Ce compromis limite le coût à six prédictions par tuile.

Les masks `valid_mask` et les pixels NoData/padding sont remis à zéro après chaque transformation et après la fusion. La fusion intervient avant le threshold et la fusion globale des overlaps reste inchangée.

## Résultats 2024

| Mode | Candidats | Pixels positifs | Ratio | Surface totale m² | Temps | Facteur CPU |
|---|---:|---:|---:|---:|---:|---:|
| STANDARD | 13 | 5 214 | 0,1243 % | 638,715 | 23,2 s | 1,00× |
| TTA | 12 | 4 331 | 0,1033 % | 530,548 | 64,9 s | 2,79× |
| MULTI_SCALE | 2 | 1 944 | 0,0463 % | 238,140 | 50,6 s | 2,18× |
| ENHANCED | 5 | 3 254 | 0,0776 % | 398,615 | 101,8 s | 4,39× |

## Résultats 2025

| Mode | Candidats | Pixels positifs | Ratio | Surface totale m² | Temps | Facteur CPU |
|---|---:|---:|---:|---:|---:|---:|
| STANDARD | 22 | 7 190 | 0,1714 % | 880,775 | 19,1 s | 1,00× |
| TTA | 19 | 5 137 | 0,1225 % | 629,283 | 74,5 s | 3,90× |
| MULTI_SCALE | 0 | 0 | 0 % | — | 53,8 s | 2,82× |
| ENHANCED | 6 | 2 482 | 0,0592 % | 304,045 | 106,2 s | 5,56× |

Mémoire globale estimée par le post-traitement : 67 108 864 octets pour chaque mode et chaque date. Le nombre de tuiles traitées est identique ; seules les prédictions par tuile sont multipliées.

## Inspection qualitative

Les comparatifs sont disponibles dans `test-data/validation-results/enhanced-inference-benchmark/comparison_2024.png` et `comparison_2025.png`, avec un overlay par mode. TTA produit moins de candidats et moins de pixels positifs ; aucune récupération visuelle nette de bâtiments manqués n’est démontrée. MULTI_SCALE est trop conservateur sur ces scènes et supprime presque tout le signal, jusqu’à zéro candidat en 2025. ENHANCED reste plus conservateur que STANDARD tout en coûtant environ 4,4 à 5,6 fois plus cher. La fragmentation apparente diminue avec le nombre de candidats, mais sans référence annotée cela ne permet pas de distinguer une meilleure cohérence d’un excès de faux négatifs.

Conclusion qualitative : aucune variante ne justifie le remplacement automatique de STANDARD. Le mode STANDARD reste la référence opérationnelle ; TTA, MULTI_SCALE et ENHANCED restent des modes expérimentaux internes non exposés au frontend.

## Tests et non-régression

- Tests d’inversion flip horizontal, flip vertical et rotation 90° : passés.
- Tests de dimensions, grille exacte, valid mask, padding, fusion moyenne et absence de NaN/Inf : passés.
- Benchmark 2024/2025 : terminé.
- Backend : `214 passed, 0 failed`.
- Le frontend n’a pas été modifié pour exposer ces modes ; les builds/tests frontend précédemment validés restent applicables.
- Checkpoint inchangé ; aucun fine-tuning et aucune pseudo-labelisation.

Artefacts :

- `test-data/validation-results/enhanced-inference-benchmark/benchmark_summary.json`
- `test-data/validation-results/enhanced-inference-benchmark/{2024,2025}/*_standard.png`
- `test-data/validation-results/enhanced-inference-benchmark/{2024,2025}/*_tta.png`
- `test-data/validation-results/enhanced-inference-benchmark/{2024,2025}/*_multi_scale.png`
- `test-data/validation-results/enhanced-inference-benchmark/{2024,2025}/*_enhanced.png`

## ÉTAPE 10I — STATUT :
VALIDÉE

STANDARD :
VALIDÉ

TTA :
VALIDÉ

MULTI_SCALE :
VALIDÉ

ENHANCED :
VALIDÉ

BEST QUALITATIVE MODE :
STANDARD

CPU COST :
ÉLEVÉ

MODEL CHECKPOINT :
INCHANGÉ

GROUND TRUTH :
ABSENTE

SCIENTIFIC ACCURACY :
NON VALIDÉE

PROMOTION :
AUCUNE

BACKEND REGRESSION :
AUCUNE

PRÊT POUR ÉTAPE SUIVANTE :
NON
