from pathlib import Path
import csv, json
import numpy as np
import rasterio
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
EXP=BASE/'14A2_expansion'; QA=EXP/'qa'; OUT=EXP/'targeted_review_14A3E2'; OUT.mkdir(parents=True,exist_ok=True)
NEG_MAN=EXP/'balanced_dataset_14A3E'/ 'hard_negative_manifest.json'
POS_MAN=EXP/'balanced_dataset_14A3E'/ 'hard_positive_review_subset.json'
PRIORITY=list(csv.DictReader((QA/'14A3E_patch_priority.csv').open(encoding='utf-8')))

def bounds(pid,x,y,size=256):
    with rasterio.open(EXP/'train/rgb'/f'{pid}.tif') as ds:
        t=ds.transform; a,b=t.c, t.a; top=t.f; bottom=t.f+t.e*ds.height
        left=t.c+t.a*x; right=t.c+t.a*(x+size); ytop=t.f+t.e*y; ybottom=t.f+t.e*(y+size)
    return [min(left,right),min(ytop,ybottom),max(left,right),max(ytop,ybottom)]

neg=json.loads(NEG_MAN.read_text(encoding='utf-8'))
neg_rows=[]
for i,r in enumerate(neg,1):
    pid=r['patch_id']; bb=bounds(pid,int(r['x']),int(r['y']),256)
    neg_rows.append({'candidate_id':f'14A3E2_HN_{i:03d}','crop_id':r.get('crop_id',''),'patch_id':pid,'crop_x':r['x'],'crop_y':r['y'],'crop_size':256,
                     'minx':bb[0],'miny':bb[1],'maxx':bb[2],'maxy':bb[3],
                     'source_false_positive_id':'TRAIN_GRID_PROPOSAL','model_c4_confidence':r.get('model_c4_mean_probability',''),
                     'candidate_category':r['category'],'human_status':'UNREVIEWED','comment':''})
with (QA/'14A3E2_negative_review.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(neg_rows[0].keys())); w.writeheader(); w.writerows(neg_rows)

# Portable candidate layer for QGIS review (no dependency on GeoPandas/Fiona).
features=[]
for r in neg_rows:
    features.append({'type':'Feature','properties':{k:r[k] for k in ('candidate_id','patch_id','candidate_category','human_status','comment')},
                     'geometry':{'type':'Polygon','coordinates':[[[r['minx'],r['miny']],[r['maxx'],r['miny']],[r['maxx'],r['maxy']],[r['minx'],r['maxy']],[r['minx'],r['miny']]]]}})
(OUT/'HARD_NEGATIVE_CANDIDATES.geojson').write_text(json.dumps({'type':'FeatureCollection','name':'HARD_NEGATIVE_CANDIDATES','crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:EPSG::32637'}},'features':features},indent=2),encoding='utf-8')

pos=json.loads(POS_MAN.read_text(encoding='utf-8')); pos_rows=[]
for i,r in enumerate(pos,1):
    pid=r['patch_id']; bb=bounds(pid,int(r['x']),int(r['y']),256)
    pos_rows.append({'target_id':f'14A3E2_HP_{i:03d}','patch_id':pid,'crop_id':r['crop_id'],'crop_x':r['x'],'crop_y':r['y'],
                     'minx':bb[0],'miny':bb[1],'maxx':bb[2],'maxy':bb[3],'building_pixels':r.get('building_pixels',''),
                     'annotation_source':'MANUAL_TARGETED','review_status':'PENDING_MANUAL_TARGET_GT','geometry_status':'NOT_ANNOTATED','qa_result':'PENDING'})
with (QA/'14A3E2_positive_geometry_qa.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(pos_rows[0].keys())); w.writeheader(); w.writerows(pos_rows)

summary={'priority_patches':4,'hard_negative_candidates':len(neg_rows),'valid_negatives':0,'rejected_negatives':0,'unreviewed_negatives':len(neg_rows),
         'hard_positives_proposed':len(pos_rows),'hard_positives_annotated':0,'positive_geometry_qa':'PENDING_MANUAL_ANNOTATION',
         'final_positive_crops':196,'final_negative_crops':3,'val_leakage':0,'locked_test_leakage':0,'training_started':False,
         'balanced_dataset_ready':False,'next_step':'COMPLETE TARGETED REVIEW','models':{'MODEL_C':'UNCHANGED','MODEL_C2':'UNCHANGED','MODEL_C3':'UNCHANGED','MODEL_C4':'UNCHANGED'}}
(QA/'14A3E2_balanced_dataset_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

# Contact sheet of every candidate crop, labelled with the review decision that is still pending.
thumbs=[]
for r in neg_rows:
    p=EXP/'balanced_dataset_14A3E'/ 'hard_negatives' / f"{r['crop_id']}.png"
    if not p.exists():
        # Match by manifest order when files were written with per-patch numbering.
        p=next(iter((EXP/'balanced_dataset_14A3E'/'hard_negatives').glob(f"{r['patch_id']}_HN_*.png")),None)
    if p and p.exists():
        im=Image.open(p).convert('RGB').resize((128,128)); thumbs.append((r['candidate_id'],r['patch_id'],r['candidate_category'],im))
cols=6; cellw,cellh=190,160; rows=(len(thumbs)+cols-1)//cols
sheet=Image.new('RGB',(cols*cellw,rows*cellh),'white'); d=ImageDraw.Draw(sheet)
for i,(cid,pid,cat,im) in enumerate(thumbs):
    x=(i%cols)*cellw; y=(i//cols)*cellh; sheet.paste(im,(x,y)); d.text((x,y+130),cid,fill='black'); d.text((x,y+144),f'{pid} {cat}',fill='black')
sheet.save(QA/'14A3E2_contact_sheet.png')
print(json.dumps(summary,indent=2))
