"""Run via --code in a dedicated QGIS Desktop instance, never an existing session."""
from pathlib import Path
import json,traceback
from qgis.PyQt.QtCore import QTimer
from qgis.core import QgsProject,QgsRasterLayer,QgsVectorLayer,Qgis
from qgis.utils import iface
ROOT=Path(r'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10')
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
AL=BASE/'14A9B_active_learning';DEV=BASE/'14A9B_dev_set'
P=AL/'qgis/14A9B_ACTIVE_LEARNING_CORRECTION.qgz';D=DEV/'qgis/14A9B_DEV_CALIBRATION_CORRECTION.qgz'
RESULT={'version':Qgis.QGIS_VERSION,'train':{},'dev':{}}
def persist():
 (AL/'qa/QGIS_DESKTOP_QA.json').write_text(json.dumps(RESULT,indent=2))
def inspect(n):
 p=QgsProject.instance();ls=list(p.mapLayers().values());assert len(ls)==3*n
 assert all(l.isValid() for l in ls) and p.crs().authid()=='EPSG:32637'
 counts={};manual=0
 for l in ls:
  if isinstance(l,QgsVectorLayer):
   counts[l.name()]=sum(1 for _ in l.getFeatures())
   if '_MANUAL_CORRECTED_GT_PENDING' in l.name():
    assert l.startEditing() and l.isEditable();assert l.rollBack();manual+=1
 assert manual==n
 return dict(layers=len(ls),rgb=sum(isinstance(l,QgsRasterLayer) for l in ls),manual_editable=manual,feature_counts=counts,broken_sources=0)
def fail():RESULT['error']=traceback.format_exc();persist()
def start():
 try:
  RESULT['train']['opening']=inspect(10);assert QgsProject.instance().write(str(P));RESULT['train']['save']='PASS';assert iface.addProject(str(P));QTimer.singleShot(5000,reopen_train)
 except Exception:fail()
def reopen_train():
 try:
  RESULT['train']['reopening']=inspect(10);RESULT['train']['open_reopen_editing']='PASS';iface.mapCanvas().saveAsImage(str(AL/'qa/DESKTOP_TRAIN_CANVAS.png'));persist();assert iface.addProject(str(D));QTimer.singleShot(5000,open_dev)
 except Exception:fail()
def open_dev():
 try:
  RESULT['dev']['opening']=inspect(4);assert QgsProject.instance().write(str(D));RESULT['dev']['save']='PASS';assert iface.addProject(str(D));QTimer.singleShot(5000,reopen_dev)
 except Exception:fail()
def reopen_dev():
 try:
  RESULT['dev']['reopening']=inspect(4);RESULT['dev']['open_reopen_editing']='PASS';iface.mapCanvas().saveAsImage(str(DEV/'qa/DESKTOP_DEV_CANVAS.png'));RESULT['geometry_edits']='NONE';persist();assert iface.addProject(str(P))
 except Exception:fail()
QTimer.singleShot(10000,start)
