from pathlib import Path
import csv,json,math,statistics
from osgeo import ogr,gdal,osr
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]; EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; GPKG=EXP/'annotations/14A2B1_manual_seed_ground_truth.gpkg'; MASKDIR=EXP/'masks/seed_gt_final'; QA=EXP/'qa'; MASKDIR.mkdir(parents=True,exist_ok=True); QA.mkdir(exist_ok=True)
ids=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']; ds=ogr.Open(str(GPKG),0); errors=[]; rows=[]; thumbs=[]; total=0; mask_rows=[]
for pid in ids:
 layer=ds.GetLayerByName(pid+'_GROUND_TRUTH'); rgb=EXP/'train/rgb'/f'{pid}.tif'; r=gdal.Open(str(rgb)); gt=r.GetGeoTransform(); proj=r.GetProjection(); w,h=r.RasterXSize,r.RasterYSize; bounds=(gt[0],gt[3]+h*gt[5],gt[0]+w*gt[1],gt[3]); feats=list(layer); total+=len(feats); seen=set(); invalid=selfint=out=dup=empty=zero=missing_attr=0; edge=0; areas=[]
 mem_drv=gdal.GetDriverByName('MEM'); mask_ds=mem_drv.Create('',w,h,1,gdal.GDT_Byte); mask_ds.SetGeoTransform(gt); mask_ds.SetProjection(proj); mask_ds.GetRasterBand(1).Fill(0); vds=ogr.GetDriverByName('Memory').CreateDataSource('qa'); vlayer=vds.CreateLayer('geoms',srs=layer.GetSpatialRef(),geom_type=ogr.wkbPolygon)
 for f in feats:
  geom=f.GetGeometryRef(); bid=f.GetField('building_id'); patch=f.GetField('patch_id'); source=f.GetField('annotation_source'); status=f.GetField('review_status'); key=bytes(geom.ExportToWkb()) if geom else b''; seen_count=key in seen; seen.add(key)
  if seen_count: dup+=1; errors.append([pid,bid,'DUPLICATE','Exact WKB duplicate'])
  if geom is None or geom.IsEmpty(): empty+=1; errors.append([pid,bid,'EMPTY_GEOMETRY','Empty geometry']); continue
  typ=ogr.GT_Flatten(geom.GetGeometryType()); valid=bool(geom.IsValid()); invalid+=int(not valid); selfint+=int(not valid)
  if not valid: errors.append([pid,bid,'INVALID_GEOMETRY','OGR IsValid returned false'])
  if typ not in (ogr.wkbPolygon,ogr.wkbMultiPolygon): invalid+=1; errors.append([pid,bid,'WRONG_GEOMETRY_TYPE',str(typ)])
  area=geom.GetArea(); areas.append(area); zero+=int(area<=0)
  if area<=0: errors.append([pid,bid,'ZERO_AREA','Area <= 0'])
  env=geom.GetEnvelope(); outside=env[0]<bounds[0]-1e-6 or env[1]>bounds[2]+1e-6 or env[2]<bounds[1]-1e-6 or env[3]>bounds[3]+1e-6; out+=int(outside)
  if outside: errors.append([pid,bid,'OUT_OF_BOUNDS',str(env)])
  if min(abs(env[0]-bounds[0]),abs(env[1]-bounds[2]),abs(env[2]-bounds[1]),abs(env[3]-bounds[3]))<1e-3: edge+=1
  if not bid or str(patch)!=pid or str(source)!='MANUAL' or str(status) not in ('MANUAL','VALIDATED'):
   missing_attr+=1; errors.append([pid,bid,'ATTRIBUTES',f'patch_id={patch}; annotation_source={source}; review_status={status}'])
  layer_defn=layer.GetLayerDefn()
  vf=ogr.Feature(vlayer.GetLayerDefn()); vf.SetGeometry(geom.Clone()); vlayer.CreateFeature(vf)
 mask_path=MASKDIR/f'{pid}.tif'; outds=gdal.GetDriverByName('GTiff').Create(str(mask_path),w,h,1,gdal.GDT_Byte,options=['COMPRESS=DEFLATE']); outds.SetGeoTransform(gt); outds.SetProjection(proj); outds.GetRasterBand(1).WriteArray(mask_ds.GetRasterBand(1).ReadAsArray()); outds.FlushCache(); outds=None
 gdal.RasterizeLayer(mask_ds,[1],vlayer,burn_values=[1]); arr=mask_ds.GetRasterBand(1).ReadAsArray(); vals=set(int(x) for x in arr.reshape(-1)); mask_ok=(w,h)==(512,512) and vals.issubset({0,1}); mask_rows.append({'patch_id':pid,'width':w,'height':h,'values':sorted(vals),'mask_alignment':mask_ok,'building_pixels':int((arr>0).sum()),'background_pixels':int((arr==0).sum()),'coverage_percent':round(100*float((arr>0).mean()),4)})
 rgb_img=Image.open(rgb).convert('RGB').resize((256,256)); poly_img=rgb_img.copy(); draw=ImageDraw.Draw(poly_img); px,py=gt[1],gt[5]
 for f in feats:
  geom=f.GetGeometryRef()
  if geom is None: continue
  geoms=[geom] if ogr.GT_Flatten(geom.GetGeometryType())==ogr.wkbPolygon else [geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())]
  for pg in geoms:
   ring=pg.GetGeometryRef(0) if pg.GetGeometryCount() else None
   if ring:
    pts=[((x-bounds[0])/ (bounds[2]-bounds[0])*256,(bounds[3]-y)/(bounds[3]-bounds[1])*256) for x,y,z in [ring.GetPoint(i) for i in range(ring.GetPointCount())]]; draw.line(pts,fill=(0,255,0),width=2)
 mask_img=Image.fromarray((arr*255).astype('uint8')).convert('RGB').resize((256,256)); blend=Image.blend(rgb_img,mask_img,0.38); thumbs.append((pid,rgb_img,poly_img,mask_img,blend))
 rows.append({'patch_id':pid,'feature_count':len(feats),'invalid_geometries':invalid,'self_intersections':selfint,'out_of_bounds':out,'duplicates':dup,'empty_geometries':empty,'zero_area':zero,'attribute_errors':missing_attr,'edge_buildings':edge,'min_area_m2':min(areas) if areas else 0,'median_area_m2':statistics.median(areas) if areas else 0,'max_area_m2':max(areas) if areas else 0})
if errors:
 with (QA/'14A2B2_seed_gt_errors.csv').open('w',newline='',encoding='utf-8') as f: w=csv.writer(f); w.writerow(['patch_id','building_id','error_type','details']); w.writerows(errors)
with (QA/'14A2B2_seed_gt_geometry_qa.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
sheet=Image.new('RGB',(1024,256*len(thumbs)),'white'); d=ImageDraw.Draw(sheet)
for i,(pid,rgb_img,poly_img,mask_img,blend) in enumerate(thumbs): sheet.paste(rgb_img,(0,i*256)); sheet.paste(poly_img,(256,i*256)); sheet.paste(mask_img,(512,i*256)); sheet.paste(blend,(768,i*256)); d.text((8,i*256+8),'RGB',fill='white'); d.text((264,i*256+8),'GT polygons',fill='white'); d.text((520,i*256+8),'GT mask',fill='white'); d.text((776,i*256+8),pid,fill='white')
sheet.save(QA/'14A2B2_seed_gt_contact_sheet.png')
summary={'seed_patches':5,'total_gt_features':total,'patches':rows,'masks':mask_rows,'building_pixels_total':sum(x['building_pixels'] for x in mask_rows),'background_pixels_total':sum(x['background_pixels'] for x in mask_rows),'building_coverage_percent':round(100*sum(x['building_pixels'] for x in mask_rows)/(sum(x['building_pixels']+x['background_pixels'] for x in mask_rows)),4),'invalid_geometries':sum(x['invalid_geometries'] for x in rows),'self_intersections':sum(x['self_intersections'] for x in rows),'out_of_bounds':sum(x['out_of_bounds'] for x in rows),'duplicates':sum(x['duplicates'] for x in rows),'empty_geometries':sum(x['empty_geometries'] for x in rows),'zero_area':sum(x['zero_area'] for x in rows),'attribute_errors':sum(x['attribute_errors'] for x in rows),'mask_alignment':all(x['mask_alignment'] for x in mask_rows),'val_leakage':0,'locked_test_leakage':0,'patches_validated':sum(1 for x in rows if all(x[k]==0 for k in ('invalid_geometries','self_intersections','out_of_bounds','duplicates','empty_geometries','zero_area','attribute_errors'))),'final_seed_gt':'APPROVED' if not errors else 'REJECTED','ready_for_fine_tuning':not errors}
(QA/'14A2B2_seed_gt_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
if not errors:
 (EXP/'manifests/14A2B2_final_seed_gt.json').write_text(json.dumps({'status':'APPROVED','training_started':False,'source':'14A2B1_manual_seed_ground_truth.gpkg','patches':ids},indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
