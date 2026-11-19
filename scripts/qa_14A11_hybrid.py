"""Read-only source and native-grid QA for the experimental hybrid labels."""
from pathlib import Path
import sys,json,csv
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,OUT,sha,dump
from osgeo import gdal
from shapely.geometry import shape,box
from shapely.ops import transform
from pyproj import Transformer
from scipy import ndimage
from score_14A10_models import instances
import numpy as np

def main():
 p=json.loads((OUT/'protocol.json').read_text());rows=[];counts=Counter();conflicts=[]
 decisions=list(csv.DictReader((OUT/'hybrid_teacher/object_decisions.csv').open(encoding='utf-8-sig')))
 for r in p['records']:
  pid=r['patch_id'];assert sha(ROOT/r['rgb_path'])==r['rgb_sha256'];rgb=gdal.Open(str(ROOT/r['rgb_path']));ds=gdal.Open(str(OUT/'hybrid_teacher'/(pid+'_PSEUDO_MASK.tif')))
  assert ds.GetGeoTransform()==rgb.GetGeoTransform() and ds.GetProjection()==rgb.GetProjection();assert (ds.RasterXSize,ds.RasterYSize)==(512,512)
  kind='train' if r['split']=='ACTIVE_LEARNING_TRAIN' else 'dev'
  with np.load(OUT/kind/(pid+'.npz')) as f:m=f['mask'];w=f['weight'];labels=f['instance_labels']
  with np.load(OUT/'teacher_predictions'/(pid+'.npz')) as f:
   for name,expected_shape in [('c6',(512,512)),('dist3',(3,512,512)),('dist3_flip',(3,512,512))]:
    a=f[name];assert a.shape==expected_shape and np.isfinite(a).all() and a.min()>=0 and a.max()<=1
   c6=f['c6'];d=instances(f['dist3'],dict(model='UNET_DIST3',threshold=.5))
   c,_=ndimage.label(c6>=.3,ndimage.generate_binary_structure(2,1));sizes=np.bincount(c.ravel());keep=sizes>=479;keep[0]=False;c=np.where(keep[c],c,0)
   used={int(k) for row in decisions if row['patch_id']==pid and row['type']=='TYPE_A_CONSENSUS' for k in row['c6_associations'].split(';') if k}
   for k in np.unique(c[c>0]):
    if int(k) not in used and np.any(d[c==k]>0):conflicts.append(dict(patch_id=pid,source_object='C6_'+str(k),type='TYPE_D_CONFLICT',label_class='UNCERTAIN',accepted=False,area_px=int((c==k).sum()),reason='C6_UNASSIGNED_OVERLAPS_DIST3_CONFLICT',used_train=False))
  assert m.shape==w.shape==labels.shape==(512,512);assert set(np.unique(m))<={0,1};assert np.array_equal(m,ds.ReadAsArray()) and np.array_equal(m,labels>0);assert np.isfinite(w).all() and (w>=0).all() and w.sum()>0 and m.any();assert (w[m>0]>0).all()
  inv=gdal.InvGeoTransform(rgb.GetGeoTransform());tx=Transformer.from_crs('EPSG:32637',rgb.GetProjection(),always_xy=True)
  def coords(x,y,z=None):
   x,y=tx.transform(x,y);x=np.asarray(x);y=np.asarray(y);return inv[0]+inv[1]*x+inv[2]*y,inv[3]+inv[4]*x+inv[5]*y
  fs=json.loads((OUT/'hybrid_teacher'/(pid+'_PSEUDO_OBJECTS.geojson')).read_text())['features'];seen=set()
  for f in fs:
   g=shape(f['geometry']);assert g.geom_type in ['Polygon','MultiPolygon'] and g.is_valid and not g.is_empty and g.area>0;assert box(0,0,512,512).buffer(1e-6).covers(transform(coords,g));assert g.normalize().wkb not in seen;seen.add(g.normalize().wkb);counts[f['properties']['label_class']]+=1
  counts['objects']+=len(fs);counts['ignored_pixels']+=int((w==0).sum());rows.append(dict(patch_id=pid,objects=len(fs),alignment='PASS',invalid=0,oob=0,duplicates=0))
 assert all(sha(ROOT/k)==v for k,v in json.loads((OUT/'qa/GOLD_BEFORE.json').read_text()).items())
 from prepare_14A11_hybrid import csvwrite
 if conflicts:csvwrite(OUT/'hybrid_teacher/C6_CONFLICT_EXCLUSIONS.csv',conflicts)
 excluded=sum(row['accepted']=='False' for row in decisions)+len(conflicts);assert excluded==json.loads((OUT/'qa/HYBRID_SUMMARY.json').read_text())['counts']['uncertain_excluded'];counts['excluded_proposals_audited']=excluded
 dump(OUT/'qa/PSEUDO_TECHNICAL_QA.json',dict(all_checks_pass=True,patches=rows,counts=dict(counts),semantic_correctness='PSEUDO_NOT_HUMAN_VALIDATED'))
 print('PSEUDO_QA_PASS',dict(counts),flush=True)
if __name__=='__main__':main()
