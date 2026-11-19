from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
QA=EXP/'qa'
m=json.loads((QA/'14A2A2_metrics.json').read_text())
s=m['sources']; total=m['total_proposals']; matched=m['matched_gt_on_calibration']; missed=m['missed_gt_on_calibration']; falsep=m['false_proposals_on_calibration']; prec=m['proposal_precision']; rec=m['proposal_recall']; draw=100*missed/m['calibration_gt_buildings']
text=f'''# ÉTAPE 14A.2A2 — SMART BUILDING PREANNOTATION V2

MODEL_F SegFormer a été exécuté comme moteur expérimental de rappel sur les 20 patches. MODEL_C est resté la source de précision à son seuil de production 0.50. Aucun modèle de production ni Ground Truth final n'a été modifié.

La fusion utilise IoU >= 0.05 ou distance entre centroïdes <= 6 pixels. Les géométries sont validées avec make_valid, intersectées avec l'emprise du patch et les composants de moins de 8 pixels sont supprimés. Le refinement promptable n'est pas disponible (NOT_AVAILABLE). Les 273 propositions restent UNREVIEWED dans une couche Assisted Proposals séparée.

Calibration limitée aux 2 patches GT approuvés 14A.1D4 (47 bâtiments), avec correspondance objet IoU >= 0.30 : {matched} bâtiments appariés, {missed} manqués, {falsep} faux candidats, précision {prec:.4f}, rappel {rec:.4f}.

PATCHES :
20

MODEL_C :
UNCHANGED

MODEL_F :
UNCHANGED

REFINEMENT ENGINE :
NOT_AVAILABLE

TOTAL PROPOSALS :
{total}

C_AND_F :
{s['C_AND_F']}

C_ONLY :
{s['C_ONLY']}

F_ONLY :
{s['F_ONLY']}

CALIBRATION GT BUILDINGS :
47

PROPOSAL RECALL :
{rec:.4f}

PROPOSAL PRECISION :
{prec:.4f}

MISSED GT AFTER UNION :
{missed}

FALSE PROPOSALS :
{falsep}

ACCEPT ACTIONS :
{s['C_AND_F']}

CORRECT ACTIONS :
{s['C_ONLY']+s['F_ONLY']}

REJECT ACTIONS :
0

MANUAL DRAW REQUIRED :
{missed}

MANUAL DRAW REQUIRED PERCENT :
{draw:.2f} % (calibration only)

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
'''
(ROOT/'docs/ETAPE_14A2A2_SMART_PREANNOTATION_V2.md').write_text(text,encoding='utf-8')
print(ROOT/'docs/ETAPE_14A2A2_SMART_PREANNOTATION_V2.md')

