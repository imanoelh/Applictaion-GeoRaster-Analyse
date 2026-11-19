"""Isolated new architecture inference workers; no production modules."""
from pathlib import Path
import sys,os,json,time,hashlib
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';OUT=BASE/'14A10_specialized_benchmark'
os.environ['HF_HOME']=str(OUT/'runtime_cache/huggingface');os.environ['TRANSFORMERS_CACHE']=str(OUT/'runtime_cache/transformers');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
sys.path.insert(0,str(OUT/'python_ml_packages'))
import numpy as np
import onnxruntime as ort
P=json.loads((OUT/'protocol.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 mid=sys.argv[1];stage=sys.argv[2];spec=next(s for s in P['models'] if s['model']==mid);assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text();assert sha(ROOT/spec['path'])==spec['sha256']
 assert all(sha(ROOT/p)==h for p,h in json.loads((OUT/'qa/GOLD_BEFORE.json').read_text()).items())
 start=time.perf_counter();m=None;session=None
 if mid=='SEGFORMER_F':
  import torch
  from transformers import SegformerConfig,SegformerForSemanticSegmentation
  torch.set_num_threads(4);torch.set_num_interop_threads(1);sd=torch.load(ROOT/spec['path'],map_location='cpu',weights_only=True);sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()};cfg=SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256);m=SegformerForSemanticSegmentation(cfg);m.load_state_dict(sd,strict=True);m.eval()
 else:
  opt=ort.SessionOptions();opt.intra_op_num_threads=4;opt.inter_op_num_threads=1;session=ort.InferenceSession(str(ROOT/spec['path']),sess_options=opt,providers=['CPUExecutionProvider'])
 load=time.perf_counter()-start
 def forward(rgb):
  if mid=='DINO_FAST':return session.run(None,{session.get_inputs()[0].name:np.moveaxis(rgb,0,-1)[None]})[0][0]
  x=rgb.astype('float32')/255.
  if m is not None:
   with torch.inference_mode():o=m(pixel_values=torch.from_numpy(x[None])).logits;o=torch.nn.functional.interpolate(o,size=(512,512),mode='bilinear',align_corners=False);return torch.sigmoid(o[0]).numpy()
  n=spec['tile_size'];stride=spec['stride'];ys=list(range(0,512-n+1,stride));xs=ys.copy()
  if ys[-1]!=512-n:ys.append(512-n);xs.append(512-n)
  result=np.zeros((3,512,512),np.float32);counts=np.zeros((512,512),np.float32)
  x=(x-np.array([.485,.456,.406],dtype='float32')[:,None,None])/np.array([.229,.224,.225],dtype='float32')[:,None,None]
  for y in ys:
   for xx in xs:
    z=np.ascontiguousarray(x[None,:,y:y+n,xx:xx+n]);o=session.run(None,{session.get_inputs()[0].name:z})[0][0];assert o.shape==(3,n,n);prob=1/(1+np.exp(-np.clip(o,-80,80)));result[:,y:y+n,xx:xx+n]+=prob;counts[y:y+n,xx:xx+n]+=1
  return result/counts[None]
 if stage=='smoke':
  with np.load(BASE/'14A9_auto_pipeline/candidate_pool'/(P['smoke_patch']+'.npz')) as f:rgb=f['rgb']
  t=time.perf_counter();out=forward(rgb);seconds=time.perf_counter()-t;assert out.shape[-2:]==(512,512) and np.isfinite(out).all()
  if mid!='DINO_FAST':assert out.min()>=0 and out.max()<=1
  np.savez_compressed(OUT/'smoke'/(mid+'.npz'),channels=out,probability=out[0]);result=dict(model=mid,load='PASS',strict_load='PASS' if m else 'ONNX_GRAPH',forward='PASS',output_shape=list(out.shape),dtype=str(out.dtype),minimum=float(out.min()),maximum=float(out.max()),load_seconds=load,smoke_seconds=seconds,status='INCOMPATIBLE' if mid=='DINO_FAST' else 'READY',reason=spec['postprocessing']);(OUT/'smoke'/(mid+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 else:
  smoke=json.loads((OUT/'smoke'/(mid+'.json')).read_text());assert smoke['status']=='READY';folder=OUT/'predictions'/mid;folder.mkdir(exist_ok=True)
  if (folder/'STARTED.json').exists():raise RuntimeError('GOLD inference already attempted')
  (folder/'STARTED.json').write_text(json.dumps(dict(protocol_sha256=sha(OUT/'protocol.json'),model_sha256=spec['sha256'])))
  forward(np.zeros((3,512,512),np.uint8));rows=[]
  for r in P['gold_patches']:
   with np.load(BASE/'qa/14A8_model_shootout/inputs'/(r['patch_id']+'.npz')) as f:rgb=f['rgb']
   t=time.perf_counter();out=forward(rgb);seconds=time.perf_counter()-t;np.savez_compressed(folder/(r['patch_id']+'.npz'),probability=out[0],channels=out);rows.append(dict(patch_id=r['patch_id'],inference_seconds=seconds));print(mid,'GOLD',r['patch_id'],seconds,flush=True)
  (folder/'runtime.json').write_text(json.dumps(dict(model=mid,engine='PYTORCH_CPU' if m else 'ONNX_RUNTIME_CPU',load_seconds=load,threads=4,patches=rows),indent=2))
 assert sha(ROOT/spec['path'])==spec['sha256']
if __name__=='__main__':main()
