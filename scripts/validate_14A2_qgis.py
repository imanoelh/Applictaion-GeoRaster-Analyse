from qgis.core import QgsApplication, QgsProject, QgsVectorLayer

app = QgsApplication([], False); app.initQgis()
path = 'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/qgis/14A2_training_ground_truth.qgz'
p = QgsProject(); ok = p.read(path)
layers = list(p.mapLayers().values())
print('OPEN', ok)
print('LAYERS', len(layers))
print('VALID', sum(x.isValid() for x in layers))
print('CRS', p.crs().authid())
print('BOOKMARKS', len(p.bookmarkManager().bookmarks()))
print('RGB', sum(x.name().endswith('_RGB') for x in layers))
print('PSEUDO', sum('MODEL_C_PREANNOTATED' in x.name() for x in layers))
print('GT', sum(x.name().endswith('GROUND_TRUTH_PENDING') for x in layers))
print('EDITABLE_PROVIDER', sum(isinstance(x, QgsVectorLayer) and bool(x.dataProvider().capabilities() & x.dataProvider().AddFeatures) for x in layers))
print('INVALID_SOURCES', [x.name() for x in layers if not x.isValid()])
p.clear(); ok2 = p.read(path)
print('REOPEN', ok2, 'LAYERS', len(p.mapLayers()), 'BOOKMARKS', len(p.bookmarkManager().bookmarks()))
app.exitQgis()
