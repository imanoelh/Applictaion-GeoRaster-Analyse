from pathlib import Path
import csv
from qgis.core import QgsProject,QgsRasterLayer,QgsVectorLayer,QgsCoordinateReferenceSystem,QgsRectangle,QgsReferencedRectangle,QgsBookmark

ROOT=Path(__file__).resolve().parents[1]; EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'; QA=EXP/'qa'; OUT=EXP/'targeted_review_14A3E2'; SELECTED=['14A2_2025_15','14A2_2024_14','14A2_2025_12','14A2_2024_11']
proj=QgsProject.instance(); proj.clear(); proj.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
for pid in SELECTED:
    rl=QgsRasterLayer(str(EXP/'train/rgb'/f'{pid}.tif'),f'{pid} RGB')
    if rl.isValid(): proj.addMapLayer(rl)
candidate=QgsVectorLayer(str(OUT/'HARD_NEGATIVE_CANDIDATES.geojson'),'HARD_NEGATIVE_CANDIDATES','ogr')
if candidate.isValid(): proj.addMapLayer(candidate)
gtgpkg=EXP/'balanced_dataset_14A3E'/'target_ground_truth_14A3E.gpkg'
for pid in SELECTED:
    vl=QgsVectorLayer(f'{gtgpkg}|layername={pid}_TARGET_GT',f'{pid} TARGET_GT','ogr')
    if vl.isValid(): proj.addMapLayer(vl)
try:
    bm=proj.bookmarkManager()
    for r in csv.DictReader((QA/'14A3E2_negative_review.csv').open(encoding='utf-8')):
        ext=QgsReferencedRectangle(QgsRectangle(float(r['minx']),float(r['miny']),float(r['maxx']),float(r['maxy'])),QgsCoordinateReferenceSystem('EPSG:32637'))
        b=QgsBookmark(); b.setName(r['candidate_id']); b.setExtent(ext); bm.addBookmark(b)
except Exception as e: print('bookmark warning',e)
path=EXP/'qgis/14A3E2_TARGETED_REVIEW.qgz'; path.parent.mkdir(exist_ok=True); proj.write(str(path)); print(path)
