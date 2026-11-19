# ÉTAPE 14A.2B — MINIMAL HIGH-QUALITY SEED GROUND TRUTH

Sélection de cinq patches TRAIN parmi les seize disponibles. Les patches VAL, les tests verrouillés et les deux patches 14A.1D4 sont exclus. Les couches Seed Ground Truth sont créées vides et éditables; aucune annotation automatique n'est validée.

## 14A2_2025_13
- Catégorie : RESIDENTIAL LOW DENSITY
- Pourquoi : Very sparse MODEL_C foreground with substantially broader MODEL_F coverage; useful for missed small or low contrast homes.
- MODEL_C foreground : 0.006924
- MODEL_F foreground : 0.19899
- Désaccord C/F : 0.20116
- Difficulté attendue : LOW

## 14A2_2024_13
- Catégorie : RESIDENTIAL DENSE
- Pourquoi : Residential patch with high foreground ratios and strong model disagreement; covers dense roof patterns.
- MODEL_C foreground : 0.165802
- MODEL_F foreground : 0.360115
- Désaccord C/F : 0.262932
- Difficulté attendue : HIGH

## 14A2_2024_15
- Catégorie : INDUSTRIAL / LARGE ROOFS
- Pourquoi : Largest industrial roof coverage with close C/F foreground ratios; representative of large regular roofs.
- MODEL_C foreground : 0.194416
- MODEL_F foreground : 0.183292
- Désaccord C/F : 0.0382
- Difficulté attendue : MEDIUM

## 14A2_2025_14
- Catégorie : COMPLEX URBAN
- Pourquoi : Dense urban morphology with high candidate density and substantial disagreement.
- MODEL_C foreground : 0.153255
- MODEL_F foreground : 0.212494
- Désaccord C/F : 0.14249
- Difficulté attendue : HIGH

## 14A2_2024_12
- Catégorie : SMALL BUILDINGS / SHADOWS
- Pourquoi : Very low MODEL_C foreground, low contrast RGB and extra MODEL_F detections; difficult review case.
- MODEL_C foreground : 0.000771
- MODEL_F foreground : 0.031494
- Désaccord C/F : 0.031082
- Difficulté attendue : LOW

TRAIN PATCHES AVAILABLE :
16

SEED PATCHES SELECTED :
5

SEED PATCH IDS :
14A2_2025_13, 14A2_2024_13, 14A2_2024_15, 14A2_2025_14, 14A2_2024_12

RESIDENTIAL LOW DENSITY :
14A2_2025_13

RESIDENTIAL DENSE :
14A2_2024_13

INDUSTRIAL / LARGE ROOFS :
14A2_2024_15

COMPLEX URBAN :
14A2_2025_14

SMALL BUILDINGS / SHADOWS :
14A2_2024_12

VAL PATCHES USED :
0

LOCKED TEST PATCHES USED :
0

LEGACY TEST LEAKAGE :
0

PILOT TEST LEAKAGE :
0

GROUND TRUTH FEATURES :
0

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

TRAINING STARTED :
NO

READY_FOR_SEED_ANNOTATION :
YES

NEXT STEP :
14A.2B2 SEED GT MANUAL REVIEW AND QA