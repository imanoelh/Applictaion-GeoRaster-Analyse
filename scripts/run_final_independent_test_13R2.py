from __future__ import annotations
import csv, hashlib, json, time
from pathlib import Path
import numpy as np, rasterio, onnxruntime as ort, torch
import torch.nn.functional as F
from transformers import SegformerConfig, SegformerForSemanticSegmentation
from rasterio.features import shapes
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]; TEST=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test'; IMG=TEST/'images'; GT=TEST/'qa_13M1A/masks'; OUT=ROOT/'backend/data/models/building/experimental/benchmark_13R2_FINAL'; OUT.mkdir(parents=True,exist_ok=True)
C=ROOT/'backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx'; F0=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_f_segformer/best_segformer.pth'; F2=ROOT/'backend/data/models/building/experimental/model_f2_industrial_finetuned/best_model_f2.pth'; TH={'MODEL_C':0.5,'MODEL_F':0.35,'MODEL_F2':0.35}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest().upper()
def make_model(path):
 c=SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256); m=SegformerForSemanticSegmentation(c); sd=torch.load(path,map_location='cpu',weights_only=True); sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()}; m.load_state_dict(sd,strict=True); return m.eval()
def comps(mask):
 seen=np.zeros(mask.shape,bool); out=[]; H,W=mask.shape
 for y,x in zip(*np.where(mask & ~seen)):
  if seen[y,x]: continue
  st=[(y,x)]; seen[y,x]=1; n=0
  while st:
   yy,xx=st.pop(); n+=1
   for dy,dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
    ny,nx=yy+dy,xx+dx
    if 0<=ny<H and 0<=nx<W and mask[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1; st.append((ny,nx))
  out.append(n)
 return out
def boundary(m):
 b=m.copy(); b[1:-1,1:-1] &= ~(m[:-2,1:-1]&m[2:,1:-1]&m[1:-1,:-2]&m[1:-1,2:]); return b
def dilate(b,r=2):
 o=np.zeros_like(b)
 for dy in range(-r,r+1):
  for dx in range(-r,r+1):
   ys=slice(max(0,dy),min(512,512+dy)); yt=slice(max(0,-dy),min(512,512-dy)); xs=slice(max(0,dx),min(512,512+dx)); xt=slice(max(0,-dx),min(512,512-dx)); o[ys,xs] |= b[yt,xt]
 return o
def metrics(pred,gt):
 inter=int((pred&gt).sum()); pp=int(pred.sum()); gg=int(gt.sum()); un=int((pred|gt).sum()); b1=boundary(pred); b2=boundary(gt); d1=dilate(b1); d2=dilate(b2); bp=int((b1&d2).sum()); br=int((b2&d1).sum()); bf=2*bp/(b1.sum()+b2.sum()) if b1.sum()+b2.sum() else 1.
 return {'iou':inter/un if un else 1.,'dice':2*inter/(pp+gg) if pp+gg else 1.,'precision':inter/pp if pp else 1.,'recall':inter/gg if gg else 1.,'f1':2*inter/(pp+gg) if pp+gg else 1.,'boundary_f1':bf,'boundary_iou':bp/int((b1|b2).sum()) if (b1|b2).sum() else 1.}
def agg(ms): return {k:float(np.mean([m[k] for m in ms])) for k in ms[0]}
def main():
 files=sorted(IMG.glob('GT_*.tif')); test_hashes={sha(p) for p in files}; train_hashes={r['rgb_sha256'] for r in csv.DictReader(open(ROOT/'backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R/manifest.csv'))}; leak=len(test_hashes&train_hashes)
 so=ort.SessionOptions(); so.intra_op_num_threads=4; cs=ort.InferenceSession(str(C),sess_options=so,providers=['CPUExecutionProvider']); cin=cs.get_inputs()[0].name; fm=make_model(F0); f2=make_model(F2); records=[]
 for ip in files:
  name=ip.stem; gtpath=GT/(name+'_ground_truth_mask.tif')
  with rasterio.open(ip) as s: a=s.read((1,2,3)).astype('float32'); tr=s.transform; crs=s.crs; rgb=np.moveaxis(a,0,-1).astype('uint8')
  with rasterio.open(gtpath) as s: gt=s.read(1).astype(bool)
  t=time.perf_counter(); z=(a-a.min())/(a.max()-a.min() or 1); pc=np.squeeze(1/(1+np.exp(-cs.run(None,{cin:z[None]})[0][0]))); tc=time.perf_counter()-t
  t=time.perf_counter();
  with torch.no_grad(): pf=torch.sigmoid(F.interpolate(fm(pixel_values=torch.from_numpy(a/255)[None]).logits,size=(512,512),mode='bilinear',align_corners=False))[0,0].numpy()
  tf=time.perf_counter()-t
  t=time.perf_counter();
  with torch.no_grad(): p2=torch.sigmoid(F.interpolate(f2(pixel_values=torch.from_numpy(a/255)[None]).logits,size=(512,512),mode='bilinear',align_corners=False))[0,0].numpy()
  t2=time.perf_counter()-t
  probs={'MODEL_C':pc,'MODEL_F':pf,'MODEL_F2':p2}; outs={}; od=OUT/name; od.mkdir(exist_ok=True)
  for mod,p in probs.items():
   bi=p>=TH[mod]; md=od/mod.lower(); md.mkdir(exist_ok=True); prof={'driver':'GTiff','height':512,'width':512,'count':1,'dtype':'float32','crs':crs,'transform':tr,'compress':'deflate'}
   with rasterio.open(md/'probability.tif','w',**prof) as d:d.write(p.astype('float32'),1)
   prof['dtype']='uint8';
   with rasterio.open(md/'mask.tif','w',**prof) as d:d.write(bi.astype('uint8'),1)
   fs=[{'type':'Feature','geometry':g,'properties':{'model':mod}} for g,v in shapes(bi.astype('uint8'),mask=bi,transform=tr)]; (md/'polygons.geojson').write_text(json.dumps({'type':'FeatureCollection','features':fs}),encoding='utf-8')
   ov=rgb.copy(); ov[bi]=(0.55*ov[bi]+np.array([255,30,20])*0.45).astype('uint8'); Image.fromarray(ov).save(md/'overlay.png'); outs[mod]=metrics(bi,gt)
  scene='industrial' if 'industrial' in name else 'residential' if 'residential' in name else 'difficult_mixed'; records.append({'patch_id':name,'scene_type':scene,'gt':gt,'metrics':outs,'gt_buildings':len(comps(gt)),'times_sec':{'MODEL_C':tc,'MODEL_F':tf,'MODEL_F2':t2}})
  ims=[Image.fromarray(rgb),Image.fromarray((gt*255).astype('uint8'))]+[Image.open(od/mod.lower()/'overlay.png') for mod in ('MODEL_C','MODEL_F','MODEL_F2')]; sh=Image.new('RGB',(5*160,185),'white'); dd=ImageDraw.Draw(sh)
  for j,im in enumerate(ims): sh.paste(im.resize((160,160)),(j*160,0)); dd.text((j*160+2,163),['RGB','GT','C','F','F2'][j],fill='black')
  sh.save(od/'contact_sheet.png')
 allmods={}
 for mod in ('MODEL_C','MODEL_F','MODEL_F2'):
  allmods[mod]={'global':agg([r['metrics'][mod] for r in records]),'by_scene':{s:agg([r['metrics'][mod] for r in records if r['scene_type']==s]) for s in ('industrial','residential','difficult_mixed') if any(r['scene_type']==s for r in records)},'seconds_per_patch':float(np.mean([r['times_sec'][mod] for r in records])),'seconds_per_mp':float(np.mean([r['times_sec'][mod] for r in records]))}
 thumbs=[Image.open(OUT/r['patch_id']/'contact_sheet.png').resize((500,185)) for r in records]; global_sheet=Image.new('RGB',(1000,185*((len(thumbs)+1)//2)),'white')
 for i,im in enumerate(thumbs): global_sheet.paste(im,((i%2)*500,(i//2)*185))
 global_sheet.save(OUT/'global_contact_sheet.png')
 summary={'test_leakage':leak,'test_patches':len(files),'test_rgb_sha256':sorted(test_hashes),'metrics':allmods,'patches':[{'patch_id':r['patch_id'],'scene_type':r['scene_type'],'gt_buildings':r['gt_buildings'],'models':r['metrics']} for r in records]}; (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
