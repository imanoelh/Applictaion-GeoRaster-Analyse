# ÉTAPE 14A.3 — MODEL_C2 experimental high precision fine-tuning

MODEL_C2 a été créé dans un dossier expérimental séparé à partir du checkpoint MODEL_C validé. Le fichier MODEL_C de production et le registry n'ont pas été modifiés.

## Données et méthode

- Entraînement : 5 patches Seed 14A2, 100 bâtiments, masques binaires validés.
- Alignement RGB/masque : 512x512, transform et bounds identiques, valeurs `{0,1}`.
- Les 4 patches VAL 14A.2 sont restés indépendants et sans GT humaine disponible; aucune métrique VAL n'a été inventée.
- Les deux patches `14A_001_residential` et `14A_003_dense_urban` ont été utilisés uniquement comme benchmark verrouillé après entraînement.
- Loss : BCE + Dice, poids bâtiment/background 1.0/1.0.
- Phase 1 : tête de segmentation et tête auxiliaire, backbone gelé.
- Phase 2 : `layer4` dégelée avec learning rate 5e-6.
- Augmentations : flips horizontal/vertical et rotation 90 degrés.
- Pour rester exécutable sur CPU, l'optimisation a été conduite sur une représentation 128x128 issue des sources 512x512; l'export et le benchmark restent en contrat 3x512x512.

## Résultats benchmark verrouillé

MODEL_C2 améliore globalement IoU (0.1483 contre 0.1312), Dice (0.2544 contre 0.2319), Recall (0.1703 contre 0.1465) et Boundary F1 à 1 pixel (0.1757 contre 0.0640). Les faux positifs passent de 27 à 34 et l'Object F1 passe de 0.1728 à 0.1607; l'amélioration est donc partielle et ne justifie aucune promotion production.

Le risque d'overfitting est **HIGH** : seulement cinq patches ont servi à l'apprentissage et aucune GT VAL indépendante n'est disponible. Les métriques VAL sont donc `NOT AVAILABLE`.

Artefacts : `backend/data/models/model_c2_experimental/` contient les checkpoints initial/best/final, la configuration et l'ONNX. Les métriques, l'historique et la planche comparative sont dans `14A2_expansion/qa/`.

MODEL :
MODEL_C2_EXPERIMENTAL

INITIALIZED FROM :
MODEL_C

TRAIN PATCHES :
5

TRAIN GT BUILDINGS :
100

VAL PATCHES :
4

VAL GT AVAILABLE :
NO

LOCKED BENCHMARK PATCHES :
2

TRAINING EPOCHS :
2

BEST EPOCH :
2

LOSS :
BCE + Dice

OVERFITTING RISK :
HIGH

MODEL_C BASELINE IOU :
0.1312

MODEL_C2 IOU :
0.1483

MODEL_C BASELINE DICE :
0.2319

MODEL_C2 DICE :
0.2544

MODEL_C BASELINE PRECISION :
0.5572

MODEL_C2 PRECISION :
0.5167

MODEL_C BASELINE RECALL :
0.1465

MODEL_C2 RECALL :
0.1703

MODEL_C BASELINE BOUNDARY F1 @1PX :
0.0640

MODEL_C2 BOUNDARY F1 @1PX :
0.1757

MODEL_C BASELINE OBJECT F1 :
0.1728

MODEL_C2 OBJECT F1 :
0.1607

MODEL_C MISSED BUILDINGS :
40

MODEL_C2 MISSED BUILDINGS :
40

MODEL_C FALSE POSITIVES :
27

MODEL_C2 FALSE POSITIVES :
34

MODEL_C WEIGHTS :
UNCHANGED

MODEL_F :
UNCHANGED

MODEL_C2 ONNX :
PASS

PRODUCTION PROMOTION :
NO

DECISION :
MODEL_C2_PARTIAL_IMPROVEMENT

NEXT STEP :
14A.4 MODEL_C2 ACTIVE-LEARNING EXPANSION
