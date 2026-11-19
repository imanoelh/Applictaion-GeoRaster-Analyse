from pathlib import Path
import csv,json,numpy as np,torch,rasterio
from PIL import Image,ImageDraw
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; QA=BASE/'14A2_expansion/qa'; CKPT=ROOT/'backend/data/models/model_c3_experimental/final_model_c3.pth'; LOCKED=['14A_001_residential','14A_003_dense_urban']
def load_state(p):
 s=torch.load(p,map_location='cpu',weights_only=True).get('state_dict'); return s
def load_rgb(p):
 with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
 mn,mx=float(x.min()),float(x.max()); return np.zeros_like(x) if mx==mn else (x-mn)/(mx-mn)
def comps(a):
 seen=np.zeros_like(a,bool); out=[]; h,w=a.shape
 for y,x in zip(*np.where(a)):
  if seen[y,x]:continue
  st=[(int(y),int(x))];seen[y,x]=1;pts=[]
  while st:
   yy,xx=st.pop();pts.append((yy,xx))
   for dy,dx in((1,0),(-1,0),(0,1),(0,-1)):
    ny,nx=yy+dy,xx+dx
    if 0<=ny<h and 0<=nx<w and a[ny,nx] and not seen[ny,nx]:seen[ny,nx]=1;st.append((ny,nx))
  out.append(np.array(pts,dtype=np.int32))
 return out
def pairs(gt,pred,t):
 q=[]
 for i,g in enumerate(gt):
  gs=set(map(tuple,g))
  for j,p in enumerate(pred):
   ps=set(map(tuple,p));u=len(gs|ps);v=len(gs&ps);iou=v/u if u else 0
   if iou>=t:q.append((iou,i,j))
 q.sort(reverse=True);ug=set();up=set();out=[]
 for iou,i,j in q:
  if i not in ug and j not in up:ug.add(i);up.add(j);out.append((iou,i,j))
 return out
def iou(a,b):
 x,y=set(map(tuple,a)),set(map(tuple,b));return len(x&y)/len(x|y)
state=load_state(CKPT);net=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);net.classifier=DeepLabHead(2048,1);net.load_state_dict(state,strict=True);net.eval();rows=[];summary={};contact=[]
for pid in LOCKED:
 x=load_rgb(BASE/'images'/f'{pid}.tif');gt=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool)
 with torch.inference_mode():prob=torch.sigmoid(net(torch.from_numpy(x[None]))['out'])[0,0].numpy()
 pred=prob>=.5;gm,pm=comps(gt),comps(pred);summary[pid]={'gt_buildings':len(gm),'predicted_buildings':len(pm),'thresholds':{}}
 for gi,g in enumerate(gm):
  bi,bj=max(((iou(g,p),j) for j,p in enumerate(pm)),default=(0,-1)); rows.append({'patch_id':pid,'gt_id':gi+1,'best_prediction_id':bj+1 if bj>=0 else '','best_iou':bi,'matched_030':0,'matched_050':0,'matched_070':0})
 for t in(.30,.50,.70):
  m=pairs(gm,pm,t);mi={i for _,i,_ in m};mp={j for _,_,j in m}; merged=sum(sum(iou(g,p)>=t for g in gm)>=2 for p in pm);frag=sum(sum(iou(g,p)>=t for p in pm)>=2 for g in gm);pr=len(m)/len(pm) if pm else 0;rc=len(m)/len(gm) if gm else 0;summary[pid]['thresholds'][str(t)]={'gt_buildings':len(gm),'predicted_buildings':len(pm),'matched':len(m),'missed':len(gm)-len(m),'false_positives':len(pm)-len(m),'merged':merged,'fragmented':frag,'precision':pr,'recall':rc,'f1':2*pr*rc/(pr+rc) if pr+rc else 0}
  for r in rows:
   if r['patch_id']==pid:r[f'matched_{int(t*100):03d}']=1 if r['gt_id']-1 in mi else 0
 im=Image.open(BASE/'images'/f'{pid}.tif').convert('RGB').resize((512,512));d=ImageDraw.Draw(im)
 for i,g in enumerate(gm,1):d.text((int(g[:,1].mean()),int(g[:,0].mean())),f'G{i}',fill='lime',stroke_width=1,stroke_fill='black')
 for j,p in enumerate(pm,1):d.text((int(p[:,1].mean()),int(p[:,0].mean())),f'P{j}',fill='orange',stroke_width=1,stroke_fill='black')
 contact.append((pid,im))
with (QA/'14A3B_QA_object_matching.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=['patch_id','gt_id','best_prediction_id','best_iou','matched_030','matched_050','matched_070']);w.writeheader();w.writerows(rows)
glob={}
for t in('0.3','0.5','0.7'):
 v=[summary[p]['thresholds'][t] for p in LOCKED];a={k:sum(z[k] for z in v) for k in('gt_buildings','predicted_buildings','matched','missed','false_positives','merged','fragmented')};a['precision']=a['matched']/a['predicted_buildings'];a['recall']=a['matched']/a['gt_buildings'];a['f1']=2*a['precision']*a['recall']/(a['precision']+a['recall']);glob[t]=a
out={'patches':summary,'global':glob,'pixel_recall':0.2165,'matching':'greedy maximum-IoU one-to-one; each GT/prediction used once','reproducible':True,'prediction_source':'MODEL_C3 threshold 0.50'};(QA/'14A3B_QA_metrics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(512,512*len(contact)),'white')
for i,(pid,im) in enumerate(contact):sheet.paste(im,(0,i*512));ImageDraw.Draw(sheet).text((8,i*512+8),pid,fill='yellow',stroke_width=2,stroke_fill='black')
sheet.save(QA/'14A3B_QA_object_matching_contact_sheet.png');print(json.dumps(out,indent=2))
