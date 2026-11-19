"""Read-only diagnosis of frozen 14A8 C6 outputs. No inference or calibration."""
from pathlib import Path
import csv, json, hashlib, math, sys
from collections import Counter, defaultdict
import numpy as np
from scipy import ndimage
from osgeo import gdal, ogr, osr
from shapely import wkb
from shapely.ops import transform as geom_transform
from pyproj import Transformer
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parent))
from evaluate_14A8_shootout import objects, matrices, matching, draw_geom, save_tif

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
BENCH=BASE/'qa/14A8_model_shootout'
OUT=BASE/'qa/14A9A_small_building_diagnostic'
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)

def readcsv(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def writecsv(p, rows):
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
def rasterize(g,tx,tr,proj):
    v=ogr.GetDriverByName('Memory').CreateDataSource('');srs=osr.SpatialReference();srs.ImportFromWkt(proj)
    l=v.CreateLayer('gt',srs,ogr.wkbUnknown);f=ogr.Feature(l.GetLayerDefn());f.SetGeometry(ogr.CreateGeometryFromWkb(geom_transform(tx.transform,g).wkb));l.CreateFeature(f)
    d=gdal.GetDriverByName('MEM').Create('',512,512,1,gdal.GDT_Byte);d.SetProjection(proj);d.SetGeoTransform(tr);d.GetRasterBand(1).Fill(0);gdal.RasterizeLayer(d,[1],l,burn_values=[1])
    return d.ReadAsArray().astype(bool)
def tile_sheet(panels, titles, width=256):
    sheet=Image.new('RGB',(width*len(panels),width+28),'white');d=ImageDraw.Draw(sheet)
    for i,(im,title) in enumerate(zip(panels,titles)):
        sheet.paste(im.resize((width,width),Image.Resampling.NEAREST),(i*width,28));d.text((i*width+4,4),title,fill='black',font=FONT)
    return sheet
def bounds_px(g,tx,inv,margin=12):
    b=geom_transform(tx.transform,g).bounds;pts=[gdal.ApplyGeoTransform(inv,b[0],b[1]),gdal.ApplyGeoTransform(inv,b[2],b[3])]
    return (max(0,math.floor(min(p[0] for p in pts))-margin),max(0,math.floor(min(p[1] for p in pts))-margin),min(512,math.ceil(max(p[0] for p in pts))+margin),min(512,math.ceil(max(p[1] for p in pts))+margin))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((BENCH/'14A8_frozen_protocol.json').read_text())
    spec=next(s for s in protocol['models'] if s['model']=='MODEL_C6')
    assert (spec['threshold'],spec['min_component_pixels'],spec['connectivity'])==(.3,479,4)
    # Declared diagnostic rules; never a candidate inference configuration.
    rules=dict(small='GT area <=50 m2, unchanged historical definition',
      signal='Descriptive spatial enrichment: GT mean > local-background mean AND GT p90 > local-background p90. Background = 3-pixel square dilation ring excluding ALL rasterized GT. Not a calibrated probability or statistical significance test.',
      stages='First failure: no threshold pixels -> A if no enrichment, B if enrichment; raw coverage wholly removed -> C; final coverage with frozen >=30% GT coverage merge diagnostic -> D; remaining unmatched final coverage -> E; otherwise F.',
      medium='50 < GT area <=200 m2; new descriptive area stratum, not a historical benchmark class',large='GT area >200 m2; descriptive round area boundary fixed before this diagnostic run, no parameter selection',
      interpretation='A is no local enrichment at this image scale, NOT proof of zero internal network signal. B is subthreshold localized evidence. E is insufficient IoU/competition, NOT a metric bug.',
      calibration=False,inference=False)
    dump(OUT/'14A9A_diagnostic_rules.json',rules)
    # Hash every old benchmark artifact plus all frozen GOLD inputs and model weights.
    paths=set(p for p in BENCH.rglob('*') if p.is_file())
    for r in readcsv(BENCH/'14A8_gold_input_hashes.csv'):
        p=ROOT/r['PATH'];assert sha(p).lower()==r['SHA256'].lower();paths.add(p)
    for s in protocol['models']:
        p=ROOT/s['path']
        if p.exists():paths.add(p)
    paths.update(p for p in (BASE/'14A7_gold_set/manifest').glob('*') if p.is_file())
    before={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
    assert sha(ROOT/spec['path'])==spec['sha256']
    ds=gdal.OpenEx(str(ROOT/protocol['patches'][0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
    gt=defaultdict(list)
    for f in ds.GetLayerByName('buildings_gt'):
        gt[f['patch_id']].append(dict(fid=f.GetFID(),building_id=f['building_id'],geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
    ds=None
    oldmatch={(r['PATCH'],int(r['GT_ID'])):r for r in readcsv(BENCH/'14A8_gt_object_matching.csv') if r['MODEL']=='MODEL_C6'}
    fps=[r for r in readcsv(BENCH/'14A8_false_positive_analysis.csv') if r['MODEL']=='MODEL_C6']
    allrows=[];small_panels=[];fp_panels=[]
    for patch in protocol['patches']:
        pid=patch['patch_id'];print('DIAGNOSE',pid,flush=True);rgbpath=ROOT/patch['rgb_path']
        r=gdal.Open(str(rgbpath));tr=r.GetGeoTransform();inv=gdal.InvGeoTransform(tr);proj=r.GetProjection();r=None
        tx=Transformer.from_crs('EPSG:32637',proj,always_xy=True)
        data=np.load(BENCH/'inputs'/(pid+'.npz'));rgb=np.moveaxis(data['rgb'],0,-1);fullgt=data['gt'].astype(bool)
        prob=gdal.Open(str(BENCH/'models/MODEL_C6'/(pid+'_probability.tif'))).ReadAsArray()
        raw=prob>=.30;labels,n=ndimage.label(raw,structure=ndimage.generate_binary_structure(2,1));sizes=np.bincount(labels.ravel())
        keep=sizes>=479;keep[0]=False;final=keep[labels]
        assert np.array_equal(raw,gdal.Open(str(BENCH/'models/MODEL_C6'/(pid+'_raw_threshold.tif'))).ReadAsArray().astype(bool))
        assert np.array_equal(final,gdal.Open(str(BENCH/'models/MODEL_C6'/(pid+'_final_mask.tif'))).ReadAsArray().astype(bool))
        _,pred,_=objects(raw,rgbpath,spec)
        _,rawpred,_=objects(raw,rgbpath,{**spec,'min_component_pixels':1})
        gs=sorted(gt[pid],key=lambda x:x['fid']);mat,inter=matrices(gs,pred);rawmat,_=matrices(gs,rawpred)
        pairs=matching(mat,.30);matched={i for i,_,_ in pairs}
        rawmatched={i for i,_,_ in matching(rawmat,.30)}
        areas=np.array([g['geometry'].area for g in gs]);mergehit=inter/areas[:,None]>=.30
        merged=set(np.flatnonzero(mergehit.sum(axis=0)>=2))
        ims=[Image.fromarray(rgb),Image.fromarray(rgb).copy(),Image.fromarray(np.stack([prob*255,np.zeros_like(prob),255-prob*255],axis=-1).astype('uint8')),
             Image.fromarray((raw*255).astype('uint8')).convert('RGB'),Image.fromarray(np.stack([(labels*71)%255,(labels*137)%255,(labels*199)%255],axis=-1).astype('uint8')),Image.fromarray((final*255).astype('uint8')).convert('RGB')]
        d=ImageDraw.Draw(ims[1])
        for g in gs:draw_geom(d,g['geometry'],tx,inv,'lime',1)
        # GT outlines on each diagnostic state; raw RGB remains unaltered.
        for im in ims[2:]:
            d=ImageDraw.Draw(im)
            for g in gs:draw_geom(d,g['geometry'],tx,inv,'lime',1)
        tile_sheet(ims,['RGB','GT (green)','Probability: blue0 red1','Threshold >=0.30','Components prefilter','Final >=479 px']).save(OUT/(pid+'_stages.png'))
        for suffix,a,dt in [('probability',prob,gdal.GDT_Float32),('threshold',raw.astype('uint8'),gdal.GDT_Byte),('components',labels.astype('int32'),gdal.GDT_Int32),('final',final.astype('uint8'),gdal.GDT_Byte)]:
            save_tif(OUT/(pid+'_'+suffix+'.tif'),a,rgbpath,dt)
        for i,g in enumerate(gs):
            mask=rasterize(g['geometry'],tx,tr,proj);assert mask.any()
            ring=ndimage.binary_dilation(mask,structure=np.ones((7,7),bool)) & ~fullgt & ~mask
            vals=prob[mask];bg=prob[ring];assert len(bg)>0
            enriched=bool(vals.mean()>bg.mean() and np.percentile(vals,90)>np.percentile(bg,90))
            hits=int((raw&mask).sum());remaining=int((final&mask).sum());removed=hits>0 and remaining==0
            ismerge=any(mergehit[i,j] for j in merged)
            stage=('MATCHED' if i in matched else ('BELOW_THRESHOLD' if enriched else 'MODEL_SIGNAL_ABSENT') if hits==0 else 'REMOVED_BY_MIN_COMPONENT' if removed else 'MERGED_WITH_NEIGHBOR' if ismerge else 'MATCHING_FAILURE' if remaining else 'OTHER')
            old=oldmatch[pid,g['fid']];assert (old['MATCHED_030']=='True')==(i in matched)
            ids=np.unique(labels[mask&raw]);best=float(mat[i].max()) if len(pred) else 0
            row=dict(patch_id=pid,building_id=g['building_id'],gt_id=g['fid'],gt_area_px=int(mask.sum()),gt_area_m2=g['geometry'].area,
                size_class='SMALL' if g['geometry'].area<=50 else 'MEDIUM' if g['geometry'].area<=200 else 'LARGE',matched_final=i in matched,failure_stage=stage,
                max_probability=float(vals.max()),mean_probability=float(vals.mean()),p90_probability=float(np.percentile(vals,90)),pixels_above_0_30=hits,
                background_mean=float(bg.mean()),background_p90=float(np.percentile(bg,90)),signal_present=enriched,final_positive_pixels=remaining,removed_all_by_479=removed,
                overlapping_raw_component_ids=';'.join(map(str,ids)),overlapping_raw_component_sizes=';'.join(str(sizes[k]) for k in ids),
                merged_frozen_rule=ismerge,best_final_iou=best,best_raw_iou=float(rawmat[i].max()) if len(rawpred) else 0,
                raw_one_to_one_matched=i in rawmatched,eligible_final_iou_ge030=bool(best>=.3))
            allrows.append(row)
            if row['size_class']=='SMALL':
                b=bounds_px(g['geometry'],tx,inv);panels=[im.crop(b) for im in ims]
                sheet=tile_sheet(panels,['RGB','GT','Probability','Threshold0.30','Prefilter CC','Final479'],160)
                canvas=Image.new('RGB',(960,225),'white');canvas.paste(sheet,(0,37));dd=ImageDraw.Draw(canvas)
                dd.text((4,1),f"{pid} GT{g['fid']} {row['gt_area_m2']:.1f}m2 {stage}",fill='black',font=FONT)
                dd.text((4,19),f"pmax={vals.max():.3f} mean={vals.mean():.3f} p90={np.percentile(vals,90):.3f} hits={hits} final={remaining} IoU={best:.3f}",fill='black',font=FONT)
                canvas.save(OUT/(f"SMALL_GT{g['fid']}.png"));small_panels.append(canvas)
        for fp in [x for x in fps if x['PATCH']==pid]:
            q=next(p for p in pred if p['label']==int(fp['PRED_ID']));b=bounds_px(q['geometry'],tx,inv,18)
            overlay=ims[1].copy();draw_geom(ImageDraw.Draw(overlay),q['geometry'],tx,inv,'magenta',2)
            sheet=tile_sheet([Image.fromarray(rgb).crop(b),overlay.crop(b),ims[2].crop(b)],[fp['REVIEW_ID']+' RGB','GT green / FP magenta','Probability'],256)
            fp_panels.append((fp['REVIEW_ID'],sheet));sheet.save(OUT/(fp['REVIEW_ID']+'.png'))
    small=[r for r in allrows if r['size_class']=='SMALL'];assert len(small)==38 and sum(r['matched_final'] for r in small)==0
    writecsv(OUT/'14A9A_small_buildings.csv',small);writecsv(OUT/'14A9A_all_buildings.csv',allrows)
    counts=Counter(r['failure_stage'] for r in small)
    stages=['MODEL_SIGNAL_ABSENT','BELOW_THRESHOLD','REMOVED_BY_MIN_COMPONENT','MERGED_WITH_NEIGHBOR','MATCHING_FAILURE','OTHER']
    writecsv(OUT/'14A9A_failure_stage_summary.csv',[dict(failure_stage=s,count=counts[s],denominator=38) for s in stages])
    metrics=[]
    for cl in ['SMALL','MEDIUM','LARGE']:
        group=[r for r in allrows if r['size_class']==cl];n=len(group)
        metrics.append(dict(size_class=cl,gt_buildings=n,detected_final=sum(r['matched_final'] for r in group),detection_rate=sum(r['matched_final'] for r in group)/n,
            signal_present=sum(r['signal_present'] for r in group),survive_threshold=sum(r['pixels_above_0_30']>0 for r in group),all_coverage_removed_by_479=sum(r['removed_all_by_479'] for r in group),remaining_final_coverage=sum(r['final_positive_pixels']>0 for r in group)))
    writecsv(OUT/'14A9A_size_class_metrics.csv',metrics)
    for start in range(0,len(small_panels),6):
        sheet=Image.new('RGB',(960,225*len(small_panels[start:start+6])),'white')
        for j,im in enumerate(small_panels[start:start+6]):sheet.paste(im,(0,225*j))
        sheet.save(OUT/(f'14A9A_SMALL_CONTACT_{start//6+1}.png'))
    sheet=Image.new('RGB',(768,284*len(fp_panels)),'white')
    for j,(_,im) in enumerate(fp_panels):sheet.paste(im,(0,284*j))
    sheet.save(OUT/'14A9A_FP_ALL_11.png')
    summary=dict(small=38,stages=dict(counts),signal_present=sum(r['signal_present'] for r in small),survive_threshold=sum(r['pixels_above_0_30']>0 for r in small),
        removed_by_479=sum(r['removed_all_by_479'] for r in small),remaining_final_coverage=sum(r['final_positive_pixels']>0 for r in small),
        raw_one_to_one_matched=sum(r['raw_one_to_one_matched'] for r in small),raw_matched_and_removed=sum(r['raw_one_to_one_matched'] and r['removed_all_by_479'] for r in small),
        merged=sum(r['merged_frozen_rule'] for r in small),eligible_final_iou=sum(r['eligible_final_iou_ge030'] for r in small),size_classes=metrics,fp_count=len(fps),rules=rules)
    changed=[p for p,h in before.items() if sha(ROOT/p)!=h];assert not changed,changed
    dump(OUT/'14A9A_integrity.json',dict(files_checked=len(before),changed=changed,sha256_before_after=before))
    dump(OUT/'14A9A_summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
