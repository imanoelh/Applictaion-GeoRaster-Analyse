"""Final integrity checks, tables and standalone figure. No inference or tuning."""
from pathlib import Path
import csv,json,hashlib,subprocess,sys,os,shutil
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def read(name):return list(csv.DictReader((OUT/name).open(encoding='utf-8-sig')))
def write(name,rows):
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 summary=json.loads((OUT/'14A8_summary.json').read_text());rank=summary['ranking'];models=summary['models_benchmarked'];assert len(models)==8
 hashes=read('14A8_gold_input_hashes.csv');assert all(sha(ROOT/r['PATH'])==r['SHA256'] for r in hashes)
 weights=json.loads((OUT/'14A8_model_weight_hashes.json').read_text());assert all(sha(ROOT/r['path'])==r['sha256'] for r in weights)
 assert sha(OUT/'14A8_frozen_protocol.json')==(OUT/'14A8_frozen_protocol.sha256').read_text()
 matching=read('14A8_gt_object_matching.csv');assert len(matching)==165*8
 for mid in models:
  rows=[r for r in matching if r['MODEL']==mid];assert len({r['GT_ID'] for r in rows})==165
  pairs=[(r['PATCH'],r['MATCHED_PRED_ID']) for r in rows if r['MATCHED_030']=='True'];assert len(pairs)==len(set(pairs))
  agg=next(r for r in rank if r['MODEL']==mid);assert agg['GT_OBJECTS']==agg['TP']+agg['FN']==165 and agg['PRED_OBJECTS']==agg['TP']+agg['FP'];assert abs(agg['OBJECT_F1']-2*agg['TP']/(165+agg['PRED_OBJECTS']))<1e-12
  assert all(0<=agg[k]<=1 for k in ('OBJECT_F1','OBJECT_PRECISION','OBJECT_RECALL','PIXEL_IOU','DICE','BOUNDARY_F1','SMALL_RECALL'))
 assert sum(r['FP'] for r in rank)==len(read('14A8_false_positive_analysis.csv'));assert sum(r['FN'] for r in rank)==len(read('14A8_missed_buildings_analysis.csv'))
 sensitivity=read('14A8_object_iou_sensitivity.csv');srows=[]
 for mid in models:
  for t in ['0.3','0.5','0.7']:
   q=[r for r in sensitivity if r['MODEL']==mid and r['IOU_THRESHOLD']==t];tp=sum(int(r['TP']) for r in q);pred=sum(int(r['PRED']) for r in q)
   srows.append(dict(MODEL=mid,IOU_THRESHOLD=t,GT=165,PRED=pred,TP=tp,FP=pred-tp,FN=165-tp,F1=2*tp/(165+pred)))
 write('14A8_global_object_iou_sensitivity.csv',srows)
 patch=read('14A8_patch_metrics.csv');winners=[]
 for scene in ['RESIDENTIAL','DENSE','INDUSTRIAL','DIFFICULT']:
  rr=[r for r in patch if r['SCENE']==scene];best=max(float(r['OBJECT_F1']) for r in rr)
  winners.append(dict(SCENE=scene,BEST_OBJECT_F1=best,MODELS=';'.join(r['MODEL'] for r in rr if abs(float(r['OBJECT_F1'])-best)<1e-12)))
 write('14A8_scene_winners.csv',winners)
 area=read('14A8_gt_area_distribution.csv');a=np.array([float(r['area_m2']) for r in area]);assert len(a)==165
 distribution=dict(count=165,small_count=int((a<=50).sum()),small_cutoff_m2=50,cutoff_predeclared=True,min_m2=float(a.min()),q25_m2=float(np.quantile(a,.25)),median_m2=float(np.median(a)),q75_m2=float(np.quantile(a,.75)),max_m2=float(a.max()))
 (OUT/'14A8_area_summary.json').write_text(json.dumps(distribution,indent=2),encoding='utf-8')
 adjacent=read('14A8_adjacent_buildings_analysis.csv');adj_summary=[]
 for mid in models:
  rr=[r for r in adjacent if r['MODEL']==mid];involved={(r['PATCH'],g) for r in rr if r['TYPE']=='MERGED' for g in r['GT_IDS'].split(';')}
  adj_summary.append(dict(MODEL=mid,MERGED_PREDICTED_OBJECTS=sum(r['TYPE']=='MERGED' for r in rr),GT_BUILDINGS_INVOLVED_IN_MERGES=len(involved),FRAGMENTED_GT_OBJECTS=sum(r['TYPE']=='FRAGMENTED' for r in rr)))
 write('14A8_merge_fragment_summary.csv',adj_summary)
 # Stable figure, not an interactive UI; all values come from frozen-run CSVs.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 labels=[r['MODEL'] for r in rank];colors=['#117c83' if r['MODEL']=='MODEL_C6' else '#4a70a0' for r in rank]
 fig,axes=plt.subplots(2,3,figsize=(16,9),layout='constrained')
 for ax,(field,title) in zip(axes.ravel(),[('OBJECT_F1','Object F1 @ IoU >= 0.30'),('OBJECT_RECALL','Object recall'),('FP','False positives'),('SMALL_RECALL','Small-building recall (38 GT)'),('BOUNDARY_F1','Boundary F1 @ 1 px'),('CPU_TIME_MEAN','Mean CPU seconds / patch')]):
  vals=[r[field] for r in rank];ax.barh(labels[::-1],vals[::-1],color=colors[::-1]);ax.set_title(title);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
  if field in ('OBJECT_F1','OBJECT_RECALL','SMALL_RECALL','BOUNDARY_F1'):ax.set_xlim(0,1)
 fig.suptitle('GeoRaster 14A.8 | Locked internal GOLD: 4 patches, 165 human objects | No tuning / no promotion',fontsize=15)
 fig.savefig(OUT/'14A8_METRICS_DASHBOARD.png',dpi=170);plt.close(fig)
 # No production code changed in this task; earlier offline lifecycle edits are separate.
 git=os.environ.get('GEORASTER_GIT_EXE') or shutil.which('git');assert git,'Provide GEORASTER_GIT_EXE when QGIS wrapper replaces PATH'
 p=subprocess.run([git,'diff','--name-only','--','backend/app','frontend'],cwd=ROOT,capture_output=True,text=True);assert p.returncode==0 and not p.stdout.strip()
 exits=json.loads((OUT/'14A8_worker_exits.json').read_text());assert len(exits)==8 and all(r['exit_code']==0 for r in exits)
 decision=dict(best_candidate=rank[0]['MODEL'],best_overall_tested=rank[0]['MODEL'],model_c6_generalization='PARTIAL',final_decision='MODEL_C6_PARTIAL',next_step='TARGETED_ACTIVE_LEARNING',
   rationale='C6 ranks first on object F1/recall and boundaries, but misses128/165; small recall0/38, industrial0/23; merged14 predicted groups. Relative gain confirmed, intended detection quality not reached.',
   gold_input_hashes_unchanged=len(hashes),model_artifact_hashes_unchanged=len(weights),models_audited=len(read('14A8_model_availability.csv')),models_benchmarked=8,
   primary_object_iou=.30,all_worker_exit_codes_zero=True,unique_gt_rows_verified=1320,no_many_to_one_tp=True,no_training=True,no_threshold_tuning=True,production_model='MODEL_C',production_modified=False,external_generalization_claim=False)
 (OUT/'14A8_FINAL_DECISION.json').write_text(json.dumps(decision,indent=2),encoding='utf-8');print(json.dumps(decision,indent=2))
if __name__=='__main__':main()
