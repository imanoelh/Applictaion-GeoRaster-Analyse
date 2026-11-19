# ÉTAPE 14A.2B1-M — MINIMAL MANUAL SEED GROUND TRUTH PROJECT

Projet créé séparément : `qgis/14A2B1_MANUAL_SEED_GT.qgz`.

Il contient uniquement les 5 RGB et les 5 couches Polygon Ground Truth manuelles. Aucun MODEL_C, MODEL_F, Assisted Proposal, probability map ou diagnostic n'est chargé.

Les couches sont dans `annotations/14A2B1_manual_seed_ground_truth.gpkg` avec les seuls champs `building_id`, `patch_id`, `annotation_source` et `review_status`. Elles sont vides, en EPSG:32637 et éditables. Les couches Ground Truth sont placées au-dessus du RGB dans chacun des cinq groupes.

Utilisation : ouvrir le bookmark du patch, sélectionner la couche Ground Truth, activer Toggle Editing, choisir Add Polygon Feature, dessiner le contour de toiture visible, terminer par clic droit et sauvegarder. Le RGB est la seule référence visuelle ; ne pas suivre les anciennes prédictions.

QA post-annotation : réutiliser `scripts/qa_14A2B2_seed_gt.py` en adaptant le chemin vers `14A2B1_manual_seed_ground_truth.gpkg` si nécessaire. Aucune QA finale n'est lancée tant que les couches sont vides.

SEED PATCHES :
5

RGB :
5 / 5

GROUND TRUTH :
5 / 5

TOTAL LAYERS :
10

BOOKMARKS :
5 / 5

EDITABLE GT :
5 / 5

BROKEN SOURCES :
0

CRS :
EPSG:32637

ASSISTED PROPOSALS LOADED :
NO

MODEL_C LOADED :
NO

MODEL_F LOADED :
NO

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

TRAINING STARTED :
NO

READY_FOR_DIRECT_MANUAL_ANNOTATION :
YES

NEXT STEP :
14A.2B2 FINAL SEED GT QA
