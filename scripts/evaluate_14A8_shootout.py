"""Common frozen GOLD evaluation, separate from ML workers. Writes benchmark outputs only."""
from pathlib import Path
import csv,json,time,hashlib,math
from collections import defaultdict
import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from shapely import wkb,make_valid
from shapely.geometry import mapping,Polygon
from shapely.ops import transform as geom_transform,unary_union
from pyproj import Transformer
from osgeo import ogr,gdal,osr
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';GOLD=BASE/'14A7_gold_set';OUT=BASE/'qa/14A8_model_shootout'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def csvwrite(path,rows,fields=None):
 with path.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def dump(path,obj):path.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def boundary(m):return m & ~ndimage.binary_erosion(m,structure=np.ones((3,3),bool),border_value=0)
def pixel(p,g):
 tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum())
 return dict(PIXEL_TP=tp,PIXEL_FP=fp,PIXEL_FN=fn,PIXEL_IOU=tp/(tp+fp+fn) if tp+fp+fn else 1.,DICE=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.,PIXEL_PRECISION=tp/(tp+fp) if tp+fp else 0.,PIXEL_RECALL=tp/(tp+fn) if tp+fn else 0.)
def boundaries(p,g):
 pb=boundary(p);gb=boundary(g);npb=int(pb.sum());ngb=int(gb.sum());a=int((pb&ndimage.binary_dilation(gb,structure=np.ones((3,3),bool))).sum());b=int((gb&ndimage.binary_dilation(pb,structure=np.ones((3,3),bool))).sum())
 pr=a/npb if npb else 0.;rc=b/ngb if ngb else 0.;f=2*pr*rc/(pr+rc) if pr+rc else 0.
 assert 0<=f<=1
 return dict(BOUNDARY_F1=f,BOUNDARY_PRECISION=pr,BOUNDARY_RECALL=rc,BOUNDARY_PRED_PIXELS=npb,BOUNDARY_GT_PIXELS=ngb,BOUNDARY_PRED_WITHIN1=a,BOUNDARY_GT_WITHIN1=b),pb,gb
def chamfer(target):
 # Exact historical14A1E two-pass 8-neighbour chamfer, diag sqrt2, no border wrap.
 d=np.full(target.shape,np.inf,float);d[target]=0.;h,w=d.shape;diag=math.sqrt(2)
 for y in range(h):
  for x in range(w):
   if y:d[y,x]=min(d[y,x],d[y-1,x]+1)
   if x:d[y,x]=min(d[y,x],d[y,x-1]+1)
   if y and x:d[y,x]=min(d[y,x],d[y-1,x-1]+diag)
   if y and x+1<w:d[y,x]=min(d[y,x],d[y-1,x+1]+diag)
 for y in range(h-1,-1,-1):
  for x in range(w-1,-1,-1):
   if y+1<h:d[y,x]=min(d[y,x],d[y+1,x]+1)
   if x+1<w:d[y,x]=min(d[y,x],d[y,x+1]+1)
   if y+1<h and x+1<w:d[y,x]=min(d[y,x],d[y+1,x+1]+diag)
   if y+1<h and x:d[y,x]=min(d[y,x],d[y+1,x-1]+diag)
 return d
def objects(mask,rgb_path,spec):
 labels,n=ndimage.label(mask,structure=ndimage.generate_binary_structure(2,1 if spec['connectivity']==4 else 2));count=np.bincount(labels.ravel());keep=count>=spec['min_component_pixels'];keep[0]=False;labels=np.where(keep[labels],labels,0).astype('int32');filtered=labels>0
 r=gdal.Open(str(rgb_path));tr=r.GetGeoTransform();proj=r.GetProjection();r=None
 d=gdal.GetDriverByName('MEM').Create('',512,512,2,gdal.GDT_Int32);d.SetGeoTransform(tr);d.SetProjection(proj);d.GetRasterBand(1).WriteArray(labels);d.GetRasterBand(2).WriteArray(filtered.astype('int32'))
 v=ogr.GetDriverByName('Memory').CreateDataSource('');srs=osr.SpatialReference();srs.ImportFromWkt(proj);l=v.CreateLayer('pred',srs,ogr.wkbUnknown);l.CreateField(ogr.FieldDefn('label',ogr.OFTInteger))
 assert gdal.Polygonize(d.GetRasterBand(1),d.GetRasterBand(2),l,0,options=['8CONNECTED=8'] if spec['connectivity']==8 else [])==0
 tx=Transformer.from_crs(proj,'EPSG:32637',always_xy=True);groups=defaultdict(list);repairs=0
 for f in l:
  g=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()));g=geom_transform(tx.transform,g)
  if not g.is_valid:g=make_valid(g);repairs+=1
  if g.geom_type=='GeometryCollection':g=unary_union([q for q in g.geoms if q.geom_type in ('Polygon','MultiPolygon')])
  assert g.is_valid and not g.is_empty and g.area>0;groups[f['label']].append(g)
 result=[dict(label=k,geometry=unary_union(gs)) for k,gs in sorted(groups.items())];d=None;v=None
 return filtered,result,repairs
def matrices(gt,pred):
 inter=np.zeros((len(gt),len(pred)));iou=inter.copy()
 for i,g in enumerate(gt):
  a=g['geometry']
  for j,p in enumerate(pred):
   b=p['geometry'];ab=a.bounds;bb=b.bounds
   if ab[0]>bb[2] or bb[0]>ab[2] or ab[1]>bb[3] or bb[1]>ab[3]:continue
   s=a.intersection(b).area;inter[i,j]=s;iou[i,j]=s/(a.area+b.area-s) if s else 0.
 return iou,inter
def matching(mat,t):
 n,m=mat.shape
 if not n or not m:return []
 # One extra valid match outweighs all IoU tie-break bonuses together.
 score=np.where(mat>=t,1+mat/(min(n,m)+1),0.)
 i,j=linear_sum_assignment(np.c_[score,np.zeros((n,n))],maximize=True)
 return [(int(a),int(b),float(mat[a,b])) for a,b in zip(i,j) if b<m and mat[a,b]>=t]
def draw_geom(draw,g,tx,inv,color,width=2,offset=(0,0)):
 parts=[g] if g.geom_type=='Polygon' else list(g.geoms)
 for part in parts:
  if part.geom_type!='Polygon':continue
  for ring in [part.exterior]+list(part.interiors):
   pts=[tuple(gdal.ApplyGeoTransform(inv,*tx.transform(x,y))) for x,y in ring.coords];draw.line([(x-offset[0],y-offset[1]) for x,y in pts],fill=color,width=width)
def save_tif(path,a,source,dtype=gdal.GDT_Byte):
 r=gdal.Open(str(source));d=gdal.GetDriverByName('GTiff').Create(str(path),512,512,1,dtype,options=['COMPRESS=DEFLATE']);d.SetProjection(r.GetProjection());d.SetGeoTransform(r.GetGeoTransform());d.GetRasterBand(1).WriteArray(a);d=None;r=None
def main():
 protocol=json.loads((OUT/'14A8_frozen_protocol.json').read_text());assert sha(OUT/'14A8_frozen_protocol.json')==(OUT/'14A8_frozen_protocol.sha256').read_text()
 runs=json.loads((OUT/'14A8_worker_exits.json').read_text());specs=[s for s in protocol['models'] if any(r['model']==s['model'] and r['exit_code']==0 for r in runs)]
 ds=gdal.OpenEx(str(ROOT/protocol['patches'][0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES']);gt_by_patch=defaultdict(list)
 for f in ds.GetLayerByName('buildings_gt'):gt_by_patch[f['patch_id']].append(dict(fid=f.GetFID(),building_id=f['building_id'],geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
 ds=None
 for v in gt_by_patch.values():v.sort(key=lambda g:g['fid'])
 assert sum(map(len,gt_by_patch.values()))==165
 patchrows=[];runtime_rows=[];gtrows=[];fp_rows=[];fn_rows=[];adj_rows=[];threshold_rows=[];area_rows=[];visual={};case_crops=[]
 fp_case_id=0;fn_case_id=0
 for p in protocol['patches']:
  pid=p['patch_id'];rgbpath=ROOT/p['rgb_path'];r=gdal.Open(str(rgbpath));tr=r.GetGeoTransform();inv=gdal.InvGeoTransform(tr);proj=r.GetProjection();r=None
  to_native=Transformer.from_crs('EPSG:32637',proj,always_xy=True)
  with np.load(OUT/'inputs'/(pid+'.npz')) as f:rgb=np.moveaxis(f['rgb'],0,-1);gtmask=f['gt'].astype(bool)
  gt=gt_by_patch[pid];gt_boundary=boundary(gtmask);gt_dist=chamfer(gt_boundary)
  # Exact image-space footprint, reprojected in the already validated manifest bounds for edge proximity tags.
  area_gt=np.array([g['geometry'].area for g in gt]);near=[]
  for i,g in enumerate(gt):
   native=geom_transform(to_native.transform,g['geometry']);pts=[gdal.ApplyGeoTransform(inv,x,y) for x,y in native.exterior.coords] if native.geom_type=='Polygon' else [gdal.ApplyGeoTransform(inv,x,y) for part in native.geoms for x,y in part.exterior.coords]
   edge=any(min(x,y,512-x,512-y)<1.5 for x,y in pts);adjacent=any(g['geometry'].distance(q['geometry'])<=1.0 for k,q in enumerate(gt) if k!=i)
   near.append((edge,adjacent));area_rows.append(dict(patch_id=pid,scene_type=p['scene_type'],gt_id=g['fid'],building_id=g['building_id'],area_m2=g['geometry'].area,size_class='SMALL' if g['geometry'].area<=50 else 'NOT_SMALL',edge_building=edge,adjacent_within_1m=adjacent))
  visual[pid]=dict(rgb=rgb,gt=gt,tx=to_native,inv=inv,models={})
  for spec in specs:
   mid=spec['model'];print('EVALUATE',mid,pid,flush=True);base=OUT/'models'/mid;base.mkdir(exist_ok=True)
   with np.load(OUT/'inference'/(mid+'__'+pid+'.npz')) as f:prob=f['probability']
   raw=prob>=spec['threshold'];post_start=time.perf_counter();final,pred,polyrep=objects(raw,rgbpath,spec);postseconds=time.perf_counter()-post_start
   metrics_start=time.perf_counter();mat,inter=matrices(gt,pred);pairs=matching(mat,.30);mg={a for a,_,_ in pairs};mp={b for _,b,_ in pairs};tp=len(pairs);fp=len(pred)-tp;fn=len(gt)-tp
   merged_hits=(inter/area_gt[:,None]>=.30) if len(pred) else np.zeros((len(gt),0),bool)
   pred_area=np.array([q['geometry'].area for q in pred]);frag_hits=(inter/pred_area[None,:]>=.30) if len(pred) else np.zeros((len(gt),0),bool)
   merged_pred=np.flatnonzero(merged_hits.sum(axis=0)>=2);fragmented_gt=np.flatnonzero(frag_hits.sum(axis=1)>=2)
   pix=pixel(raw,gtmask);bf,pb,gb=boundaries(raw,gtmask);fm=pixel(final,gtmask);fbf,_,_=boundaries(final,gtmask)
   if pb.any() and gb.any():
    pd=chamfer(pb);dist=np.r_[gt_dist[pb],pd[gb]];mbd=float(dist.mean());dist_sum=float(dist.sum());dist_count=len(dist)
   else:mbd='INF';dist_sum=float('inf');dist_count=int(pb.sum()+gb.sum())
   rt=json.loads((OUT/'models'/(mid+'_runtime.json')).read_text());tim=next(x for x in rt['patches'] if x['patch_id']==pid)
   precision=tp/len(pred) if pred else 0.;recall=tp/len(gt);small={i for i,g in enumerate(gt) if g['geometry'].area<=50};small_tp=len(small&mg)
   row=dict(MODEL=mid,PATCH=pid,SCENE=p['scene_type'],GT_OBJECTS=len(gt),PRED_OBJECTS=len(pred),TP=tp,FP=fp,FN=fn,OBJECT_PRECISION=precision,OBJECT_RECALL=recall,OBJECT_F1=2*tp/(len(gt)+len(pred)),
       **pix,**bf,MEAN_BOUNDARY_DISTANCE_PX=mbd,MISSED=fn,MERGED=len(merged_pred),FRAGMENTED=len(fragmented_gt),SMALL_GT=len(small),SMALL_TP=small_tp,SMALL_RECALL=small_tp/len(small) if small else None,
       FINAL_MASK_PIXEL_IOU=fm['PIXEL_IOU'],FINAL_MASK_DICE=fm['DICE'],FINAL_MASK_BOUNDARY_F1=fbf['BOUNDARY_F1'],CPU_INFERENCE_SECONDS=tim['inference_seconds'],CPU_POSTPROCESS_SECONDS=postseconds,
       CPU_TIME_TOTAL=tim['preprocessing_seconds']+tim['inference_seconds']+postseconds,POLYGONIZATION_REPAIRS=polyrep,BOUNDARY_DISTANCE_SUM=dist_sum,BOUNDARY_DISTANCE_COUNT=dist_count)
   patchrows.append(row)
   runtime_rows.append(dict(MODEL=mid,PATCH=pid,ENGINE=spec['engine'],THREADS=4,INTER_OP_THREADS=1,LOAD_SECONDS=rt['load_seconds'],WARMUP_SECONDS=rt['warmup_seconds'],PREPROCESS_SECONDS=tim['preprocessing_seconds'],INFERENCE_SECONDS=tim['inference_seconds'],POSTPROCESS_SECONDS=postseconds,
      EVALUATION_SECONDS=time.perf_counter()-metrics_start,OUTPUT_WRITE_SECONDS=tim['write_seconds'],TOTAL_STEADY_PIPELINE_SECONDS=row['CPU_TIME_TOTAL'],PEAK_WORKER_MB=rt['peak_working_set_mb']))
   matched={i:(j,v) for i,j,v in pairs}
   for threshold in (.30,.50,.70):
    q=matching(mat,threshold);threshold_rows.append(dict(MODEL=mid,PATCH=pid,IOU_THRESHOLD=threshold,GT=len(gt),PRED=len(pred),TP=len(q),FP=len(pred)-len(q),FN=len(gt)-len(q),F1=2*len(q)/(len(gt)+len(pred))))
   for i,g in enumerate(gt):
    j=int(mat[i].argmax()) if len(pred) else -1;best=float(mat[i,j]) if j>=0 else 0.;pair=matched.get(i)
    gtrows.append(dict(MODEL=mid,PATCH=pid,GT_ID=g['fid'],BUILDING_ID=g['building_id'],GT_AREA_M2=g['geometry'].area,BEST_PRED_ID=pred[j]['label'] if j>=0 else '',BEST_IOU=best,MATCHED_PRED_ID=pred[pair[0]]['label'] if pair else '',MATCHED_IOU=pair[1] if pair else 0,MATCHED_030=i in mg,SMALL=i in small))
    if i not in mg:
     tags=[]
     if i in small:tags.append('SMALL')
     if near[i][0]:tags.append('PATCH_EDGE')
     if p['scene_type']=='DENSE':tags.append('DENSE_CLUSTER')
     if near[i][1]:tags.append('ADJACENT_BUILDINGS')
     fn_case_id+=1;fn_rows.append(dict(REVIEW_ID='FN'+str(fn_case_id),MODEL=mid,PATCH=pid,GT_ID=g['fid'],BUILDING_ID=g['building_id'],AREA_M2=g['geometry'].area,BEST_IOU=best,CATEGORIES=';'.join(tags or ['OTHER']),BASIS='DETERMINISTIC_GEOMETRY_CONTEXT_NOT_CAUSAL_PROOF',VISUAL_REVIEW='NO',NOTE='Below object IoU0.30 after historical postprocess; not necessarily zero predicted pixels'))
   for j,q in enumerate(pred):
    if j not in mp:
     fp_case_id+=1;fp_rows.append(dict(REVIEW_ID='FP'+str(fp_case_id),MODEL=mid,PATCH=pid,PRED_ID=q['label'],AREA_M2=q['geometry'].area,BEST_GT_IOU=float(mat[:,j].max()) if len(gt) else 0.,CATEGORY='OTHER',BASIS='UNREVIEWED_FP_RELATIVE_TO_LOCKED_GT',VISUAL_REVIEW='NO',NOTE='Could be shape mismatch or missing GT; not automatically semantic background'))
   for j in merged_pred:adj_rows.append(dict(MODEL=mid,PATCH=pid,TYPE='MERGED',PRED_ID=pred[j]['label'],GT_IDS=';'.join(str(gt[i]['fid']) for i in np.flatnonzero(merged_hits[:,j])),RULE='intersection/GTarea>=0.30 for >=2GT; no duplicate TP credit'))
   for i in fragmented_gt:adj_rows.append(dict(MODEL=mid,PATCH=pid,TYPE='FRAGMENTED',PRED_ID=';'.join(str(pred[j]['label']) for j in np.flatnonzero(frag_hits[i])),GT_IDS=gt[i]['fid'],RULE='intersection/predarea>=0.30 for >=2preds'))
   save_tif(base/(pid+'_probability.tif'),prob,rgbpath,gdal.GDT_Float32);save_tif(base/(pid+'_raw_threshold.tif'),raw.astype('uint8'),rgbpath);save_tif(base/(pid+'_final_mask.tif'),final.astype('uint8'),rgbpath)
   dump(base/(pid+'_polygons.geojson'),dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:32637'}},features=[dict(type='Feature',geometry=mapping(q['geometry']),properties=dict(prediction_id=q['label'],model=mid,patch_id=pid)) for q in pred]))
   overlay=Image.fromarray(rgb).copy();od=ImageDraw.Draw(overlay)
   for g in gt:draw_geom(od,g['geometry'],to_native,inv,'lime',2)
   for q in pred:draw_geom(od,q['geometry'],to_native,inv,'magenta',2)
   overlay.save(OUT/'overlays'/(mid+'__'+pid+'.png'))
   visual[pid]['models'][mid]=dict(pred=pred,overlay=overlay,row=row)
   # Review the two largest unmatched predictions and two smallest FN per model/scene.
   fp_cases=sorted([x for x in fp_rows if x['MODEL']==mid and x['PATCH']==pid],key=lambda x:-x['AREA_M2'])[:2]
   fn_cases=sorted([x for x in fn_rows if x['MODEL']==mid and x['PATCH']==pid],key=lambda x:x['AREA_M2'])[:2]
   for record in fp_cases+fn_cases:
    g=next(q['geometry'] for q in pred if q['label']==record['PRED_ID']) if record['REVIEW_ID'].startswith('FP') else next(q['geometry'] for q in gt if q['fid']==record['GT_ID'])
    native=geom_transform(to_native.transform,g);bounds=native.bounds;corn=[gdal.ApplyGeoTransform(inv,bounds[0],bounds[1]),gdal.ApplyGeoTransform(inv,bounds[2],bounds[3])];x0=max(0,math.floor(min(a[0] for a in corn))-12);y0=max(0,math.floor(min(a[1] for a in corn))-12);x1=min(512,math.ceil(max(a[0] for a in corn))+12);y1=min(512,math.ceil(max(a[1] for a in corn))+12)
    crop=overlay.crop((x0,y0,x1,y1)).resize((192,192));cd=ImageDraw.Draw(crop);case_crops.append((record['REVIEW_ID'],mid,p['scene_type'],crop))
 global_rows=[]
 for spec in specs:
  mid=spec['model'];rr=[r for r in patchrows if r['MODEL']==mid];s=lambda k:sum(r[k] for r in rr);tp=s('TP');fp=s('FP');fn=s('FN');pr=tp/(tp+fp) if tp+fp else 0.;rc=tp/165;pt=s('PIXEL_TP');pf=s('PIXEL_FP');pn=s('PIXEL_FN');bpr=s('BOUNDARY_PRED_WITHIN1')/s('BOUNDARY_PRED_PIXELS') if s('BOUNDARY_PRED_PIXELS') else 0.;brc=s('BOUNDARY_GT_WITHIN1')/s('BOUNDARY_GT_PIXELS');rt=json.loads((OUT/'models'/(mid+'_runtime.json')).read_text())
  global_rows.append(dict(MODEL=mid,GT_OBJECTS=165,PRED_OBJECTS=s('PRED_OBJECTS'),TP=tp,FP=fp,FN=fn,OBJECT_PRECISION=pr,OBJECT_RECALL=rc,OBJECT_F1=2*tp/(165+s('PRED_OBJECTS')),PIXEL_IOU=pt/(pt+pf+pn),DICE=2*pt/(2*pt+pf+pn),PIXEL_PRECISION=pt/(pt+pf),PIXEL_RECALL=pt/(pt+pn),BOUNDARY_F1=2*bpr*brc/(bpr+brc) if bpr+brc else 0.,MEAN_BOUNDARY_DISTANCE_PX='INF' if any(r['MEAN_BOUNDARY_DISTANCE_PX']=='INF' for r in rr) else s('BOUNDARY_DISTANCE_SUM')/s('BOUNDARY_DISTANCE_COUNT') if s('BOUNDARY_DISTANCE_COUNT') else None,
    MISSED=fn,MERGED=s('MERGED'),FRAGMENTED=s('FRAGMENTED'),SMALL_GT=s('SMALL_GT'),SMALL_TP=s('SMALL_TP'),SMALL_RECALL=s('SMALL_TP')/s('SMALL_GT') if s('SMALL_GT') else None,
    CPU_TIME_TOTAL=s('CPU_TIME_TOTAL'),CPU_TIME_MEAN=s('CPU_TIME_TOTAL')/4,CPU_INFERENCE_MEAN=s('CPU_INFERENCE_SECONDS')/4,MODEL_LOAD_SECONDS=rt['load_seconds'],WARMUP_SECONDS=rt['warmup_seconds'],CPU_COLD_TOTAL=s('CPU_TIME_TOTAL')+rt['load_seconds']+rt['warmup_seconds'],PEAK_WORKER_MB=rt['peak_working_set_mb'],PIXEL_IOU_MACRO=float(np.mean([r['PIXEL_IOU'] for r in rr])),BOUNDARY_F1_MACRO=float(np.mean([r['BOUNDARY_F1'] for r in rr])),FINAL_MASK_IOU_MACRO=float(np.mean([r['FINAL_MASK_PIXEL_IOU'] for r in rr])),FINAL_MASK_BOUNDARY_F1_MACRO=float(np.mean([r['FINAL_MASK_BOUNDARY_F1'] for r in rr]))))
 ranked=sorted(global_rows,key=lambda r:(-r['OBJECT_F1'],-r['OBJECT_RECALL'],r['MISSED'],r['FP'],-r['BOUNDARY_F1'],-r['PIXEL_IOU'],r['CPU_TIME_MEAN']))
 for i,r in enumerate(ranked,1):r['RANK']=i
 for name,rows in [('14A8_patch_metrics.csv',patchrows),('14A8_global_model_comparison.csv',ranked),('14A8_runtime_metrics.csv',runtime_rows),('14A8_gt_object_matching.csv',gtrows),('14A8_false_positive_analysis.csv',fp_rows),('14A8_missed_buildings_analysis.csv',fn_rows),('14A8_adjacent_buildings_analysis.csv',adj_rows),('14A8_object_iou_sensitivity.csv',threshold_rows),('14A8_gt_area_distribution.csv',area_rows)]:
  csvwrite(OUT/name,rows)
 # Full-sized overlays are retained separately; comparative panels all use identical RGB grids.
 cols=2+len(specs);sheet=Image.new('RGB',(cols*256,4*296),'white');sd=ImageDraw.Draw(sheet)
 for i,p in enumerate(protocol['patches']):
  pid=p['patch_id'];v=visual[pid];y=i*296;gtimage=Image.fromarray(v['rgb']).copy();gd=ImageDraw.Draw(gtimage)
  for g in v['gt']:draw_geom(gd,g['geometry'],v['tx'],v['inv'],'lime',2)
  panels=[('RGB '+p['scene_type'],Image.fromarray(v['rgb'])),('GT '+str(len(v['gt'])),gtimage)]+[(s['model']+' TP/FP/FN '+ '/'.join(str(v['models'][s['model']]['row'][k]) for k in ['TP','FP','FN']),v['models'][s['model']]['overlay']) for s in specs]
  for j,(title,im) in enumerate(panels):sheet.paste(im.resize((256,256)),(j*256,y+32));sd.text((j*256+4,y+4),title,fill='black')
  sheet.crop((0,y,cols*256,y+296)).save(OUT/'overlays'/(pid+'_comparison.png'))
 sheet.save(OUT/'14A8_GLOBAL_CONTACT_SHEET.png')
 for kind in ['FP','FN']:
  cases=[q for q in case_crops if q[0].startswith(kind)]
  for page in range((len(cases)+15)//16):
   panel=Image.new('RGB',(4*208,4*240),'white');pd=ImageDraw.Draw(panel)
   for i,(rid,mid,scene,im) in enumerate(cases[page*16:(page+1)*16]):
    x=(i%4)*208;y=(i//4)*240;panel.paste(im,(x,y+40));pd.text((x+3,y+2),rid+' '+mid,fill='black');pd.text((x+3,y+18),scene,fill='black')
   panel.save(OUT/'diagnostics'/(kind+'_REVIEW_'+str(page+1)+'.png'))
 dump(OUT/'14A8_summary.json',dict(models_benchmarked=[s['model'] for s in specs],ranking=ranked,gt_buildings=165,small_buildings=ranked[0]['SMALL_GT'],primary_object_iou=.30,gold_unchanged=True,production_modified=False,no_training=True,no_threshold_sweep=True))
 print(json.dumps(ranked,indent=2),flush=True)
if __name__=='__main__':main()
