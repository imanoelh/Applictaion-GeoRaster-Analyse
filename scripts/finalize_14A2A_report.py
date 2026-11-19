from pathlib import Path
import json
import rasterio
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
QA=EXP/'qa'; summary=json.loads((QA/'14A2A_summary.json').read_text(encoding='utf-8'))
manifest=json.loads((EXP/'manifests/dataset_manifest.json').read_text(encoding='utf-8'))
aligned=0
for p in manifest['patches']:
    rgb=EXP/p['split']/'rgb'/f"{p['patch_id']}.tif"
    c=EXP/'pseudo_labels/model_c/probability'/f"{p['patch_id']}.tif"
    d=EXP/'smart_assisted_annotation/model_d/probability'/f"{p['patch_id']}.tif"
    with rasterio.open(rgb) as a, rasterio.open(c) as b, rasterio.open(d) as e:
        ok=(a.width,a.height,a.crs,a.transform)==(b.width,b.height,b.crs,b.transform)==(e.width,e.height,e.crs,e.transform)
        aligned+=int(ok)
summary['spatial_alignment']=f'{aligned} / {len(manifest["patches"])}'
calibration = {}
calib_root = ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
for threshold in (0.5, 0.65, 0.8):
    tp = fp = fn = tn = 0
    for patch_id in ('14A_001_residential', '14A_003_dense_urban'):
        with rasterio.open(calib_root/'masks/ground_truth_final'/f'{patch_id}.tif') as gsrc, rasterio.open(calib_root/'qa/14A1E_model_c_rebenchmark/probability'/f'{patch_id}.tif') as psrc:
            gt = gsrc.read(1) > 0
            pred = psrc.read(1) >= threshold
            tp += int(np.logical_and(pred, gt).sum())
            fp += int(np.logical_and(pred, ~gt).sum())
            fn += int(np.logical_and(~pred, gt).sum())
            tn += int(np.logical_and(~pred, ~gt).sum())
    calibration[str(threshold)] = {
        'precision': round(tp/(tp+fp), 6) if tp+fp else 0.0,
        'recall': round(tp/(tp+fn), 6) if tp+fn else 0.0,
        'false_positive_rate': round(fp/(fp+tn), 6) if fp+tn else 0.0,
        'support': '2 approved 14A.1D4 patches; pixel calibration proxy only'
    }
summary['calibration_results'] = calibration
(QA/'14A2A_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
report=ROOT/'docs/ETAPE_14A2A_SMART_ASSISTED_ANNOTATION.md'
report.write_text(f'''# ÉTAPE 14A.2A — SMART ASSISTED BUILDING ANNOTATION & ACTIVE LEARNING

## Exécution

Le workflow a analysé les 20 patches 14A.2 sans modifier MODEL_C, la production, les indices ou les patches TEST. MODEL_C n’a pas été réexécuté : ses probabilités et polygones existants ont été réutilisés. MODEL_D est exécuté uniquement comme second moteur expérimental ONNX CPU.

La confiance est calculée à partir de la probabilité moyenne/médiane/maximale, de la surface, de la compacité, de la distance au bord et de l’accord spatial MODEL_C/MODEL_D. Les seuils testés sont explicitement 0.50, 0.65 et 0.80 ; ils restent provisoires car la calibration repose uniquement sur les deux patches GT approuvés 14A.1D4.

Les propositions sont écrites dans `smart_assisted_annotation/proposals/ASSISTED_PROPOSALS.geojson`, séparées du Ground Truth final. Le projet QGIS contient RGB, MODEL_C, MODEL_D, Ground Truth, propositions catégorisées et bookmarks de revue.

## Résultats QA

- Alignement RGB / MODEL_C / MODEL_D : {aligned} / 20.
- Les prédictions MODEL_D sont expérimentales et ne sont pas enregistrées comme production.
- Le taux de revue est calculé sur les objets produits, sans estimation théorique.
- Aucun entraînement n’a été lancé.

Calibration proxy (pixels, 14A.1D4 only) : {json.dumps(calibration, ensure_ascii=False)}.

Livrables : `qa/14A2A_candidate_confidence.csv`, `qa/14A2A_model_agreement.csv`, `qa/14A2A_active_learning_priority.csv`, `qa/14A2A_summary.json`, `qa/14A2A_contact_sheet.png`, `qgis/14A2A_SMART_ASSISTED_ANNOTATION.qgz`.

PATCHES ANALYZED :
20

MODEL_C :
UNCHANGED

SECOND MODEL :
MODEL_D WHU U-Net++ EfficientNet-B4 ONNX Runtime CPU (EXPERIMENTAL ONLY)

TOTAL CANDIDATES :
{summary['total_candidates']}

HIGH CONFIDENCE CONSENSUS :
{summary['high_confidence_consensus']}

REVIEW REQUIRED :
{summary['review_required']}

LOW CONFIDENCE :
{summary['low_confidence']}

PERCENT HUMAN REVIEW REQUIRED :
{summary['percentage_human_review_required']} %

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
''',encoding='utf-8')
print(report)
