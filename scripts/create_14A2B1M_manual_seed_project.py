from pathlib import Path
import json
from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
ids=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']
rows={r['patch_id']:r for r in json.loads((EXP/'manifests/dataset_manifest.json').read_text())['patches']}
app=QgsApplication([],False); app.initQgis()
gpkg=EXP/'annotations/14A2B1_manual_seed_ground_truth.gpkg'; gpkg.parent.mkdir(exist_ok=True)
for i,pid in enumerate(ids):
    mem=QgsVectorLayer('Polygon?crs=EPSG:32637',pid+'_GROUND_TRUTH','memory')
    mem.dataProvider().addAttributes([QgsField('building_id',QVariant.String),QgsField('patch_id',QVariant.String),QgsField('annotation_source',QVariant.String),QgsField('review_status',QVariant.String)])
    mem.updateFields(); opt=QgsVectorFileWriter.SaveVectorOptions(); opt.driverName='GPKG'; opt.layerName=pid+'_GROUND_TRUTH'; opt.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteFile if i==0 else QgsVectorFileWriter.CreateOrOverwriteLayer
    result=QgsVectorFileWriter.writeAsVectorFormatV3(mem,str(gpkg),QgsCoordinateTransformContext(),opt)
    if result[0]!=QgsVectorFileWriter.NoError: raise RuntimeError(result)
project=QgsProject(); project.setCrs(QgsCoordinateReferenceSystem('EPSG:32637')); root=project.layerTreeRoot()
for pid in ids:
    row=rows[pid]; group=root.addGroup('PATCH_'+pid)
    rgb=QgsRasterLayer(str(EXP/row['split']/'rgb'/f'{pid}.tif'),pid+'_RGB','gdal'); project.addMapLayer(rgb,False)
    gt=QgsVectorLayer(f'{gpkg}|layername={pid}_GROUND_TRUTH',pid+'_GROUND_TRUTH','ogr'); project.addMapLayer(gt,False)
    if not rgb.isValid() or not gt.isValid(): raise RuntimeError('Invalid layer for '+pid)
    gt.renderer().symbol().setColor(QColor(0,190,50,55)); gt.renderer().symbol().symbolLayer(0).setStrokeColor(QColor(0,150,40,230)); gt.renderer().symbol().symbolLayer(0).setStrokeWidth(0.8)
    group.addLayer(rgb); group.addLayer(gt)
    bm=QgsBookmark(); bm.setName(pid+'_MANUAL_GT'); bm.setGroup('MANUAL_SEED_GT'); bm.setExtent(QgsReferencedRectangle(rgb.extent(),project.crs())); project.bookmarkManager().addBookmark(bm)
out=EXP/'qgis/14A2B1_MANUAL_SEED_GT.qgz'; out.parent.mkdir(exist_ok=True); project.write(str(out)); print('PROJECT',out,'LAYERS',len(project.mapLayers()),'BOOKMARKS',len(project.bookmarkManager().bookmarks()),'GPKG',gpkg); app.exitQgis()
