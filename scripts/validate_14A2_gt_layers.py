from qgis.core import QgsApplication, QgsProject, QgsVectorLayer

app = QgsApplication([], False); app.initQgis()
path = 'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/qgis/14A2_training_ground_truth.qgz'
p = QgsProject(); p.read(path)
gt = [x for x in p.mapLayers().values() if x.name().endswith('GROUND_TRUTH_PENDING')]
print('GT_LAYERS', len(gt))
print('GT_FEATURES', sum(x.featureCount() for x in gt))
print('GT_POLYGON', sum(x.geometryType() == 2 for x in gt))
print('GT_EPSG32637', sum(x.crs().authid() == 'EPSG:32637' for x in gt))
print('GT_EDITABLE', sum(bool(x.dataProvider().capabilities() & x.dataProvider().AddFeatures) for x in gt))
print('FIELDS_OK', sum({'building_id','patch_id','annotation_status','review_status','annotator','source'}.issubset({f.name() for f in x.fields()}) for x in gt))
app.exitQgis()
