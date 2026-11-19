from pathlib import Path
import json
from qgis.core import *
from qgis.PyQt.QtGui import QColor

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
src=EXP/'smart_preannotation_v2/ASSISTED_PROPOSALS.geojson'
gpkg=EXP/'annotations/14A2A2_ASSISTED_PROPOSALS.gpkg'; gpkg.parent.mkdir(exist_ok=True)
app=QgsApplication([],False); app.initQgis()
proposals=QgsVectorLayer(str(src),'ASSISTED_PROPOSALS','ogr')
if not proposals.isValid(): raise RuntimeError('proposal source invalid')
proposals.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
opts=QgsVectorFileWriter.SaveVectorOptions(); opts.driverName='GPKG'; opts.layerName='ASSISTED_PROPOSALS'; opts.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteFile
err=QgsVectorFileWriter.writeAsVectorFormatV3(proposals,str(gpkg),QgsCoordinateTransformContext(),opts)
if err[0]!=QgsVectorFileWriter.NoError: raise RuntimeError(str(err))
out=EXP/'qgis/14A2A2_FAST_REVIEW.qgz'; p=QgsProject(); p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637')); root=p.layerTreeRoot()
prop=QgsVectorLayer(f'{gpkg}|layername=ASSISTED_PROPOSALS','ASSISTED_PROPOSALS','ogr'); p.addMapLayer(prop,False); root.addLayer(prop)
cat=QgsCategorizedSymbolRenderer('source_class',[])
for val,col in [('C_AND_F',QColor(0,190,60,170)),('C_ONLY',QColor(255,165,0,170)),('F_ONLY',QColor(255,120,0,170))]:
    s=QgsSymbol.defaultSymbol(prop.geometryType()); s.setColor(col); cat.addCategory(QgsRendererCategory(val,s,val))
prop.setRenderer(cat)
rows=json.loads((EXP/'manifests/dataset_manifest.json').read_text())['patches']
gt=EXP/'annotations/ground_truth_layers_14A2.gpkg'
for row in rows:
    pid=row['patch_id']; group=root.addGroup(pid)
    rgb=QgsRasterLayer(str(EXP/row['split']/'rgb'/f'{pid}.tif'),pid+'_RGB','gdal'); p.addMapLayer(rgb,False); group.addLayer(rgb)
    for path,name,vis in [(EXP/'pseudo_labels/model_c/mask'/f'{pid}.tif',pid+'_MODEL_C',False),(EXP/'smart_preannotation_v2/model_f'/f'{pid}.tif',pid+'_MODEL_F',False)]:
        lyr=QgsRasterLayer(str(path),name,'gdal');
        if lyr.isValid(): p.addMapLayer(lyr,False); n=group.addLayer(lyr); n.setItemVisibilityChecked(vis)
    g=QgsVectorLayer(f'{gt}|layername={pid}',pid+'_FINAL_GT_EDITABLE','ogr'); p.addMapLayer(g,False); group.addLayer(g)
    b=rgb.extent(); bm=QgsBookmark(); bm.setName(pid+'_REVIEW'); bm.setGroup('14A2A2_REVIEW'); bm.setExtent(QgsReferencedRectangle(b,p.crs())); p.bookmarkManager().addBookmark(bm)
if not p.write(str(out)): raise RuntimeError('write failed')
print('GPKG',gpkg,'PROJECT',out,'LAYERS',len(p.mapLayers()),'BOOKMARKS',len(p.bookmarkManager().bookmarks()))
app.exitQgis()
