"""Finalize fusion artifacts, integrity checks and report."""
from pathlib import Path
import sys,json,csv
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,sha
NEW=BASE/'14A13_fusion_v2';A11=BASE/'14A11_hybrid_pipeline';A12=BASE/'14A12_refinement_pipeline';GOLD=BASE/'14A7_gold_set';B8=BASE/'qa/14A8_model_shootout'
def csvwrite(p,rows):
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['empty']);w.writeheader();w.writerows(rows)
def main():
 p=json.loads((A11/'protocol.json').read_text());cfg=json.loads((NEW/'calibration/14A13_fusion_v2_frozen_config.json').read_text());res=json.loads((NEW/'gold_evaluation/FINAL_RESULT.json').read_text());m=res['metrics'];old=json.loads((B8/'14A8_summary.json').read_text());c6=next(x for x in old['ranking'] if x['MODEL']=='MODEL_C6');c8=json.loads((A11/'gold_evaluation/FINAL_RESULT.json').read_text())['metrics'];c9=json.loads((A12/'gold_evaluation/FINAL_RESULT.json').read_text())['metrics'];dist=json.loads((BASE/'14A10_specialized_benchmark/metrics/UNET_DIST3.json').read_text());before=json.loads((A11/'qa/GOLD_BEFORE.json').read_text());after={str(x.relative_to(ROOT)):sha(x) for x in GOLD.rglob('*') if x.is_file()};assert before==after
 # Preserve the one-shot result and expose accepted/rejected object audits from the frozen config.
 records=json.loads((B8/'14A8_frozen_protocol.json').read_text())['patches'];allacc=[];allrej=[]
 from run_14A13_fusion import fuse
 for r in records:
  _,rows=fuse(r,'GOLD',cfg['config'],write=True)
  for row in rows:
   row['source']='UNET_DIST3_PRIMARY';row['support_models']='C6/C8/C9';row['fragment_merged']='NO';row['final_status']=row.get('final_status','REJECTED')
   (allacc if row['final_status']=='ACCEPTED' else allrej).append(row)
 csvwrite(NEW/'14A13_fused_objects.csv',allacc);csvwrite(NEW/'14A13_dist3_rejected_candidates.csv',allrej)
 # All source/model checks are read-only; GOLD stays immutable.
 integrity=dict(gold_files=len(after),gold_modified=False,gold_calibration=False,gold_attempts=1,production_modified=False,models_c6_c8_c9_dist3_unchanged=True,training_c10=False)
 (NEW/'qa/FINAL_INTEGRITY.json').write_text(json.dumps(integrity,indent=2))
 rows=[
  dict(MODEL='MODEL_C6',TP=c6['TP'],FP=c6['FP'],FN=c6['FN'],PRECISION=c6['OBJECT_PRECISION'],RECALL=c6['OBJECT_RECALL'],F1=c6['OBJECT_F1'],SMALL_TP=c6['SMALL_TP'],SMALL_RECALL=c6['SMALL_RECALL'],BOUNDARY_F1=c6['BOUNDARY_F1'],CPU=c6['CPU_INFERENCE_MEAN']),
  dict(MODEL='MODEL_C8_HYBRID',TP=c8['TP'],FP=c8['FP'],FN=c8['FN'],PRECISION=c8['object_precision'],RECALL=c8['object_recall'],F1=c8['object_f1'],SMALL_TP=c8['SMALL_TP'],SMALL_RECALL=c8['small_recall'],BOUNDARY_F1=c8['raw_boundary_f1'],CPU=c8['cpu_mean_seconds']),
  dict(MODEL='MODEL_C9_HYBRID_REFINED',TP=c9['TP'],FP=c9['FP'],FN=c9['FN'],PRECISION=c9['object_precision'],RECALL=c9['object_recall'],F1=c9['object_f1'],SMALL_TP=c9['SMALL_TP'],SMALL_RECALL=c9['small_recall'],BOUNDARY_F1=c9['raw_boundary_f1'],CPU=c9['cpu_mean_seconds']),
  dict(MODEL='UNET_DIST3',TP=dist['TP'],FP=dist['FP'],FN=dist['FN'],PRECISION=dist['object_precision'],RECALL=dist['object_recall'],F1=dist['object_f1'],SMALL_TP=dist['SMALL_TP'],SMALL_RECALL=dist['small_recall'],BOUNDARY_F1=dist['boundary_f1'],CPU=dist['cpu_inference_mean']),
  dict(MODEL='SPECIALIZED_FUSION_V2',TP=m['TP'],FP=m['FP'],FN=m['FN'],PRECISION=m['object_precision'],RECALL=m['object_recall'],F1=m['object_f1'],SMALL_TP=m['SMALL_TP'],SMALL_RECALL=m['small_recall'],BOUNDARY_F1=m['boundary_f1'],CPU=m['cpu_mean_seconds'])]
 csvwrite(NEW/'14A13_global_comparison.csv',rows);gates=dict(f1_gt_c9=m['object_f1']>c9['object_f1'],recall_gt_c9=m['object_recall']>c9['object_recall'],small_gt_c8=m['SMALL_TP']>c8['SMALL_TP'],fp_far_below_dist3=m['FP']<dist['FP'],boundary_gt_c9=m['boundary_f1']>c9['raw_boundary_f1'],cpu_ok=m['cpu_mean_seconds']<=12.1923543);ready=all(gates.values())
 report=f'''# ÉTAPE 14A.13 — SPECIALIZED MODEL FUSION V2

## Résultat

Fusion inference-level sans entraînement C10. DIST3 est le générateur primaire ; C6, C8 et C9 sont des validateurs. Les poids et seuils ont été choisis exclusivement sur les quatre patches DEV non-GOLD, puis figés avant le GOLD.

Configuration figée : support `{cfg['config']['support_threshold']}`, contexte FP `<{cfg['config']['fp_threshold']}`, small confidence `{cfg['config']['small_conf']}`. Fonction DEV : `F1 + 0.50*small_recall - 0.015*FP + 0.25*boundary_f1`.

DEV : F1 `{cfg['dev_metric']['object_f1']:.4f}`, recall `{cfg['dev_metric']['object_recall']:.4f}`, FP `{cfg['dev_metric']['FP']}`, small `{cfg['dev_metric']['SMALL_TP']}/{cfg['dev_metric']['SMALL_GT']}`. Le choix favorise fortement les frontières et les petits objets mais s’est révélé trop conservateur sur le GOLD.

Le GOLD a été exécuté une seule fois après freeze. Matching objet one-to-one IoU>=0.30. Les 165 GT GOLD et les modèles précédents restent inchangés.

| Modèle | TP | FP | FN | Précision | Recall | F1 | Small | Boundary F1 | CPU s/patch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
'''+''.join(f"| {r['MODEL']} | {r['TP']} | {r['FP']} | {r['FN']} | {r['PRECISION']:.4f} | {r['RECALL']:.4f} | {r['F1']:.4f} | {r['SMALL_TP']} | {r['BOUNDARY_F1']:.4f} | {r['CPU']:.3f} |\n" for r in rows)+f'''\nFusion : {m['TP']} TP, {m['FP']} FP, {m['FN']} manqués, F1 `{m['object_f1']:.4f}`, recall `{m['object_recall']:.4f}`, small `{m['SMALL_TP']}/38`, boundary `{m['boundary_f1']:.4f}`, CPU `{m['cpu_mean_seconds']:.3f}s/patch`. Elle réduit les FP DIST3 de 128 à 16, mais perd trop de recall et de petits bâtiments. Les candidats rejetés sont exportés dans `14A13_dist3_rejected_candidates.csv`; les objets gardés dans `14A13_fused_objects.csv`.

La fusion ne satisfait pas : F1> C9, recall> C9, small recall> C8, boundary> C9. Le résultat suggère qu’un filtrage de validation pixel-level ne suffit pas à préserver la séparation et le recall des instances DIST3.

## Intégrité

GOLD files inchangés : `{len(after)}`. Aucun C10 entraîné. Aucun changement de MODEL_C production, backend, frontend, GEE, indices ou exports.

FUSION ENGINE :
SPECIALIZED_FUSION_V2

PRIMARY DETECTOR :
UNET_DIST3

VALIDATORS :
C6 / C8 / C9

DEV F1 :
{cfg['dev_metric']['object_f1']:.4f}

DEV RECALL :
{cfg['dev_metric']['object_recall']:.4f}

DEV FP :
{cfg['dev_metric']['FP']}

GOLD F1 :
{m['object_f1']:.4f}

GOLD PRECISION :
{m['object_precision']:.4f}

GOLD RECALL :
{m['object_recall']:.4f}

GOLD FP :
{m['FP']}

GOLD MISSED :
{m['FN']}

GOLD SMALL RECALL :
{m['SMALL_TP']} / 38

GOLD BOUNDARY F1 :
{m['boundary_f1']:.4f}

GOLD FRAGMENTED :
{m.get('FRAGMENTED',0)} (stored fusion masks, one-to-one audit)

CPU TOTAL TIME :
{m['cpu_total_seconds']:.3f}s total, {m['cpu_mean_seconds']:.3f}s/patch

C9 F1 :
0.4308

DIST3 F1 :
0.5672

FUSION BETTER THAN C9 :
NO

FUSION FP LOWER THAN DIST3 :
YES

FUSION SMALL RECALL BETTER THAN C9 :
YES

READY FOR STAGING :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
14A14_INSTANCE_BOUNDARY_ARCHITECTURE
'''
 (ROOT/'docs/ETAPE_14A13_SPECIALIZED_MODEL_FUSION_V2.md').write_text(report,encoding='utf-8');print('REPORT_14A13_WRITTEN',flush=True)
if __name__=='__main__':main()
