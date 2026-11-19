# ÉTAPE 14A.13 — SPECIALIZED MODEL FUSION V2

## Résultat

Fusion inference-level sans entraînement C10. DIST3 est le générateur primaire ; C6, C8 et C9 sont des validateurs. Les poids et seuils ont été choisis exclusivement sur les quatre patches DEV non-GOLD, puis figés avant le GOLD.

Configuration figée : support `0.65`, contexte FP `<0.25`, small confidence `0.85`. Fonction DEV : `F1 + 0.50*small_recall - 0.015*FP + 0.25*boundary_f1`.

DEV : F1 `0.3053`, recall `0.1946`, FP `12`, small `15/51`. Le choix favorise fortement les frontières et les petits objets mais s’est révélé trop conservateur sur le GOLD.

Le GOLD a été exécuté une seule fois après freeze. Matching objet one-to-one IoU>=0.30. Les 165 GT GOLD et les modèles précédents restent inchangés.

| Modèle | TP | FP | FN | Précision | Recall | F1 | Small | Boundary F1 | CPU s/patch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MODEL_C6 | 37 | 11 | 128 | 0.7708 | 0.2242 | 0.3474 | 0 | 0.2829 | 6.060 |
| MODEL_C8_HYBRID | 54 | 37 | 111 | 0.5934 | 0.3273 | 0.4219 | 3 | 0.3364 | 6.360 |
| MODEL_C9_HYBRID_REFINED | 56 | 39 | 109 | 0.5895 | 0.3394 | 0.4308 | 1 | 0.2493 | 5.407 |
| UNET_DIST3 | 116 | 128 | 49 | 0.4754 | 0.7030 | 0.5672 | 14 | 0.5020 | 1.213 |
| SPECIALIZED_FUSION_V2 | 18 | 16 | 147 | 0.5294 | 0.1091 | 0.1809 | 4 | 0.0812 | 0.507 |

Fusion : 18 TP, 16 FP, 147 manqués, F1 `0.1809`, recall `0.1091`, small `4/38`, boundary `0.0812`, CPU `0.507s/patch`. Elle réduit les FP DIST3 de 128 à 16, mais perd trop de recall et de petits bâtiments. Les candidats rejetés sont exportés dans `14A13_dist3_rejected_candidates.csv`; les objets gardés dans `14A13_fused_objects.csv`.

La fusion ne satisfait pas : F1> C9, recall> C9, small recall> C8, boundary> C9. Le résultat suggère qu’un filtrage de validation pixel-level ne suffit pas à préserver la séparation et le recall des instances DIST3.

## Intégrité

GOLD files inchangés : `78`. Aucun C10 entraîné. Aucun changement de MODEL_C production, backend, frontend, GEE, indices ou exports.

FUSION ENGINE :
SPECIALIZED_FUSION_V2

PRIMARY DETECTOR :
UNET_DIST3

VALIDATORS :
C6 / C8 / C9

DEV F1 :
0.3053

DEV RECALL :
0.1946

DEV FP :
12

GOLD F1 :
0.1809

GOLD PRECISION :
0.5294

GOLD RECALL :
0.1091

GOLD FP :
16

GOLD MISSED :
147

GOLD SMALL RECALL :
4 / 38

GOLD BOUNDARY F1 :
0.0812

GOLD FRAGMENTED :
1 (stored fusion masks, one-to-one audit)

CPU TOTAL TIME :
2.029s total, 0.507s/patch

C9 F1 :
0.4308

DIST3 F1 :
0.5672

FUSION BETTER THAN C9 :
NO

FUSION FP LOWER THAN DIST3 :
YES

FUSION SMALL RECALL BETTER THAN C9 :
YES

READY FOR STAGING :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
14A14_INSTANCE_BOUNDARY_ARCHITECTURE
