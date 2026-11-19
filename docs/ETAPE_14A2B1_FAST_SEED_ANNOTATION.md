# ÉTAPE 14A.2B1 — FAST SEED GROUND TRUTH ANNOTATION WORKFLOW

Projet : `qgis/14A2B1_FAST_SEED_ANNOTATION.qgz`

Les propositions orange sont des aides uniquement. La couche `SEED_GROUND_TRUTH` verte est la seule couche qui devient la vérité terrain de travail.

## A. Accepter une proposition

1. Dans le groupe du patch, sélectionner la proposition orange.
2. Relever son `proposal_id` dans la table attributaire.
3. Exécuter : `python-qgis-ltr.bat scripts/accept_14A2B1_seed_proposal.py PATCH_ID PROPOSAL_ID`.
4. La géométrie est copiée dans `SEED_GROUND_TRUTH` avec `review_status=ACCEPTED`.

La proposition originale reste inchangée.

## B. Corriger une proposition

Accepter d'abord la proposition, puis activer l'édition sur `SEED_GROUND_TRUTH`, utiliser Vertex Tool, corriger le contour et enregistrer. Remplacer `review_status` par `CORRECTED`.

## C. Rejeter

Ne rien copier dans `SEED_GROUND_TRUTH`. La proposition reste dans la couche d'aide et peut être ignorée.

## D. Bâtiment manquant

Sur RGB, activer l'édition de `SEED_GROUND_TRUTH`, utiliser Add Polygon Feature, dessiner uniquement la toiture visible, puis renseigner `annotation_source=MANUAL` et `review_status=MANUAL`.

## E. Sauvegarder

Après chaque série de corrections : Save Layer Edits, puis sauvegarder le projet QGIS. Les couches de travail sont dans `annotations/14A2B_seed_ground_truth_WORKING.gpkg`.

La QA post-annotation est préparée dans `scripts/qa_14A2B2_seed_gt.py` mais n'est pas exécutée avant la fin de l'annotation humaine.

SEED PATCHES :
5

RGB :
5 / 5

ASSISTED PROPOSALS :
5 / 5

SEED GT :
5 / 5

FAST ACCEPT WORKFLOW :
READY

FAST CORRECT WORKFLOW :
READY

MANUAL MISSING BUILDING WORKFLOW :
READY

BOOKMARKS :
5 / 5

BROKEN SOURCES :
0

QGIS OPEN :
SUCCESS

QGIS REOPEN :
SUCCESS

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

TRAINING STARTED :
NO

READY_FOR_SEED_GT_ANNOTATION :
YES

NEXT STEP :
14A.2B2 SEED GT FINAL QA
