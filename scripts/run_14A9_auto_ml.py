"""CPU workers for one isolated C7 pseudo-supervised cycle."""
from pathlib import Path
import os,sys,json,time,hashlib,random,importlib.util,importlib.metadata
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
import numpy as np
import torch
import onnxruntime as ort
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A9_auto_pipeline'
P=json.loads((OUT/'protocol.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text()
assert all(sha(ROOT/p)==h for p,h in json.loads((OUT/'qa/GOLD_BEFORE.json').read_text()).items()),'GOLD hash mismatch: abort'
torch.set_num_threads(4);torch.set_num_interop_threads(1)
def model(path):
 m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);m.classifier=DeepLabHead(2048,1);ck=torch.load(path,map_location='cpu',weights_only=True);m.load_state_dict(ck['state_dict'],strict=True);m.eval();return m
def rgb(r):
 with np.load(OUT/'candidate_pool'/(r['patch_id']+'.npz')) as d:a=d['rgb'].astype('float32')
 return a,(a-a.min())/max(1e-6,float(a.max()-a.min()))
def predict(m,x):
 with torch.inference_mode():return torch.sigmoid(m(torch.from_numpy(np.ascontiguousarray(x[None])))['out'][0,0]).numpy().astype('float32')
def teachers():
 audit=[]
 for s in P['teachers']:
  path=ROOT/s['path'];assert sha(path)==s['sha256'];start=time.perf_counter();mid=s['model'];session=None;m=None
  if mid=='MODEL_C6':m=model(path)
  else:
   opts=ort.SessionOptions();opts.intra_op_num_threads=4;opts.inter_op_num_threads=1
   session=ort.InferenceSession(str(path),sess_options=opts,providers=['CPUExecutionProvider'])
  for r in P['records']:
   a,x=rgb(r);pid=r['patch_id'];t=time.perf_counter()
   def forward(z):
    if m is not None:return predict(m,z)
    o=session.run(None,{session.get_inputs()[0].name:np.ascontiguousarray(z[None])})[0]
    if mid=='MODEL_D':q=np.exp(o[0]-o[0].max(axis=0,keepdims=True));return (q[1]/q.sum(axis=0)).astype('float32')
    return (1/(1+np.exp(-np.clip(o[0,0],-80,80)))).astype('float32')
   z=a/255. if mid=='MODEL_D' else x;p=forward(z);data={'probability':p}
   if mid=='MODEL_D':data['hflip_probability']=np.flip(forward(np.flip(z,axis=2)),axis=1).copy()
   assert p.shape==(512,512) and np.isfinite(p).all();np.savez_compressed(OUT/'teacher_predictions'/(mid+'__'+pid+'.npz'),**data)
   print('TEACHER',mid,pid,round(time.perf_counter()-t,2),flush=True)
  audit.append(dict(model=mid,load_forward='PASS',seconds=time.perf_counter()-start,weights_unchanged=sha(path)==s['sha256']));m=None;session=None
 metadata=dict(selected=audit,optional_runtime={n:bool(importlib.util.find_spec(n)) for n in ['transformers','segmentation_models_pytorch']},torch=torch.__version__,onnxruntime=ort.__version__,training=False)
 (OUT/'qa/TEACHER_RUNTIME.json').write_text(json.dumps(metadata,indent=2))
def train():
 cfg=P['training'];torch.manual_seed(cfg['seed']);np.random.seed(cfg['seed']);random.seed(cfg['seed'])
 c6=next(s for s in P['teachers'] if s['model']=='MODEL_C6');m=model(ROOT/c6['path'])
 for name,p in m.named_parameters():p.requires_grad=name.startswith('classifier.') or name.startswith('backbone.layer4.')
 opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
 records=[r for r in P['records'] if r['split']=='ACTIVE_LEARNING_TRAIN'];dev=[r for r in P['records'] if r['split']=='DEV_CALIBRATION'];rng=np.random.default_rng(cfg['seed']);history=[]
 for epoch in range(1,cfg['epochs']+1):
  losses=[];m.train()
  for mod in m.modules():
   if isinstance(mod,torch.nn.modules.batchnorm._BatchNorm):mod.eval()
  for idx in rng.permutation(len(records)):
   r=records[idx];_,x=rgb(r)
   with np.load(OUT/'auto_train'/(r['patch_id']+'.npz')) as d:y=d['mask'].astype('float32');w=d['weight'].astype('float32')
   k=int(rng.integers(4));x=np.rot90(x,k,axes=(1,2));y=np.rot90(y,k);w=np.rot90(w,k)
   if rng.random()<.5:x=np.flip(x,axis=2);y=np.flip(y,axis=1);w=np.flip(w,axis=1)
   x=np.clip(x*rng.uniform(.9,1.1),0,1);xt=torch.from_numpy(np.ascontiguousarray(x[None]));yt=torch.from_numpy(y.copy()[None,None]);wt=torch.from_numpy(w.copy()[None,None]);opt.zero_grad(set_to_none=True)
   z=m(xt)['out'];pr=torch.sigmoid(z);bce=(torch.nn.functional.binary_cross_entropy_with_logits(z,yt,reduction='none')*wt).sum()/wt.sum().clamp_min(1);dice=1-(2*(pr*yt*wt).sum()+1)/((pr*wt).sum()+(yt*wt).sum()+1);loss=bce+dice;loss.backward();opt.step();losses.append(float(loss.detach()))
   print('TRAIN',epoch,r['patch_id'],'LOSS',round(losses[-1],5),flush=True)
  path=OUT/'models'/f'MODEL_C7_AUTO_epoch{epoch}.pth';torch.save(dict(state_dict=m.state_dict(),epoch=epoch,source='MODEL_C6',labels='MULTI_TEACHER_PSEUDO_NOT_HUMAN',protocol_sha256=sha(OUT/'protocol.json')),path);m.eval()
  for r in dev:
   _,x=rgb(r);p=predict(m,x);np.savez_compressed(OUT/'auto_dev'/(f"epoch{epoch}__"+r['patch_id']+'.npz'),probability=p)
  history.append(dict(epoch=epoch,mean_loss=float(np.mean(losses)),checkpoint=str(path.relative_to(ROOT)),sha256=sha(path)));(OUT/'models/training_history.json').write_text(json.dumps(history,indent=2));print('EPOCH_COMPLETED',epoch,flush=True)
def gold():
 freeze=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());path=ROOT/freeze['checkpoint'];assert sha(path)==freeze['checkpoint_sha256']
 if (OUT/'gold_evaluation/ATTEMPT_STARTED.json').exists():raise RuntimeError('GOLD evaluation already attempted; no second cycle')
 (OUT/'gold_evaluation/ATTEMPT_STARTED.json').write_text(json.dumps(dict(freeze_sha256=sha(OUT/'calibration/FROZEN_CANDIDATE.json'),checkpoint_sha256=sha(path))))
 old=json.loads((ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout/14A8_frozen_protocol.json').read_text());m=model(path);timings=[]
 # One synthetic warmup, excluded from timing and not a GOLD parameter decision.
 predict(m,np.zeros((3,512,512),dtype='float32'))
 for r in old['patches']:
  import rasterio
  with rasterio.open(ROOT/r['rgb_path']) as ds:x=ds.read((1,2,3)).astype('float32')
  x=(x-x.min())/max(1e-6,float(x.max()-x.min()));t=time.perf_counter();p=predict(m,x);seconds=time.perf_counter()-t;np.savez_compressed(OUT/'gold_evaluation'/(r['patch_id']+'.npz'),probability=p);timings.append(dict(patch_id=r['patch_id'],seconds=seconds));print('GOLD_ONCE',r['patch_id'],seconds,flush=True)
 (OUT/'gold_evaluation/inference_times.json').write_text(json.dumps(timings,indent=2))
if __name__=='__main__':{'teachers':teachers,'train':train,'gold':gold}[sys.argv[1]]()
