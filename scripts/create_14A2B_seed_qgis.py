from pathlib import Path
import json
from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
ROOT=Path(__file__).resolve().parents[1]; EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; ids=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']; rows={r['patch_id']:r for r in json.loads((EXP/'manifests/dataset_manifest.json').read_text())['patches']}
app=QgsApplication([],False); app.initQgis(); gpkg=EXP/'annotations/14A2B_seed_ground_truth.gpkg'; gpkg.parent.mkdir(exist_ok=True)
for i,pid in enumerate(ids):
 mem=QgsVectorLayer('Polygon?crs=EPSG:32637',pid+'_SEED_GROUND_TRUTH','memory'); pr=mem.dataProvider(); pr.addAttributes([QgsField('building_id',QVariant.String),QgsField('annotation_status',QVariant.String),QgsField('review_status',QVariant.String),QgsField('annotator',QVariant.String)]); mem.updateFields()
 opt=QgsVectorFileWriter.SaveVectorOptions(); opt.driverName='GPKG'; opt.layerName=pid+'_SEED_GROUND_TRUTH'; opt.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteFile if i==0 else QgsVectorFileWriter.CreateOrOverwriteLayer
 res=QgsVectorFileWriter.writeAsVectorFormatV3(mem,str(gpkg),QgsCoordinateTransformContext(),opt)
 if res[0]!=QgsVectorFileWriter.NoError: raise RuntimeError(res)
proj=QgsProject(); proj.setCrs(QgsCoordinateReferenceSystem('EPSG:32637')); root=proj.layerTreeRoot(); proposal_path=EXP/'annotations/14A2A2_ASSISTED_PROPOSALS.gpkg'
for pid in ids:
 row=rows[pid]; group=root.addGroup('PATCH_'+pid); rgb=QgsRasterLayer(str(EXP/row['split']/'rgb'/f'{pid}.tif'),pid+'_RGB','gdal'); proj.addMapLayer(rgb,False); group.addLayer(rgb)
 c=QgsRasterLayer(str(EXP/'pseudo_labels/model_c/mask'/f'{pid}.tif'),pid+'_MODEL_C','gdal'); proj.addMapLayer(c,False); n=group.addLayer(c); n.setItemVisibilityChecked(False)
 f=QgsRasterLayer(str(EXP/'smart_preannotation_v2/model_f'/f'{pid}.tif'),pid+'_MODEL_F','gdal'); proj.addMapLayer(f,False); n=group.addLayer(f); n.setItemVisibilityChecked(False)
 prop=QgsVectorLayer(f'{proposal_path}|layername=ASSISTED_PROPOSALS',pid+'_ASSISTED_PROPOSALS','ogr'); prop.setSubsetString(f"patch_id='{pid}'"); proj.addMapLayer(prop,False); group.addLayer(prop)
 gt=QgsVectorLayer(f'{gpkg}|layername={pid}_SEED_GROUND_TRUTH',pid+'_SEED_GROUND_TRUTH','ogr'); proj.addMapLayer(gt,False); group.addLayer(gt); gt.renderer().symbol().setColor(QColor(0,220,70,80))
 bm=QgsBookmark(); bm.setName(pid+'_SEED_REVIEW'); bm.setGroup('SEED_PATCHES'); bm.setExtent(QgsReferencedRectangle(rgb.extent(),proj.crs())); proj.bookmarkManager().addBookmark(bm)
out=EXP/'qgis/14A2B_SEED_GT_ANNOTATION.qgz'; out.parent.mkdir(exist_ok=True); proj.write(str(out)); print('PROJECT',out,'LAYERS',len(proj.mapLayers()),'BOOKMARKS',len(proj.bookmarkManager().bookmarks()),'GPKG',gpkg); app.exitQgis()
