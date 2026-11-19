# ÉTAPE 14A.12 — HYBRID TEACHER REFINEMENT

## Décision

Un seul cycle C9 a été exécuté à partir de C8. La préparation, la qualité DIST3_ONLY, les négatifs difficiles et la calibration ont utilisé uniquement les 16 patches non-GOLD. Le GOLD a été utilisé une seule fois après freeze, pour l’évaluation finale. `MODEL_C` reste production.

## Préparation

- Hard-negative pool V2 : `2661659` pixels non-GOLD, provenant de l'accord background C6/DIST3/flip ; aucun masque GOLD n'a été ajouté au train.
- DIST3_ONLY : `247` HIGH, `6` MEDIUM, `0` LOW exclus.
- Qualité : `0.35 confidence + 0.30 augmentation_consistency + 0.20 rectangularity_proxy + 0.10 aspect_plausibility + 0.05 area_prior`. Edge density et contexte sémantique restent indisponibles ; ces scores sont des proxies.
- Les 37 FP GOLD C8 ont été classés à titre diagnostique seulement : `{"INDUSTRIAL_TEXTURE": 37}`. Cette analyse n'a modifié aucun seuil et n'a pas alimenté le train.
- Small/dense patches sur-échantillonnés dans TRAIN. Les géométries et les splits sont inchangés.

## Entraînement et calibration

C9 initialise le checkpoint C8 epoch 2. Loss : Focal gamma=2 + Dice pondérée ; learning rates backbone `1e-5`, tête `5e-5`, weight decay `1e-4`, clipping1, batch1, native512, BN gelées. Trois epochs ont été réalisées. Les probabilités DEV ont été évaluées avec une grille : seuils `[0.35, 0.45, 0.5, 0.55]`, minimums `[16, 32, 64, 128]`, morphologies `['NONE', 'OPEN3']`. La fonction de sélection est : `F1 + 0.50*small_recall - 0.015*FP + 0.25*boundary_f1`.

Freeze DEV : epoch `2`, seuil `0.35`, minimum `128`, morphologie `OPEN3`, merge threshold `0.6`. DEV F1 `0.4622`, FP `34`, small `7/51`. Les labels DEV sont pseudo-labels hybrides, pas une vérité terrain humaine.

## GOLD final

Matching one-to-one IoU >= 0.30, sans réutilisation d'une prédiction. Les 165 bâtiments GOLD ont été lus en mode immuable. C9 : F1 `0.4308`, précision `0.5895`, recall `0.3394`, FP `39`, manqués `109`, small `1/38`, Boundary F1 `0.2493`, CPU `5.407s/patch`. Le score est reproductible depuis `gold_evaluation/FINAL_RESULT.json`.

| Modèle | TP | FP | FN | F1 | Recall | Small | Boundary F1 | CPU s/patch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MODEL_C6 | 37 | 11 | 128 | 0.3474 | 0.2242 | 0 | 0.2829 | 6.060 |
| MODEL_C8_HYBRID | 54 | 37 | 111 | 0.4219 | 0.3273 | 3 | 0.3364 | 6.360 |
| UNET_DIST3 | 116 | 128 | 49 | 0.5672 | 0.7030 | 14 | 0.5020 | 1.213 |
| MODEL_C9_HYBRID_REFINED | 56 | 39 | 109 | 0.4308 | 0.3394 | 1 | 0.2493 | 5.407 |

## Gate staging

`{"f1_gt_c8": true, "recall_non_degraded": true, "fp_lower": false, "small_recall_higher": false, "boundary_stable": false, "cpu_acceptable": true}`. C9 dépasse C8 en F1 et recall, mais les FP passent de `37` à `39`, les petits bâtiments passent de `3/38` à `1/38`, et Boundary F1 baisse de `0.3364` à `0.2493`. C9 n'est donc pas prêt pour staging.

## Intégrité

Les `78` fichiers GOLD sont inchangés. C6, C7, C8, DIST3, MODEL_C et la production n'ont pas été modifiés. Aucun entraînement GOLD, aucune calibration GOLD et aucun remplacement de production n'ont été réalisés.

Artefacts : `14A12_refinement_pipeline/diagnostic`, `hard_negative_pool_v2`, `models`, `calibration`, `gold_evaluation`, `14A12_global_comparison.csv`.

NEW MODEL :
MODEL_C9_HYBRID_REFINED

TRAIN HARD NEGATIVES :
2661659 pixels non-GOLD

DIST3_ONLY_HIGH :
247

DIST3_ONLY_MEDIUM :
6

DIST3_ONLY_LOW_EXCLUDED :
0

DEV F1 :
0.4622

DEV FP :
34

GOLD F1 :
0.4308

GOLD PRECISION :
0.5895

GOLD RECALL :
0.3394

GOLD FP :
39

GOLD MISSED :
109

GOLD SMALL RECALL :
1 / 38

GOLD BOUNDARY F1 :
0.2493

C8 F1 :
0.4219

UNET_DIST3 F1 :
0.5672

C9 BETTER THAN C8 :
YES

C9 READY FOR STAGING :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
14A13_SPECIALIZED_MODEL_FUSION_V2
