# ÉTAPE 14A.2A2 — SMART BUILDING PREANNOTATION V2

MODEL_F SegFormer a été exécuté comme moteur expérimental de rappel sur les 20 patches. MODEL_C est resté la source de précision à son seuil de production 0.50. Aucun modèle de production ni Ground Truth final n'a été modifié.

La fusion utilise IoU >= 0.05 ou distance entre centroïdes <= 6 pixels. Les géométries sont validées avec make_valid, intersectées avec l'emprise du patch et les composants de moins de 8 pixels sont supprimés. Le refinement promptable n'est pas disponible (NOT_AVAILABLE). Les 273 propositions restent UNREVIEWED dans une couche Assisted Proposals séparée.

Calibration limitée aux 2 patches GT approuvés 14A.1D4 (47 bâtiments), avec correspondance objet IoU >= 0.30 : 7 bâtiments appariés, 40 manqués, 25 faux candidats, précision 0.2188, rappel 0.1489.

PATCHES :
20

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

REFINEMENT ENGINE :
NOT_AVAILABLE

TOTAL PROPOSALS :
273

C_AND_F :
81

C_ONLY :
83

F_ONLY :
109

CALIBRATION GT BUILDINGS :
47

PROPOSAL RECALL :
0.1489

PROPOSAL PRECISION :
0.2188

MISSED GT AFTER UNION :
40

FALSE PROPOSALS :
25

ACCEPT ACTIONS :
81

CORRECT ACTIONS :
192

REJECT ACTIONS :
0

MANUAL DRAW REQUIRED :
40

MANUAL DRAW REQUIRED PERCENT :
85.11 % (calibration only)

GEOMETRY QA :
PASS

SMART PREANNOTATION USEFUL :
YES

TRAINING STARTED :
NO

FINAL GT MODIFIED :
NO

NEXT STEP :
14A.2B FAST HUMAN REVIEW /
REVISE PREANNOTATION STRATEGY
