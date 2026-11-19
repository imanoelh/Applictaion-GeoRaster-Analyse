"""C9 experimental worker: non-GOLD refinement, focal+Dice, one frozen GOLD pass."""
from pathlib import Path
import os,sys,json,time,random,hashlib
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
import numpy as np,torch
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';OLD=BASE/'14A11_hybrid_pipeline';OUT=BASE/'14A12_refinement_pipeline';P=json.loads((OUT/'protocol.json').read_text())
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
torch.set_num_threads(4);torch.set_num_interop_threads(1)
def model(path):
 m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);m.classifier=DeepLabHead(2048,1);ck=torch.load(path,map_location='cpu',weights_only=True);m.load_state_dict(ck['state_dict'],strict=True);return m
def loadrgb(r):
 with np.load(OLD/'inputs'/(r['patch_id']+'.npz')) as f:a=f['rgb']
 x=a.astype('float32');x=(x-x.min())/max(1e-6,float(x.max()-x.min()));return a,x
def predict(m,x):
 with torch.inference_mode():return torch.sigmoid(m(torch.from_numpy(np.ascontiguousarray(x[None])))['out'][0,0]).numpy().astype('float32')
def train():
 random.seed(P['training']['seed']);rng=np.random.default_rng(P['training']['seed']);ck=OLD/'models/MODEL_C8_HYBRID_epoch2.pth';m=model(ck)
 for n,p in m.named_parameters():p.requires_grad=not n.startswith('aux_classifier.')
 opt=torch.optim.AdamW([{'params':m.backbone.parameters(),'lr':P['training']['lr']},{'params':m.classifier.parameters(),'lr':P['training']['lr']*5}],weight_decay=P['training']['weight_decay'])
 train=[r for r in P['records'] if r['split']=='ACTIVE_LEARNING_TRAIN'];dev=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];hist=[];best=float('inf');stale=0
 for epoch in range(1,4):
  # small/dense patches are sampled twice per epoch; no new data are created.
  queue=train+[r for r in train if r['primary_group'] in ('SMALL','DENSE_ADJACENT')];queue=list(rng.permutation(queue));m.train()
  for mod in m.modules():
   if isinstance(mod,torch.nn.modules.batchnorm._BatchNorm):mod.eval()
  losses=[]
  for r in queue:
   _,x=loadrgb(r)
   with np.load(OUT/'train'/(r['patch_id']+'.npz')) as z:y=z['mask'].astype('float32');w=z['weight'].astype('float32')
   k=int(rng.integers(4));x=np.rot90(x,k,axes=(1,2));y=np.rot90(y,k);w=np.rot90(w,k)
   if rng.random()<.5:x=np.flip(x,2);y=np.flip(y,1);w=np.flip(w,1)
   x=np.clip(x*rng.uniform(.92,1.08),0,1);xt=torch.from_numpy(np.ascontiguousarray(x[None]));yt=torch.from_numpy(y.copy()[None,None]);wt=torch.from_numpy(w.copy()[None,None]);opt.zero_grad(set_to_none=True);z=m(xt)['out'];pr=torch.sigmoid(z);bce=torch.nn.functional.binary_cross_entropy_with_logits(z,yt,reduction='none');pt=pr*yt+(1-pr)*(1-yt);focal=((1-pt).pow(2)*bce*wt).sum()/wt.sum().clamp_min(1);dice=1-(2*(pr*yt*wt).sum()+1)/((pr*wt).sum()+(yt*wt).sum()+1);loss=focal+dice;loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.);opt.step();losses.append(float(loss.detach()))
  path=OUT/'models'/f'MODEL_C9_HYBRID_REFINED_epoch{epoch}.pth';torch.save(dict(state_dict=m.state_dict(),epoch=epoch,source='MODEL_C8_HYBRID',loss='focal_gamma2_plus_weighted_dice',protocol_sha256=sha(OUT/'protocol.json')),path);m.eval();dl=[]
  for r in dev:
   _,x=loadrgb(r);prob=predict(m,x);np.savez_compressed(OUT/'dev'/f'epoch{epoch}__{r["patch_id"]}.npz',probability=prob)
   with np.load(OUT/'dev'/(r['patch_id']+'.npz')) as z:y=z['mask'].astype('float32');w=z['weight'].astype('float32')
   q=np.clip(prob,1e-6,1-1e-6);dl.append(float(((-y*np.log(q)-(1-y)*np.log(1-q))*w).sum()/max(1,w.sum())))
  value=float(np.mean(dl));stale=0 if value<best-1e-6 else stale+1;best=min(best,value);hist.append(dict(epoch=epoch,checkpoint=str(path.relative_to(ROOT)),sha256=sha(path),train_loss=float(np.mean(losses)),dev_weighted_bce=value,stale_epochs=stale,queue_size=len(queue)));(OUT/'models/training_history.json').write_text(json.dumps(hist,indent=2));print('C9_EPOCH',epoch,value,flush=True)
def gold():
 freeze=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());assert sha(ROOT/freeze['checkpoint'])==freeze['checkpoint_sha256'];marker=OUT/'gold_evaluation/STARTED.json';runtime_path=OUT/'gold_evaluation/runtime.json';assert (not marker.exists()) or (not runtime_path.exists());marker.write_text(json.dumps(dict(freeze_sha=sha(OUT/'calibration/FROZEN_CANDIDATE.json'))));m=model(ROOT/freeze['checkpoint']);m.eval();old=BASE/'qa/14A8_model_shootout';records=json.loads((old/'14A8_frozen_protocol.json').read_text())['patches'];times=[]
 for r in records:
  with np.load(old/'inputs'/(r['patch_id']+'.npz')) as z:a=z['rgb'].astype('float32')
  x=(a-a.min())/max(1e-6,float(a.max()-a.min()));t=time.perf_counter();p=predict(m,x);times.append(dict(patch_id=r['patch_id'],seconds=time.perf_counter()-t));np.savez_compressed(OUT/'gold_evaluation'/(r['patch_id']+'.npz'),probability=p)
 (OUT/'gold_evaluation/runtime.json').write_text(json.dumps(times,indent=2))
if __name__=='__main__':{'train':train,'gold':gold}[sys.argv[1]]()
