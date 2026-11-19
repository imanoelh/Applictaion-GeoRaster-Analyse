# ÉTAPE 13R.1 — Targeted fine-tuning MODEL_F2

## Exécution

Un fine-tuning isolé a été exécuté à partir de `best_segformer.pth`, sans initialisation aléatoire. Le preprocessing officiel MODEL_F a été conservé : RGB, division par 255, entrée 512×512. La loss est `BCEWithLogitsLoss + Dice loss`, avec AdamW, learning rate `1e-5` et weight decay `1e-4`.

Le dataset utilisé est `training_ready_manifest.json`. Les deux patches rejetés sont exclus. Aucun patch TEST 13M/13Q n'a été chargé. La séparation train/val n'a pas été modifiée.

Le fine-tuning a demandé 12 epochs au maximum et s'est arrêté à l'epoch 6 par early stopping (patience 4). Le meilleur checkpoint est l'epoch 2, sélectionné sur VAL Dice. Les courbes sont dans `training_curves.png`, et les métriques détaillées dans `training_history.json` et `metadata.json`.

## Résultats

Sur les 5 patches VAL, tous sont de type industriel. L'IoU VAL industrielle progresse de 0.357 (MODEL_F) à 0.449 (MODEL_F2), mais le recall industriel baisse de 0.904 à 0.642. Le critère minimal de recall n'est donc pas satisfait. Il n'existe aucun patch résidentiel dans le split VAL actuel ; une mesure résidentielle VAL n'est pas disponible et aucune conclusion de conservation de qualité résidentielle ne peut être tirée.

Le modèle F2 reste expérimental et n'est pas ajouté au registry, à l'API, au frontend ou au modèle par défaut. Le checkpoint original a été copié en `MODEL_F_original_backup.pth` et marqué lecture seule. Le hash original reste `10487CC6C8C32FA998605543C203EB00E3B3B5D70664515B246CFB2883AC13A1`.

BASE MODEL :
MODEL_F

NEW MODEL :
MODEL_F2

TRAIN PATCHES :
29

VAL PATCHES :
5

TEST PATCHES USED :
0

TEST LEAKAGE :
0

LEARNING RATE :
1e-5

EPOCHS RUN :
6

BEST EPOCH :
2

TRAIN LOSS FINAL :
0.863158

VAL LOSS BEST :
0.636478

MODEL_F VAL IOU :
0.378500

MODEL_F2 VAL IOU :
0.498310

MODEL_F VAL DICE :
0.537641

MODEL_F2 VAL DICE :
0.649209

MODEL_F INDUSTRIAL VAL RECALL :
0.904253

MODEL_F2 INDUSTRIAL VAL RECALL :
0.642339

MODEL_F INDUSTRIAL VAL IOU :
0.356721

MODEL_F2 INDUSTRIAL VAL IOU :
0.448956

MODEL_F RESIDENTIAL VAL IOU :
NOT_AVAILABLE — 0 residential VAL patches

MODEL_F2 RESIDENTIAL VAL IOU :
NOT_AVAILABLE — 0 residential VAL patches

OVERFITTING :
YES — validation Dice peaked at epoch 2 and degraded afterward; early stopping applied

BEST CHECKPOINT :
backend/data/models/building/experimental/model_f2_industrial_finetuned/best_model_f2.pth

CHECKPOINT SHA256 :
60026F07885A3A4960A11699B187DC8D1F13A2D0AB4C1301F7116D259F765707

MODEL_F ORIGINAL :
UNCHANGED

MODEL_C :
PRODUCTION UNCHANGED

REGISTRY :
UNCHANGED

READY_FOR_INDEPENDENT_TEST :
NO

NEXT STEP :
13R.2 INDEPENDENT MODEL_C VS MODEL_F VS MODEL_F2 TEST /
CORRECT TRAINING
