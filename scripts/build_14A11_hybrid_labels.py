"""Object-level hybrid pseudo-labels. Never reads GOLD geometries or predictions."""
from pathlib import Path
import sys,json,math
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,OUT,sha,dump,csvwrite
from score_14A10_models import instances,polygonize
from evaluate_14A8_shootout import draw_geom,save_tif
from osgeo import gdal
from scipy import ndimage
from pyproj import Transformer
from shapely.geometry import mapping
from PIL import Image,ImageDraw
import numpy as np
P=json.loads((OUT/'protocol.json').read_text());assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text()
CROSS=ndimage.generate_binary_structure(2,1)
def stats(mask):
 y,x=np.nonzero(mask);area=len(y);edge=mask&~ndimage.binary_erosion(mask,CROSS);per=float(edge.sum());compact=min(1.,4*math.pi*area/max(1,per*per));h=int(y.max()-y.min()+1);w=int(x.max()-x.min()+1);aspect=max(h,w)/max(1,min(h,w));cov=np.cov(np.stack([x,y])) if area>2 else np.eye(2);ev,vec=np.linalg.eigh(cov);angle=math.degrees(math.atan2(vec[1,-1],vec[0,-1]))%180
 return compact,aspect,angle,edge
def adjacent(labels):
 pairs=set()
 for a,b in [(labels[:,:-1],labels[:,1:]),(labels[:-1,:],labels[1:,:])]:
  good=(a>0)&(b>0)&(a!=b)
  for x,y in np.unique(np.sort(np.stack([a[good],b[good]],axis=1),axis=1),axis=0):pairs.add((int(x),int(y)))
 return sorted(pairs)
def dominant_c6(mask,c):
 z=np.bincount(c[mask]);z[0]=0;return int(z.argmax()) if z.sum() else 0
def main():
 rows=[];actions=[];smallrows=[];summary=Counter();patchrows=[]
 for r in P['records']:
  pid=r['patch_id'];rgbpath=ROOT/r['rgb_path'];ds=gdal.Open(str(rgbpath));tr=ds.GetGeoTransform();proj=ds.GetProjection();inv=gdal.InvGeoTransform(tr);tx=Transformer.from_crs('EPSG:32637',proj,always_xy=True)
  with np.load(OUT/'inputs'/(pid+'.npz')) as f:rgb=np.moveaxis(f['rgb'],0,-1)
  with np.load(OUT/'teacher_predictions'/(pid+'.npz')) as f:c6=f['c6'];ch=f['dist3'];flip=f['dist3_flip']
  c,n=ndimage.label(c6>=.3,CROSS);sizes=np.bincount(c.ravel());keep=sizes>=479;keep[0]=False;c=np.where(keep[c],c,0).astype('int32')
  d=instances(ch,dict(model='UNET_DIST3',threshold=.5));fl=instances(flip,dict(model='UNET_DIST3',threshold=.5));parent={int(i):int(i) for i in np.unique(d) if i}
  def find(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  # Group fragments only on non-GOLD with conjunction of separation/shape evidence.
  for a,b in adjacent(d):
   ma=d==a;mb=d==b;contact=(ndimage.binary_dilation(ma,CROSS)&mb)|(ndimage.binary_dilation(mb,CROSS)&ma)
   if int(contact.sum())<2:continue
   ca,aa,oa,_=stats(ma);cb,ab,ob,_=stats(mb);cc,_,_,_=stats(ma|mb);delta=abs(oa-ob);delta=min(delta,180-delta)
   same=dominant_c6(ma,c);passed=bool(same and same==dominant_c6(mb,c) and ch[2][contact].mean()<.25 and ch[0][contact].mean()>.8 and (delta<=20 or (aa<1.3 and ab<1.3)) and cc>=.6*min(ca,cb))
   if passed and find(a)!=find(b):parent[find(b)]=find(a);summary['fragment_pairs_merged']+=1;actions.append(dict(patch_id=pid,action='FRAGMENT_CANDIDATE_MERGED',source_ids=f'{a};{b}',evidence=f"contact={contact.sum()},boundary={ch[2][contact].mean():.4f},orientation_delta={delta:.2f}"))
  remap=np.arange(int(d.max())+1)
  for i in parent:remap[i]=find(i)
  d=remap[d].astype('int32')
  # Split a DIST3 unit only when separate C6 cores AND internal boundary evidence exist.
  for label in list(np.unique(d[d>0])):
   mask=d==label;z=np.bincount(c[mask]);ids=np.flatnonzero(z>=20);ids=ids[ids>0];inside=ndimage.binary_erosion(mask,np.ones((3,3),bool))
   if len(ids)<2 or not inside.any() or float((ch[2][inside]>=.35).mean())<.01:continue
   seeds=np.where(mask&np.isin(c,ids),c,0).astype('int32')
   from skimage.segmentation import watershed
   split=watershed(ch[2],markers=seeds,mask=mask);children=[]
   if any(int((split==k).sum())<4 for k in ids):continue
   maximum=int(d.max())
   for offset,k in enumerate(ids,1):d[split==k]=maximum+offset;children.append(maximum+offset)
   summary['merged_objects_split']+=1;actions.append(dict(patch_id=pid,action='SPLIT_IF_BOUNDARY_EVIDENCE',source_ids=str(label),evidence='C6_CORES_'+str(ids.tolist())+';children='+str(children)))
  pred,_,_=polygonize(d,rgbpath,0.);candidates=[];used_c6=set();grey=rgb.astype('float32').mean(axis=2);texture=float(grey.std());c6multiplicity=Counter()
  for q in pred:
   mask=d==q['label']
   for cl in np.unique(c[mask]):
    if cl:c6multiplicity[int(cl)]+=1
  for q in pred:
   mask=d==q['label'];npx=int(mask.sum());area=q['geometry'].area;confidence=float(ch[0][mask].mean());compact,aspect,angle,edge=stats(mask);cm=float(c6[mask].mean());bg=float((c6[mask]<.05).mean());fids,intersection=np.unique(fl[mask],return_counts=True);stable=0.
   for k,inter in zip(fids,intersection):
    if k:stable=max(stable,float(inter/(npx+int((fl==k).sum())-inter)))
   spatial=[]
   for cl in np.unique(c[mask]):
    if cl:
     inter=int((mask&(c==cl)).sum());iou=inter/(npx+int((c==cl).sum())-inter);spatial.append((int(cl),inter/npx,iou))
   association=[a for a in spatial if a[1]>=.6 or a[2]>=.3];context=r['primary_group']=='FP_CONTEXT';shape_penalty=min(1.,max(0.,(.25-compact)/.25)+max(0.,aspect-4)/8);flat=float(grey[mask].std()<10);fp_score=min(1.,.3*(1-confidence)+.25*(1-stable)+.2*shape_penalty+.15*bg+.1*flat+.15*context)
   typ='TYPE_A_CONSENSUS' if association else 'TYPE_D_CONFLICT' if spatial else 'TYPE_B_DIST3_ONLY';accept=False;kind='UNCERTAIN';reason='GEOMETRIC_CONFLICT' if spatial else 'INSUFFICIENT_FILTER_EVIDENCE';chosen=mask;geometry_source='DIST3_INSTANCE'
   if typ=='TYPE_A_CONSENSUS':
    accept=True;kind='HIGH_CONFIDENCE_CONSENSUS';reason='C6_AND_DIST3_SPATIAL_SUPPORT';used_c6.update(a[0] for a in association)
    if len(association)==1 and c6multiplicity[association[0][0]]==1:
     candidate=c==association[0][0];ccompact,_,_,cedge=stats(candidate);dq=.4*float(ch[2][edge].mean())+.3*compact+.3*confidence;cq=.4*float(ch[2][cedge].mean())+.3*ccompact+.3*float(c6[candidate].mean())
     if cq>dq+.1:chosen=candidate;geometry_source='C6_BOUNDARY_QUALITY_PROXY'
   elif typ=='TYPE_B_DIST3_ONLY':
    plausible=area>=1 and compact>=.08 and aspect<=8;accept=bool(plausible and ((confidence>=.8 and stable>=.5) or (confidence>=.95 and stable>=.35)) and fp_score<.55)
    if accept:kind='HIGH_CONFIDENCE_DIST3_ONLY';reason='PLAUSIBLE_SHAPE_CONFIDENCE_FLIP_CONSISTENCY'
    else:reason='DIST3_FP_REJECTION_SCORE_OR_GEOMETRY';summary['dist3_candidates_rejected']+=1
   row=dict(patch_id=pid,source_object=int(q['label']),type=typ,label_class=kind,accepted=accept,confidence=confidence,augmentation_iou=stable,compactness=compact,aspect=aspect,area_m2=area,area_px=npx,c6_mean=cm,c6_associations=';'.join(str(a[0]) for a in association),DIST3_FP_REJECTION_SCORE=fp_score,context=r['primary_group'],road_distance='NOT_AVAILABLE',bare_soil_probability='NOT_AVAILABLE',geometry_source=geometry_source,reason=reason,split=r['split'],is_human_gt=False)
   rows.append(row)
   if area<=50:smallrows.append(row.copy())
   if accept:candidates.append((chosen,kind,row))
   else:summary['uncertain_excluded']+=1
  for cl in np.unique(c[c>0]):
   if int(cl) in used_c6:continue
   mask=c==cl
   if np.any(d[mask]>0):
    summary['uncertain_excluded']+=1;continue
   conf=float(c6[mask].mean());dm=float(ch[0][mask].mean());accept=conf>=.85 and dm>=.05
   row=dict(patch_id=pid,source_object='C6_'+str(cl),type='TYPE_C_C6_ONLY',label_class='HIGH_CONFIDENCE_C6_ONLY' if accept else 'UNCERTAIN',accepted=accept,confidence=conf,augmentation_iou=None,compactness=None,aspect=None,area_m2=None,area_px=int(mask.sum()),c6_mean=conf,c6_associations=str(cl),DIST3_FP_REJECTION_SCORE=None,context=r['primary_group'],road_distance='NOT_AVAILABLE',bare_soil_probability='NOT_AVAILABLE',geometry_source='C6_COMPONENT',reason='HIGH_C6_NO_STRONG_DIST3_BACKGROUND' if accept else 'LOW_C6_OR_STRONG_DIST3_BACKGROUND',split=r['split'],is_human_gt=False);rows.append(row)
   if accept:candidates.append((mask,'HIGH_CONFIDENCE_C6_ONLY',row))
   else:summary['uncertain_excluded']+=1
  labels=np.zeros((512,512),np.int32);weights=np.zeros((512,512),np.float32);background=(c6<.05)&(ch[0]<.05)&(flip[0]<.05);weights[background]=.7;summary['hard_negative_pixels']+=int(background.sum());applied={}
  priorities={'HIGH_CONFIDENCE_CONSENSUS':0,'HIGH_CONFIDENCE_DIST3_ONLY':1,'HIGH_CONFIDENCE_C6_ONLY':2}
  for n,(mask,kind,row) in enumerate(sorted(candidates,key=lambda x:priorities[x[1]]),1):
   mask=mask&(labels==0)
   if not mask.any():continue
   labels[mask]=n;value={'HIGH_CONFIDENCE_CONSENSUS':1.,'HIGH_CONFIDENCE_DIST3_ONLY':.6,'HIGH_CONFIDENCE_C6_ONLY':.75}[kind];weights[mask]=value*np.clip(200/int(mask.sum()),.25,4);applied[n]=row;summary[kind]+=1
  contacts=np.zeros(labels.shape,bool)
  for a,b,ca,cb in [(labels[:,:-1],labels[:,1:],contacts[:,:-1],contacts[:,1:]),(labels[:-1,:],labels[1:,:],contacts[:-1,:],contacts[1:,:])]:
   border=(a>0)&(b>0)&(a!=b);ca|=border;cb|=border
  labels[contacts]=0;weights[contacts]=1.;mask=labels>0;kind='train' if r['split']=='ACTIVE_LEARNING_TRAIN' else 'dev';np.savez_compressed(OUT/kind/(pid+'.npz'),mask=mask.astype('uint8'),weight=weights,instance_labels=labels)
  final,_,_=polygonize(labels,rgbpath,0.);features=[];im=Image.fromarray(rgb);dr=ImageDraw.Draw(im);size=Counter()
  for q in final:
   row=applied[q['label']];area=q['geometry'].area;size['SMALL' if area<=50 else 'MEDIUM' if area<=200 else 'LARGE']+=1;features.append(dict(type='Feature',geometry=mapping(q['geometry']),properties=dict(source='HYBRID_TEACHER_C6_DIST3_PSEUDO_NOT_GT',object_id=q['label'],type=row['type'],label_class=row['label_class'],confidence=row['confidence'],area_m2=area,used_train=kind=='train',geometry_source=row['geometry_source'])));draw_geom(dr,q['geometry'],tx,inv,'lime' if row['type']=='TYPE_A_CONSENSUS' else 'orange',1)
  im.save(OUT/'qa'/(pid+'_HYBRID_OVERLAY.png'));dump(OUT/'hybrid_teacher'/(pid+'_PSEUDO_OBJECTS.geojson'),dict(type='FeatureCollection',crs={'type':'name','properties':{'name':'EPSG:32637'}},features=features));save_tif(OUT/'hybrid_teacher'/(pid+'_PSEUDO_MASK.tif'),mask.astype('uint8'),rgbpath);save_tif(OUT/'hard_negatives'/(pid+'_BACKGROUND.tif'),background.astype('uint8'),rgbpath)
  summary[kind+'_objects']+=len(final);summary[kind+'_small']+=size['SMALL'];summary[kind+'_medium']+=size['MEDIUM'];summary[kind+'_large']+=size['LARGE'];patchrows.append(dict(patch_id=pid,split=r['split'],context=r['primary_group'],objects=len(final),small=size['SMALL'],medium=size['MEDIUM'],large=size['LARGE'],contact_gap_pixels=int(contacts.sum()),positive_weight=float(weights[mask].sum()),background_pixels=int(background.sum())));print('HYBRID_LABELS',pid,len(final),dict(size),flush=True)
  assert np.isfinite(weights).all() and set(np.unique(mask))<={False,True}
 csvwrite(OUT/'hybrid_teacher/object_decisions.csv',rows);csvwrite(OUT/'hybrid_teacher/patch_manifest.csv',patchrows)
 if actions:csvwrite(OUT/'hybrid_teacher/FRAGMENT_AND_SPLIT_ACTIONS.csv',actions)
 if smallrows:csvwrite(OUT/'small_candidates/HYBRID_SMALL_BUILDING_CANDIDATES.csv',smallrows)
 dump(OUT/'qa/HYBRID_SUMMARY.json',dict(counts=dict(summary),human_gt=False,road_and_bare_soil_maps_available=False,semantic_fp_rejections_confirmed=False,all_gold_sources_unused=True));print(json.dumps(dict(summary),indent=2))
if __name__=='__main__':main()
