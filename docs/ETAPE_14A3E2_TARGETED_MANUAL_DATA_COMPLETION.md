# ÉTAPE 14A.3E2 — Targeted Manual Data Completion

## État préparatoire

La revue est préparée pour quatre patches TRAIN prioritaires : `14A2_2025_15`, `14A2_2024_14`, `14A2_2025_12` et `14A2_2024_11`. Les 44 zones négatives sont enregistrées dans `qa/14A3E2_negative_review.csv` avec le statut initial `UNREVIEWED`. Aucune zone n'est déclarée négative automatiquement.

La couche QGIS `HARD_NEGATIVE_CANDIDATES` contient les emprises des 44 crops, leurs catégories et leurs identifiants. Un bookmark est créé par candidat. La décision attendue est seulement `VALID_NEGATIVE` ou `REJECT_NEGATIVE`; aucun polygone de bâtiment ne doit être dessiné pour les négatifs.

Les 20 hard positives sont listés dans `qa/14A3E2_positive_geometry_qa.csv`. Ils restent à dessiner manuellement dans les couches `TARGET_GT`, avec `annotation_source = MANUAL_TARGETED` et `review_status = MANUAL`. Leur QA géométrique est donc `PENDING_MANUAL_ANNOTATION`.

Le projet `qgis/14A3E2_TARGETED_REVIEW.qgz` contient 4 RGB, 1 couche `HARD_NEGATIVE_CANDIDATES`, 4 couches `TARGET_GT` vides et 44 bookmarks. Le projet est en EPSG:32637. MODEL_C4 n'est pas activé dans ce projet.

Les contrôles de fuite restent à zéro. Aucun entraînement n'a été lancé et les quatre modèles restent inchangés. Le dataset ne peut pas encore être déclaré équilibré : les négatifs et les positifs ciblés doivent d'abord être validés par l'utilisateur.

PRIORITY PATCHES :
4

HARD NEGATIVE CANDIDATES :
44

VALID NEGATIVES :
0

REJECTED NEGATIVES :
0

UNREVIEWED NEGATIVES :
44

HARD POSITIVES PROPOSED :
20

HARD POSITIVES ANNOTATED :
0

POSITIVE GEOMETRY QA :
PENDING_MANUAL_ANNOTATION

FINAL POSITIVE CROPS :
196

FINAL NEGATIVE CROPS :
3

SAMPLING CONFIG A :
60% POSITIVE / 40% NEGATIVE

SAMPLING CONFIG B :
50% POSITIVE / 50% NEGATIVE

SAMPLING CONFIG C :
40% POSITIVE / 60% NEGATIVE

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

MODEL_C :
UNCHANGED

MODEL_C2 :
UNCHANGED

MODEL_C3 :
UNCHANGED

MODEL_C4 :
UNCHANGED

TRAINING STARTED :
NO

BALANCED_DATASET_READY :
NO

NEXT STEP :
14A.3F MODEL_C5 BALANCED FINE-TUNING /
COMPLETE TARGETED REVIEW
