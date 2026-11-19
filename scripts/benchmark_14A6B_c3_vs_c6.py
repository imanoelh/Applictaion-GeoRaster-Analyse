from pathlib import Path
import csv,json,time
import numpy as np, rasterio, onnxruntime as ort, torch
from PIL import Image, ImageDraw
# Use native torchvision operator ownership; no temporary schema at shutdown (14A.7B).
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; QA=BASE/'qa'; QA.mkdir(exist_ok=True)
LOCKED=['14A_001_residential','14A_003_dense_urban']
def comps(a,min_area=4):
    seen=np.zeros_like(a,bool); out=[]; h,w=a.shape
    for y,x in zip(*np.where(a)):
        if seen[y,x]: continue
        st=[(int(y),int(x))];seen[y,x]=1; pts=[]
        while st:
            yy,xx=st.pop();pts.append((yy,xx))
            for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<h and 0<=nx<w and a[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1;st.append((ny,nx))
        if len(pts)>=min_area: out.append(np.array(pts,np.int32))
    return out
def iou(a,b):
    x,y=set(map(tuple,a)),set(map(tuple,b));u=len(x|y);return len(x&y)/u if u else 0
def hungarian(mat):
    n,m=mat.shape
    if n==0 or m==0:return []
    tr=n>m
    if tr: mat=mat.T;n,m=mat.shape
    u=np.zeros(n+1);v=np.zeros(m+1);p=np.zeros(m+1,dtype=int);way=np.zeros(m+1,dtype=int)
    for i in range(1,n+1):
        p[0]=i;j0=0;mv=np.full(m+1,np.inf);used=np.zeros(m+1,bool)
        while True:
            used[j0]=1;i0=p[j0];delta=np.inf;j1=0
            for j in range(1,m+1):
                if not used[j]:
                    cur=-mat[i0-1,j-1]-u[i0]-v[j]
                    if cur<mv[j]:mv[j]=cur;way[j]=j0
                    if mv[j]<delta:delta=mv[j];j1=j
            for j in range(m+1):
                if used[j]:u[p[j]]+=delta;v[j]-=delta
                else:mv[j]-=delta
            j0=j1
            if p[j0]==0:break
        while True:
            j1=way[j0];p[j0]=p[j1];j0=j1
            if j0==0:break
    a=[(p[j]-1,j-1) for j in range(1,m+1) if p[j]]
    return [(j,i) for i,j in a] if tr else a
def dil(a,r):
    z=np.zeros_like(a,bool)
    for dy in range(-r,r+1):
        for dx in range(-r,r+1):z|=np.roll(np.roll(a,dy,0),dx,1)
    return z
def boundary(a):return a & ~((np.roll(a,1,0)&np.roll(a,-1,0)&np.roll(a,1,1)&np.roll(a,-1,1)))
def pix(p,g):
    tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum());den=tp+fp+fn
    out={'pixel_iou':tp/(den or 1),'dice':2*tp/(2*tp+fp+fn or 1),'pixel_precision':tp/(tp+fp or 1),'pixel_recall':tp/(tp+fn or 1),'pixel_f1':2*tp/(2*tp+fp+fn or 1)}
    for r in (1,2,3):
        pb,gb=boundary(p),boundary(g);a=int((pb&dil(gb,r)).sum());b=int((gb&dil(pb,r)).sum());out[f'boundary_f1_{r}px']=2*(a+b)/(pb.sum()+gb.sum()+1e-9)
    return out
def obj(gt,pred,t):
    mat=np.array([[iou(a,b) for b in pred] for a in gt],float);ass=hungarian(mat) if mat.size else [];ch=[(i,j,mat[i,j]) for i,j in ass if mat[i,j]>=t];tp=len(ch);pr=tp/len(pred) if pred else 0;rc=tp/len(gt) if gt else 0
    merged=sum(sum(mat[i,j]>=t for i in range(len(gt)))>1 for j in range(len(pred)));frag=sum(sum(mat[i,j]>=t for j in range(len(pred)))>1 for i in range(len(gt)))
    return {'gt':len(gt),'predicted':len(pred),'tp':tp,'fp':len(pred)-tp,'fn':len(gt)-tp,'precision':pr,'recall':rc,'f1':2*pr*rc/(pr+rc) if pr+rc else 0,'merged':merged,'fragmented':frag}
def load_rgb(pid):
    with rasterio.open(BASE/'images'/(pid+'.tif')) as d:x=d.read((1,2,3)).astype('float32')
    lo,hi=float(x.min()),float(x.max());return (x-lo)/(hi-lo) if hi>lo else np.zeros_like(x)
def main():
    c3=ort.InferenceSession(str(ROOT/'backend/data/models/model_c3_experimental/model_c3.onnx'),providers=['CPUExecutionProvider'])
    c6=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);c6.classifier=DeepLabHead(2048,1);ck=torch.load(ROOT/'backend/data/models/model_c6_experimental/best_model_c6.pth',map_location='cpu',weights_only=False);c6.load_state_dict(ck['state_dict'],strict=True);c6.eval()
    rows_obj=[];rows_pix=[];rows_b=[];perf=[];panels=[];allres={}
    for pid in LOCKED:
        x=load_rgb(pid);g=rasterio.open(BASE/'masks/ground_truth_final'/(pid+'.tif')).read(1).astype(bool);gt=comps(g,1)
        t=time.perf_counter();z=c3.run(['out'],{'image':x[None].astype('float32')})[0][0,0];p3=1/(1+np.exp(-np.clip(z,-80,80)));t3=time.perf_counter()-t
        t=time.perf_counter();
        with torch.inference_mode(): z6=c6(torch.from_numpy(x[None]))['out'][0,0].numpy()
        p6=1/(1+np.exp(-np.clip(z6,-80,80)));t6=time.perf_counter()-t
        allres[pid]={}
        for name,pred,tm in [('MODEL_C3',p3,t3),('MODEL_C6',p6,t6)]:
            bm=pred>=.30; pc=comps(bm,479); allres[pid][name]={'mask':bm,'obj':{str(t):obj(gt,pc,t) for t in (.3,.5,.7)},'pix':pix(bm,g)}
            for th,val in allres[pid][name]['obj'].items(): rows_obj.append({'patch_id':pid,'model':name,'iou_threshold':th,**val})
            rows_pix.append({'patch_id':pid,'model':name,**allres[pid][name]['pix']}); rows_b.append({'patch_id':pid,'model':name,**{k:v for k,v in allres[pid][name]['pix'].items() if k.startswith('boundary_')}}); perf.append({'patch_id':pid,'model':name,'cpu_seconds_512':tm})
        im=Image.open(BASE/'images'/(pid+'.tif')).convert('RGB').resize((256,256));panels.append((pid,im,g,allres[pid]['MODEL_C3']['mask'],allres[pid]['MODEL_C6']['mask']))
    for fn,rows in [('14A6B_c3_c6_object_metrics.csv',rows_obj),('14A6B_c3_c6_pixel_metrics.csv',rows_pix),('14A6B_c3_c6_boundary_metrics.csv',rows_b)]:
        with (QA/fn).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # aggregate and reference reproduction check
    agg={}
    for model in ('MODEL_C3','MODEL_C6'):
        vals=[r for r in rows_obj if r['model']==model and r['iou_threshold']=='0.3']; tp=sum(r['tp'] for r in vals);pred=sum(r['predicted'] for r in vals);gt=sum(r['gt'] for r in vals); agg[model]={'object_recall':tp/gt,'object_precision':tp/pred if pred else 0,'object_f1':2*tp/(pred+gt),'false_positives':sum(r['fp'] for r in vals),'missed':sum(r['fn'] for r in vals),'pixel_iou':float(np.mean([r['pixel_iou'] for r in rows_pix if r['model']==model])),'boundary_f1_1px':float(np.mean([r['boundary_f1_1px'] for r in rows_b if r['model']==model])),'cpu_seconds_512':float(np.mean([r['cpu_seconds_512'] for r in perf if r['model']==model]))}
    c3pass=abs(agg['MODEL_C3']['object_recall']-.2190)<=.05 and abs(agg['MODEL_C3']['object_f1']-.2585)<=.08 and abs(agg['MODEL_C3']['false_positives']-14)<=6 and abs(agg['MODEL_C3']['missed']-37)<=8
    summary={'reference':{'object_recall':.2190,'object_f1':.2585,'false_positives':14,'missed':37},'aggregate':agg,'c3_reproduction':'PASS' if c3pass else 'FAIL','decision':'MODEL_C6_CLEAR_IMPROVEMENT' if c3pass and agg['MODEL_C6']['object_recall']>agg['MODEL_C3']['object_recall'] and agg['MODEL_C6']['object_f1']>agg['MODEL_C3']['object_f1'] and agg['MODEL_C6']['false_positives']<=agg['MODEL_C3']['false_positives']+5 else 'MODEL_C6_NO_IMPROVEMENT','production':'MODEL_C UNCHANGED'}
    (QA/'14A6B_c3_c6_performance.json').write_text(json.dumps({'summary':summary,'per_patch':perf},indent=2),encoding='utf-8')
    sheet=Image.new('RGB',(1024,512*len(panels)),'white');d=ImageDraw.Draw(sheet)
    for i,(pid,im,g,m3,m6) in enumerate(panels):
        y=i*512; sheet.paste(im,(0,y));
        for x,mask,col,label in [(256,g,'lime','GT'),(512,m3,'red','C3'),(768,m6,'cyan','C6')]:
            a=Image.new('RGBA',(256,256),(0,0,0,0)); aa=np.asarray(mask); alpha=Image.fromarray((aa*130).astype('uint8')).resize((256,256),Image.Resampling.NEAREST); a.putalpha(alpha); layer=Image.new('RGBA',(256,256),col); layer.putalpha(a.getchannel('A')); sheet.paste(layer,(x,y),layer); d.text((x+5,y+5),label,fill='white',stroke_width=2,stroke_fill='black')
        d.text((5,y+5),pid,fill='yellow',stroke_width=2,stroke_fill='black')
    sheet.save(QA/'14A6B_c3_c6_contact_sheet.png'); print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
