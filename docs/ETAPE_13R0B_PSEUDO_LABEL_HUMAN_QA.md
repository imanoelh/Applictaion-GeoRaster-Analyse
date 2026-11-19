# ÉTAPE 13R.0B — Fast human QA of MODEL_C pseudo-labels

## Revue effectuée

La planche complète est disponible ici :

`backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R/qa_contact_sheet_rgb_mask_overlay_labeled.png`

Chaque tuile montre RGB, masque binaire pseudo-label et superposition RGB/contour, avec son identifiant, son split, son type de scène et son sous-type industriel.

La revue rapide a appliqué les règles de l'étape 13R.0B : les imperfections de bord ont été acceptées, tandis que les masques manifestement inutilisables ont été exclus. Deux patches ont été rejetés : `13R_industrial_007_01024_06144` et `13R_residential_036_06144_04096`, car leur pseudo-label contient trop peu de bâtiments exploitables par rapport à leur image. Aucun patch n'a nécessité de correction géométrique humaine majeure ; aucun statut `NEEDS_CORRECTION` ne reste.

Les 34 patches acceptés ont reçu `label_source = MODEL_C_PSEUDO_LABEL_REVIEWED`. Les deux patches rejetés restent dans le manifeste source pour traçabilité, mais sont exclus de `training_ready_manifest.json`.

## Contrôles techniques

- Tous les masques ont été relus après QA.
- Dimensions : 512×512.
- Valeurs : `{0,1}` uniquement.
- Transform, CRS et bounds identiques au RGB correspondant.
- TEST leakage : 0.
- La séparation géographique train/val est inchangée.
- Aucun fine-tuning n'a été exécuté.

Fichiers produits :

- `manifest.csv` — manifeste complet avec statut de revue.
- `training_ready_manifest.json` — 34 patches acceptés, prêts à être utilisés après décision de lancement du fine-tuning.
- `human_qa_summary.json` — synthèse des comptes.

TOTAL PATCHES :
36

ACCEPTED :
34

HUMAN CORRECTED :
0

REJECTED :
2

TRAIN USABLE :
29

VAL USABLE :
5

INDUSTRIAL USABLE :
23

RESIDENTIAL USABLE :
11

TEST LEAKAGE :
0

MASK ALIGNMENT :
VALIDATED

READY_FOR_FINE_TUNING :
YES

MODEL_F :
UNCHANGED

MODEL_C :
PRODUCTION UNCHANGED

NEXT STEP :
13R.1 TARGETED MODEL_F FINE-TUNING /
CORRECT REMAINING LABELS
