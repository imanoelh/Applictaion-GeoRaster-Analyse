from pathlib import Path
import json
from qgis.core import *
from qgis.PyQt.QtCore import QVariant

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / 'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
gpkg = B / 'annotations/ground_truth_layers_14A2.gpkg'
rows = json.loads((B/'manifests/dataset_manifest.json').read_text(encoding='utf-8'))['patches']
app = QgsApplication([], False); app.initQgis()
existing = {n.name() for n in QgsProviderRegistry.instance().querySublayers(str(gpkg))}
fields = QgsFields()
for name in ['building_id','patch_id','annotation_status','review_status','annotator','source']:
    fields.append(QgsField(name, QVariant.String))
for r in rows:
    pid = r['patch_id']
    if pid in existing:
        continue
    mem = QgsVectorLayer('Polygon?crs=EPSG:32637', pid, 'memory')
    mem.dataProvider().addAttributes(fields); mem.updateFields()
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = 'GPKG'; opts.layerName = pid; opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    err, msg, newfile, newlayer = QgsVectorFileWriter.writeAsVectorFormatV3(mem, str(gpkg), QgsCoordinateTransformContext(), opts)
    if err != QgsVectorFileWriter.NoError:
        raise RuntimeError(f'{pid}: {err} {msg}')
print('ADDED', len(rows)-len(existing))
app.exitQgis()
