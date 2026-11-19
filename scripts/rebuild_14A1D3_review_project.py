from pathlib import Path
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
SRC=BASE/'qgis/14A1D3_SURGICAL_CORRECTION_REVIEW.qgz'
OUT=BASE/'qgis/14A1D3_SURGICAL_CORRECTION_REVIEW_REBUILT.qgz'
app=QgsApplication([],False); app.initQgis(); proj=QgsProject.instance()
assert proj.read(str(SRC)), proj.error()
root=proj.layerTreeRoot(); root.removeAllChildren()
for layer in proj.mapLayers().values():
    node=root.addLayer(layer)
    node.setItemVisibilityChecked(True)
    if isinstance(layer,QgsRasterLayer) and ('RGB' in layer.name()): node.setItemVisibilityChecked(True)
if OUT.exists(): OUT.unlink()
assert proj.write(str(OUT))
proj.clear(); assert proj.read(str(OUT)), proj.error()
print('PROJECT_READ=SUCCESS')
print('MAP_LAYERS=',len(proj.mapLayers()))
print('TREE_LAYERS=',len(proj.layerTreeRoot().findLayers()))
print('BOOKMARKS=',len([b for b in proj.bookmarkManager().bookmarks() if b.name().endswith('_REVIEW')]))
print('CRS=',proj.crs().authid())
print('REOPEN=SUCCESS')
app.exitQgis()
