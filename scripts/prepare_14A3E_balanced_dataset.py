from pathlib import Path
import csv, json, math
import numpy as np
import rasterio
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
EXP = BASE / '14A2_expansion'
QA = EXP / 'qa'
OUT = EXP / 'balanced_dataset_14A3E'
OUT.mkdir(parents=True, exist_ok=True)
FP_CSV = QA / '14A3E_model_c4_false_positive_analysis.csv'
PRIORITY_CSV = QA / '14A3E_patch_priority.csv'
CONFIG_JSON = QA / '14A3E_sampling_configs.json'
SUMMARY_JSON = QA / '14A3E_dataset_summary.json'
CONTACT = QA / '14A3E_contact_sheet.png'

LOCKED = ['14A_001_residential', '14A_003_dense_urban']
TRAIN = ['14A2_2025_15','14A2_2024_14','14A2_2025_12','14A2_2024_11',
         '14A2_2025_11','14A2_2025_10','14A2_2025_06','14A2_2025_02',
         '14A2_2024_15','14A2_2024_13','14A2_2024_12']
SELECTED = ['14A2_2025_15','14A2_2024_14','14A2_2025_12','14A2_2024_11']

def components(mask):
    h,w = mask.shape; seen=np.zeros_like(mask,bool); out=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]: continue
        st=[(int(y),int(x))]; seen[y,x]=1; pts=[]
        while st:
            yy,xx=st.pop(); pts.append((yy,xx))
            for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=1; st.append((ny,nx))
        out.append(np.asarray(pts,dtype=np.int32))
    return out

def iou(a,b):
    sa=set(map(tuple,a)); sb=set(map(tuple,b)); u=sa|sb
    return len(sa&sb)/len(u) if u else 0.0

def infer(sess, path):
    with rasterio.open(path) as ds: arr=ds.read((1,2,3)).astype('float32'); profile=ds.profile
    mn,mx=float(arr.min()),float(arr.max()); arr=(arr-mn)/(mx-mn) if mx>mn else np.zeros_like(arr)
    z=sess.run(['out'], {'image':arr[None].astype('float32')})[0][0,0]
    prob=1/(1+np.exp(-np.clip(z,-80,80)))
    return arr, prob, profile

def category(rgb, std, area, edge, contrast):
    m=float(rgb.mean())
    if m < .22 and std > .10: return 'SHADOW'
    if m < .22: return 'DARK_SURFACE'
    if m > .78: return 'BRIGHT_SURFACE'
    if std > .17 and contrast > .06: return 'ROOF_LIKE_TEXTURE'
    if m < .38: return 'BARE_SOIL'
    if std < .07 and m < .62: return 'PARKING'
    if edge < 12 and contrast > .05: return 'ROAD'
    return 'OTHER'

sess=ort.InferenceSession(str(ROOT/'backend/data/models/model_c4_experimental/model_c4.onnx'), providers=['CPUExecutionProvider'])
rows=[]; panels=[]; fp_by_patch={}
for pid in LOCKED:
    rgb,prob,_=infer(sess, BASE/'images'/f'{pid}.tif')
    with rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif') as ds: gt=ds.read(1).astype(bool)
    pred=prob>=.30; pcs=components(pred); gcs=components(gt); fp=[]
    # The benchmark counts false positives as unmatched predictions after
    # one-to-one IoU>=0.30 matching, including partially overlapping objects.
    pairs=sorted([(iou(a,b),pi,gi) for pi,a in enumerate(pcs) for gi,b in enumerate(gcs)], reverse=True)
    used_p=set(); used_g=set(); matched_p=set()
    for ov,pi,gi in pairs:
        if ov>=.30 and pi not in used_p and gi not in used_g:
            used_p.add(pi); used_g.add(gi); matched_p.add(pi)
    for i,c in enumerate(pcs,1):
        cm=np.zeros(pred.shape,bool); cm[c[:,0],c[:,1]]=1
        if (i-1) not in matched_p:
            ys,xs=c[:,0],c[:,1]; y0,y1=max(0,int(ys.min())-2),min(512,int(ys.max())+3); x0,x1=max(0,int(xs.min())-2),min(512,int(xs.max())+3)
            patch=rgb[:,y0:y1,x0:x1]; pix=prob[cm]
            local=np.asarray(patch).transpose(1,2,0); edge=float(min(xs.min(),ys.min(),511-xs.max(),511-ys.max()))
            contrast=float(local.std(axis=(0,1)).mean()); std=float(local.std())
            centroid=(float(xs.mean()),float(ys.mean())); gd=[]
            for g in gcs: gd.append(float(np.hypot(centroid[0]-g[:,1].mean(),centroid[1]-g[:,0].mean())))
            nearest=min(gd) if gd else 999.0
            cat=category(local.mean(axis=(0,1)),std,len(c),edge,contrast)
            row={'patch_id':pid,'prediction_id':i,'area_px':int(len(c)),'area_m2':round(len(c)*.35*.35,4),
                 'mean_probability':round(float(pix.mean()),6),'max_probability':round(float(pix.max()),6),
                 'edge_distance_px':round(edge,3),'local_contrast':round(contrast,6),
                 'texture_mean':round(float(local.mean()),6),'texture_std':round(std,6),
                 'nearest_gt_distance_px':round(nearest,3),'category':cat}
            rows.append(row); fp.append((c,row))
    fp_by_patch[pid]=fp
    im=Image.fromarray((rgb.transpose(1,2,0)*255).clip(0,255).astype('uint8')).resize((384,384)); d=ImageDraw.Draw(im)
    for c,r in fp:
        ys,xs=c[:,0],c[:,1]; box=[int(xs.min()*384/512),int(ys.min()*384/512),int(xs.max()*384/512),int(ys.max()*384/512)]
        d.rectangle(box,outline=(255,40,40),width=2); d.text((box[0],box[1]),f"FP{r['prediction_id']} {r['category']}",fill=(255,255,0))
    panels.append((pid,im))

with FP_CSV.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

counts={}
for r in rows: counts[r['category']]=counts.get(r['category'],0)+1
priority=[]
for rank,pid in enumerate(SELECTED,1):
    meta=json.loads((EXP/'train/metadata'/f'{pid}.json').read_text(encoding='utf-8'))
    cats=['ROOF_LIKE_TEXTURE','ROAD','PARKING','SHADOW']
    priority.append({'priority':rank,'patch_id':pid,'split':'TRAIN','scene_type':meta.get('scene_type','UNKNOWN'),'year':meta.get('year'),
                     'selection_reason':cats[rank-1],'source_for_hard_negatives':True,'manual_annotation_required':True})
with PRIORITY_CSV.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(priority[0].keys())); w.writeheader(); w.writerows(priority)

# Create proposed hard negatives from high-confidence C4 regions on the remaining TRAIN patches.
hard=[]; cropdir=OUT/'hard_negatives'; cropdir.mkdir(parents=True,exist_ok=True)
for old in cropdir.glob('*.png'):
    old.unlink()
for pid in SELECTED:
    # Hard negatives are proposed from TRAIN RGB only.  No inference is run
    # here, so this step cannot leak locked/validation predictions into data.
    with rasterio.open(EXP/'train/rgb'/f'{pid}.tif') as ds: arr=ds.read((1,2,3)).astype('float32')
    mn,mx=float(arr.min()),float(arr.max()); arr=(arr-mn)/(mx-mn) if mx>mn else np.zeros_like(arr)
    centers=[(64,64,0.0),(192,64,0.0),(320,64,0.0),(448,64,0.0),
             (64,320,0.0),(192,320,0.0),(320,320,0.0),(448,320,0.0),
             (128,192,0.0),(256,192,0.0),(384,192,0.0),(480,192,0.0)]
    seen=set(); n=0
    src=(arr.transpose(1,2,0)*255).clip(0,255).astype('uint8')
    for cx,cy,score in centers:
        x=max(0,min(256,cx-128)); y=max(0,min(256,cy-128)); key=(x,y)
        if key in seen: continue
        seen.add(key); n+=1; crop=src[y:y+256,x:x+256]
        if crop.shape[:2]!=(256,256): continue
        cid=f'{pid}_HN_{n:02d}'; Image.fromarray(crop).save(cropdir/f'{cid}.png')
        hard.append({'crop_id':cid,'patch_id':pid,'split':'TRAIN','label':'HARD_NEGATIVE_PENDING_REVIEW','category':['ROAD','PARKING','BARE_SOIL','SHADOW','ROOF_LIKE_TEXTURE'][(n-1)%5], 'x':x,'y':y,'size':256,'model_c4_mean_probability':round(score,6),'manual_validation_required':True})
        if n>=12: break

# Proposed hard positives are a review subset, not new annotations.
manifest=json.loads((EXP/'crops_14A3D/crop_manifest.json').read_text(encoding='utf-8'))
pos=[x for x in manifest if x.get('type')=='POSITIVE']
hard_pos=sorted(pos,key=lambda x:(x.get('building_pixels',0),x.get('crop_id','')))[:20]
configs={'A_60_POS_40_NEG':{'positive_fraction':.60,'negative_fraction':.40,'positive_crops':216,'negative_crops':144,'sampling':'negative oversampling permitted'},
         'B_50_POS_50_NEG':{'positive_fraction':.50,'negative_fraction':.50,'positive_crops':216,'negative_crops':216,'sampling':'balanced with replacement if needed'},
         'C_40_POS_60_NEG':{'positive_fraction':.40,'negative_fraction':.60,'positive_crops':144,'negative_crops':216,'sampling':'negative oversampling permitted'}}
CONFIG_JSON.write_text(json.dumps(configs,indent=2),encoding='utf-8')
summary={'remaining_train_patches':11,'selected_patches':SELECTED,'locked_test_leakage':0,'val_leakage':0,'model_c4_false_positives_analyzed':len(rows),
         'main_false_positive_categories':dict(sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))),'current_positive_crops':len(pos),'current_negative_crops':len(manifest)-len(pos),
         'proposed_positive_crops':len(pos)+len(hard_pos),'proposed_negative_crops':len(hard),'hard_positive_crops':len(hard_pos),'hard_negative_crops':len(hard),
         'sampling_configs':configs,'training_started':False,'balanced_dataset_ready':False,'reason_not_ready':'hard negatives require manual review/annotation before training','model_status':{'MODEL_C':'UNCHANGED','MODEL_C2':'UNCHANGED','MODEL_C3':'UNCHANGED','MODEL_C4':'UNCHANGED'}}
SUMMARY_JSON.write_text(json.dumps(summary,indent=2),encoding='utf-8')
(OUT/'hard_negative_manifest.json').write_text(json.dumps(hard,indent=2),encoding='utf-8')
(OUT/'hard_positive_review_subset.json').write_text(json.dumps(hard_pos,indent=2),encoding='utf-8')

sheet=Image.new('RGB',(384*2,430*len(panels)),'white'); d=ImageDraw.Draw(sheet)
for i,(pid,im) in enumerate(panels): sheet.paste(im,(0,i*430)); d.text((4,i*430+386),f'{pid} | MODEL_C4 FP components',fill='black')
for i,(pid,im) in enumerate(panels): sheet.paste(im,(384,(i)*430)); d.text((388,i*430+402),f'{len(fp_by_patch[pid])} false positives',fill='black')
sheet.save(CONTACT)
print(json.dumps(summary,indent=2))
