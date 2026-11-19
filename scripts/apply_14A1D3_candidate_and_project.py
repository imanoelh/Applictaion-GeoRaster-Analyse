import json, sqlite3, subprocess
from pathlib import Path
from qgis.core import *
from PyQt5.QtGui import QColor

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
ANN=BASE/'annotations'; QA=BASE/'qa'; QGISDIR=BASE/'qgis'
WORK=ANN/'ground_truth_layers_14A1C_WORKING.gpkg'; CAND=ANN/'ground_truth_layers_14A1D3_CANDIDATE.gpkg'
records=json.loads((QA/'14A1D3_candidate_wkb.json').read_text())
RB={
 '14A_001_residential':(582091.8914781093,2368001.637367532,582271.0914781092,2368180.8373675323),
 '14A_003_dense_urban':(582091.8914781093,2367732.8373675323,582271.0914781092,2367912.0373675325),
}
if CAND.exists(): CAND.unlink()
src=sqlite3.connect(str(WORK)); dst=sqlite3.connect(str(CAND)); src.backup(dst); dst.commit(); src.close(); dst.close()

app=QgsApplication([],False); app.initQgis(); proj=QgsProject.instance(); proj.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
patches=sorted({r['patch_id'] for r in records})
candidate_layers={}
for patch in patches:
    layer=QgsVectorLayer(f"{CAND}|layername={patch}_ground_truth",patch+'_ground_truth','ogr'); assert layer.isValid(); assert layer.startEditing()
    for f in layer.getFeatures():
        hit=next((r for r in records if r['patch_id']==patch and r['building_id']==str(f['building_id'])),None)
        if hit:
            geom=QgsGeometry(); geom.fromWkb(bytes.fromhex(hit['candidate_wkb'])); f.setGeometry(geom); layer.updateFeature(f)
    assert layer.commitChanges(); proj.addMapLayer(layer,False); candidate_layers[patch]=layer
    rgb=QgsRasterLayer(str(BASE/'images'/(patch+'_v2.tif')),patch+'_RGB','gdal'); assert rgb.isValid(); proj.addMapLayer(rgb,False)
    old=QgsVectorLayer(f"{WORK}|layername={patch}_ground_truth",patch+'_WORKING_GT','ogr'); assert old.isValid(); proj.addMapLayer(old,False)

review=QA/'14A1D3_review_layers.gpkg'
if review.exists(): review.unlink()
def write_layer(name,features,nlt):
    gj=QA/(name+'.geojson'); gj.write_text(json.dumps({'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:32637'}},'features':features},indent=2),encoding='utf-8')
    cmd=[r'C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe']
    if review.exists(): cmd += ['-update']
    cmd += ['-f','GPKG',str(review),str(gj),'-nln',name,'-a_srs','EPSG:32637','-nlt',nlt]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
features=[]; points=[]; bounds=[]
for r in records:
    g=QgsGeometry(); g.fromWkb(bytes.fromhex(r['candidate_wkb']))
    features.append({'type':'Feature','properties':{'patch_id':r['patch_id'],'building_id':r['building_id'],'correction':r['kind']},'geometry':json.loads(g.asJson())})
    if r['kind']=='SELF_INTERSECTION': points.append({'type':'Feature','properties':{'patch_id':r['patch_id'],'building_id':r['building_id']},'geometry':{'type':'Point','coordinates':[r['intersection_x'],r['intersection_y']]}})
    b=RB[r['patch_id']]; bounds.append({'type':'Feature','properties':{'patch_id':r['patch_id']},'geometry':{'type':'Polygon','coordinates':[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]] ]}})
write_layer('SURGICAL_CORRECTIONS',features,'PROMOTE_TO_MULTI'); write_layer('SELF_INTERSECTION_POINTS',points,'POINT'); write_layer('RASTER_BOUNDS',bounds,'PROMOTE_TO_MULTI')
for name in ['SURGICAL_CORRECTIONS','SELF_INTERSECTION_POINTS','RASTER_BOUNDS']:
    lyr=QgsVectorLayer(f"{review}|layername={name}",name,'ogr'); assert lyr.isValid(); proj.addMapLayer(lyr,False)

for lyr in proj.mapLayers().values():
    if not isinstance(lyr,QgsVectorLayer): continue
    sym=lyr.renderer().symbol()
    if lyr.name().endswith('_WORKING_GT'): sym.setColor(QColor(255,165,0,80))
    elif lyr.name()=='SURGICAL_CORRECTIONS': sym.setColor(QColor(0,255,0,80))
    elif lyr.name()=='SELF_INTERSECTION_POINTS': sym.setColor(QColor(255,0,0,255))
    elif lyr.name()=='RASTER_BOUNDS': sym.setColor(QColor(0,120,255,40))
    lyr.triggerRepaint()

bm=proj.bookmarkManager()
for r in records:
    layer=candidate_layers[r['patch_id']]; f=next(f for f in layer.getFeatures() if str(f['building_id'])==r['building_id']); bb=f.geometry().boundingBox(); pad=max(bb.width(),bb.height(),1)*0.5; ext=QgsRectangle(bb.xMinimum()-pad,bb.yMinimum()-pad,bb.xMaximum()+pad,bb.yMaximum()+pad); b=QgsBookmark(); b.setName(f"{r['patch_id']}_{r['building_id']}_REVIEW"); b.setGroup('14A1D3_SURGICAL_REVIEW'); b.setExtent(QgsReferencedRectangle(ext,proj.crs())); bm.addBookmark(b)
out=QGISDIR/'14A1D3_SURGICAL_CORRECTION_REVIEW.qgz'
if out.exists(): out.unlink()
assert proj.write(str(out)); proj.clear(); assert proj.read(str(out)); print('PROJECT_READ=SUCCESS','LAYERS=',len(proj.mapLayers()),'BOOKMARKS=',len([b for b in proj.bookmarkManager().bookmarks() if b.name().endswith('_REVIEW')]))
app.exitQgis()
