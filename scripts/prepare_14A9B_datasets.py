"""Inventory RGB and prepare spatially isolated review data; no training/calibration."""
from pathlib import Path
import sys,json,csv,hashlib,math
from collections import Counter
import numpy as np
from osgeo import gdal
from shapely.geometry import box
from shapely.ops import unary_union
from pyproj import Transformer
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
AL=BASE/'14A9B_active_learning';DEV=BASE/'14A9B_dev_set';GOLD=BASE/'14A7_gold_set'
SOURCE=ROOT/'backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif'
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def csvwrite(p,rows):
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def bounds(ds,x=0,y=0):
 tr=ds.GetGeoTransform();w=h=512
 if x==y==0:w,h=ds.RasterXSize,ds.RasterYSize
 pts=[gdal.ApplyGeoTransform(tr,xx,yy) for xx,yy in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]]
 tx=Transformer.from_crs(ds.GetProjection(),'EPSG:32637',always_xy=True)
 q=[tx.transform(*p) for p in pts];return [min(p[0] for p in q),min(p[1] for p in q),max(p[0] for p in q),max(p[1] for p in q)]
def windowbounds(ds,x,y):
 tr=ds.GetGeoTransform();pts=[gdal.ApplyGeoTransform(tr,xx,yy) for xx,yy in [(x,y),(x+512,y),(x+512,y+512),(x,y+512)]]
 tx=Transformer.from_crs(ds.GetProjection(),'EPSG:32637',always_xy=True);q=[tx.transform(*p) for p in pts]
 return [min(p[0] for p in q),min(p[1] for p in q),max(p[0] for p in q),max(p[1] for p in q)]
def screen():
 for d in ['train_candidates','corrected_gt','manifests','qa','qgis']:(AL/d).mkdir(parents=True,exist_ok=True)
 for d in ['rgb','gt','masks','manifests','qa','qgis']:(DEV/d).mkdir(parents=True,exist_ok=True)
 goldhash={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()}
 dump(AL/'qa/GOLD_HASHES_BEFORE.json',goldhash)
 inv=[];seen={};blocks=[]
 roots=[ROOT/'backend/data/fine_tuning/buildings',ROOT/'test-data']
 for root in roots:
  for p in sorted(root.rglob('*.tif')):
   if AL in p.parents or DEV in p.parents:continue
   ds=gdal.Open(str(p))
   if not ds or ds.RasterCount<3 or max(ds.RasterXSize,ds.RasterYSize)>1024:continue
   path=p.relative_to(ROOT).as_posix();pid=p.stem
   try:
    a=ds.ReadAsArray()[:3];b=bounds(ds);assert np.isfinite(b).all() and b[0]<b[2] and b[1]<b[3]
    assert a.shape[1:]==(ds.RasterYSize,ds.RasterXSize)
    pixelhash=hashlib.sha256(a.tobytes()).hexdigest();duplicate=seen.get(pixelhash,'');seen.setdefault(pixelhash,path)
    lower=path.lower()
    status='GOLD_LOCKED' if GOLD in p.parents else 'TEST_LOCKED' if any(s in lower for s in ['test','benchmark','validation_expansion']) else 'TRAIN' if '/train/' in lower else 'VAL' if '/val/' in lower else 'AMBIGUOUS_EXCLUDED'
    rec=dict(patch_id=pid,rgb_path=path,width=ds.RasterXSize,height=ds.RasterYSize,bands=ds.RasterCount,readable=True,sha256=sha(p),pixel_sha256=pixelhash,duplicate_of=duplicate,bounds_32637=b,historical_train_status=status,
      scene_type='UNKNOWN',small_buildings_expected='UNREVIEWED',dense='UNREVIEWED',shadow='UNREVIEWED',adjacent_roofs='UNREVIEWED',bare_soil='UNREVIEWED',industrial='UNREVIEWED',eligible_active_learning='NO',reason='HISTORICAL_SOURCE_PROTECTED;NEW_BATCH_USES_NEW_WINDOWS')
    blocks.append(dict(path=path,bounds_32637=b,status=status));inv.append(rec)
   except Exception as e:
    inv.append(dict(patch_id=pid,rgb_path=path,readable=False,error=str(e),eligible_active_learning='NO'))
   ds=None
 old=json.loads((BASE/'14A7_validation_expansion/qa/14A7A_protected_footprints.json').read_text())['footprints']
 blocks.extend(dict(path=r['source'],bounds_32637=r['bounds_32637'],status='HISTORICAL_DECLARED') for r in old)
 dump(AL/'qa/14A9B_all_rgb_inventory.json',inv)
 dump(AL/'qa/14A9B_protected_footprints.json',dict(buffer_m=20,footprints=blocks))
 protected=unary_union([box(*b['bounds_32637']) for b in blocks]);safe=protected.buffer(20)
 ds=gdal.Open(str(SOURCE));candidates=[];reject=Counter()
 for row in range(0,ds.RasterYSize-511,256):
  for col in range(0,ds.RasterXSize-511,256):
   b=windowbounds(ds,col,row);g=box(*b)
   if g.intersects(safe):reject['PROTECTED_OR_20M_MARGIN']+=1;continue
   a=ds.ReadAsArray(col,row,512,512)[:3]
   if a.shape!=(3,512,512) or np.mean(np.any(a!=0,axis=0))<.98:reject['NODATA']+=1;continue
   grey=a.mean(axis=0);texture=float((abs(np.diff(grey,axis=0)).mean()+abs(np.diff(grey,axis=1)).mean())/2)
   candidates.append(dict(index=len(candidates)+1,key=f'R{row:05d}_C{col:05d}',row=row,col=col,bounds_32637=b,texture=texture,dark_fraction=float((grey<40).mean()),pixel_sha256=hashlib.sha256(a.tobytes()).hexdigest(),min_distance_historical_m=g.distance(protected)))
 dump(AL/'qa/14A9B_fresh_window_screen.json',dict(source=str(SOURCE.relative_to(ROOT)),candidates=candidates,rejected=dict(reject),inventory_rgb=len(inv),policy='All old RGB footprints protected including ambiguous sources. Same parent acquisition; spatial internal development only.'))
 for start in range(0,len(candidates),42):
  subset=candidates[start:start+42];sheet=Image.new('RGB',(7*160,math.ceil(len(subset)/7)*185),'white');d=ImageDraw.Draw(sheet)
  for i,c in enumerate(subset):
   a=ds.ReadAsArray(c['col'],c['row'],512,512)[:3];x=i%7*160;y=i//7*185
   sheet.paste(Image.fromarray(np.moveaxis(a,0,-1)).resize((160,160)),(x,y));d.text((x+2,y+162),f"{c['index']} {c['key']}",fill='black',font=FONT)
  sheet.save(AL/'qa'/f'FRESH_SCREEN_{start//42+1}.png')
 print(json.dumps(dict(inventory_rgb=len(inv),fresh_candidates=len(candidates),rejected=dict(reject))))
def materialize():
 pool=json.loads((AL/'qa/14A9B_fresh_window_screen.json').read_text())['candidates']
 # RGB inspection of all five screening sheets; exclusive primary review quotas.
 selection=[(4,'ACTIVE_LEARNING_TRAIN','SMALL','RESIDENTIAL','Small varied roofs and narrow shadowed gaps'),
 (19,'ACTIVE_LEARNING_TRAIN','SMALL','DENSE','Small irregular adjacent roofs'),
 (148,'ACTIVE_LEARNING_TRAIN','SMALL','RESIDENTIAL','Small roofs around road and bare ground'),
 (195,'ACTIVE_LEARNING_TRAIN','SMALL','DENSE','Very small tightly packed roofs'),
 (139,'ACTIVE_LEARNING_TRAIN','DENSE_ADJACENT','DENSE','Adjacent residential roof boundaries'),
 (172,'ACTIVE_LEARNING_TRAIN','DENSE_ADJACENT','DENSE','Dense varied roof sizes'),
 (158,'ACTIVE_LEARNING_TRAIN','SHADOW_LOW_CONTRAST','RESIDENTIAL','Roof/shadow interfaces and dark narrow gaps'),
 (182,'ACTIVE_LEARNING_TRAIN','SHADOW_LOW_CONTRAST','RESIDENTIAL','Low contrast roof/ground and shadow interfaces'),
 (45,'ACTIVE_LEARNING_TRAIN','FP_CONTEXT','ROAD','Road and bare ground hard-negative context'),
 (77,'ACTIVE_LEARNING_TRAIN','FP_CONTEXT','BARE_SOIL','Bare rocky ground hard-negative context'),
 (11,'DEV_CALIBRATION','DEV_DENSE','DENSE','Dense small roofs and curved road'),
 (143,'DEV_CALIBRATION','DEV_RESIDENTIAL','RESIDENTIAL','Mixed roofs and road'),
 (167,'DEV_CALIBRATION','DEV_SHADOW','RESIDENTIAL','Small roofs beside rocky ground with shadows'),
 (206,'DEV_CALIBRATION','DEV_MIXED','RESIDENTIAL','Sparse small roofs, shadows and exposed soil')]
 blocks=json.loads((AL/'qa/14A9B_protected_footprints.json').read_text())['footprints'];protected=unary_union([box(*b['bounds_32637']) for b in blocks])
 rows=[];geoms=[];ds=gdal.Open(str(SOURCE))
 for num,(idx,split,group,scene,note) in enumerate(selection,1):
  c=next(c for c in pool if c['index']==idx);g=box(*c['bounds_32637']);assert g.distance(protected)>20
  assert all(g.distance(q)>20 for q in geoms),(idx,'OVERLAP');geoms.append(g)
  pid=f"14A9B_{'AL' if split=='ACTIVE_LEARNING_TRAIN' else 'DEV'}_{num:02d}_{c['key']}"
  target=(AL/'train_candidates' if split=='ACTIVE_LEARNING_TRAIN' else DEV/'rgb')/(pid+'.tif')
  if target.exists():raise RuntimeError('Refuse overwriting dataset RGB: '+str(target))
  d=gdal.Translate(str(target),ds,format='GTiff',srcWin=[c['col'],c['row'],512,512],bandList=[1,2,3],creationOptions=['COMPRESS=DEFLATE']);assert d
  a=d.ReadAsArray();assert np.array_equal(a,ds.ReadAsArray(c['col'],c['row'],512,512)[:3]);d=None
  rows.append(dict(**c,patch_id=pid,split=split,primary_group=group,scene_type=scene,observation=note,rgb_path=str(target.relative_to(ROOT)),rgb_sha256=sha(target),
   source=str(SOURCE.relative_to(ROOT)),source_sha256='',historical_train_status='NEVER_USED_NEW_WINDOW',used_train='NO',used_dev='NO',used_gold='NO',human_gt_status='PENDING_HUMAN_CORRECTION',
   small_buildings_expected='YES' if group in ['SMALL','DENSE_ADJACENT'] or 'DEV' in group else 'POSSIBLE' if scene=='RESIDENTIAL' else 'NO_EXPECTED',
   dense='YES' if scene=='DENSE' else 'NO',shadow='YES' if group=='SHADOW_LOW_CONTRAST' or group=='DEV_SHADOW' else 'POSSIBLE',adjacent_roofs='YES' if scene=='DENSE' else 'POSSIBLE',bare_soil='YES' if scene in ['ROAD','BARE_SOIL'] else 'POSSIBLE',industrial='NO_CONFIRMED'))
 sourcehash=sha(SOURCE)
 for r in rows:r['source_sha256']=sourcehash
 dump(AL/'manifests/14A9B_selected_patches.json',rows)
 # Audited historical RGB records and spatially eligible new windows are separate origins.
 inv=json.loads((AL/'qa/14A9B_all_rgb_inventory.json').read_text());table=[]
 for r in inv:
  eligible=r.get('historical_train_status')=='TRAIN' and not r.get('duplicate_of')
  table.append(dict(patch_id=r['patch_id'],scene_type=r.get('scene_type','UNKNOWN'),small_buildings_expected=r.get('small_buildings_expected','UNKNOWN'),dense=r.get('dense','UNKNOWN'),shadow=r.get('shadow','UNKNOWN'),adjacent_roofs=r.get('adjacent_roofs','UNKNOWN'),bare_soil=r.get('bare_soil','UNKNOWN'),industrial=r.get('industrial','UNKNOWN'),historical_train_status=r.get('historical_train_status','AMBIGUOUS_EXCLUDED'),eligible_active_learning='YES_RE_REVIEW_ONLY' if eligible else 'NO',rgb_path=r['rgb_path'],origin='HISTORICAL_RGB',selected='NO',reason='STRICT_DUPLICATE' if r.get('duplicate_of') else r.get('reason','CORRUPT')))
 for c in pool:
  s=next((r for r in rows if r['index']==c['index']),None)
  table.append(dict(patch_id=s['patch_id'] if s else 'NEW_'+c['key'],scene_type=s['scene_type'] if s else 'UNREVIEWED',small_buildings_expected=s['small_buildings_expected'] if s else 'UNREVIEWED',dense=s['dense'] if s else 'UNREVIEWED',shadow=s['shadow'] if s else 'UNREVIEWED',adjacent_roofs=s['adjacent_roofs'] if s else 'UNREVIEWED',bare_soil=s['bare_soil'] if s else 'UNREVIEWED',industrial=s['industrial'] if s else 'UNREVIEWED',historical_train_status='NEVER_USED_NEW_WINDOW',eligible_active_learning='NO_RESERVED_DEV' if s and s['split']=='DEV_CALIBRATION' else 'YES',rgb_path=s['rgb_path'] if s else '',origin='FRESH_WINDOW_SCREEN',selected=s['split'] if s else 'NO',reason='SPATIALLY_SCREENED_NOT_ALL_WINDOWS_MUTUALLY_DISJOINT'))
 csvwrite(AL/'manifests/14A9B_active_learning_candidates.csv',table)
 csvwrite(DEV/'manifests/14A9B_dev_set_manifest.csv',[dict(patch_id=r['patch_id'],source=r['rgb_path'],used_train='NO',used_dev='YES_RESERVED_NOT_CALIBRATED',used_gold='NO',eligible='PENDING_HUMAN_GT',rgb_sha256=r['rgb_sha256'],split=r['split']) for r in rows if r['split']=='DEV_CALIBRATION'])
 dump(AL/'qa/14A9B_split_lock.json',dict(train=[r['patch_id'] for r in rows if r['split']=='ACTIVE_LEARNING_TRAIN'],dev=[r['patch_id'] for r in rows if r['split']=='DEV_CALIBRATION'],train_dev_overlap=0,gold_overlap=0,all_old_crop_overlap=0,minimum_separation_m=20,policy='No reassignment; same parent acquisition, spatial internal development only. GT pending; never train directly on preannotations.'))
 print('MATERIALIZED',len(rows),'TRAIN',10,'DEV',4)
if __name__=='__main__':
 materialize() if '--materialize' in sys.argv else screen()
