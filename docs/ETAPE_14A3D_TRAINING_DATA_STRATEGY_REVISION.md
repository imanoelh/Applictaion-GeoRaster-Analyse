# ÉTAPE 14A.3D — Training/data strategy revision for object recall

Les 37 bâtiments manqués par MODEL_C3 sur les deux patches verrouillés ont été analysés sans modifier les modèles existants. Les catégories dominantes sont `MODEL_LOW_CONFIDENCE` (34/37), `EDGE_BUILDING` (7/37), `POSTPROCESS_REMOVED` (11/37), avec seulement 2 bâtiments sous 479 pixels. Le seuil d'aire n'est donc pas la cause principale du rappel faible.

Un manifest de 199 crops natifs 256×256 a été généré depuis les 5 Seed patches : 196 crops positifs et 3 négatifs. Le précédent entraînement n'utilisait que 10 crops. MODEL_C4 a été initialisé depuis MODEL_C3 et entraîné expérimentalement sur un sous-ensemble équilibré de 40 crops, avec Weighted BCE + Dice, backbone gelé et résolution native 256×256. Le benchmark verrouillé n'a pas servi au choix des paramètres.

Le résultat MODEL_C4 améliore le pixel recall mais produit 82 faux positifs et un Object F1 global de 0,1958, inférieur à MODEL_C3 calibré (0,2585). Il n'est donc pas retenu pour Active Learning.

MISSED BUILDINGS ANALYZED :
37

MAIN MISSED CATEGORIES :
MODEL_LOW_CONFIDENCE (34), POSTPROCESS_REMOVED (11), EDGE_BUILDING (7), SMALL_BUILDING (2)

TRAIN CROPS BEFORE :
10

TRAIN CROPS AFTER :
199

POSITIVE CROPS :
196

NEGATIVE CROPS :
3

HARD POSITIVES :
0 explicitly identified in Seed training crops

HARD NEGATIVES :
0

SELECTED LOSS :
WEIGHTED BCE + Dice

MODEL :
MODEL_C4_EXPERIMENTAL

TRAINING RESOLUTION :
256x256 native crops

OVERFITTING RISK :
HIGH

MODEL_C3 CALIBRATED OBJECT RECALL :
0.2190

MODEL_C4 OBJECT RECALL :
0.2979

MODEL_C3 CALIBRATED OBJECT F1 :
0.2585

MODEL_C4 OBJECT F1 :
0.1958

MODEL_C3 FALSE POSITIVES :
14

MODEL_C4 FALSE POSITIVES :
82

MODEL_C3 MISSED :
37

MODEL_C4 MISSED :
33

BOUNDARY F1 :
NOT_RECORDED_FOR_C4_OBJECT_RUN

MODEL_C :
UNCHANGED

MODEL_C2 :
UNCHANGED

MODEL_C3 :
UNCHANGED

MODEL_C4 :
EXPERIMENTAL

PRODUCTION :
UNCHANGED

DECISION :
MODEL_C4_NO_CLEAR_IMPROVEMENT

READY_FOR_ACTIVE_LEARNING_EXPANSION :
NO

NEXT STEP :
14A.3E DATASET EXPANSION STRATEGY
