# ÉTAPE 14A.3F — MODEL_C5 Balanced Fine-Tuning

## Résultat

Le fine-tuning n’a pas pu démarrer dans l’environnement actuel. Le pipeline requis utilise `torchvision.models.segmentation.deeplabv3_resnet50`, mais `torchvision` n’était pas disponible avec PyTorch 2.8.0 CPU. Une tentative d’installation a été interrompue puis PyTorch 2.8.0 a été restauré. Aucun checkpoint MODEL_C5 n’a été produit et aucune métrique n’a été inventée.

Les trois configurations demandées sont documentées comme `NOT_RUN`. La production, l’API, le frontend, le registry et tous les modèles existants restent inchangés. Le benchmark verrouillé n’a pas été exécuté après sélection puisqu’aucun candidat entraîné n’existe.

MODEL :
MODEL_C5_EXPERIMENTAL

TRAINING CONFIG :
NOT RUN — torchvision incompatible/non disponible avec torch 2.8.0+cpu

SAMPLING :
CONFIG_A 60/40, CONFIG_B 50/50, CONFIG_C 40/60 — toutes NOT RUN

LOSS :
Weighted BCE + Dice — NOT RUN

BEST EPOCH :
NOT RUN

OVERFITTING RISK :
NOT ASSESSED

MODEL_C3 CALIBRATED OBJECT RECALL :
0.2190

MODEL_C5 OBJECT RECALL :
NOT RUN

MODEL_C3 CALIBRATED OBJECT F1 :
0.2585

MODEL_C5 OBJECT F1 :
NOT RUN

MODEL_C3 FALSE POSITIVES :
14

MODEL_C5 FALSE POSITIVES :
NOT RUN

MODEL_C3 MISSED :
37

MODEL_C5 MISSED :
NOT RUN

PIXEL IOU :
NOT RUN

BOUNDARY F1 @1PX :
NOT RUN

MODEL_C5 ONNX :
SKIPPED

MODEL_C :
UNCHANGED

MODEL_C2 :
UNCHANGED

MODEL_C3 :
UNCHANGED

MODEL_C4 :
UNCHANGED

PRODUCTION :
UNCHANGED

DECISION :
MODEL_C5_NO_IMPROVEMENT

READY_FOR_ACTIVE_LEARNING :
NO

NEXT STEP :
SHORT ERROR REVIEW
