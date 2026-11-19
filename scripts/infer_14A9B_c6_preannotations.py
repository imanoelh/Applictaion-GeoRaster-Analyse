"""C6 preannotation only, CPU inference; never train, tune or touch GOLD."""
from pathlib import Path
import os,json,time,hashlib
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
import numpy as np
import torch
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
import rasterio
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';AL=BASE/'14A9B_active_learning'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 records=json.loads((AL/'manifests/14A9B_selected_patches.json').read_text())
 modelpath=ROOT/'backend/data/models/model_c6_experimental/best_model_c6.pth';expected='7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84';assert sha(modelpath)==expected
 torch.set_num_threads(4);torch.set_num_interop_threads(1)
 model=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);model.classifier=DeepLabHead(2048,1)
 ck=torch.load(modelpath,map_location='cpu',weights_only=True);model.load_state_dict(ck['state_dict'],strict=True);del ck;model.eval();timings=[]
 for r in records:
  path=ROOT/r['rgb_path'];assert sha(path)==r['rgb_sha256']
  with rasterio.open(path) as ds:rgb=ds.read((1,2,3))
  x=rgb.astype('float32');x=(x-float(x.min()))/max(1e-6,float(x.max())-float(x.min()));t=time.perf_counter()
  with torch.inference_mode():p=torch.sigmoid(model(torch.from_numpy(x[None]))['out'][0,0]).numpy().astype('float32')
  assert p.shape==(512,512) and np.isfinite(p).all()
  np.savez_compressed(AL/'qa'/(r['patch_id']+'_C6_probability.npz'),probability=p)
  timings.append(dict(patch_id=r['patch_id'],seconds=time.perf_counter()-t));print('PREANNOTATION',r['patch_id'],round(timings[-1]['seconds'],2),flush=True)
 assert sha(modelpath)==expected
 (AL/'qa/14A9B_C6_inference.json').write_text(json.dumps(dict(model='MODEL_C6',weights_sha256=expected,strict_load='PASS',preprocessing='RGB_GLOBAL_PATCH_MINMAX',activation='SIGMOID_OUT',engine='PYTORCH_CPU',threads=4,inference=timings,training=False,calibration=False),indent=2))
if __name__=='__main__':main()
