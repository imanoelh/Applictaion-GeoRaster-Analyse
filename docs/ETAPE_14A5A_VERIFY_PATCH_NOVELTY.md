# ÉTAPE 14A.5A — VERIFY PATCH NOVELTY BEFORE MANUAL ANNOTATION

## Audit

Les 16 patches TRAIN du manifest 14A2 ont été comparés aux manifests Seed GT, TARGET GT, crops positifs/négatifs et dataset balanced. Neuf patches sont déjà utilisés ; sept sont réellement vierges. La sélection 14A.5 initiale contenait quatre patches précédemment utilisés et a été remplacée.

Patches précédemment utilisés : `14A2_2024_13`, `14A2_2025_14`, `14A2_2024_14`, `14A2_2025_15` et les autres patches Seed/Target déjà identifiés.

Patches vierges disponibles : `14A2_2024_02`, `14A2_2024_06`, `14A2_2024_10`, `14A2_2025_02`, `14A2_2025_06`, `14A2_2025_10`, `14A2_2025_11`.

Sélection finale de cinq patches vierges :

- `14A2_2024_06`
- `14A2_2024_10`
- `14A2_2025_02`
- `14A2_2025_06`
- `14A2_2025_10`

Un nouveau GeoPackage vide et un projet QGIS séparé ont été créés. Aucun ancien Ground Truth n'a été fusionné ou modifié. Aucun modèle n'a été exécuté.

TOTAL TRAIN PATCHES :
16

PREVIOUSLY USED TRAIN PATCHES :
9

TRULY UNUSED TRAIN PATCHES :
7

CURRENT 14A5 SELECTION VALID :
NO

PATCHES TO REPLACE :
14A2_2024_13, 14A2_2025_14, 14A2_2024_14, 14A2_2025_15

FINAL NEW PATCH SELECTION :
14A2_2024_06, 14A2_2024_10, 14A2_2025_02, 14A2_2025_06, 14A2_2025_10

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

TRAINING STARTED :
NO

READY_FOR_NEW_MANUAL_ANNOTATION :
YES

NEXT STEP :
ANNOTATE ONLY TRULY NEW PATCHES
