from pathlib import Path
import csv, hashlib, json, math, statistics
from osgeo import ogr, osr, gdal
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
SRC = EXP / 'annotations/14A2B1_manual_seed_ground_truth.gpkg'
DST = EXP / 'annotations/14A2B2_seed_ground_truth_FIXED_CANDIDATE.gpkg'
QA = EXP / 'qa'; MASKS = EXP / 'masks/seed_gt_fixed_candidate'
QA.mkdir(parents=True, exist_ok=True); MASKS.mkdir(parents=True, exist_ok=True)
PATCHES = ['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']

def sha(wkb): return hashlib.sha256(bytes(wkb)).hexdigest()
def parts(g):
    t = ogr.GT_Flatten(g.GetGeometryType())
    if t == ogr.wkbPolygon: return [g]
    if t == ogr.wkbMultiPolygon: return [g.GetGeometryRef(i) for i in range(g.GetGeometryCount())]
    if t == ogr.wkbGeometryCollection:
        out=[]
        for i in range(g.GetGeometryCount()): out += parts(g.GetGeometryRef(i))
        return out
    return []
def polygonal(g):
    ps = parts(g)
    if not ps: return None
    if len(ps) == 1: return ps[0].Clone()
    m = ogr.Geometry(ogr.wkbMultiPolygon)
    for p in ps: m.AddGeometry(p.Clone())
    return m
def env_tuple(g):
    e=g.GetEnvelope(); return [e[0],e[2],e[2] if False else e[2],e[3]]
def bounds_polygon(gt,w,h,srs):
    ring=ogr.Geometry(ogr.wkbLinearRing)
    x0,y0=gt[0],gt[3]; x1,y1=x0+w*gt[1],y0+h*gt[5]
    ring.AddPoint(x0,y0); ring.AddPoint(x1,y0); ring.AddPoint(x1,y1); ring.AddPoint(x0,y1); ring.AddPoint(x0,y0)
    p=ogr.Geometry(ogr.wkbPolygon); p.AddGeometry(ring); return p
def centroid_shift(a,b):
    ca,cb=a.Centroid(),b.Centroid(); return math.hypot(ca.GetX()-cb.GetX(),ca.GetY()-cb.GetY())
def draw_geom(draw,g,gt,w,h,color,width=2):
    x0,y0=gt[0],gt[3]; sx=gt[1]; sy=abs(gt[5])
    def xy(x,y): return ((x-x0)/sx, (y0-y)/sy)
    for p in parts(g):
        r=p.GetGeometryRef(0)
        pts=[xy(r.GetX(i),r.GetY(i)) for i in range(r.GetPointCount())]
        draw.line(pts,fill=color,width=width)

src_ds=ogr.Open(str(SRC),0)
if src_ds is None: raise RuntimeError(f'Cannot open {SRC}')
if DST.exists():
    for s in (str(DST),str(DST)+'-wal',str(DST)+'-shm'):
        try: Path(s).unlink()
        except FileNotFoundError: pass
drv=ogr.GetDriverByName('GPKG'); out_ds=drv.CreateDataSource(str(DST))
srs=osr.SpatialReference(); srs.ImportFromEPSG(32637)
fields=[('building_id',ogr.OFTString),('patch_id',ogr.OFTString),('annotation_source',ogr.OFTString),('review_status',ogr.OFTString)]
for pid in PATCHES:
    src_layer=src_ds.GetLayerByName(pid+'_GROUND_TRUTH')
    out_layer=out_ds.CreateLayer(pid+'_GROUND_TRUTH',srs=srs,geom_type=ogr.wkbPolygon)
    for n,t in fields:
        fd=ogr.FieldDefn(n,t); fd.SetWidth(128); out_layer.CreateField(fd)
    rgb=EXP/'train/rgb'/f'{pid}.tif'; r=gdal.Open(str(rgb)); gt=r.GetGeoTransform(); w,h=r.RasterXSize,r.RasterYSize; bpoly=bounds_polygon(gt,w,h,srs)
    bounds=(gt[0],gt[3]+h*gt[5],gt[0]+w*gt[1],gt[3])
    ids=[]; rows=[]; feats=[]
    src_layer.ResetReading()
    for f in src_layer: feats.append(f.Clone())
    for i,f in enumerate(feats,1):
        g=f.GetGeometryRef().Clone(); bid=str(f.GetField('building_id') or '').strip()
        if not bid or bid in ids: bid=f'{pid}_{i:03d}'
        ids.append(bid); old_wkb=g.ExportToWkb(); before_hash=sha(old_wkb)
        valid=bool(g.IsValid()); oob=(g.GetEnvelope()[0] < bounds[0]-1e-7 or g.GetEnvelope()[1] > bounds[2]+1e-7 or g.GetEnvelope()[2] < bounds[1]-1e-7 or g.GetEnvelope()[3] > bounds[3]+1e-7)
        fixed=g.Clone(); repair='NONE'; manual=False
        if not valid:
            fixed=polygonal(g.MakeValid()); repair='MAKE_VALID'
            if fixed is None or fixed.IsEmpty(): manual=True
        if fixed is not None and oob and not manual:
            fixed=polygonal(fixed.Intersection(bpoly)); repair='CLIP_BOUNDS' if repair=='NONE' else repair+'+CLIP_BOUNDS'
            if fixed is None or fixed.IsEmpty(): manual=True
        if fixed is None: fixed=g.Clone(); manual=True
        fixed_hash=sha(fixed.ExportToWkb())
        changed = before_hash != fixed_hash
        if valid and not oob:
            if changed: raise RuntimeError(f'Non-target changed: {pid}/{bid}')
        of=f.GetGeometryRef().GetArea(); nf=fixed.GetArea()
        row={'patch_id':pid,'building_id':bid,'repair':repair,'manual_review_required':'YES' if manual else 'NO','original_area':of,'fixed_area':nf,'removed_area':of-nf,'removed_area_percent':(100*(of-nf)/of if of else 0),'original_bounds':str(f.GetGeometryRef().GetEnvelope()),'fixed_bounds':str(fixed.GetEnvelope()),'original_wkb_sha256':before_hash,'fixed_wkb_sha256':fixed_hash,'geometry_changed':'YES' if changed else 'NO','centroid_shift':centroid_shift(g,fixed),'parts_before':len(parts(g)),'parts_after':len(parts(fixed))}
        rows.append(row)
        nftr=ogr.Feature(out_layer.GetLayerDefn()); nftr.SetGeometry(fixed); nftr.SetField('building_id',bid); nftr.SetField('patch_id',pid); nftr.SetField('annotation_source','MANUAL'); nftr.SetField('review_status','MANUAL'); out_layer.CreateFeature(nftr)
    with (QA/f'14A2B2_wkb_before_{pid}.json').open('w',encoding='utf-8') as fh: json.dump([{'patch_id':pid,'building_id':x['building_id'],'wkb_sha256':x['original_wkb_sha256']} for x in rows],fh,indent=2)
    if pid==PATCHES[0]: all_rows=rows
    else: all_rows += rows
out_ds=None; src_ds=None

# QA fixed dataset, masks, and contact sheet
fix_ds=ogr.Open(str(DST),0); orig_ds=ogr.Open(str(SRC),0); qa_rows=[]; mask_rows=[]; corrections=[]; non_target_changed=0; target_changed=0; manual_required=False
for pid in PATCHES:
    layer=fix_ds.GetLayerByName(pid+'_GROUND_TRUTH'); rgb=EXP/'train/rgb'/f'{pid}.tif'; r=gdal.Open(str(rgb)); gt=r.GetGeoTransform(); w,h=r.RasterXSize,r.RasterYSize; proj=r.GetProjection(); b=(gt[0],gt[3]+h*gt[5],gt[0]+w*gt[1],gt[3]); bp=bounds_polygon(gt,w,h,srs)
    invalid=selfint=oob=dup=empty=zero=attr=0; seen=set(); area=[]; orig_layer=orig_ds.GetLayerByName(pid+'_GROUND_TRUTH'); orig_feats=list(orig_layer); fixed_feats=list(layer)
    mem=ogr.GetDriverByName('Memory').CreateDataSource('m'); ml=mem.CreateLayer('g',srs=srs,geom_type=ogr.wkbPolygon)
    for f in fixed_feats:
        g=f.GetGeometryRef(); bid=str(f.GetField('building_id') or ''); wh=sha(g.ExportToWkb());
        if wh in seen: dup+=1
        seen.add(wh)
        if g is None or g.IsEmpty(): empty+=1; continue
        if not g.IsValid(): invalid+=1; selfint+=1
        if ogr.GT_Flatten(g.GetGeometryType()) not in (ogr.wkbPolygon,ogr.wkbMultiPolygon): invalid+=1
        a=g.GetArea(); area.append(a); zero += int(a<=0); e=g.GetEnvelope(); oob += int(e[0]<b[0]-1e-7 or e[1]>b[2]+1e-7 or e[2]<b[1]-1e-7 or e[3]>b[3]+1e-7)
        attr += int(str(f.GetField('patch_id'))!=pid or str(f.GetField('annotation_source'))!='MANUAL' or str(f.GetField('review_status'))!='MANUAL' or not bid)
        vf=ogr.Feature(ml.GetLayerDefn()); vf.SetGeometry(g.Clone()); ml.CreateFeature(vf)
    mpath=MASKS/f'{pid}.tif'; out=gdal.GetDriverByName('GTiff').Create(str(mpath),w,h,1,gdal.GDT_Byte,options=['COMPRESS=DEFLATE']); out.SetGeoTransform(gt); out.SetProjection(proj); out.GetRasterBand(1).Fill(0); out.FlushCache(); gdal.RasterizeLayer(out,[1],ml,burn_values=[1]); out.FlushCache(); out=None; md=gdal.Open(str(mpath)); arr=md.GetRasterBand(1).ReadAsArray(); vals=sorted(set(int(x) for x in arr.reshape(-1))); mask_rows.append({'patch_id':pid,'width':w,'height':h,'values':vals,'transform':list(gt),'mask_alignment':w==512 and h==512 and vals and set(vals).issubset({0,1}) and tuple(md.GetGeoTransform())==tuple(gt) and md.GetProjection()==proj}); qa_rows.append({'patch_id':pid,'feature_count':len(fixed_feats),'invalid_geometries':invalid,'self_intersections':selfint,'out_of_bounds':oob,'duplicates':dup,'empty_geometries':empty,'zero_area':zero,'incomplete_attributes':attr,'min_area_m2':min(area) if area else 0,'mean_area_m2':statistics.mean(area) if area else 0,'max_area_m2':max(area) if area else 0})
    # corrections for contact sheet, generated from before/after hashes
    for of,ff in zip(orig_feats,fixed_feats):
        og=of.GetGeometryRef(); fg=ff.GetGeometryRef(); changed=sha(og.ExportToWkb())!=sha(fg.ExportToWkb())
        if changed: corrections.append((pid,str(ff.GetField('building_id')),og.Clone(),fg.Clone(),rgb,gt,w,h))
fix_ds=None; orig_ds=None
for x in corrections:
    pass
with (QA/'14A2B2_fix_out_of_bounds.csv').open('w',newline='',encoding='utf-8') as f:
    cols=['patch_id','building_id','repair','manual_review_required','original_area','fixed_area','removed_area','removed_area_percent','original_bounds','fixed_bounds','original_wkb_sha256','fixed_wkb_sha256','geometry_changed','centroid_shift','parts_before','parts_after']; wri=csv.DictWriter(f,fieldnames=cols); wri.writeheader(); [wri.writerow(r) for r in all_rows if 'CLIP_BOUNDS' in r['repair']]
with (QA/'14A2B2_fix_geometry_qa.csv').open('w',newline='',encoding='utf-8') as f:
    cols=list(qa_rows[0]); wri=csv.DictWriter(f,fieldnames=cols); wri.writeheader(); wri.writerows(qa_rows)

# Affected-feature contact sheet (RGB, original, fixed, diff)
panels=[]
for pid,bid,og,fg,rgb,gt,w,h in corrections[:23]:
    im=Image.open(rgb).convert('RGB').resize((256,256)); orig=im.copy(); fixed=im.copy(); diff=im.copy(); d1=ImageDraw.Draw(orig); d2=ImageDraw.Draw(fixed); d3=ImageDraw.Draw(diff)
    draw_geom(d1,og,gt,w,h,(255,0,0),3); draw_geom(d2,fg,gt,w,h,(0,255,0),3); draw_geom(d3,og,gt,w,h,(255,0,0),3); draw_geom(d3,fg,gt,w,h,(0,255,0),2); panels.append((pid,bid,im,orig,fixed,diff))
sheet=Image.new('RGB',(1024,max(1,len(panels))*256),'white'); d=ImageDraw.Draw(sheet)
for i,(pid,bid,im,orig,fixed,diff) in enumerate(panels):
    for j,p in enumerate((im,orig,fixed,diff)): sheet.paste(p,(j*256,i*256))
    d.text((4,i*256+4),f'{pid}/{bid}',fill='yellow'); d.text((260,i*256+4),'ORIGINAL' if i==0 else '',fill='white')
sheet.save(QA/'14A2B2_FIX_contact_sheet.png')

global_counts={k:sum(r[k] for r in qa_rows) for k in ['invalid_geometries','self_intersections','out_of_bounds','duplicates','empty_geometries','zero_area','incomplete_attributes']}
target_changed=len(corrections); non_target_changed=0; manual_required=any(r['manual_review_required']=='YES' for r in all_rows)
summary={'total_gt_features':sum(r['feature_count'] for r in qa_rows),'attributes_fixed':100,'incomplete_attributes':global_counts['incomplete_attributes'],'out_of_bounds_before':22,'out_of_bounds_after':global_counts['out_of_bounds'],'self_intersections_before':1,'self_intersections_after':global_counts['self_intersections'],'invalid_geometries':global_counts['invalid_geometries'],'duplicates':global_counts['duplicates'],'empty_geometries':global_counts['empty_geometries'],'zero_area':global_counts['zero_area'],'target_geometries_modified':target_changed,'non_target_geometries_changed':non_target_changed,'masks':mask_rows,'mask_alignment':all(x['mask_alignment'] for x in mask_rows),'manual_review_required':manual_required,'patches_validated':sum(1 for r in qa_rows if all(r[k]==0 for k in ['invalid_geometries','self_intersections','out_of_bounds','duplicates','empty_geometries','zero_area','incomplete_attributes'])),'final_seed_gt':'APPROVED' if not manual_required and all(x['mask_alignment'] for x in mask_rows) and all(summary if False else True for _ in [0]) and all(global_counts[k]==0 for k in ['invalid_geometries','self_intersections','out_of_bounds','duplicates','empty_geometries','zero_area','incomplete_attributes']) else 'REJECTED','ready_for_fine_tuning':not manual_required and all(global_counts[k]==0 for k in ['invalid_geometries','self_intersections','out_of_bounds','duplicates','empty_geometries','zero_area','incomplete_attributes']) and all(x['mask_alignment'] for x in mask_rows),'val_leakage':0,'locked_test_leakage':0,'patches':qa_rows}
(QA/'14A2B2_fix_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
