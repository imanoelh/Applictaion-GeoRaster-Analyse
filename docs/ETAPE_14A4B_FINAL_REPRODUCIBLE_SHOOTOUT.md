# ÉTAPE 14A.4B — FINAL REPRODUCTIBLE MODEL_F2 / MODEL_D2 SHOOTOUT

## Résultat d'exécution

L'environnement ML isolé est Python 3.12.10 avec PyTorch 2.8.0 CPU et Torchvision 0.23.0 CPU. Le checkpoint MODEL_F/SegFormer existe, mais `transformers`, `tokenizers` et `safetensors` sont absents. Les paquets ne sont pas disponibles dans le cache local et l'accès réseau est bloqué. Le test d'import et de chargement MODEL_F échoue donc avant le forward CPU.

`MODEL_F_RUNTIME = FAIL` et `MODEL_F2_TRAINING = NOT_PRACTICAL` sont ainsi des résultats d'environnement mesurés, pas des métriques inventées. Aucun MODEL_F original n'a été modifié.

MODEL_D2 reste un candidat U-Net++/EfficientNet-B4 ONNX expérimental. Aucun nouveau fine-tuning n'a été lancé dans cette passe : le checkpoint original et la production restent inchangés. Les tableaux CSV conservent les lignes comparables disponibles et marquent les exécutions non réalisées explicitement.

Le protocole verrouillé est défini pour 47 bâtiments sur `14A_001_residential` et `14A_003_dense_urban`, avec matrice IoU complète, Hungarian strict un-à-un et seuils 0.30/0.50/0.70. Aucun réglage de seuil, choix de loss ou sélection d'époque n'a utilisé le locked benchmark.

## Décision

MODEL_C3 reste la meilleure référence expérimentale disponible. Il n'y a pas de gagnant F2/D2 démontré qui améliore simultanément rappel objet, F1 objet et qualité de contour sans explosion des faux positifs. Active Learning reste bloqué jusqu'à l'installation reproductible du runtime SegFormer et à une nouvelle passe comparable.

MODEL_C3 OBJECT RECALL :
0.2190

MODEL_C3 OBJECT F1 :
0.2585

MODEL_C3 FALSE POSITIVES :
14

MODEL_C3 MISSED :
37

MODEL_F RUNTIME :
FAIL

MODEL_F2 TRAINING :
NOT_PRACTICAL

MODEL_F2 OBJECT RECALL :
NOT_RUN

MODEL_F2 OBJECT F1 :
NOT_RUN

MODEL_F2 FALSE POSITIVES :
NOT_RUN

MODEL_F2 MISSED :
NOT_RUN

MODEL_D2 TRAINING :
NOT_PRACTICAL

MODEL_D2 OBJECT RECALL :
NOT_RUN

MODEL_D2 OBJECT F1 :
NOT_RUN

MODEL_D2 FALSE POSITIVES :
NOT_RUN

MODEL_D2 MISSED :
NOT_RUN

BEST PIXEL MODEL :
MODEL_C3

BEST BOUNDARY MODEL :
MODEL_C3

BEST OBJECT MODEL :
MODEL_C3

BEST OVERALL EXPERIMENTAL MODEL :
MODEL_C3

PRODUCTION MODEL :
MODEL_C

PRODUCTION PROMOTION :
NO

DECISION :
MODEL_C3_REMAINS_BEST

READY_FOR_ACTIVE_LEARNING :
NO

MODEL_FOR_ACTIVE_LEARNING :
NONE

NEXT STEP :
DATASET_SCALE_DECISION
