"""Run with QGIS Desktop --code in a dedicated new instance; no model execution."""
from pathlib import Path
import json,time,traceback
from qgis.PyQt.QtCore import QTimer
from qgis.core import QgsProject,QgsVectorLayer,QgsRasterLayer,Qgis
from qgis.utils import iface

ROOT=Path(r'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10')
OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_validation_expansion'
PROJECT=OUT/'qgis/14A7_INDEPENDENT_VALIDATION_ANNOTATION.qgz'
started=time.perf_counter()
(OUT/'qa/14A7A_desktop_started.txt').write_text('Desktop startup code entered',encoding='utf-8')
result={'qgis_version':Qgis.QGIS_VERSION,'desktop_open':'NOT_EXECUTED','desktop_reopen':'NOT_EXECUTED','editing':'NOT_EXECUTED'}

def inspect():
    project=QgsProject.instance();layers=list(project.mapLayers().values())
    rgbs=[l for l in layers if isinstance(l,QgsRasterLayer)]
    gt=[l for l in layers if isinstance(l,QgsVectorLayer) and 'buildings_gt' in l.source()]
    bad=[l.name() for l in layers if not l.isValid()]
    assert len(layers)==30 and len(rgbs)==14 and len(gt)==15,(len(layers),len(rgbs),len(gt))
    assert not bad,bad
    assert project.crs().authid()=='EPSG:32637'
    for layer in gt:
        count=layer.featureCount()
        assert count==0,dict(layer=layer.name(),count=count,provider_error=layer.dataProvider().error().message(),source=layer.source())
        assert layer.startEditing() and layer.isEditable(),layer.name()
        assert layer.rollBack()
    return dict(total_layers=len(layers),rgb_layers=len(rgbs),gt_aliases=len(gt),broken_sources=bad,bookmarks=len(project.bookmarkManager().bookmarks()),gt_features=0,crs=project.crs().authid())

def finish():
    try:
        result['reopened_checks']=inspect();result['desktop_reopen']='PASS'
        iface.mapCanvas().refresh()
        iface.mapCanvas().saveAsImage(str(OUT/'qa/14A7A_desktop_canvas.png'))
        result['elapsed_seconds']=time.perf_counter()-started
    except Exception:result['error']=traceback.format_exc()
    (OUT/'qa/14A7A_desktop_qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

def run():
    try:
        result['opening_checks']=inspect();result['desktop_open']='PASS';result['editing']='PASS_NO_GEOMETRY_EDITS'
        assert QgsProject.instance().write(str(PROJECT))
        result['desktop_save']='PASS'
        # Dedicated validation instance, created with --project; no user project is replaced.
        assert iface.addProject(str(PROJECT))
        QTimer.singleShot(6000,finish)
    except Exception:
        result['error']=traceback.format_exc()
        (OUT/'qa/14A7A_desktop_qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

QTimer.singleShot(8000,run)
