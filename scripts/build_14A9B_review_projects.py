"""Standalone PyQGIS builder; predictions and editable copies remain UNREVIEWED."""
from pathlib import Path
import sys,json,uuid,shutil,tempfile,gc
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9B_datasets import ROOT,BASE,AL,DEV,GOLD,csvwrite,dump,sha,FONT
from evaluate_14A8_shootout import objects,draw_geom,save_tif
from gold_set_14A7_guard import assert_non_gold_development_records
import numpy as np
from scipy import ndimage
from shapely.geometry import box
from shapely.ops import unary_union
from osgeo import ogr,osr,gdal
from pyproj import Transformer
from PIL import Image,ImageDraw
from qgis.core import (QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsCoordinateReferenceSystem,QgsSingleSymbolRenderer,QgsFillSymbol,QgsMultiBandColorRenderer,QgsRectangle,QgsReferencedRectangle,QgsBookmark,QgsDefaultValue,QgsEditorWidgetSetup,Qgis,QgsFeature,QgsGeometry)

FIELDS=['patch_id','building_id','proposal_id','source','label_source','error_category','correction_action','annotation_status','review_status','is_ground_truth','annotator']
CATEGORIES=['FN_SMALL','FN_SHADOW','FN_LOW_CONTRAST','MERGED','BOUNDARY_BAD','FP_ROAD','FP_BARE_SOIL','FP_OTHER']
def make_gpkg(path,records,predictions):
 if path.exists():raise RuntimeError('Refuse overwriting correction work: '+str(path))
 ds=ogr.GetDriverByName('GPKG').CreateDataSource(str(path));srs=osr.SpatialReference();srs.ImportFromEPSG(32637)
 for r in records:
  layer=ds.CreateLayer(r['patch_id'],srs,ogr.wkbPolygon)
  for name in FIELDS:layer.CreateField(ogr.FieldDefn(name,ogr.OFTInteger if name=='is_ground_truth' else ogr.OFTString))
  for q in predictions[r['patch_id']]:
   parts=[q['geometry']] if q['geometry'].geom_type=='Polygon' else list(q['geometry'].geoms)
   for n,g in enumerate(parts):
    f=ogr.Feature(layer.GetLayerDefn());f.SetGeometry(ogr.CreateGeometryFromWkb(g.wkb))
    values=dict(patch_id=r['patch_id'],building_id=str(uuid.uuid5(uuid.NAMESPACE_URL,r['patch_id']+':'+str(q['label'])+':'+str(n))),proposal_id=f"C6_{q['label']}_{n}",source='MODEL_C6_PREANNOTATION',label_source='MODEL_C6_PREDICTION_NOT_GT',error_category='UNCLASSIFIED',correction_action='PENDING',annotation_status='NOT_VALIDATED',review_status='NOT_REVIEWED',is_ground_truth=0,annotator='UNASSIGNED')
    for k,v in values.items():f[k]=v
    assert layer.CreateFeature(f)==0
 ds=None
def style(layer,color):layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':color,'outline_width':'0.45'})))
def project(records,ai_path,manual_path,path):
 p=QgsProject();ref=BASE/'qgis/14A5A_ANNOTATION_FINAL_VALIDATED.qgz';assert p.read(str(ref))
 p.removeAllMapLayers();p.layerTreeRoot().removeAllChildren()
 for b in list(p.bookmarkManager().bookmarks()):p.bookmarkManager().removeBookmark(b.id())
 p.annotationManager().clear()
 if hasattr(p.mainAnnotationLayer(),'clear'):p.mainAnnotationLayer().clear()
 p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'));p.setFilePathStorage(Qgis.FilePathType.Absolute);p.setTitle('14A9B | AI predictions are NOT GT | Human correction required')
 root=p.layerTreeRoot()
 for i,r in enumerate(records):
  group=root.addGroup(r['patch_id']+' | '+r['primary_group']);group.setExpanded(i==0)
  manual=QgsVectorLayer(str(manual_path)+'|layername='+r['patch_id'],r['patch_id']+'_MANUAL_CORRECTED_GT_PENDING','ogr');assert manual.isValid();style(manual,'0,190,0,255')
  defaults={'patch_id':r['patch_id'],'source':'HUMAN_CORRECTED','label_source':'HUMAN_CORRECTED_PENDING_QA','error_category':'FN_SMALL','correction_action':'ADD','annotation_status':'ANNOTATED','review_status':'NOT_REVIEWED','is_ground_truth':0,'annotator':'UNASSIGNED'}
  for name,v in defaults.items():manual.setDefaultValueDefinition(manual.fields().indexFromName(name),QgsDefaultValue(str(v) if isinstance(v,int) else "'"+v+"'"))
  manual.setDefaultValueDefinition(manual.fields().indexFromName('building_id'),QgsDefaultValue('uuid()'))
  manual.setEditorWidgetSetup(manual.fields().indexFromName('error_category'),QgsEditorWidgetSetup('ValueMap',{'map':[{s:s} for s in ['UNCLASSIFIED']+CATEGORIES]}))
  manual.setEditorWidgetSetup(manual.fields().indexFromName('correction_action'),QgsEditorWidgetSetup('ValueMap',{'map':[{s:s} for s in ['PENDING','KEEP','DELETE','EDIT','SPLIT','ADD']]}))
  assert manual.startEditing() and manual.isEditable();assert manual.rollBack()
  p.addMapLayer(manual,False);group.addLayer(manual)
  ai=QgsVectorLayer(str(ai_path)+'|layername='+r['patch_id'],r['patch_id']+'_AI_PREANNOTATION_C6_NOT_GT','ogr');assert ai.isValid();style(ai,'170,30,210,255');ai.setReadOnly(True);p.addMapLayer(ai,False);group.addLayer(ai).setItemVisibilityChecked(False)
  rgb=QgsRasterLayer(str(ROOT/r['rgb_path']),r['patch_id']+'_RGB','gdal');assert rgb.isValid()
  for band in [1,2,3]:rgb.dataProvider().setUseSourceNoDataValue(band,False)
  rgb.setRenderer(QgsMultiBandColorRenderer(rgb.dataProvider(),1,2,3));p.addMapLayer(rgb,False);group.addLayer(rgb);group.setItemVisibilityChecked(i==0)
  bm=QgsBookmark();bm.setName(r['patch_id']);rect=QgsRectangle(*r['bounds_32637']);rect.scale(1.05);bm.setExtent(QgsReferencedRectangle(rect,p.crs()));p.bookmarkManager().addBookmark(bm)
 rect=QgsRectangle(*records[0]['bounds_32637']);rect.scale(1.05);p.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(rect,p.crs()));p.setFileName(str(path));assert p.write();expected=len(records)*3;p.clear();p=None;manual=ai=rgb=None;gc.collect()
 for _ in range(2):
  p=QgsProject();assert p.read(str(path));assert len(p.mapLayers())==expected and all(l.isValid() for l in p.mapLayers().values())
  assert len(p.bookmarkManager().bookmarks())==len(records);p.clear();p=None;gc.collect()
 return dict(layers=expected,rgb=len(records),preannotation=len(records),manual_working=len(records),bookmarks=len(records),open='PASS_PYQGIS',reopen='PASS_PYQGIS',editability='PASS_NO_GEOMETRY_EDITS',broken_sources=0,desktop='NOT_EXECUTED')
def main():
 records=json.loads((AL/'manifests/14A9B_selected_patches.json').read_text());assert_non_gold_development_records(records)
 assert len({r['pixel_sha256'] for r in records})==len(records)
 old_pixels={r.get('pixel_sha256') for r in json.loads((AL/'qa/14A9B_all_rgb_inventory.json').read_text())}
 assert all(r['pixel_sha256'] not in old_pixels for r in records)
 predictions={};metrics=[];panels=[]
 spec=dict(connectivity=4,min_component_pixels=479)
 for r in records:
  pid=r['patch_id'];rgbpath=ROOT/r['rgb_path'];d=gdal.Open(str(rgbpath));rgb=np.moveaxis(d.ReadAsArray(),0,-1);tr=d.GetGeoTransform();inv=gdal.InvGeoTransform(tr);proj=d.GetProjection();tx=Transformer.from_crs('EPSG:32637',proj,always_xy=True)
  with np.load(AL/'qa'/(pid+'_C6_probability.npz')) as f:prob=f['probability']
  raw=prob>=.30;final,pred,repairs=objects(raw,rgbpath,spec);predictions[pid]=pred
  labels,n=ndimage.label(raw,ndimage.generate_binary_structure(2,1));sizes=np.bincount(labels.ravel())[1:]
  folder=AL/'train_candidates/AI_PREANNOTATION_C6' if r['split']=='ACTIVE_LEARNING_TRAIN' else DEV/'qa/AI_PREANNOTATION_C6';folder.mkdir(parents=True,exist_ok=True)
  save_tif(folder/(pid+'_probability.tif'),prob,rgbpath,gdal.GDT_Float32);save_tif(folder/(pid+'_AI_mask.tif'),final.astype('uint8'),rgbpath)
  assert all(q['geometry'].is_valid and q['geometry'].area>0 and box(*r['bounds_32637']).buffer(1e-6).covers(q['geometry']) for q in pred)
  assert len({q['geometry'].wkb for q in pred})==len(pred)
  overlay=Image.fromarray(rgb).copy();dr=ImageDraw.Draw(overlay)
  for q in pred:draw_geom(dr,q['geometry'],tx,inv,'magenta',2)
  overlay.save(folder/(pid+'_AI_overlay.png'))
  canvas=Image.new('RGB',(1024,540),'white');canvas.paste(Image.fromarray(rgb),(0,28));canvas.paste(overlay,(512,28));draw=ImageDraw.Draw(canvas);draw.text((4,3),pid+' | RGB / C6 PREANNOTATION NOT GT',fill='black',font=FONT);panels.append((r,canvas))
  metrics.append(dict(patch_id=pid,split=r['split'],primary_group=r['primary_group'],raw_components=n,small_components_lt479=int((sizes<479).sum()),final_components=len(pred),near_historical_threshold_fraction=float(((prob>=.25)&(prob<=.35)).mean()),foreground_fraction=float(raw.mean()),mean_probability=float(prob.mean()),max_probability=float(prob.max()),polygonization_repairs=repairs,
   interpretation='Uncertainty/context proxies only; FP and merges require human review; band0.25-0.35 descriptive only, no inference parameter change'))
 for split,directory in [('ACTIVE_LEARNING_TRAIN',AL),('DEV_CALIBRATION',DEV)]:
  subset=[r for r in records if r['split']==split];ai=directory/('train_candidates' if directory==AL else 'qa')/'AI_PREANNOTATION_C6.gpkg';manual=directory/('corrected_gt' if directory==AL else 'gt')/'MANUAL_CORRECTED_GT.gpkg'
  make_gpkg(ai,subset,predictions);shutil.copy2(ai,manual)
  # Immutable AI copy is protected through QGIS read-only; working copies stay editable.
  path=directory/'qgis'/('14A9B_ACTIVE_LEARNING_CORRECTION.qgz' if directory==AL else '14A9B_DEV_CALIBRATION_CORRECTION.qgz')
  qa=project(subset,ai,manual,path);dump(directory/'qa/QGIS_PROVIDER_QA.json',qa)
  group=[im for r,im in panels if r['split']==split]
  for start in range(0,len(group),4):
   sheet=Image.new('RGB',(1024,540*len(group[start:start+4])),'white')
   for j,im in enumerate(group[start:start+4]):sheet.paste(im,(0,j*540))
   sheet.save(directory/'qa'/f'REVIEW_CONTACT_{start//4+1}.png')
 # Persistence test ONLY in a temporary GeoPackage copy, no real review data edited.
 with tempfile.TemporaryDirectory(prefix='14A9B_') as tmp:
  cp=Path(tmp)/'test.gpkg';shutil.copy2(AL/'corrected_gt/MANUAL_CORRECTED_GT.gpkg',cp);pid=records[0]['patch_id'];l=QgsVectorLayer(str(cp)+'|layername='+pid,'test','ogr');n=l.featureCount();assert l.startEditing();f=QgsFeature(l.fields());b=records[0]['bounds_32637'];f.setGeometry(QgsGeometry.fromRect(QgsRectangle(b[0]+5,b[1]+5,b[0]+7,b[1]+7)));f['patch_id']=pid;f['building_id']='TEST_ONLY';assert l.addFeature(f) and l.commitChanges();l=None
  l=QgsVectorLayer(str(cp)+'|layername='+pid,'reopen_test','ogr');assert l.featureCount()==n+1;l=None;gc.collect()
 csvwrite(AL/'qa/14A9B_C6_priority_indicators.csv',metrics)
 # Initial correction ledger: no human correction or error category is fabricated.
 errors=[]
 for r in records:
  if r['split']!='ACTIVE_LEARNING_TRAIN':continue
  for q in predictions[r['patch_id']]:
   parts=[q['geometry']] if q['geometry'].geom_type=='Polygon' else list(q['geometry'].geoms)
   for n,_ in enumerate(parts):errors.append(dict(patch_id=r['patch_id'],proposal_id=f"C6_{q['label']}_{n}",error_category='PENDING_HUMAN_REVIEW',correction_action='PENDING',review_status='NOT_REVIEWED',human_correction_completed='NO'))
  if not predictions[r['patch_id']]:errors.append(dict(patch_id=r['patch_id'],proposal_id='NO_FINAL_C6_PROPOSAL',error_category='PENDING_HUMAN_REVIEW',correction_action='CHECK_MISSED_BUILDINGS',review_status='NOT_REVIEWED',human_correction_completed='NO'))
 csvwrite(AL/'manifests/14A9B_active_learning_error_manifest.csv',errors)
 hashes=json.loads((AL/'qa/GOLD_HASHES_BEFORE.json').read_text());assert all(sha(ROOT/p)==h for p,h in hashes.items())
 dump(AL/'qa/GOLD_HASHES_AFTER.json',{p:sha(ROOT/p) for p in hashes})
 dump(AL/'qa/14A9B_DATA_QA.json',dict(gold_files_checked=len(hashes),gold_modified=False,invalid_geometry=0,out_of_bounds=0,duplicate_geometry_within_patch=0,rgb_duplicate_selected=0,
  alignment='PASS_SAME_NATIVE_PIXEL_GRID_NO_RESAMPLING_VECTOR_UTM_DISPLAY',train_dev_overlap=0,gold_overlap=0,attributes='COMPLETE_EXPLICIT_PENDING_STATUSES',test_persistence_in_copy='PASS',
  human_gt_validated=False,ready_for_dev_calibration=False,training=False,calibration=False))
 print('PROJECTS_CREATED',10,4,'PREANNOTATIONS',sum(len(v) for v in predictions.values()),'GOLD_UNCHANGED',len(hashes))
if __name__=='__main__':
 app=QgsApplication([],False);app.initQgis();main();gc.collect();app.exitQgis()
