# ÉTAPE 14A.5 — DATASET SCALE DECISION & TARGETED EXPANSION

Les 11 patches TRAIN disponibles ont été analysés à partir du manifest 14A2 et des densités de candidats MODEL_C existantes. Cinq patches sont sélectionnés pour couvrir les petits bâtiments, la densité résidentielle, le contraste faible, les bords et la diversité des toitures. Aucun entraînement n’a été lancé et aucun modèle n’a été modifié.

Le projet QGIS minimal contient exactement 10 couches : 5 RGB et 5 couches Polygon Ground Truth vides en EPSG:32637. Aucun pseudo-label, diagnostic ou modèle IA n’est chargé. Le GeoPackage est prêt pour la numérisation manuelle.

REMAINING TRAIN PATCHES :
11

SELECTED PATCHES :
5

SELECTED PATCH IDS :
14A2_2024_13, 14A2_2025_14, 14A2_2024_06, 14A2_2024_14, 14A2_2025_15

MAIN ERROR CATEGORIES COVERED :
SMALL_BUILDING, DENSE_RESIDENTIAL, LOW_CONTRAST, EDGE_BUILDING, ROOF_DIVERSITY

CURRENT GT BUILDINGS :
33 target features + 5 seed patches (consolidated count deferred until annotation QA)

TARGET NEW GT BUILDINGS :
100-150

VAL PATCHES USED :
0

LOCKED TEST PATCHES USED :
0

VAL LEAKAGE :
0

LOCKED TEST LEAKAGE :
0

MODEL_C :
UNCHANGED

MODEL_C3 :
UNCHANGED

TRAINING STARTED :
NO

READY_FOR_TARGETED_ANNOTATION :
YES

NEXT STEP :
14A.5B TARGETED GT ANNOTATION
