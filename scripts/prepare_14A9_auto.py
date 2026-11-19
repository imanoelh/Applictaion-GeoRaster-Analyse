"""Pre-register one experimental pseudo-supervised cycle, never mutate GOLD."""
from pathlib import Path
import sys,json,importlib.util
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9B_datasets import ROOT,BASE,AL,DEV,GOLD,sha,dump,csvwrite
from gold_set_14A7_guard import assert_non_gold_development_records
from osgeo import gdal
import numpy as np
OUT=BASE/'14A9_auto_pipeline'
def main():
 if (OUT/'protocol.json').exists():raise RuntimeError('Cycle already registered: do not start another cycle or overwrite evidence')
 for d in ['candidate_pool','teacher_predictions','consensus','pseudo_labels','hard_negatives','auto_train','auto_dev','models','calibration','qa','gold_evaluation']:(OUT/d).mkdir(parents=True,exist_ok=True)
 goldhash={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()}
 expected=json.loads((AL/'qa/GOLD_HASHES_AFTER.json').read_text());assert all(goldhash.get(p)==h for p,h in expected.items()),'GOLD differs from prior locked baseline'
 dump(OUT/'qa/GOLD_BEFORE.json',goldhash)
 records=json.loads((AL/'manifests/14A9B_selected_patches.json').read_text());assert_non_gold_development_records(records)
 assert len(records)==14 and len({r['pixel_sha256'] for r in records})==14
 for r in records:
  assert sha(ROOT/r['rgb_path'])==r['rgb_sha256'];d=gdal.Open(str(ROOT/r['rgb_path']));a=d.ReadAsArray();assert a.shape==(3,512,512)
  np.savez_compressed(OUT/'candidate_pool'/(r['patch_id']+'.npz'),rgb=a)
 dump(OUT/'candidate_pool/manifest.json',records)
 old=json.loads((BASE/'qa/14A8_model_shootout/14A8_frozen_protocol.json').read_text());specs=[s for s in old['models'] if s['model'] in ['MODEL_C','MODEL_C3','MODEL_C6','MODEL_D']]
 for s in specs:assert sha(ROOT/s['path'])==s['sha256']
 protocol=dict(cycle=1,max_cycles=1,model='MODEL_C7_AUTO',production='MODEL_C_UNCHANGED',records=records,teachers=specs,
  votes='Four models, not four independent families: C/C3/C6 correlated; D required for tier A. E=max(C,D) is derived, excluded as an independent vote.',
  consensus=dict(A='votes>=3 AND D>=0.5 AND arithmetic mean>=0.6 AND abs(D-D_hflip)<=0.15',B='not A AND D>=0.95 AND D_hflip>=0.90; specialist-only proposals are lower weight, not human GT',
   C='other foreground uncertainty, ignored in supervised loss',D='all four probabilities<=0.05 AND D_hflip<=0.05; consensus-background proxy, not verified semantic negative',weights=dict(A=1.,B=.35,C=0.,D=.5),positive_min_component=1),
  training=dict(epochs=3,learning_rate=1e-5,weight_decay=1e-4,seed=149,initialization='MODEL_C6',native_size=512,batch=1,trainable='classifier and backbone.layer4; BatchNorm running stats frozen',augmentation='seeded flips, rotations90, brightness0.9-1.1; no resize',loss='confidence-weighted BCE + confidence-weighted Dice',threads=4),
  calibration=dict(thresholds=[.2,.3,.5],min_components=[4,64,128,479],morphology=['NONE','OPEN3'],connectivity=4,object_iou=.30,objective='Max one-to-one Object F1; constrained small recall >= baseline + one DEV small detection, FP <= max(baselineFP*1.5,baselineFP+3), final Boundary F1 >=95% baseline. If infeasible choose best F1 but mark constraints failed.',dev_labels='MULTI_TEACHER_PSEUDO_LABELS_NOT_HUMAN_GT'),
  gold_gates=dict(object_f1_gt=.3474178403755869,recall_gt=.22424242424242424,missed_lt=128,small_recall_ge=.10,fp_le=17,raw_boundary_f1_ge=.2829149533*.95,cpu_mean_seconds_le=12.1923543),
  gold_policy='ONE frozen checkpoint/config evaluation; no modifications after GOLD; compare cached C6 14A8; no retraining or next generation in this cycle',staging_only=True)
 dump(OUT/'protocol.json',protocol);(OUT/'protocol.sha256').write_text(sha(OUT/'protocol.json'))
 print('REGISTERED_ONE_CYCLE',len(records))
if __name__=='__main__':main()
