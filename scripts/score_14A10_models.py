"""Instance-preserving polygonization and frozen GOLD scoring."""
from pathlib import Path
import sys,json,time
from collections import defaultdict,Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from discover_14A10_models import ROOT,OUT
sys.path.insert(0,str(OUT/'python_packages'))
from prepare_14A9B_datasets import BASE,sha,dump,csvwrite
from evaluate_14A8_shootout import objects,matrices,matching,pixel,boundaries,draw_geom,save_tif
from osgeo import gdal,ogr,osr
from shapely import wkb,make_valid
from shapely.geometry import mapping
from shapely.ops import transform as gt,unary_union
from pyproj import Transformer
from scipy import ndimage
from skimage.segmentation import watershed
import numpy as np
from PIL import Image,ImageDraw
P=json.loads((OUT/'protocol.json').read_text())
def instances(ch,spec):
 mask=ch[0]>=spec['threshold']
 if spec['model']=='UNET_DIST3':
  markers,_=ndimage.label((ch[1]>.5)&mask);labels=watershed(-ndimage.distance_transform_edt(mask),markers=markers,mask=mask).astype('int32')
 else:
  labels,_=ndimage.label(mask,ndimage.generate_binary_structure(2,2 if spec['model']=='SEGFORMER_F' else 1));sizes=np.bincount(labels.ravel());keep=sizes>=4 if spec['model']=='SEGFORMER_F' else sizes>=1;keep[0]=False;labels=np.where(keep[labels],labels,0).astype('int32')
 return labels
def polygonize(labels,rgbpath,minimum):
 r=gdal.Open(str(rgbpath));proj=r.GetProjection();tr=r.GetGeoTransform();d=gdal.GetDriverByName('MEM').Create('',512,512,2,gdal.GDT_Int32);d.SetProjection(proj);d.SetGeoTransform(tr);d.GetRasterBand(1).WriteArray(labels);d.GetRasterBand(2).WriteArray((labels>0).astype('int32'))
 v=ogr.GetDriverByName('Memory').CreateDataSource('');srs=osr.SpatialReference();srs.ImportFromWkt(proj);l=v.CreateLayer('instances',srs,ogr.wkbUnknown);l.CreateField(ogr.FieldDefn('id',ogr.OFTInteger));gdal.Polygonize(d.GetRasterBand(1),d.GetRasterBand(2),l,0)
 tx=Transformer.from_crs(proj,'EPSG:32637',always_xy=True);groups=defaultdict(list)
 for f in l:
  g=gt(tx.transform,wkb.loads(bytes(f.GetGeometryRef().ExportToWkb())))
  if not g.is_valid:g=make_valid(g)
  if g.geom_type=='GeometryCollection':g=unary_union([a for a in g.geoms if a.geom_type in ['Polygon','MultiPolygon']])
  if not g.is_empty:groups[f['id']].append(g)
 pred=[]
 for label,parts in sorted(groups.items()):
  g=unary_union(parts)
  if g.area>=minimum:assert g.is_valid;pred.append(dict(label=label,geometry=g))
 final=np.isin(labels,[p['label'] for p in pred]);return pred,final,np.where(final,labels,0).astype('int32')
def smoke_postprocess(mid):
 spec=next(s for s in P['models'] if s['model']==mid)
 with np.load(OUT/'smoke'/(mid+'.npz')) as f:labels=instances(f['channels'],spec)
 record=json.loads((BASE/'14A9B_active_learning/manifests/14A9B_selected_patches.json').read_text())[0]
 pred,final,labels=polygonize(labels,ROOT/record['rgb_path'],spec['min_area_m2']);assert labels.shape==(512,512)
 dump(OUT/'smoke'/(mid+'_postprocess.json'),dict(model=mid,status='READY',instances=len(pred),invalid=0,instance_ids_preserved=True));print('POSTPROCESS_READY',mid,len(pred),flush=True)
def main():
 mid=sys.argv[1]
 if '--smoke' in sys.argv:smoke_postprocess(mid);return
 spec=next(s for s in P['models'] if s['model']==mid);assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text();folder=OUT/'predictions'/mid;runtime=json.loads((folder/'runtime.json').read_text());gts=defaultdict(list)
 ds=gdal.OpenEx(str(ROOT/P['gold_patches'][0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):gts[f['patch_id']].append(dict(fid=f.GetFID(),building_id=f['building_id'],geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
 ds=None;rows=[];matches=[];tot=Counter();boundary_counts=Counter();posttimes=[]
 for r in P['gold_patches']:
  pid=r['patch_id'];gs=gts[pid]
  with np.load(folder/(pid+'.npz')) as f:ch=f['channels'];prob=f['probability']
  with np.load(BASE/'qa/14A8_model_shootout/inputs'/(pid+'.npz')) as f:rgb=np.moveaxis(f['rgb'],0,-1);target=f['gt'].astype(bool)
  t=time.perf_counter();labels=instances(ch,spec);pred,final,labels=polygonize(labels,ROOT/r['rgb_path'],spec['min_area_m2']);posttimes.append(time.perf_counter()-t)
  mat,inter=matrices(gs,pred);pairs=matching(mat,.3);mg={i for i,_,_ in pairs};raw=prob>=spec['threshold'];pix=pixel(raw,target);b=boundaries(raw,target)[0]
  boundary_counts.update({k:b[k] for k in ['BOUNDARY_PRED_PIXELS','BOUNDARY_GT_PIXELS','BOUNDARY_PRED_WITHIN1','BOUNDARY_GT_WITHIN1']})
  small={i for i,g in enumerate(gs) if g['geometry'].area<=50};medium={i for i,g in enumerate(gs) if 50<g['geometry'].area<=200};large=set(range(len(gs)))-small-medium;areas=np.array([g['geometry'].area for g in gs]);pa=np.array([p['geometry'].area for p in pred]);merged=int(((inter/areas[:,None]>=.3).sum(axis=0)>=2).sum()) if pred else 0;frag=int(((inter/pa[None,:]>=.3).sum(axis=1)>=2).sum()) if pred else 0
  row=dict(model=mid,patch_id=pid,TP=len(pairs),FP=len(pred)-len(pairs),FN=len(gs)-len(pairs),GT=len(gs),PRED=len(pred),SMALL_TP=len(small&mg),SMALL_FN=len(small-mg),SMALL_GT=len(small),MEDIUM_TP=len(medium&mg),MEDIUM_GT=len(medium),LARGE_TP=len(large&mg),LARGE_GT=len(large),MERGED=merged,FRAGMENTED=frag,PIXEL_TP=pix['PIXEL_TP'],PIXEL_FP=pix['PIXEL_FP'],PIXEL_FN=pix['PIXEL_FN'],BOUNDARY_F1=b['BOUNDARY_F1']);rows.append(row);tot.update({k:v for k,v in row.items() if k not in ['model','patch_id','BOUNDARY_F1']})
  for i,g in enumerate(gs):matches.append(dict(model=mid,patch_id=pid,gt_id=g['fid'],building_id=g['building_id'],area_m2=g['geometry'].area,matched=i in mg,best_iou=float(mat[i].max()) if pred else 0,matched_prediction=next((pred[j]['label'] for a,j,_ in pairs if a==i),'')))
  dump(folder/(pid+'_instances.geojson'),dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:32637'}},features=[dict(type='Feature',geometry=mapping(q['geometry']),properties=dict(prediction_id=q['label'],model=mid)) for q in pred]));save_tif(folder/(pid+'_instances.tif'),labels,ROOT/r['rgb_path'],gdal.GDT_Int32);save_tif(folder/(pid+'_probability.tif'),prob,ROOT/r['rgb_path'],gdal.GDT_Float32)
  ds=gdal.Open(str(ROOT/r['rgb_path']));tx=Transformer.from_crs('EPSG:32637',ds.GetProjection(),always_xy=True);inv=gdal.InvGeoTransform(ds.GetGeoTransform());im=Image.fromarray(rgb);draw=ImageDraw.Draw(im)
  for g in gs:draw_geom(draw,g['geometry'],tx,inv,'lime',1)
  for q in pred:draw_geom(draw,q['geometry'],tx,inv,'magenta',1)
  im.save(OUT/'overlays'/(mid+'__'+pid+'.png'))
 tp,fp,fn=tot['TP'],tot['FP'],tot['FN'];pt,pf,pn=tot['PIXEL_TP'],tot['PIXEL_FP'],tot['PIXEL_FN'];bp=boundary_counts['BOUNDARY_PRED_WITHIN1']/max(1,boundary_counts['BOUNDARY_PRED_PIXELS']);br=boundary_counts['BOUNDARY_GT_WITHIN1']/max(1,boundary_counts['BOUNDARY_GT_PIXELS'])
 result=dict(model=mid,**dict(tot),object_precision=tp/(tp+fp) if tp+fp else 0,object_recall=tp/165,object_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,small_recall=tot['SMALL_TP']/38,medium_recall=tot['MEDIUM_TP']/tot['MEDIUM_GT'],large_recall=tot['LARGE_TP']/tot['LARGE_GT'],pixel_iou=pt/(pt+pf+pn),dice=2*pt/(2*pt+pf+pn),boundary_f1=2*bp*br/(bp+br) if bp+br else 0,cpu_inference_mean=float(np.mean([t['inference_seconds'] for t in runtime['patches']])),cpu_postprocess_mean=float(np.mean(posttimes)),load_seconds=runtime['load_seconds'])
 csvwrite(OUT/'metrics'/(mid+'_patches.csv'),rows);csvwrite(OUT/'metrics'/(mid+'_matching.csv'),matches);dump(OUT/'metrics'/(mid+'.json'),result);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
