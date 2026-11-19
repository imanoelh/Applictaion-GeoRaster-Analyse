# ÉTAPE 14A.2A — SMART ASSISTED BUILDING ANNOTATION & ACTIVE LEARNING

## Exécution

Le workflow a analysé les 20 patches 14A.2 sans modifier MODEL_C, la production, les indices ou les patches TEST. MODEL_C n’a pas été réexécuté : ses probabilités et polygones existants ont été réutilisés. MODEL_D est exécuté uniquement comme second moteur expérimental ONNX CPU.

La confiance est calculée à partir de la probabilité moyenne/médiane/maximale, de la surface, de la compacité, de la distance au bord et de l’accord spatial MODEL_C/MODEL_D. Les seuils testés sont explicitement 0.50, 0.65 et 0.80 ; ils restent provisoires car la calibration repose uniquement sur les deux patches GT approuvés 14A.1D4.

Les propositions sont écrites dans `smart_assisted_annotation/proposals/ASSISTED_PROPOSALS.geojson`, séparées du Ground Truth final. Le projet QGIS contient RGB, MODEL_C, MODEL_D, Ground Truth, propositions catégorisées et bookmarks de revue.

## Résultats QA

- Alignement RGB / MODEL_C / MODEL_D : 20 / 20.
- Les prédictions MODEL_D sont expérimentales et ne sont pas enregistrées comme production.
- Le taux de revue est calculé sur les objets produits, sans estimation théorique.
- Aucun entraînement n’a été lancé.

Calibration proxy (pixels, 14A.1D4 only) : {"0.5": {"precision": 0.557202, "recall": 0.146455, "false_positive_rate": 0.026002, "support": "2 approved 14A.1D4 patches; pixel calibration proxy only"}, "0.65": {"precision": 0.583537, "recall": 0.129503, "false_positive_rate": 0.020649, "support": "2 approved 14A.1D4 patches; pixel calibration proxy only"}, "0.8": {"precision": 0.612288, "recall": 0.105961, "false_positive_rate": 0.01499, "support": "2 approved 14A.1D4 patches; pixel calibration proxy only"}}.

Livrables : `qa/14A2A_candidate_confidence.csv`, `qa/14A2A_model_agreement.csv`, `qa/14A2A_active_learning_priority.csv`, `qa/14A2A_summary.json`, `qa/14A2A_contact_sheet.png`, `qgis/14A2A_SMART_ASSISTED_ANNOTATION.qgz`.

PATCHES ANALYZED :
20

MODEL_C :
UNCHANGED

SECOND MODEL :
MODEL_D WHU U-Net++ EfficientNet-B4 ONNX Runtime CPU (EXPERIMENTAL ONLY)

TOTAL CANDIDATES :
527

HIGH CONFIDENCE CONSENSUS :
29

REVIEW REQUIRED :
498

LOW CONFIDENCE :
0

PERCENT HUMAN REVIEW REQUIRED :
94.5 %

CALIBRATION GT :
14A.1D4 ONLY

AUTO ACCEPT SAFE :
NO

ACTIVE LEARNING READY :
YES

TRAINING STARTED :
NO

DECISION :
MANUAL_GT_STILL_REQUIRED

NEXT STEP :
14A.2B SMART HUMAN REVIEW /
IMPROVE ASSISTED ANNOTATION
