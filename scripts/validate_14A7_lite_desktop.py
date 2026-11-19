"""QGIS --code validation, dedicated test instance only; edits no features."""
from pathlib import Path
import json,time,traceback
from qgis.PyQt.QtCore import QTimer
from qgis.core import QgsProject,QgsRasterLayer,QgsVectorLayer,Qgis
from qgis.utils import iface
ROOT=Path(r'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10')
OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set'
P=OUT/'qgis/14A7_GOLD_SET_MANUAL_4.qgz';START=time.perf_counter()
RESULT=dict(qgis_version=Qgis.QGIS_VERSION,open='NOT_EXECUTED',reopen='NOT_EXECUTED',editing='NOT_EXECUTED')
def inspect():
    project=QgsProject.instance();layers=list(project.mapLayers().values());assert len(layers)==9
    assert all(l.isValid() for l in layers);assert project.crs().authid()=='EPSG:32637'
    assert sum(isinstance(l,QgsRasterLayer) for l in layers)==4
    for layer in layers:
        if isinstance(layer,QgsVectorLayer):
            # QGIS may expose -1 for a not-yet-estimated filtered empty layer.
            # Inspect actual provider features instead of treating an unknown estimate as data.
            count=layer.featureCount()
            actual=sum(1 for _ in layer.getFeatures())
            assert actual==0,(layer.name(),count,actual)
            RESULT.setdefault('feature_count_checks',{})[layer.name()]={'estimate':count,'actual':actual}
            assert layer.startEditing() and layer.isEditable();assert layer.rollBack()
    assert len(project.bookmarkManager().bookmarks())==4
def finish():
    try:
        inspect();RESULT.update(reopen='PASS',editing='PASS_NO_FEATURE_EDITS',rgb=4,gt_features=0,broken_sources=0,elapsed_seconds=time.perf_counter()-START)
        iface.mapCanvas().saveAsImage(str(OUT/'qa/gold_desktop_canvas.png'))
    except Exception:RESULT['error']=traceback.format_exc()
    (OUT/'qa/gold_desktop_qa.json').write_text(json.dumps(RESULT,indent=2),encoding='utf-8')
def run():
    try:
        inspect();RESULT['open']='PASS';assert QgsProject.instance().write(str(P));RESULT['save']='PASS';assert iface.addProject(str(P));QTimer.singleShot(6000,finish)
    except Exception:
        RESULT['error']=traceback.format_exc();(OUT/'qa/gold_desktop_qa.json').write_text(json.dumps(RESULT,indent=2),encoding='utf-8')
QTimer.singleShot(10000,run)
