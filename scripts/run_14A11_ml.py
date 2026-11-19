"""Isolated C8 workers: teachers, supervised pseudo training, final frozen GOLD."""
from pathlib import Path
import os,sys,json,time,hashlib,random
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
import numpy as np
import torch
import onnxruntime as ort
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';OUT=BASE/'14A11_hybrid_pipeline';P=json.loads((OUT/'protocol.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text();assert all(sha(ROOT/p)==h for p,h in json.loads((OUT/'qa/GOLD_BEFORE.json').read_text()).items())
torch.set_num_threads(4);torch.set_num_interop_threads(1)
def model(path):
 m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);m.classifier=DeepLabHead(2048,1);ck=torch.load(path,map_location='cpu',weights_only=True);m.load_state_dict(ck['state_dict'],strict=True);m.eval();return m
def loadrgb(r):
 with np.load(OUT/'inputs'/(r['patch_id']+'.npz')) as f:a=f['rgb']
 x=a.astype('float32');x=(x-x.min())/max(1e-6,float(x.max()-x.min()));return a,x
def predict(m,x):
 with torch.inference_mode():return torch.sigmoid(m(torch.from_numpy(np.ascontiguousarray(x[None])))['out'][0,0]).numpy().astype('float32')
def teachers():
 assert sha(ROOT/P['c6_path'])==P['c6_sha256'] and sha(ROOT/P['dist3_path'])==P['dist3_sha256'];o=ort.SessionOptions();o.intra_op_num_threads=4;o.inter_op_num_threads=1;s=ort.InferenceSession(str(ROOT/P['dist3_path']),sess_options=o,providers=['CPUExecutionProvider']);m=None;times=[]
 def dist(a):
  x=(a.astype('float32')/255.-np.array([.485,.456,.406],np.float32)[:,None,None])/np.array([.229,.224,.225],np.float32)[:,None,None];result=np.zeros((3,512,512),np.float32)
  for y in [0,256]:
   for xx in [0,256]:
    z=s.run(None,{s.get_inputs()[0].name:np.ascontiguousarray(x[None,:,y:y+256,xx:xx+256])})[0][0];result[:,y:y+256,xx:xx+256]=1/(1+np.exp(-np.clip(z,-80,80)))
  return result
 for r in P['records']:
  a,x=loadrgb(r);t=time.perf_counter();ch=dist(a);flip=np.flip(dist(np.flip(a,axis=2)),axis=2).copy();cache=BASE/'14A9B_active_learning/qa'/(r['patch_id']+'_C6_probability.npz')
  if cache.exists():
   with np.load(cache) as f:c6=f['probability']
  else:
   if m is None:m=model(ROOT/P['c6_path'])
   c6=predict(m,x)
  np.savez_compressed(OUT/'teacher_predictions'/(r['patch_id']+'.npz'),c6=c6,dist3=ch,dist3_flip=flip);times.append(dict(patch_id=r['patch_id'],seconds=time.perf_counter()-t,c6_cache=cache.exists()));print('HYBRID_TEACHER_INPUT',r['patch_id'],round(times[-1]['seconds'],2),flush=True)
 (OUT/'qa/TEACHER_RUNTIME.json').write_text(json.dumps(times,indent=2))
def train():
 cfg=P['training'];torch.manual_seed(cfg['seed']);rng=np.random.default_rng(cfg['seed']);random.seed(cfg['seed']);m=model(ROOT/P['c6_path'])
 for name,p in m.named_parameters():p.requires_grad=not name.startswith('aux_classifier.')
 opt=torch.optim.AdamW([dict(params=m.backbone.parameters(),lr=cfg['lr_backbone']),dict(params=m.classifier.parameters(),lr=cfg['lr_head'])],weight_decay=cfg['weight_decay'])
 train=[r for r in P['records'] if r['split']=='ACTIVE_LEARNING_TRAIN'];dev=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];history=[];best_loss=float('inf');stale=0
 # Stratified round-robin by context, each source patch exactly once per epoch.
 groups={}
 for r in train:groups.setdefault(r['primary_group'],[]).append(r)
 for epoch in range(1,cfg['epochs']+1):
  queue=[];buckets=[list(rng.permutation(len(v))) for v in groups.values()];values=list(groups.values())
  while any(buckets):
   for indices,vals in zip(buckets,values):
    if indices:queue.append(vals[indices.pop()])
  m.train()
  for mod in m.modules():
   if isinstance(mod,torch.nn.modules.batchnorm._BatchNorm):mod.eval()
  losses=[]
  for r in queue:
   _,x=loadrgb(r)
   with np.load(OUT/'train'/(r['patch_id']+'.npz')) as f:y=f['mask'].astype('float32');w=f['weight'].astype('float32')
   k=int(rng.integers(4));x=np.rot90(x,k,axes=(1,2));y=np.rot90(y,k);w=np.rot90(w,k)
   if rng.random()<.5:x=np.flip(x,2);y=np.flip(y,1);w=np.flip(w,1)
   x=np.clip(x*rng.uniform(.9,1.1),0,1);xt=torch.from_numpy(np.ascontiguousarray(x[None]));yt=torch.from_numpy(y.copy()[None,None]);wt=torch.from_numpy(w.copy()[None,None]);opt.zero_grad(set_to_none=True);z=m(xt)['out'];pr=torch.sigmoid(z);bce=(torch.nn.functional.binary_cross_entropy_with_logits(z,yt,reduction='none')*wt).sum()/wt.sum().clamp_min(1);dice=1-(2*(pr*yt*wt).sum()+1)/((pr*wt).sum()+(yt*wt).sum()+1);loss=bce+dice;loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.);opt.step();losses.append(float(loss.detach()));print('C8_TRAIN',epoch,r['patch_id'],round(losses[-1],5),flush=True)
  path=OUT/'models'/f'MODEL_C8_HYBRID_epoch{epoch}.pth';torch.save(dict(state_dict=m.state_dict(),epoch=epoch,source='MODEL_C6',labels='HYBRID_C6_DIST3_PSEUDO',protocol_sha256=sha(OUT/'protocol.json')),path);m.eval();devloss=[]
  for r in dev:
   _,x=loadrgb(r);p=predict(m,x);np.savez_compressed(OUT/'dev'/(f"epoch{epoch}__"+r['patch_id']+'.npz'),probability=p)
   with np.load(OUT/'dev'/(r['patch_id']+'.npz')) as f:y=f['mask'].astype('float32');w=f['weight']
   q=np.clip(p,1e-6,1-1e-6);devloss.append(float(((-y*np.log(q)-(1-y)*np.log(1-q))*w).sum()/max(1,w.sum())))
  dl=float(np.mean(devloss));stale=0 if dl<best_loss-1e-6 else stale+1;best_loss=min(best_loss,dl);history.append(dict(epoch=epoch,checkpoint=str(path.relative_to(ROOT)),sha256=sha(path),train_loss=float(np.mean(losses)),dev_weighted_bce=dl,stale_epochs=stale));(OUT/'models/training_history.json').write_text(json.dumps(history,indent=2));print('C8_EPOCH_COMPLETED',epoch,dl,flush=True)
  if stale>=cfg['early_stopping_patience']:break
def gold():
 frozen=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());assert sha(ROOT/frozen['checkpoint'])==frozen['checkpoint_sha256'];assert not (OUT/'gold_evaluation/STARTED.json').exists();(OUT/'gold_evaluation/STARTED.json').write_text(json.dumps(dict(freeze_sha256=sha(OUT/'calibration/FROZEN_CANDIDATE.json'))));m=model(ROOT/frozen['checkpoint']);predict(m,np.zeros((3,512,512),np.float32));times=[]
 old=BASE/'qa/14A8_model_shootout';records=json.loads((old/'14A8_frozen_protocol.json').read_text())['patches']
 for r in records:
  with np.load(old/'inputs'/(r['patch_id']+'.npz')) as f:a=f['rgb'].astype('float32')
  x=(a-a.min())/max(1e-6,float(a.max()-a.min()));t=time.perf_counter();p=predict(m,x);seconds=time.perf_counter()-t;np.savez_compressed(OUT/'gold_evaluation'/(r['patch_id']+'.npz'),probability=p);times.append(dict(patch_id=r['patch_id'],seconds=seconds));print('C8_GOLD_ONCE',r['patch_id'],seconds,flush=True)
 (OUT/'gold_evaluation/runtime.json').write_text(json.dumps(times,indent=2))
if __name__=='__main__':{'teachers':teachers,'train':train,'gold':gold}[sys.argv[1]]()
