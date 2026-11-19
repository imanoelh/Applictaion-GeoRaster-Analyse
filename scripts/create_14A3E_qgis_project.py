from pathlib import Path
from qgis.core import (QgsProject, QgsRasterLayer, QgsVectorLayer, QgsVectorFileWriter,
                       QgsCoordinateReferenceSystem, QgsFields, QgsField, QgsWkbTypes,
                       QgsVectorLayer, QgsSymbol, QgsSingleSymbolRenderer)
from qgis.PyQt.QtCore import QVariant

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
OUT=EXP/'qgis'; OUT.mkdir(exist_ok=True)
GPKG=EXP/'balanced_dataset_14A3E'/'target_ground_truth_14A3E.gpkg'
GPKG.parent.mkdir(exist_ok=True)
SELECTED=['14A2_2025_15','14A2_2024_14','14A2_2025_12','14A2_2024_11']

for pid in SELECTED:
    uri=f'{GPKG}|layername={pid}_TARGET_GT'
    if not QgsVectorLayer(uri,'x','ogr').isValid():
        fields=QgsFields(); fields.append(QgsField('building_id',QVariant.String)); fields.append(QgsField('annotation_status',QVariant.String)); fields.append(QgsField('source',QVariant.String))
        crs=QgsCoordinateReferenceSystem('EPSG:32637')
        mem=QgsVectorLayer('Polygon?crs=EPSG:32637',f'{pid}_TARGET_GT','memory'); prov=mem.dataProvider(); prov.addAttributes(list(fields)); mem.updateFields()
        opts=QgsVectorFileWriter.SaveVectorOptions(); opts.driverName='GPKG'; opts.layerName=f'{pid}_TARGET_GT'; opts.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteFile
        if GPKG.exists(): opts.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteLayer
        QgsVectorFileWriter.writeAsVectorFormatV3(mem,str(GPKG),QgsProject.instance().transformContext(),opts)

proj=QgsProject.instance(); proj.clear(); proj.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
for pid in SELECTED:
    rgb=EXP/'train/rgb'/f'{pid}.tif'; rl=QgsRasterLayer(str(rgb),f'{pid} RGB')
    if rl.isValid(): proj.addMapLayer(rl)
    vl=QgsVectorLayer(f'{GPKG}|layername={pid}_TARGET_GT',f'{pid} TARGET_GT','ogr')
    if vl.isValid():
        vl.setOpacity(0.7); proj.addMapLayer(vl)
path=OUT/'14A3E_TARGETED_DATASET_EXPANSION.qgz'; proj.write(str(path)); print(str(path))
