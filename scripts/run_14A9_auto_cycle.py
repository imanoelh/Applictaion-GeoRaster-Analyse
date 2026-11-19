"""Single-cycle orchestration. No PowerShell policy change, no production promotion."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A9_auto_pipeline'
QGIS=r'C:\Program Files\QGIS 3.40.14\bin\python-qgis-ltr.bat'
ML=str(ROOT/'.venv_model_training/Scripts/python.exe')
def run(exe,script,*args):
 print('START',script,args,flush=True)
 subprocess.run([exe,'-P','-u',str(ROOT/'scripts'/script),*args],cwd=ROOT,check=True)
 print('COMPLETE',script,args,flush=True)
def main():
 if not (OUT/'protocol.json').exists():run(QGIS,'prepare_14A9_auto.py')
 if not (OUT/'qa/TEACHER_RUNTIME.json').exists():run(ML,'run_14A9_auto_ml.py','teachers')
 if not (OUT/'qa/CONSENSUS_SUMMARY.json').exists():run(QGIS,'evaluate_14A9_auto.py','consensus')
 if not (OUT/'qa/PSEUDO_TECHNICAL_QA.json').exists():run(QGIS,'qa_14A9_auto_pseudo.py')
 if not (OUT/'models/training_history.json').exists():run(ML,'run_14A9_auto_ml.py','train')
 else:
  assert len(json.loads((OUT/'models/training_history.json').read_text()))==3,'Partial training: refuse silent restart'
 if not (OUT/'calibration/FROZEN_CANDIDATE.json').exists():run(QGIS,'evaluate_14A9_auto.py','calibrate')
 if not (OUT/'gold_evaluation/ATTEMPT_STARTED.json').exists():run(ML,'run_14A9_auto_ml.py','gold')
 else:assert (OUT/'gold_evaluation/inference_times.json').exists(),'Incomplete GOLD attempt; second attempt forbidden'
 if not (OUT/'gold_evaluation/FINAL_RESULT.json').exists():run(QGIS,'evaluate_14A9_auto.py','goldscore')
 run(QGIS,'report_14A9_auto.py')
 print('ONE_CYCLE_FINISHED_NO_PRODUCTION_PROMOTION',flush=True)
if __name__=='__main__':main()
