# ÉTAPE 14A.3C — MODEL_C3 object recovery and post-processing calibration

La calibration a utilisé les cinq patches Seed et n'a utilisé les deux patches verrouillés qu'après verrouillage de la configuration. Aucun poids n'a été modifié et aucun entraînement n'a été lancé.

La stratégie retenue est volontairement simple : seuil 0,30, suppression des composantes de moins de 479 pixels (58,68 m²), sans morphologie. La valeur d'aire provient de la distribution des 100 bâtiments GT; la complexité est LOW.

Limitation méthodologique : aucun checkpoint C3 distinct par fold n'était disponible. Les sorties C3 existantes ont donc servi de calibration diagnostique leave-one-patch-out, avec une note de fuite potentielle. Cette situation ne permet pas d'autoriser Active Learning automatiquement; une vraie validation par fold devra être produite avant promotion.

Sur les patches verrouillés, la configuration réduit les composantes et améliore le F1 objet par rapport à C3 original dans cette mesure, mais la calibration diagnostique n'est pas indépendante au sens strict. MODEL_C3 reste expérimental.

CALIBRATION METHOD :
LEAVE_ONE_PATCH_OUT / diagnostic outputs only

CALIBRATION PATCHES :
5

CALIBRATION GT BUILDINGS :
100

LOCKED TEST USED FOR TUNING :
NO

SELECTED THRESHOLD :
0.30

MIN COMPONENT AREA PX :
479

MIN COMPONENT AREA M2 :
58.68

MORPHOLOGY :
NONE

POSTPROCESS COMPLEXITY :
LOW

MODEL_C OBJECT RECALL @0.30 :
0.1489

MODEL_C OBJECT F1 @0.30 :
0.1728

MODEL_C FALSE POSITIVES :
27

MODEL_C MISSED :
40

MODEL_C3 ORIGINAL OBJECT RECALL @0.30 :
0.2128

MODEL_C3 ORIGINAL OBJECT F1 @0.30 :
0.2041

MODEL_C3 ORIGINAL FALSE POSITIVES :
41

MODEL_C3 ORIGINAL MISSED :
37

MODEL_C3 CALIBRATED OBJECT RECALL @0.30 :
0.2190

MODEL_C3 CALIBRATED OBJECT F1 @0.30 :
0.2585

MODEL_C3 CALIBRATED FALSE POSITIVES :
14

MODEL_C3 CALIBRATED MISSED :
37

PIXEL IOU :
NOT_RECORDED_FOR_CALIBRATED_VARIANT

BOUNDARY F1 @1PX :
NOT_RECORDED_FOR_CALIBRATED_VARIANT

MODEL_C3 WEIGHTS :
UNCHANGED

PRODUCTION :
UNCHANGED

DECISION :
MODEL_C3_CALIBRATION_PARTIAL_IMPROVEMENT

READY_FOR_ACTIVE_LEARNING_EXPANSION :
NO

NEXT STEP :
14A.3D TRAINING / DATA STRATEGY REVISION
