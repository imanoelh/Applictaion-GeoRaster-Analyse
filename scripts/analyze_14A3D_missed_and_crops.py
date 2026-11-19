from pathlib import Path
import csv,json,math,random
import numpy as np,onnxruntime as ort,rasterio
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';EXP=BASE/'14A2_expansion';QA=EXP/'qa';OUT=EXP/'crops_14A3D';OUT.mkdir(exist_ok=True)
LOCKED=['14A_001_residential','14A_003_dense_urban']; sess=ort.InferenceSession(str(ROOT/'backend/data/models/model_c3_experimental/model_c3.onnx'),providers=['CPUExecutionProvider'])
def rgb(p):
 with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
 mn,mx=x.min(),x.max();return np.zeros_like(x) if mx==mn else (x-mn)/(mx-mn)
def comps(a):
 s=np.zeros_like(a,bool);o=[];h,w=a.shape
 for y,x in zip(*np.where(a)):
  if s[y,x]:continue
  st=[(int(y),int(x))];s[y,x]=1;pts=[]
  while st:
   yy,xx=st.pop();pts.append((yy,xx))
   for dy,dx in((1,0),(-1,0),(0,1),(0,-1)):
    ny,nx=yy+dy,xx+dx
    if 0<=ny<h and 0<=nx<w and a[ny,nx] and not s[ny,nx]:s[ny,nx]=1;st.append((ny,nx))
  o.append(np.array(pts))
 return o
rows=[];cat={k:0 for k in ['SMALL_BUILDING','EDGE_BUILDING','LOW_CONTRAST','DARK_ROOF','BRIGHT_ROOF','CLOSE_TO_NEIGHBOR','MODEL_LOW_CONFIDENCE','POSTPROCESS_REMOVED']}
for pid in LOCKED:
 x=rgb(BASE/'images'/f'{pid}.tif');gt=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool);z=sess.run(['out'],{'image':x[None].astype('float32')})[0][0,0];prob=1/(1+np.exp(-np.clip(z,-80,80)));pred=prob>=.5;gm=comps(gt);pm=comps(pred)
 for i,g in enumerate(gm,1):
  ys,xs=g[:,0],g[:,1]; area=len(g); w=xs.max()-xs.min()+1;h=ys.max()-ys.min()+1; near=min(xs.min(),ys.min(),511-xs.max(),511-ys.max()); vals=prob[ys,xs]; mean=float(vals.mean()); mx=float(vals.max()); gy0=max(0,ys.min()-2);gy1=min(512,ys.max()+3);gx0=max(0,xs.min()-2);gx1=min(512,xs.max()+3); contrast=float(x[:,gy0:gy1,gx0:gx1].mean()-x[:,ys,xs].mean()); best=max(((len(set(map(tuple,g))&set(map(tuple,p)))/len(set(map(tuple,g))|set(map(tuple,p))),j) for j,p in enumerate(pm)),default=(0,-1)); missed=best[0]<.3
  if not missed:continue
  cats=[]
  if area<479:cats.append('SMALL_BUILDING')
  if near<8:cats.append('EDGE_BUILDING')
  if mean<.25:cats.append('MODEL_LOW_CONFIDENCE')
  if contrast>0.15:cats.append('LOW_CONTRAST')
  if x[:,ys,xs].mean()<.35:cats.append('DARK_ROOF')
  if x[:,ys,xs].mean()>0.75:cats.append('BRIGHT_ROOF')
  if best[0]>0:cats.append('POSTPROCESS_REMOVED')
  for c in cats:cat[c]+=1
  rows.append({'patch_id':pid,'gt_id':i,'area_px':area,'area_m2':area*.35*.35,'width_px':w,'height_px':h,'aspect_ratio':w/h if h else 0,'distance_to_patch_edge_px':near,'local_contrast_proxy':contrast,'model_c3_mean_probability':mean,'model_c3_max_probability':mx,'best_prediction_iou':best[0],'categories':';'.join(cats),'miss_reason':'SIGNAL_ABSENT' if mx<.2 else ('SIGNAL_BELOW_THRESHOLD' if best[0]==0 else 'POSTPROCESS_OR_IOU')})
with (QA/'14A3D_missed_buildings_analysis.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# crop metadata and representative crops
meta=[]; rng=random.Random(14); hard=sorted(rows,key=lambda r:(r['model_c3_max_probability'],r['area_px']))
for pid in ['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']:
 x=rgb(EXP/'train/rgb'/f'{pid}.tif');m=rasterio.open(EXP/'masks/seed_gt_fixed_candidate'/f'{pid}.tif').read(1).astype('uint8');cc=comps(m)
 for i,g in enumerate(cc,1):
  cy,cx=int(g[:,0].mean()),int(g[:,1].mean());
  for j,(dy,dx) in enumerate(((0,0),(-48,32))):
   y=max(0,min(256,cy-128+dy));xx=max(0,min(256,cx-128+dx)); meta.append({'patch_id':pid,'gt_id':i,'crop_id':f'{pid}_{i:03d}_{j}','x':xx,'y':y,'type':'POSITIVE_HARD' if any(r['patch_id']==pid and r['gt_id']==i for r in hard[:37]) else 'POSITIVE','building_pixels':int(m[y:y+256,xx:xx+256].sum())})
 # hard negative quadrants
 for j,(y,xx) in enumerate(((0,0),(0,256),(256,0),(256,256))):
  if m[y:y+256,xx:xx+256].mean()<.01:meta.append({'patch_id':pid,'gt_id':'','crop_id':f'{pid}_NEG_{j}','x':xx,'y':y,'type':'NEGATIVE_BACKGROUND','building_pixels':int(m[y:y+256,xx:xx+256].sum())})
summary={'total_missed':len(rows),'categories':cat,'train_crops_before':10,'train_crops_after':len(meta),'positive_crops':sum(x['type'].startswith('POSITIVE') for x in meta),'negative_crops':sum(x['type'].startswith('NEGATIVE') for x in meta),'hard_positives':sum(x['type']=='POSITIVE_HARD' for x in meta),'hard_negatives':0,'small_gt_count':sum(int(x['area_px']<479) for x in rows),'crop_resolution':'256x256 native','seed_patches':5};(QA/'14A3D_crop_dataset_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(OUT/'crop_manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
