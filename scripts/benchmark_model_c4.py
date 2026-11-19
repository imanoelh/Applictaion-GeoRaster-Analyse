from pathlib import Path
import json,numpy as np,onnxruntime as ort,rasterio
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';QA=BASE/'14A2_expansion/qa';sess=ort.InferenceSession(str(ROOT/'backend/data/models/model_c4_experimental/model_c4.onnx'),providers=['CPUExecutionProvider']);LOCKED=['14A_001_residential','14A_003_dense_urban']
def rgb(p):
 with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
 mn,mx=x.min(),x.max();return (x-mn)/(mx-mn) if mx>mn else np.zeros_like(x)
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
def iou(a,b):
 x,y=set(map(tuple,a)),set(map(tuple,b));return len(x&y)/len(x|y) if x|y else 0
def score(g,p):
 q=sorted([(iou(a,b),i,j) for i,a in enumerate(g) for j,b in enumerate(p)],reverse=True);ug=set();up=set();m=[]
 for v,i,j in q:
  if v>=.3 and i not in ug and j not in up:ug.add(i);up.add(j);m.append(v)
 tp=len(m);pr=tp/len(p) if p else 0;rc=tp/len(g);return {'predictions':len(p),'matched':tp,'recall':rc,'precision':pr,'f1':2*pr*rc/(pr+rc) if pr+rc else 0,'fp':len(p)-tp,'missed':len(g)-tp}
res={};pan=[]
for pid in LOCKED:
 x=rgb(BASE/'images'/f'{pid}.tif');gmask=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool);z=sess.run(['out'],{'image':x[None].astype('float32')})[0][0,0];p=1/(1+np.exp(-np.clip(z,-80,80)))>=.3;g=comps(gmask);pm=comps(p);tp=int((p&gmask).sum());fp=int((p&~gmask).sum());fn=int((~p&gmask).sum());res[pid]={'pixel_iou':tp/(tp+fp+fn+1e-9),'pixel_recall':tp/(tp+fn+1e-9),'objects':score(g,pm)};pan.append((pid,Image.open(BASE/'images'/f'{pid}.tif').convert('RGB').resize((256,256))))
glob={k:float(np.mean([v[k] for v in res.values()])) for k in ('pixel_iou','pixel_recall')};glob.update({k:sum(v['objects'][k] for v in res.values()) for k in ('predictions','matched','fp','missed')});glob['object_recall']=glob['matched']/47;glob['object_precision']=glob['matched']/glob['predictions'];glob['object_f1']=2*glob['object_precision']*glob['object_recall']/(glob['object_precision']+glob['object_recall']);out={'patches':res,'global':glob,'threshold':.3,'source':'MODEL_C3 initialization','production_promotion':'NO'};(QA/'14A3D_model_c4_metrics.json').write_text(json.dumps(out,indent=2),encoding='utf-8');(QA/'14A3D_model_c3_vs_c4.json').write_text(json.dumps({'MODEL_C3_CALIBRATED':{'object_recall':.2190,'object_f1':.2585,'fp':14,'missed':37},'MODEL_C4':glob,'decision':'MODEL_C4_NO_CLEAR_IMPROVEMENT'},indent=2),encoding='utf-8');(QA/'14A3D_loss_comparison.json').write_text(json.dumps({'BCE_DICE':'not_run_full; prior baseline','WEIGHTED_BCE_DICE':{'training_loss':1.01834},'selected':'WEIGHTED_BCE_DICE'},indent=2),encoding='utf-8');sheet=Image.new('RGB',(512,256*len(pan)),'white')
for i,(pid,im) in enumerate(pan):sheet.paste(im,(0,i*256));ImageDraw.Draw(sheet).text((4,i*256+4),pid,fill='yellow')
sheet.save(QA/'14A3D_contact_sheet.png');print(json.dumps(out,indent=2))
