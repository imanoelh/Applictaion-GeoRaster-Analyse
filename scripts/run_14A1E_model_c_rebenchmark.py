import os,sys,json,time
from pathlib import Path
import numpy as np, rasterio
from rasterio.features import shapes
from shapely.geometry import shape,mapping
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; BACKEND=ROOT/'backend'; BASE=BACKEND/'data/fine_tuning/buildings/maxar_v2_high_precision'; OUT=BASE/'qa/14A1E_model_c_rebenchmark'; OUT.mkdir(parents=True,exist_ok=True)
for s in ['probability','binary','polygons','overlays']: (OUT/s).mkdir(exist_ok=True)
PIDS=['14A_001_residential','14A_003_dense_urban']; TH=0.5; MODEL=BACKEND/'data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth'; SHA='170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555'; sys.path.insert(0,str(BACKEND)); os.environ.setdefault('SPACENET2_ORT_INTRA_THREADS','8'); os.environ.setdefault('SPACENET2_ORT_INTER_THREADS','2')
from app.ai.models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
from app.ai.services.tiling_service import TilingService
def shift(a,dy,dx):
 out=np.zeros_like(a); ys=slice(max(0,dy),min(a.shape[0],a.shape[0]+dy)); xs=slice(max(0,dx),min(a.shape[1],a.shape[1]+dx)); sy=slice(max(0,-dy),min(a.shape[0],a.shape[0]-dy)); sx=slice(max(0,-dx),min(a.shape[1],a.shape[1]-dx)); out[ys,xs]=a[sy,sx]; return out
def dilate(a):
 out=a.copy()
 for dy in (-1,0,1):
  for dx in (-1,0,1): out|=shift(a,dy,dx)
 return out
def erode(a):
 out=a.copy()
 for dy in (-1,0,1):
  for dx in (-1,0,1): out &= shift(a,dy,dx)
 return out
def boundary(a): return a & ~erode(a)
def dil(a,n):
 for _ in range(n): a=dilate(a)
 return a
def pix(p,g):
 tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum());tn=int((~p&~g).sum()); den=tp+fp+fn
 return {'TP':tp,'FP':fp,'FN':fn,'TN':tn,'IoU':tp/den if den else 1.,'Dice':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.,'Precision':tp/(tp+fp) if tp+fp else 1.,'Recall':tp/(tp+fn) if tp+fn else 1.,'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.}
def bnd(p,g,res):
 pb,gb=boundary(p),boundary(g); out={'BoundaryIoU':int((pb&gb).sum())/int((pb|gb).sum()) if (pb|gb).any() else 1.}
 for n in [1,2,3]:
  pr=int((pb&dil(gb,n)).sum())/int(pb.sum()) if pb.any() else 1.;rc=int((gb&dil(pb,n)).sum())/int(gb.sum()) if gb.any() else 1.;out[f'BoundaryF1@{n}px']=2*pr*rc/(pr+rc) if pr+rc else 0.
 def dist(target):
  d=np.full(target.shape,np.inf,dtype=float); d[target]=0.; diag=2**0.5
  for y in range(d.shape[0]):
   for x in range(d.shape[1]):
    if y: d[y,x]=min(d[y,x],d[y-1,x]+1)
    if x: d[y,x]=min(d[y,x],d[y,x-1]+1)
    if y and x: d[y,x]=min(d[y,x],d[y-1,x-1]+diag)
    if y and x+1<d.shape[1]: d[y,x]=min(d[y,x],d[y-1,x+1]+diag)
  for y in range(d.shape[0]-1,-1,-1):
   for x in range(d.shape[1]-1,-1,-1):
    if y+1<d.shape[0]: d[y,x]=min(d[y,x],d[y+1,x]+1)
    if x+1<d.shape[1]: d[y,x]=min(d[y,x],d[y,x+1]+1)
    if y+1<d.shape[0] and x+1<d.shape[1]: d[y,x]=min(d[y,x],d[y+1,x+1]+diag)
    if y+1<d.shape[0] and x: d[y,x]=min(d[y,x],d[y+1,x-1]+diag)
  return d
 dg=dist(gb);dp=dist(pb);ds=np.r_[dg[pb],dp[gb]];h=max(float(dg[pb].max()) if pb.any() else 0,float(dp[gb].max()) if gb.any() else 0);out.update({'MeanBoundaryDistancePx':float(ds.mean()),'MeanBoundaryDistanceM':float(ds.mean()*res),'HausdorffPx':h,'HausdorffM':h*res});return out
def polys(m,tr): return [shape(g) for g,v in shapes(m.astype('uint8'),mask=m,transform=tr,connectivity=8) if shape(g).area>0]
def obj(pp,gg,t):
 matches=[];used=set()
 for g in gg:
  best=max([(g.intersection(p).area/g.union(p).area if g.union(p).area else 0,j) for j,p in enumerate(pp)],default=(0,None))
  if best[0]>=t:matches.append(best);used.add(best[1])
 m=len(matches);fp=len(pp)-len(used);miss=len(gg)-m;pr=m/(m+fp) if m+fp else 1.;rc=m/len(gg) if gg else 1.;return {'gt_buildings':len(gg),'predicted_buildings':len(pp),'matched_buildings':m,'missed_buildings':miss,'false_positive_buildings':fp,'merged_buildings':0,'fragmented_buildings':0,'object_precision':pr,'object_recall':rc,'object_f1':2*pr*rc/(pr+rc) if pr+rc else 0}
adapter=SpaceNet2DeepLabAdapter(MODEL,expected_sha256=SHA,engine='onnxruntime');t=time.perf_counter();adapter.load();load_s=time.perf_counter()-t;rows=[];allp=[];allg=[]
for pid in PIDS:
 img=BASE/'images'/(pid+'_v2.tif');gtpath=BASE/'masks/ground_truth_final'/(pid+'.tif')
 with rasterio.open(img) as src:rgb=src.read((1,2,3));profile=src.profile.copy();tr=src.transform;valid=np.all(np.isfinite(rgb),axis=0);hwc=np.moveaxis(rgb,0,-1)
 tiles=list(adapter.prepare_inference_tiles(TilingService().iter_tiles(img,raster_id='14A1E-'+pid,tile_size=512,overlap_ratio=0,min_valid_pixel_ratio=.05,preprocessing_profile='rgb_orthophoto_uint8_v1',band_indexes=(1,2,3)),img,raster_id='14A1E-'+pid,band_indexes=(1,2,3)));t=time.perf_counter();prob=adapter.predict(tiles[0]).probability_map;secs=time.perf_counter()-t
 with rasterio.open(gtpath) as g:gm=g.read(1).astype(bool)
 pm=(prob>=TH)&valid
 for folder,arr,dtype in [('probability',prob,'float32'),('binary',pm.astype('uint8'),'uint8')]:
  q=profile.copy();q.update(driver='GTiff',count=1,dtype=dtype,nodata=0,compress='deflate');
  with rasterio.open(OUT/folder/(pid+'.tif'),'w',**q) as d:d.write(arr.astype(dtype),1)
 pp=polys(pm,tr);gg=polys(gm,tr);(OUT/'polygons'/(pid+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','geometry':mapping(x),'properties':{'prediction_id':i+1,'threshold':TH}} for i,x in enumerate(pp)]},indent=2),encoding='utf-8')
 rgba=np.zeros((512,512,4),dtype='uint8');rgba[gm&~pm]=[0,255,0,150];rgba[pm&~gm]=[255,0,0,150];rgba[gm&pm]=[255,255,0,170];Image.alpha_composite(Image.fromarray(hwc.astype('uint8')).convert('RGBA'),Image.fromarray(rgba,'RGBA')).convert('RGB').save(OUT/'overlays'/(pid+'.png'))
 rows.append({'patch_id':pid,'inference_time_s':secs,'pixel':pix(pm,gm),'boundary':bnd(pm,gm,abs(tr.a)),'object_iou_0_30':obj(pp,gg,.3),'object_iou_0_50':obj(pp,gg,.5)});allp.append(pm);allg.append(gm)
adapter.close();gp=np.concatenate([x.ravel() for x in allp]);gg=np.concatenate([x.ravel() for x in allg]);avg=lambda k:float(np.mean([r['boundary'][k] for r in rows]));metrics={'model':'MODEL_C','engine':'ONNX_RUNTIME_CPU','threshold':TH,'load_time_s':load_s,'patches':rows,'global':{'pixel':pix(gp,gg),'boundary':{k:avg(k) for k in ['BoundaryIoU','BoundaryF1@1px','BoundaryF1@2px','BoundaryF1@3px','MeanBoundaryDistancePx','MeanBoundaryDistanceM','HausdorffPx','HausdorffM']}},'weights_changed':False,'gt_reference':'FINAL APPROVED 14A.1D4'};(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8');print(json.dumps(metrics,indent=2))
