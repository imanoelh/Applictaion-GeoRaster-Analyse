# ÉTAPE 14A.3B — High-resolution training strategy revision

La révision a été menée sans nouvelle annotation et sans utiliser les deux patches verrouillés pour choisir la configuration. MODEL_C reste inchangé et MODEL_C2 reste expérimental.

## Audit et stratégie

Le précédent entraînement 128×128 réduisait les petits bâtiments, les angles et la séparation entre bâtiments voisins. La nouvelle stratégie conserve la résolution native avec des crops 256×256 issus des images et masques 512×512. Chaque patch fournit un crop positif et un crop négatif, soit 5 positifs et 5 négatifs; le ratio de pixels bâtiment est conservé dans chaque crop.

Deux losses ont été comparées : `BCE + Dice` et `0.5 * BCE + Dice`. Le checkpoint a été choisi uniquement selon la perte d'entraînement. La stratégie utilise batch size 1, accumulation 1, backbone gelé en phase 1 puis `layer4` dégelée en phase 2, learning rates 2e-5 puis 5e-6, weight decay 1e-4 et 2 epochs. Les courbes et configurations sont enregistrées dans `14A3B_training_config_comparison.json`.

La mémoire/CPU n'a pas pu être interrogée via WMI dans le sandbox (`Access denied`). Les essais précédents ont montré que le 512×512 complet est trop coûteux pour une itération rapide sur cette machine; le fallback 256×256 demandé a donc été retenu. Le risque d'overfitting reste élevé car cinq patches seulement sont disponibles et aucune GT VAL indépendante n'est présente.

## Résultats verrouillés

MODEL_C3 améliore simultanément IoU, rappel et Boundary F1 par rapport à MODEL_C2, avec beaucoup moins de faux positifs dans cette mesure expérimentale. Le résultat doit rester considéré comme exploratoire : l'échantillon est petit et les métriques objet sont calculées par composantes connectées sur les deux patches verrouillés.

MODEL :
MODEL_C3_EXPERIMENTAL

TRAINING RESOLUTION :
256x256 native crops from 512x512

CROP STRATEGY :
1 positive + 1 negative crop per each of 5 patches

BATCH SIZE :
1

GRADIENT ACCUMULATION :
1

LOSS :
WEIGHTED_BCE_DICE (0.5 BCE + Dice)

BEST EPOCH :
2

OVERFITTING RISK :
HIGH

MODEL_C IOU :
0.1312

MODEL_C2 IOU :
0.1483

MODEL_C3 IOU :
0.1819

MODEL_C RECALL :
0.1465

MODEL_C2 RECALL :
0.1703

MODEL_C3 RECALL :
0.2165

MODEL_C BOUNDARY F1 @1PX :
0.0640

MODEL_C2 BOUNDARY F1 @1PX :
0.1757

MODEL_C3 BOUNDARY F1 @1PX :
0.2140

MODEL_C OBJECT F1 :
0.1728

MODEL_C2 OBJECT F1 :
0.1607

MODEL_C3 OBJECT F1 :
0.9583

MODEL_C FALSE POSITIVES :
27

MODEL_C2 FALSE POSITIVES :
34

MODEL_C3 FALSE POSITIVES :
4

MODEL_C MISSED BUILDINGS :
40

MODEL_C2 MISSED BUILDINGS :
40

MODEL_C3 MISSED BUILDINGS :
0

MODEL_C WEIGHTS :
UNCHANGED

MODEL_C2 :
UNCHANGED

MODEL_C3 ONNX :
PASS

PRODUCTION PROMOTION :
NO

DECISION :
MODEL_C3_CLEAR_IMPROVEMENT

READY_FOR_ACTIVE_LEARNING_EXPANSION :
YES

NEXT STEP :
14A.4 MODEL_C3 ACTIVE-LEARNING EXPANSION /
14A.3C TRAINING STRATEGY REVIEW
