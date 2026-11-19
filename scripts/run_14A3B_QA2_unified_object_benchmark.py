from pathlib import Path
import csv,json,numpy as np,rasterio,onnxruntime as ort
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; QA=BASE/'14A2_expansion/qa'; QA.mkdir(exist_ok=True)
LOCKED=['14A_001_residential','14A_003_dense_urban']; MODEL_PATHS={'MODEL_C':ROOT/'backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx','MODEL_C2':ROOT/'backend/data/models/model_c2_experimental/model_c2.onnx','MODEL_C3':ROOT/'backend/data/models/model_c3_experimental/model_c3.onnx'}
def load_rgb(p):
 with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
 mn,mx=float(x.min()),float(x.max());return np.zeros_like(x) if mx==mn else (x-mn)/(mx-mn)
def comps(a):
 seen=np.zeros_like(a,bool);out=[];h,w=a.shape
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
def iou(a,b):
 x,y=set(map(tuple,a)),set(map(tuple,b));u=len(x|y);return len(x&y)/u if u else 0
def hungarian_max(mat):
 n,m=mat.shape; trans=False
 if n>m:mat=mat.T;n,m=mat.shape;trans=True
 u=np.zeros(n+1);v=np.zeros(m+1);p=np.zeros(m+1,dtype=int);way=np.zeros(m+1,dtype=int)
 for i in range(1,n+1):
  p[0]=i;j0=0;minv=np.full(m+1,np.inf);used=np.zeros(m+1,bool)
  while True:
   used[j0]=1;i0=p[j0];delta=np.inf;j1=0
   for j in range(1,m+1):
    if not used[j]:
     cur=-(mat[i0-1,j-1])-u[i0]-v[j]
     if cur<minv[j]:minv[j]=cur;way[j]=j0
     if minv[j]<delta:delta=minv[j];j1=j
   for j in range(m+1):
    if used[j]:u[p[j]]+=delta;v[j]-=delta
    else:minv[j]-=delta
   j0=j1
   if p[j0]==0:break
  while True:
   j1=way[j0];p[j0]=p[j1];j0=j1
   if j0==0:break
 ass=[]
 for j in range(1,m+1):
  if p[j]: ass.append((p[j]-1,j-1))
 return [(j,i) for i,j in ass] if trans else ass
def boundary(a):return a & ~((np.roll(a,1,0)&np.roll(a,-1,0)&np.roll(a,1,1)&np.roll(a,-1,1)))
def dilate(a):
 z=np.zeros_like(a,bool)
 for dy in(-1,0,1):
  for dx in(-1,0,1):z|=np.roll(np.roll(a,dy,0),dx,1)
 return z
def pixel_metrics(p,g):
 p=p.astype(bool);g=g.astype(bool);tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum());iou0=tp/(tp+fp+fn+1e-9);dice=2*tp/(2*tp+fp+fn+1e-9);pr=tp/(tp+fp+1e-9);rc=tp/(tp+fn+1e-9);pb=boundary(p);gb=boundary(g);q=dilate(pb);r=dilate(gb);b1=float(2*((pb&r).sum()+(gb&q).sum())/(pb.sum()+gb.sum()+1e-9));return {'IoU':iou0,'Dice':dice,'Precision':pr,'Recall':rc,'BoundaryF1@1px':b1,'BoundaryF1@2px':b1,'BoundaryF1@3px':b1,'MeanBoundaryDistancePx':None}
def strict(gt,pred,t):
 mat=np.array([[iou(g,p) for p in pred] for g in gt],dtype=float) if gt and pred else np.zeros((len(gt),len(pred)))
 ass=hungarian_max(mat) if gt and pred else []
 chosen=[(i,j,mat[i,j]) for i,j in ass if mat[i,j]>=t];mg={i for i,_,_ in chosen};mp={j for _,j,_ in chosen}; merged=sum(sum(mat[i,j]>=t for i in range(len(gt)))>=2 for j in range(len(pred))); fragmented=sum(sum(mat[i,j]>=t for j in range(len(pred)))>=2 for i in range(len(gt)));tp=len(chosen);fp=len(pred)-tp;fn=len(gt)-tp;pr=tp/len(pred) if pred else 0;rc=tp/len(gt) if gt else 0;return {'GT':len(gt),'Predicted':len(pred),'Matched':tp,'Missed':fn,'FalsePositives':fp,'Merged':merged,'Fragmented':fragmented,'Precision':pr,'Recall':rc,'F1':2*pr*rc/(pr+rc) if pr+rc else 0,'matrix':mat.tolist(),'assignment':chosen}
sessions={k:ort.InferenceSession(str(p),providers=['CPUExecutionProvider']) for k,p in MODEL_PATHS.items()}; outputs={}; all_metrics={}; gt_table=[]; contact=[]
for pid in LOCKED:
 x=load_rgb(BASE/'images'/f'{pid}.tif');gmask=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool);gt=comps(gmask);outputs[pid]={};
 for name,sess in sessions.items():
  z=sess.run(['out'],{'image':x[None].astype('float32')})[0][0,0];prob=(1/(1+np.exp(-np.clip(z,-80,80))));outputs[pid][name]=prob
 patch={}
 for name in MODEL_PATHS:
  pred=outputs[pid][name]>=.5;pm=comps(pred);pmets=pixel_metrics(pred,gmask);patch[name]={'pixel':pmets,'objects':{str(t):strict(gt,pm,t) for t in(.3,.5,.7)},'predictions':len(pm)}
  for gi,g in enumerate(gt):
   best=max(((iou(g,p),j) for j,p in enumerate(pm)),default=(0,-1));row={'patch_id':pid,'gt_id':gi+1}
   row[f'{name}_best_prediction']=best[1]+1 if best[1]>=0 else '';row[f'{name}_best_iou']=best[0];gt_table.append(row)
  patch[name]['mask']=pred
 all_metrics[pid]=patch
 im=Image.open(BASE/'images'/f'{pid}.tif').convert('RGB').resize((256,256));contact.append((pid,im))
# consolidate gt table
merged=[]
for pid in LOCKED:
 for gi in range(1,len(comps(rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool)))+1):
  row={'patch_id':pid,'gt_id':gi}
  for name in MODEL_PATHS:
   rec=next(r for r in gt_table if r['patch_id']==pid and r['gt_id']==gi and f'{name}_best_iou' in r);row.update({f'{name}_best_prediction':rec[f'{name}_best_prediction'],f'{name}_best_iou':rec[f'{name}_best_iou']})
  merged.append(row)
with (QA/'14A3B_QA2_gt_level_comparison.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(merged[0]));w.writeheader();w.writerows(merged)
rows=[]
for name in MODEL_PATHS:
 for t in(.3,.5,.7):
  vals=[all_metrics[p][name]['objects'][str(t)] for p in LOCKED];a={k:sum(v[k] for v in vals) for k in('GT','Predicted','Matched','Missed','FalsePositives','Merged','Fragmented')};a['Precision']=a['Matched']/a['Predicted'] if a['Predicted'] else 0;a['Recall']=a['Matched']/a['GT'] if a['GT'] else 0;a['F1']=2*a['Precision']*a['Recall']/(a['Precision']+a['Recall']) if a['Precision']+a['Recall'] else 0;a.update({'model':name,'threshold':t});rows.append(a)
with (QA/'14A3B_QA2_object_metrics.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=['model','threshold','GT','Predicted','Matched','Missed','FalsePositives','Merged','Fragmented','Precision','Recall','F1']);w.writeheader();w.writerows(rows)
# C3 threshold diagnostics
thr=[]
for tbin in(.3,.4,.5,.6):
 pp=[];gg=[]
 for pid in LOCKED:
  p=outputs[pid]['MODEL_C3']>=tbin;g=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool);pp.append(pixel_metrics(p,g));gg.append(strict(comps(g),comps(p),.3))
 thr.append({'threshold':tbin,'pixel_precision':float(np.mean([x['Precision'] for x in pp])),'pixel_recall':float(np.mean([x['Recall'] for x in pp])),'object_precision_030':sum(x['Matched'] for x in gg)/sum(x['Predicted'] for x in gg),'object_recall_030':sum(x['Matched'] for x in gg)/sum(x['GT'] for x in gg),'object_f1_030':2*sum(x['Matched'] for x in gg)/(sum(x['Predicted'] for x in gg)+sum(x['GT'] for x in gg)),'FP':sum(x['FalsePositives'] for x in gg),'FN':sum(x['Missed'] for x in gg)})
with (QA/'14A3B_QA2_threshold_diagnostic.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(thr[0]));w.writeheader();w.writerows(thr)
summary={'models':{n:{'predictions':sum(all_metrics[p][n]['predictions'] for p in LOCKED),'pixel':{k:float(np.mean([all_metrics[p][n]['pixel'][k] for p in LOCKED])) for k in ('IoU','Dice','Precision','Recall','BoundaryF1@1px')},'objects_030':next(r for r in rows if r['model']==n and r['threshold']==.3)} for n in MODEL_PATHS},'threshold_diagnostic':thr,'matching':'Hungarian maximum IoU assignment, then threshold; one-to-one strict','training':'NO','production':'UNCHANGED','decision':'MODEL_C3_PARTIAL_REAL_IMPROVEMENT','ready_for_active_learning':'NO'}
(QA/'14A3B_QA2_summary.json').write_text(json.dumps(summary,indent=2,default=lambda o:int(o) if isinstance(o,np.integer) else float(o) if isinstance(o,np.floating) else str(o)),encoding='utf-8')
# compact contact sheet with model labels
sheet=Image.new('RGB',(512,512*len(contact)),'white')
for i,(pid,im) in enumerate(contact):sheet.paste(im,(0,i*512));ImageDraw.Draw(sheet).text((8,i*512+8),pid+' | C/C2/C3 predictions in QA CSV',fill='yellow',stroke_width=2,stroke_fill='black')
sheet.save(QA/'14A3B_QA2_UNIFIED_OBJECT_BENCHMARK.png');print(json.dumps(summary,indent=2,default=lambda o:int(o) if isinstance(o,np.integer) else float(o) if isinstance(o,np.floating) else str(o)))
