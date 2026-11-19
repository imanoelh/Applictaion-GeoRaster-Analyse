"""Honor the frozen historical chamfer definition when a prediction is empty.

Nearest distance to an empty contour is infinite; do not silently drop that
scene from a pooled mean. This affects MBD reporting only, never ranking/configs.
"""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout'
def write(path,rows):
 with path.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 rows=list(csv.DictReader((OUT/'14A8_patch_metrics.csv').open(encoding='utf-8-sig')));summary=json.loads((OUT/'14A8_summary.json').read_text());affected=[]
 for row in rows:
  empty=int(row['BOUNDARY_PRED_PIXELS'])==0 and int(row['BOUNDARY_GT_PIXELS'])>0
  row['EMPTY_PREDICTED_CONTOUR']=empty
  if empty:
   affected.append(dict(model=row['MODEL'],patch=row['PATCH']));row['MEAN_BOUNDARY_DISTANCE_PX']='INF';row['BOUNDARY_DISTANCE_SUM']='INF';row['BOUNDARY_DISTANCE_COUNT']=row['BOUNDARY_GT_PIXELS']
 for r in summary['ranking']:
  rr=[x for x in rows if x['MODEL']==r['MODEL']];finite=[x for x in rr if not x['EMPTY_PREDICTED_CONTOUR']];n=sum(int(x['BOUNDARY_DISTANCE_COUNT']) for x in finite);total=sum(float(x['BOUNDARY_DISTANCE_SUM']) for x in finite)
  r['MBD_FINITE_PATCHES']=len(finite);r['MBD_EMPTY_PRED_PATCHES']=4-len(finite);r['MEAN_BOUNDARY_DISTANCE_FINITE_ONLY_PX']=total/n if n else None;r['MEAN_BOUNDARY_DISTANCE_PX']='INF' if len(finite)<4 else total/n if n else None
 write(OUT/'14A8_patch_metrics.csv',rows);write(OUT/'14A8_global_model_comparison.csv',summary['ranking']);(OUT/'14A8_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 (OUT/'14A8_boundary_distance_QA.json').write_text(json.dumps(dict(affected=affected,definition='Frozen historical symmetric chamfer8; empty predicted contour means infinite distance for the GT contour',ranking_unchanged=True,object_pixel_boundary_f1_unchanged=True,no_new_inference=True,no_parameter_change=True),indent=2),encoding='utf-8')
 print('MBD empty-contour QA applied; all ranking metrics unchanged:',affected)
if __name__=='__main__':main()
