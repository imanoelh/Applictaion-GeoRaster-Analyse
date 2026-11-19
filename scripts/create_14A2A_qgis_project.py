from pathlib import Path
import csv
import json
from qgis.core import *
from qgis.PyQt.QtGui import QColor

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
QA = EXP/'qa'
SMART = EXP/'smart_assisted_annotation'
rows = json.loads((EXP/'manifests/dataset_manifest.json').read_text(encoding='utf-8'))['patches']
proposal_data = json.loads((SMART/'proposals/ASSISTED_PROPOSALS.geojson').read_text(encoding='utf-8'))
app = QgsApplication([], False); app.initQgis()
p = QgsProject(); p.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
root = p.layerTreeRoot()

def add(path, name, group, visible=True):
    if path.suffix.lower() in ('.tif', '.tiff'):
        layer = QgsRasterLayer(str(path), name, 'gdal')
    else:
        layer = QgsVectorLayer(str(path), name, 'ogr')
    if not layer.isValid(): raise RuntimeError(f'Invalid layer: {path}')
    p.addMapLayer(layer, False); node = group.addLayer(layer); node.setItemVisibilityChecked(visible)
    return layer

proposal_layer = QgsVectorLayer(str(SMART/'proposals/ASSISTED_PROPOSALS.geojson'), 'ASSISTED_PROPOSALS', 'ogr')
if not proposal_layer.isValid(): raise RuntimeError('ASSISTED_PROPOSALS invalid')
p.addMapLayer(proposal_layer, False)
root.addLayer(proposal_layer)
renderer = QgsCategorizedSymbolRenderer('status', [])
for value, color in [('AUTO_ACCEPT_CANDIDATE', QColor(30,170,70,170)), ('REVIEW_REQUIRED', QColor(255,165,0,180)), ('LOW_CONFIDENCE', QColor(220,30,30,190))]:
    sym = QgsSymbol.defaultSymbol(proposal_layer.geometryType()); sym.setColor(color); renderer.addCategory(QgsRendererCategory(value, sym, value))
proposal_layer.setRenderer(renderer)

gt_path = EXP/'annotations/ground_truth_layers_14A2.gpkg'
for row in rows:
    pid = row['patch_id']; group = root.addGroup(f"{row['split'].upper()}_{pid}")
    rgb = add(EXP/row['split']/'rgb'/f'{pid}.tif', pid+'_RGB', group, True)
    c = add(EXP/'pseudo_labels/model_c/mask'/f'{pid}.tif', pid+'_MODEL_C', group, False); c.setOpacity(0.45)
    d = add(SMART/'model_d/mask'/f'{pid}.tif', pid+'_MODEL_D', group, False); d.setOpacity(0.45)
    gt = add(Path(f'{gt_path}|layername={pid}'), pid+'_GROUND_TRUTH', group, True)
    gt.renderer().symbol().setColor(QColor(0,255,0,70))
    for feat in proposal_layer.getFeatures():
        if feat['patch_id'] != pid or feat['status'] == 'AUTO_ACCEPT_CANDIDATE': continue
        b = feat.geometry().boundingBox(); margin=max(b.width(),b.height(),1.0)*1.5
        ext=QgsRectangle(b.xMinimum()-margin,b.yMinimum()-margin,b.xMaximum()+margin,b.yMaximum()+margin)
        bm=QgsBookmark(); bm.setName(f"{feat['proposal_id']}_{feat['status']}"); bm.setGroup('REVIEW_REQUIRED_AND_LOW_CONFIDENCE'); bm.setExtent(QgsReferencedRectangle(ext,p.crs())); p.bookmarkManager().addBookmark(bm)

out = EXP/'qgis/14A2_SMART_ASSISTED_ANNOTATION.qgz'; out.parent.mkdir(exist_ok=True)
if not p.write(str(out)): raise RuntimeError('QGIS project write failed')
print('PROJECT', len(p.mapLayers()), len(p.bookmarkManager().bookmarks()), str(out))
app.exitQgis()
