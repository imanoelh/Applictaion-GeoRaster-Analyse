"""Standalone smoke -> frozen GOLD benchmark, without training or tuning."""
from pathlib import Path
import subprocess,sys,json,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A10_specialized_benchmark'
ML=str(ROOT/'.venv_model_training/Scripts/python.exe');QGIS=r'C:\Program Files\QGIS 3.40.14\bin\python-qgis-ltr.bat'
def run(exe,script,mid,stage=None):
 args=[exe,'-P','-u',str(ROOT/'scripts'/script),mid]+([stage] if stage else []);log=OUT/'logs'/(mid+'_'+script.replace('.py','')+'_'+str(stage)+'.log');t=time.perf_counter()
 with log.open('w',encoding='utf-8') as f:p=subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=240)
 print(mid,script,stage,'EXIT',p.returncode,'SECONDS',round(time.perf_counter()-t,2),flush=True)
 return p.returncode
def main():
 p=json.loads((OUT/'protocol.json').read_text());runs=[]
 for s in p['models']:
  mid=s['model'];code=run(ML,'run_14A10_inference.py',mid,'smoke');status='NOT_LOADABLE' if code else json.loads((OUT/'smoke'/(mid+'.json')).read_text())['status'];post=None
  if status=='READY':post=run(QGIS,'score_14A10_models.py',mid,'--smoke');status='READY' if post==0 else 'DEPENDENCY_BLOCKED'
  runs.append(dict(model=mid,smoke_exit_code=code,postprocess_exit_code=post,status=status));(OUT/'smoke/PROCESS_EXITS.json').write_text(json.dumps(runs,indent=2))
 for r in runs:
  if r['status']!='READY':continue
  mid=r['model'];folder=OUT/'predictions'/mid
  if (folder/'STARTED.json').exists():raise RuntimeError('Refuse automatic second GOLD inference: '+mid)
  code=run(ML,'run_14A10_inference.py',mid,'gold');r['gold_exit_code']=code
  if code==0:r['scoring_exit_code']=run(QGIS,'score_14A10_models.py',mid)
  (OUT/'qa/BENCHMARK_EXITS.json').write_text(json.dumps(runs,indent=2))
 print('BENCHMARK_FINISHED',flush=True)
if __name__=='__main__':main()
