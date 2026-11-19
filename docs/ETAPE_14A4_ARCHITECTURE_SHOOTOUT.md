# ÉTAPE 14A.4 — BUILDING FOOTPRINT STRATEGIC ARCHITECTURE SHOOTOUT

## Périmètre

Le shootout porte sur les deux patches verrouillés `14A_001_residential` et `14A_003_dense_urban`, soit 47 bâtiments GT. La production MODEL_C n'a pas été modifiée. Aucun nouveau label, raster, projet QGIS ou registre n'a été touché.

## Référence expérimentale

MODEL_C3 reste la référence expérimentale fournie par le benchmark verrouillé : rappel objet 0.2190, F1 objet 0.2585, 14 faux positifs et 37 bâtiments manqués au seuil IoU 0.30, composante minimale 479 pixels, sans morphologie.

## Candidats

- **MODEL_F2** : checkpoint SegFormer local `backend/data/models/building/experimental/model_f2_industrial_finetuned/best_model_f2.pth`. Le runtime `transformers` n'est pas installé dans `.venv_model_training`; aucune nouvelle inférence ou fine-tuning reproductible n'a donc été lancée.
- **MODEL_D2** : candidat U-Net++/EfficientNet-B4 ONNX local. Les poids originaux restent présents et inchangés. Cette passe n'a pas relancé son inférence verrouillée, afin d'éviter un résultat non comparable au matching strict demandé.

Le matching requis est un appariement un-à-un sur la matrice IoU complète, aux seuils 0.30, 0.50 et 0.70. Comme les dépendances nécessaires à la reproduction complète (`scipy` pour l'affectation et `transformers` pour F2) ne sont pas disponibles et que le réseau est bloqué, les métriques F2/D2 sont explicitement `NOT_RUN`, sans valeur inventée.

## Résultats et décision

Les fichiers CSV/JSON associés conservent la baseline MODEL_C3 et marquent les deux candidats comme non exécutés dans ce cycle. Le panneau PNG reprend la comparaison visuelle MODEL_C3/C2/C3 déjà validée ; il ne constitue pas une nouvelle prédiction F2/D2.

Décision : **MODEL_C3_REMAINS_BEST_REFERENCE_PENDING_REPRODUCIBLE_F2_D2_RUN**. La promotion en production est interdite et l'extension Active Learning n'est pas autorisée tant qu'un benchmark strict reproductible des deux candidats n'a pas été exécuté.

CURRENT EXPERIMENTAL REFERENCE :
MODEL_C3

MODEL_C3 OBJECT RECALL :
0.2190

MODEL_C3 OBJECT F1 :
0.2585

MODEL_C3 FALSE POSITIVES :
14

MODEL_C3 MISSED :
37

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
MODEL_C3 (only measured candidate in this cycle)

BEST BOUNDARY MODEL :
MODEL_C3 (only measured candidate in this cycle)

BEST OBJECT MODEL :
MODEL_C3 (only measured candidate in this cycle)

BEST OVERALL MODEL :
MODEL_C3_PENDING_F2_D2_REPRODUCTION

PRODUCTION MODEL :
MODEL_C UNCHANGED

PRODUCTION PROMOTION :
NO

DECISION :
MODEL_C3_REMAINS_BEST_REFERENCE_PENDING_REPRODUCIBLE_F2_D2_RUN

READY_FOR_ACTIVE_LEARNING :
NO

NEXT STEP :
DATASET SCALE DECISION
