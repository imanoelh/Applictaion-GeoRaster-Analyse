from pathlib import Path
from qgis.core import *
from PyQt5.QtGui import QColor
import json
ROOT=Path(__file__).resolve().parents[1]; B=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; Q=B/'qgis'; Q.mkdir(exist_ok=True); rows=json.loads((B/'manifests/dataset_manifest.json').read_text())['patches']; app=QgsApplication([],False); app.initQgis(); p=QgsProject.instance();p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637')); root=p.layerTreeRoot()
for r in rows:
 pid=r['patch_id']; split=r['split']; group=root.addGroup(f'{split.upper()}_{pid}')
 rgb=QgsRasterLayer(str(B/split/'rgb'/(pid+'.tif')),pid+'_RGB','gdal'); pseudo=QgsRasterLayer(str(B/'pseudo_labels/model_c/mask'/(pid+'.tif')),pid+'_MODEL_C_PREANNOTATED','gdal'); gt=QgsVectorLayer(f"{B/'annotations/ground_truth_layers_14A2.gpkg'}|layername={pid}",pid+'_GROUND_TRUTH_PENDING','ogr')
 for l in [rgb,pseudo,gt]: assert l.isValid(); p.addMapLayer(l,False); n=group.addLayer(l); n.setItemVisibilityChecked(l!=pseudo)
 if isinstance(gt,QgsVectorLayer): gt.renderer().symbol().setColor(QColor(0,255,0,60))
 pseudo.setOpacity(.45)
 b=QgsBookmark();b.setName(pid+'_REVIEW');b.setGroup('14A2_TRAINING_REVIEW');b.setExtent(QgsReferencedRectangle(QgsRectangle(*r['bounds']),p.crs()));p.bookmarkManager().addBookmark(b)
out=Q/'14A2_training_ground_truth.qgz'; assert p.write(str(out)); p.clear(); assert p.read(str(out)); print('PROJECT',len(p.mapLayers()),len(p.layerTreeRoot().findLayers()),len(p.bookmarkManager().bookmarks()));app.exitQgis()
