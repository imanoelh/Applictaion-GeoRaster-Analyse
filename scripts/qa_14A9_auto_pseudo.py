"""Technical pseudo-label QA, separate from claims of semantic correctness."""
from pathlib import Path
import sys,json,csv
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9_auto import ROOT,OUT,sha,dump
from osgeo import gdal
from shapely.geometry import shape,box
from shapely.ops import transform as gt
from pyproj import Transformer
import numpy as np
def main():
 p=json.loads((OUT/'protocol.json').read_text());summary=Counter();patches=[]
 for r in p['records']:
  pid=r['patch_id'];rgb=gdal.Open(str(ROOT/r['rgb_path']));maskds=gdal.Open(str(OUT/'pseudo_labels'/(pid+'_PSEUDO_MASK.tif')));assert maskds.GetGeoTransform()==rgb.GetGeoTransform() and maskds.GetProjection()==rgb.GetProjection();assert (maskds.RasterXSize,maskds.RasterYSize)==(512,512)
  kind='auto_train' if r['split']=='ACTIVE_LEARNING_TRAIN' else 'auto_dev'
  with np.load(OUT/kind/(pid+'.npz')) as f:mask=f['mask'];weight=f['weight']
  assert set(np.unique(mask))<={0,1} and np.isfinite(weight).all() and np.array_equal(mask,maskds.ReadAsArray())
  with np.load(OUT/'consensus'/(pid+'.npz')) as f:tier=f['tier']
  assert np.all(weight[tier==3]==0)
  summary['A_positive_pixels']+=int((tier==1).sum());summary['B_positive_pixels']+=int((tier==2).sum());summary['ignored_pixels']+=int((tier==3).sum());summary['D_background_pixels']+=int((tier==4).sum())
  inv=gdal.InvGeoTransform(rgb.GetGeoTransform());tx=Transformer.from_crs('EPSG:32637',rgb.GetProjection(),always_xy=True)
  def coords(x,y,z=None):
   x,y=tx.transform(x,y);x=np.asarray(x);y=np.asarray(y);return inv[0]+inv[1]*x+inv[2]*y,inv[3]+inv[4]*x+inv[5]*y
  features=json.loads((OUT/'pseudo_labels'/(pid+'_PSEUDO_OBJECTS.geojson')).read_text())['features'];seen=set()
  for f in features:
   g=shape(f['geometry']);assert g.is_valid and not g.is_empty and g.area>0 and box(0,0,512,512).buffer(1e-6).covers(gt(coords,g));assert g.normalize().wkb not in seen;seen.add(g.normalize().wkb)
   summary['objects']+=1;summary['tiny_lt4px']+=int(f['properties']['area_px']<4)
  patches.append(dict(patch_id=pid,geometry_valid=True,oob=0,duplicates=0,grid_alignment='PASS',objects=len(features)))
 dump(OUT/'qa/PSEUDO_TECHNICAL_QA.json',dict(counts=dict(summary),patches=patches,semantic_correctness='NOT_HUMAN_VALIDATED',all_checks_pass=True))
 print(json.dumps(dict(summary)))
if __name__=='__main__':main()
