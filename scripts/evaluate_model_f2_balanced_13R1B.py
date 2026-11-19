from __future__ import annotations
import json
from pathlib import Path
import numpy as np, rasterio, torch
import torch.nn.functional as F
from transformers import SegformerConfig, SegformerForSemanticSegmentation

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R'; BASE=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_f_segformer/best_segformer.pth'; F2=ROOT/'backend/data/models/building/experimental/model_f2_industrial_finetuned/best_model_f2.pth'
def model(path):
 c=SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256); m=SegformerForSemanticSegmentation(c); sd=torch.load(path,map_location='cpu',weights_only=True); sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()}; m.load_state_dict(sd,strict=True); return m.eval()
def data(r):
 with rasterio.open(DATA/'images'/r['split']/(r['patch_id']+'.tif')) as s: x=s.read((1,2,3)).astype('float32')/255
 with rasterio.open(DATA/'masks'/r['split']/(r['patch_id']+'.tif')) as s: y=s.read(1).astype('float32')
 return torch.from_numpy(x[None]),torch.from_numpy(y[None,None])
def score(records, threshold):
 out={}
 for scene in ('all','industrial','residential'):
  rs=records if scene=='all' else [r for r in records if r['scene_type']==scene]; inter=pp=tt=union=0
  for r in rs:
   p=(r['prob']>=threshold); y=r['y']; inter+=int((p&y).sum()); pp+=int(p.sum()); tt+=int(y.sum()); union+=int((p|y).sum())
  out[scene]={'iou':inter/union if union else None,'dice':2*inter/(pp+tt) if pp+tt else None,'precision':inter/pp if pp else None,'recall':inter/tt if tt else None,'patches':len(rs)}
 return out
def main():
 split=json.loads((DATA/'balanced_split_13R1B_manifest.json').read_text()); val=split['val']; all_out={}
 for name,path in [('MODEL_F',BASE),('MODEL_F2_EXISTING',F2)]:
  m=model(path); rec=[]
  with torch.no_grad():
   for r in val:
    x,y=data(r); z=m(pixel_values=x).logits; prob=torch.sigmoid(F.interpolate(z,size=y.shape[-2:],mode='bilinear',align_corners=False))[0,0].numpy(); rec.append({'patch_id':r['patch_id'],'scene_type':r['scene_type'],'prob':prob,'y':y[0,0].numpy().astype(bool)})
  all_out[name]={str(t):score(rec,t) for t in (.35,.40,.45,.50,.55)}
 (DATA/'balanced_13R1B_eval.json').write_text(json.dumps(all_out,indent=2),encoding='utf-8'); print(json.dumps({k:v['0.5'] for k,v in all_out.items()},indent=2))
if __name__=='__main__': main()
