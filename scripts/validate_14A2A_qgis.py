from pathlib import Path
from qgis.core import QgsProject, QgsVectorLayer, QgsVectorDataProvider

root = Path(__file__).resolve().parents[1]
qgz = root/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/qgis/14A2_SMART_ASSISTED_ANNOTATION.qgz'
p = QgsProject.instance()
ok = p.read(str(qgz))
layers = list(p.mapLayers().values())
valid = [l for l in layers if l.isValid()]
gt = [l for l in layers if 'GROUND_TRUTH' in l.name()]
rgb = [l for l in layers if 'RGB' in l.name()]
props = [l for l in layers if 'ASSISTED_PROPOSALS' in l.name()]
editable = all(isinstance(l, QgsVectorLayer) and bool(l.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures) for l in gt)
empty = all(l.featureCount() == 0 for l in gt)
crs_ok = p.crs().authid() == 'EPSG:32637' and all(l.crs().authid() == 'EPSG:32637' for l in gt)
print('PROJECT_READ', ok)
print('LAYERS', len(layers), 'VALID', len(valid))
print('RGB', len(rgb))
print('GROUND_TRUTH', len(gt), 'EMPTY', empty, 'EDITABLE', editable)
print('ASSISTED_PROPOSALS', len(props))
print('BOOKMARKS', len(p.bookmarkManager().bookmarks()))
print('CRS', p.crs().authid(), 'CRS_OK', crs_ok)
print('BROKEN', len(layers)-len(valid))
for l in layers:
    if not l.isValid(): print('BROKEN_LAYER', l.name(), l.source())
