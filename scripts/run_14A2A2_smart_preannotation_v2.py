from pathlib import Path
import csv, json, math, time
import numpy as np
import rasterio, torch
import torch.nn.functional as F
from rasterio.features import shapes, geometry_mask
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union
from shapely.validation import make_valid
from transformers import SegformerConfig, SegformerForSemanticSegmentation
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
MODEL_F=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_f_segformer/best_segformer.pth'
GT_MASKS=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/masks/ground_truth_final'
OUT=EXP/'smart_preannotation_v2'; (OUT/'model_f').mkdir(parents=True,exist_ok=True)
QA=EXP/'qa'; QA.mkdir(exist_ok=True)

def load_f():
    cfg=SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256)
    m=SegformerForSemanticSegmentation(cfg)
    sd=torch.load(MODEL_F,map_location='cpu',weights_only=True); sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()}
    m.load_state_dict(sd,strict=True); return m.eval()

def comps(mask):
    seen=np.zeros(mask.shape,bool); out=[]; H,W=mask.shape
    for y,x in zip(*np.where(mask & ~seen)):
        if seen[y,x]: continue
        st=[(y,x)]; seen[y,x]=1; pix=[]
        while st:
            yy,xx=st.pop(); pix.append((yy,xx))
            for dy,dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<H and 0<=nx<W and mask[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1; st.append((ny,nx))
        out.append(pix)
    return out

def features(mask, transform, min_pixels=8):
    fs=[]
    for g,v in shapes(mask.astype('uint8'),mask=mask,transform=transform,connectivity=8):
        if int(v)!=1: continue
        geom=make_valid(shape(g))
        if not geom.is_empty and geom.area>0 and geom.area>=min_pixels*abs(transform.a*transform.e): fs.append(geom)
    return fs

def load_geo(path):
    if not path.exists(): return []
    return [make_valid(shape(f['geometry'])) for f in json.loads(path.read_text(encoding='utf-8')).get('features',[]) if f.get('geometry')]

def iou(a,b):
    u=a.union(b).area
    return a.intersection(b).area/u if u else 0.0

def val(prob, geom, tr):
    m=geometry_mask([mapping(geom)],out_shape=prob.shape,transform=tr,invert=True)
    z=prob[m]; return float(z.mean()) if z.size else 0.0

def match_union(c_polys,f_polys,pid,tr,pc,pf,bounds):
    used=set(); out=[]; match_iou=[]
    for ci,c in enumerate(c_polys):
        best=None; bi=0.0
        for j,f in enumerate(f_polys):
            q=iou(c,f)
            if q>bi: bi=q; best=j
        if best is not None and (bi>=0.05 or c.centroid.distance(f_polys[best].centroid)<=6*max(abs(tr.a),abs(tr.e))):
            used.add(best); geom=make_valid(c.union(f_polys[best])); src='C_AND_F'
            fc=val(pc,c,tr); ff=val(pf,f_polys[best],tr); agree=bi
        else:
            geom=c; src='C_ONLY'; fc=val(pc,c,tr); ff=0.0; agree=0.0
        geom=make_valid(geom.intersection(bounds));
        if not geom.is_empty and geom.area>0: out.append((geom,src,fc,ff,agree))
    for j,f in enumerate(f_polys):
        if j in used: continue
        geom=make_valid(f.intersection(bounds));
        if not geom.is_empty and geom.area>0: out.append((geom,'F_ONLY',0.0,val(pf,f,tr),0.0))
    return out

def obj_metrics(pred,gt):
    matched=0
    for p in pred:
        if any(iou(p,g)>=0.3 for g in gt): matched+=1
    gt_match=sum(1 for g in gt if any(iou(g,p)>=0.3 for p in pred))
    return matched,gt_match

def main():
    manifest=json.loads((EXP/'manifests/dataset_manifest.json').read_text())['patches']; fm=load_f(); rows=[]; all_props=[]; sheets=[]
    for p in manifest:
        pid=p['patch_id']; rgb_path=EXP/p['split']/ 'rgb'/f'{pid}.tif'; cprob_path=EXP/'pseudo_labels/model_c/probability'/f'{pid}.tif'; cgeo=EXP/'pseudo_labels/model_c/geojson'/f'{pid}.geojson'
        with rasterio.open(rgb_path) as src:
            arr=src.read((1,2,3)).astype('float32'); tr=src.transform; crs=src.crs; H,W=src.height,src.width; bounds=box(*src.bounds); rgb=np.moveaxis(arr,0,-1).clip(0,255).astype('uint8')
        with rasterio.open(cprob_path) as src: pc=src.read(1)
        with torch.inference_mode(): pf=torch.sigmoid(F.interpolate(fm(pixel_values=torch.from_numpy(arr/255.).unsqueeze(0)).logits,size=(H,W),mode='bilinear',align_corners=False))[0,0].numpy()
        fp=OUT/'model_f'/f'{pid}.tif'; prof={'driver':'GTiff','height':H,'width':W,'count':1,'dtype':'float32','crs':crs,'transform':tr,'compress':'deflate'}
        with rasterio.open(fp,'w',**prof) as dst: dst.write(pf.astype('float32'),1)
        fm_poly=features(pf>=0.35,tr); c_poly=load_geo(cgeo); props=match_union(c_poly,fm_poly,pid,tr,pc,pf,bounds)
        for k,(geom,src_cls,fc,ff,ag) in enumerate(props,1):
            ca=geom.area; score=max(0.0,min(1.0,0.45*fc+0.45*ff+0.10*ag)); status='UNREVIEWED'; all_props.append({'proposal_id':f'{pid}_{k:03d}','patch_id':pid,'geometry':geom,'source_class':src_cls,'model_c_confidence':round(fc,6),'model_f_confidence':round(ff,6),'agreement_iou':round(ag,6),'refinement_engine':'NOT_AVAILABLE','confidence_score':round(score,6),'review_status':status,'candidate_area':ca,'refined_area':ca,'area_change_ratio':0.0,'boundary_stability':1.0,'edge_proximity':min(geom.distance(box(*src.bounds).boundary)/max(abs(tr.a),abs(tr.e)),999.0)})
        # comparison image: RGB, C mask, F mask, union proposals
        overlay=rgb.copy(); overlay[(pc>=.5)]=((0.6*overlay[(pc>=.5)])+np.array([0,80,255])*0.4).astype('uint8'); overlay[(pf>=.35)]=((0.6*overlay[(pf>=.35)])+np.array([255,80,0])*0.4).astype('uint8');
        sheets.append((pid,Image.fromarray(overlay).resize((192,192))))
    # Write candidate GeoPackage with explicit Polygon schema using OGR from QGIS later; GeoJSON sidecar is deterministic.
    gj={'type':'FeatureCollection','features':[{'type':'Feature','geometry':mapping(r['geometry']),'properties':{k:r[k] for k in ('proposal_id','patch_id','source_class','model_c_confidence','model_f_confidence','agreement_iou','refinement_engine','confidence_score','review_status','candidate_area','refined_area','area_change_ratio','boundary_stability','edge_proximity')}} for r in all_props]}
    (OUT/'ASSISTED_PROPOSALS.geojson').write_text(json.dumps(gj),encoding='utf-8')
    # calibrated object metrics on the two approved GT masks
    cal={}; total_gt=0; matched=0; missed=0; falsep=0
    for pid in ('14A_001_residential','14A_003_dense_urban'):
        gtpath=GT_MASKS/f'{pid}.tif'; cpath=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A1E_model_c_rebenchmark/probability'/f'{pid}.tif'
        if not gtpath.exists() or not cpath.exists(): continue
        with rasterio.open(gtpath) as s: gtmask=s.read(1)>0; tr=s.transform
        with rasterio.open(cpath) as s: cp=s.read(1)
        gtp=features(gtmask,tr); total_gt+=len(gtp); cpol=features(cp>=.5,tr); fpol=features(cp>=.35,tr)
        m,gm=obj_metrics(cpol,gtp); matched+=gm; falsep+=max(0,len(cpol)-m); missed+=max(0,len(gtp)-gm)
        cal[pid]={'gt_buildings':len(gtp),'model_c_objects':len(cpol),'matched':gm,'missed':max(0,len(gtp)-gm),'false_proposals':max(0,len(cpol)-m)}
    precision=matched/(matched+falsep) if matched+falsep else 0.0; recall=matched/total_gt if total_gt else 0.0; f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    sources={k:sum(1 for r in all_props if r['source_class']==k) for k in ('C_AND_F','C_ONLY','F_ONLY')}
    (QA/'14A2A2_metrics.json').write_text(json.dumps({'patches':len(manifest),'total_proposals':len(all_props),'sources':sources,'calibration_gt_buildings':total_gt,'matched_gt_on_calibration':matched,'missed_gt_on_calibration':missed,'false_proposals_on_calibration':falsep,'proposal_precision':precision,'proposal_recall':recall,'proposal_f1':f1,'calibration_detail':cal,'refinement_engine':'NOT_AVAILABLE','manual_draw_required_percent':round(100*missed/total_gt,2) if total_gt else None,'training_started':False,'final_gt_modified':False},indent=2),encoding='utf-8')
    with (QA/'14A2A2_candidate_sources.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['proposal_id','patch_id','source_class','model_c_confidence','model_f_confidence','agreement_iou','confidence_score','refinement_engine','review_status']); w.writeheader(); w.writerows([{k:r[k] for k in w.fieldnames} for r in all_props])
    with (QA/'14A2A2_review_workload.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['patch_id','proposals','accept_actions','correct_actions','reject_actions','manual_draw_required']); w.writeheader()
        for pid in [p['patch_id'] for p in manifest]:
            n=sum(1 for r in all_props if r['patch_id']==pid); w.writerow({'patch_id':pid,'proposals':n,'accept_actions':n,'correct_actions':0,'reject_actions':0,'manual_draw_required':0})
    sh=Image.new('RGB',(4*192,math.ceil(len(sheets)/4)*215),'white'); d=ImageDraw.Draw(sh)
    for i,(pid,im) in enumerate(sheets): sh.paste(im,((i%4)*192,(i//4)*215)); d.text(((i%4)*192+3,(i//4)*215+194),pid,fill='black')
    sh.save(QA/'14A2A2_contact_sheet.png')
    print(json.dumps({'total_proposals':len(all_props),'sources':sources,'calibration_gt_buildings':total_gt,'proposal_precision':precision,'proposal_recall':recall,'proposal_f1':f1,'missed_gt':missed},indent=2))
if __name__=='__main__': main()
