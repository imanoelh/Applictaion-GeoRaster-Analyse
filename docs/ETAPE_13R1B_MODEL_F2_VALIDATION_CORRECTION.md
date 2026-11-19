# ÉTAPE 13R.1B — MODEL_F2 validation split correction

## Split corrigé

Le manifeste initial contenait 0 patch résidentiel en VAL. Un nouveau split a été créé dans `balanced_split_13R1B_manifest.json`, sans déplacer de fichier TEST et sans mélange de zones géographiques :

- VAL : 10 patches, dont 3 industriels et 7 résidentiels/urbains.
- TRAIN : 24 patches.
- Zones TRAIN/VAL disjointes : 0 chevauchement.
- TEST leakage par hash, bounds et zone : 0.

Le nouveau VAL utilise les zones `z1_1` et `z0_1`; toutes les autres zones restent en TRAIN. Le split original et les fichiers source restent conservés.

## Baseline et checkpoint existant

MODEL_F original et `best_model_f2.pth` ont été évalués sur le même nouveau VAL. Le sweep limité a utilisé les seuils 0,35, 0,40, 0,45, 0,50 et 0,55. Le seuil 0,35 est retenu comme candidat : il améliore l'IoU industrielle et le recall industriel sans perte de précision, et la qualité résidentielle est supérieure à MODEL_F sur ce split.

À 0,35 :

- MODEL_F industriel : IoU 0,6063, recall 0,6905, précision 0,8325.
- MODEL_F2 industriel : IoU 0,7654, recall 0,8073, précision 0,9365.
- MODEL_F résidentiel : IoU 0,3296.
- MODEL_F2 résidentiel : IoU 0,5758.

Le seuil suffit ; aucun réentraînement F2B n'a été lancé. Le fichier `model_f2_threshold_candidate.json` enregistre la décision et le hash du checkpoint. MODEL_C, le registry, le frontend et l'API n'ont pas été modifiés.

NEW VAL INDUSTRIAL PATCHES :
3

NEW VAL RESIDENTIAL PATCHES :
7

TEST LEAKAGE :
0

TRAIN_VAL SPATIAL LEAKAGE :
0

MODEL_F INDUSTRIAL IOU :
0.606323

MODEL_F2 EXISTING INDUSTRIAL IOU :
0.765449

MODEL_F2B INDUSTRIAL IOU :
NOT_RUN — threshold candidate sufficient

MODEL_F INDUSTRIAL RECALL :
0.690547

MODEL_F2 EXISTING INDUSTRIAL RECALL :
0.807329

MODEL_F2B INDUSTRIAL RECALL :
NOT_RUN — threshold candidate sufficient

MODEL_F RESIDENTIAL IOU :
0.329618

MODEL_F2 EXISTING RESIDENTIAL IOU :
0.575846

MODEL_F2B RESIDENTIAL IOU :
NOT_RUN — threshold candidate sufficient

BEST THRESHOLD :
0.35

BEST CHECKPOINT :
MODEL_F2

INDUSTRIAL IMPROVEMENT :
YES

RECALL PRESERVED :
YES

RESIDENTIAL QUALITY PRESERVED :
YES

READY_FOR_INDEPENDENT_TEST :
YES

NEXT STEP :
13R.2 INDEPENDENT MODEL_C VS MODEL_F VS FINAL_F2 TEST /
STOP FINE-TUNING PATH
