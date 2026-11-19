"""Finish the existing one-cycle run; never silently train or repeat GOLD."""
from pathlib import Path
import subprocess,json,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline'
QGIS=r'C:\Program Files\QGIS 3.40.14\bin\python-qgis-ltr.bat';ML=str(ROOT/'.venv_model_training/Scripts/python.exe')

def run(exe,script,*args):
 log=OUT/'logs'/(script.replace('.py','')+'_'+'_'.join(args)+'.log');t=time.perf_counter();print('START',script,args,flush=True)
 with log.open('w',encoding='utf-8') as f:p=subprocess.run([exe,'-P','-u',str(ROOT/'scripts'/script),*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 print('EXIT',script,p.returncode,'SECONDS',round(time.perf_counter()-t,2),flush=True)
 if p.returncode:raise RuntimeError(str(log))

def main():
 deadline=time.monotonic()+2400
 while True:
  path=OUT/'models/training_history.json'
  try:history=json.loads(path.read_text())
  except (FileNotFoundError,json.JSONDecodeError):history=[]
  if len(history)==3:break
  if time.monotonic()>deadline:raise RuntimeError('Incomplete training: no automatic restart')
  time.sleep(5)
 run(QGIS,'finalize_14A11_hybrid.py','devloss')
 if not (OUT/'calibration/FROZEN_CANDIDATE.json').exists():run(QGIS,'evaluate_14A11_hybrid.py','calibrate')
 if not (OUT/'gold_evaluation/STARTED.json').exists():run(ML,'run_14A11_ml.py','gold')
 else:assert (OUT/'gold_evaluation/runtime.json').exists(),'Incomplete GOLD attempt: repeat forbidden'
 if not (OUT/'gold_evaluation/FINAL_RESULT.json').exists():run(QGIS,'evaluate_14A11_hybrid.py','goldscore')
 run(QGIS,'finalize_14A11_hybrid.py');print('C8_ONE_CYCLE_COMPLETED_NO_PROMOTION',flush=True)
if __name__=='__main__':main()
