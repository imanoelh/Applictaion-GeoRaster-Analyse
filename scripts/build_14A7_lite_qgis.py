"""Standalone QGIS 3.40 builder for fixed gold and separate assisted review."""
from pathlib import Path
import json,shutil,tempfile,gc
from osgeo import ogr,osr
from qgis.PyQt.QtGui import QColor,QFont
from qgis.core import (Qgis,QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsCoordinateReferenceSystem,
 QgsSingleSymbolRenderer,QgsFillSymbol,QgsDefaultValue,QgsMultiBandColorRenderer,QgsRectangle,QgsReferencedRectangle,
 QgsBookmark,QgsPalLayerSettings,QgsTextFormat,QgsVectorLayerSimpleLabeling,QgsFeature,QgsGeometry)
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
OUT=BASE/'14A7_gold_set';OLD=BASE/'14A7_validation_expansion';REF=BASE/'qgis/14A5A_ANNOTATION_FINAL_VALIDATED.qgz'

def empty_gt(path,table):
    if not path.exists():
        srs=osr.SpatialReference();srs.ImportFromEPSG(32637);ds=ogr.GetDriverByName('GPKG').CreateDataSource(str(path))
        layer=ds.CreateLayer(table,srs,ogr.wkbPolygon,options=['FID=fid','GEOMETRY_NAME=geom'])
        for name in ('patch_id','building_id','scene_type','source','review_status'):
            f=ogr.FieldDefn(name,ogr.OFTString)
            if name=='source':f.SetDefault("'MANUAL'" if table=='buildings_gt' else "'HUMAN_CORRECTED'")
            if name=='review_status':f.SetDefault("'UNREVIEWED'")
            layer.CreateField(f)
        ds=None
    return str(path)+'|layername='+table

def symbol(layer,color):
    layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':color,'outline_width':'0.5'})))
    labels=QgsPalLayerSettings();labels.fieldName='patch_id';fmt=QgsTextFormat();fmt.setFont(QFont('Arial'));fmt.setSize(8);fmt.setColor(QColor(color));labels.setFormat(fmt)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(labels));layer.setLabelsEnabled(True)

def make_project(patches,path,gt_uri,gold=False):
    project=QgsProject();assert project.read(str(REF));project.removeAllMapLayers();project.layerTreeRoot().removeAllChildren()
    for b in list(project.bookmarkManager().bookmarks()):project.bookmarkManager().removeBookmark(b.id())
    project.annotationManager().clear()
    if hasattr(project.mainAnnotationLayer(),'clear'):project.mainAnnotationLayer().clear()
    project.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'));project.setFilePathStorage(Qgis.FilePathType.Absolute)
    project.setTitle('14A7 FIXED GOLD | MANUAL 4 ONLY | NEVER TRAIN' if gold else '14A7 AI ASSISTED | PREDICTIONS ARE NOT GT | CORRECTION POOL ONLY')
    project.setCustomVariables({'GOLD_SET_LOCKED':'YES' if gold else 'NOT_GOLD_CORRECTION_POOL'})
    root=project.layerTreeRoot();canonical=QgsVectorLayer(gt_uri,'buildings_gt_GOLD_LOCKED' if gold else 'HUMAN_CORRECTED_REVIEW_REQUIRED','ogr')
    assert canonical.isValid() and canonical.featureCount()==0
    symbol(canonical,'green');project.addMapLayer(canonical,False);root.addLayer(canonical).setItemVisibilityChecked(False)
    ai=None
    if not gold:
        ai=QgsVectorLayer(str(OUT/'ai_assisted/AI_PREANNOTATION.gpkg')+'|layername=AI_PREANNOTATION','AI_PREANNOTATION_NOT_GT','ogr');assert ai.isValid()
    for index,p in enumerate(patches):
        pid=p['patch_id'];group=root.addGroup(pid+' | '+p['scene_type']);group.setExpanded(index==0)
        gt=QgsVectorLayer(gt_uri,pid+('_GOLD_MANUAL_GT' if gold else '_HUMAN_CORRECTION_TARGET'),'ogr');assert gt.setSubsetString('"patch_id" = \''+pid+'\'')
        symbol(gt,'green')
        defaults={'patch_id':pid,'scene_type':p['scene_type'],'source':'MANUAL' if gold else 'HUMAN_CORRECTED','review_status':'UNREVIEWED'}
        for field,value in defaults.items():gt.setDefaultValueDefinition(gt.fields().indexFromName(field),QgsDefaultValue("'"+value+"'"))
        gt.setDefaultValueDefinition(gt.fields().indexFromName('building_id'),QgsDefaultValue('uuid()'))
        assert gt.isValid() and gt.startEditing();assert gt.rollBack();project.addMapLayer(gt,False);group.addLayer(gt)
        if not gold:
            proposals=QgsVectorLayer(ai.source(),pid+'_AI_PREANNOTATION_NOT_GT','ogr');assert proposals.setSubsetString('"patch_id" = \''+pid+'\'');symbol(proposals,'purple')
            proposals.setReadOnly(False);project.addMapLayer(proposals,False);group.addLayer(proposals)
        rgb=QgsRasterLayer(str(ROOT/p['rgb_path']),pid+'_RGB','gdal');assert rgb.isValid()
        for band in (1,2,3):rgb.dataProvider().setUseSourceNoDataValue(band,False)
        rgb.setRenderer(QgsMultiBandColorRenderer(rgb.dataProvider(),1,2,3));project.addMapLayer(rgb,False);group.addLayer(rgb);group.setItemVisibilityChecked(index==0)
        bm=QgsBookmark();bm.setName(pid);bm.setGroup('GOLD_LOCKED' if gold else 'AI_ASSISTED_POOL');rect=QgsRectangle(*p['bounds_32637']);rect.scale(1.08);bm.setExtent(QgsReferencedRectangle(rect,project.crs()));project.bookmarkManager().addBookmark(bm)
    rect=QgsRectangle(*patches[0]['bounds_32637']);rect.scale(1.08);project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(rect,project.crs()))
    project.setFileName(str(path));assert project.write();expected=9 if gold else 31
    assert len(project.mapLayers())==expected
    stats=dict(path=str(path.relative_to(ROOT)),layers=len(project.mapLayers()),rgb=len(patches),bookmarks=len(project.bookmarkManager().bookmarks()),gt_initial_features=canonical.featureCount(),gt_editable=True)
    project.clear();project=None
    for _ in range(2):
        reopened=QgsProject();assert reopened.read(str(path));assert len(reopened.mapLayers())==expected;assert all(l.isValid() for l in reopened.mapLayers().values());reopened.clear();reopened=None
    stats.update(open='PASS',reopen='PASS',broken_sources=0)
    return stats

def main():
    gold=json.loads((OUT/'manifest/GOLD_SET_LOCK.json').read_text(encoding='utf-8'))['patches']
    pool=json.loads((OUT/'manifest/AI_ASSISTED_POOL.json').read_text(encoding='utf-8'))['patches']
    # Preserve raw prediction export, make a separate editable review copy.
    pre=OUT/'ai_assisted/AI_PREANNOTATION.gpkg'
    if not pre.exists():
        from osgeo import gdal
        ds=gdal.VectorTranslate(str(pre),str(OUT/'ai_assisted/AI_PREANNOTATION.geojson'),format='GPKG',layerName='AI_PREANNOTATION',dstSRS='EPSG:32637',geometryType='POLYGON');assert ds;ds=None
    gt=empty_gt(OUT/'gt/14A7_GOLD_manual_gt.gpkg','buildings_gt')
    corrected=empty_gt(OUT/'ai_assisted/HUMAN_CORRECTION_REVIEW.gpkg','human_corrected')
    qa=dict(qgis_version=Qgis.QGIS_VERSION,gold=make_project(gold,OUT/'qgis/14A7_GOLD_SET_MANUAL_4.qgz',gt,True),
            ai_assisted=make_project(pool,OUT/'qgis/14A7_AI_ASSISTED_REVIEW.qgz',corrected,False))
    # Provider persistence test in temporary GT copy only.
    with tempfile.TemporaryDirectory(prefix='14A7gold_') as tmp:
        cp=Path(tmp)/'copy.gpkg';shutil.copy2(OUT/'gt/14A7_GOLD_manual_gt.gpkg',cp);layer=QgsVectorLayer(str(cp)+'|layername=buildings_gt','test','ogr');assert layer.startEditing()
        b=gold[0]['bounds_32637'];f=QgsFeature(layer.fields());f.setGeometry(QgsGeometry.fromRect(QgsRectangle(b[0]+2,b[1]+2,b[0]+3,b[1]+3)));f['patch_id']='QA_ONLY';assert layer.addFeature(f) and layer.commitChanges();layer=None
        layer=QgsVectorLayer(str(cp)+'|layername=buildings_gt','test_reopen','ogr');assert layer.featureCount()==1;layer=None
    qa['temporary_copy_feature_persistence']='PASS';qa['desktop']='NOT_EXECUTED'
    # Keep old project intact apart from its purpose label; all original data/layers stay present.
    oldpath=OLD/'qgis/14A7_INDEPENDENT_VALIDATION_ANNOTATION.qgz';old=QgsProject();assert old.read(str(oldpath));n=len(old.mapLayers())
    old.setTitle('14A7 SCENE RESERVE 14 | SUPERSEDED: ONLY 4 GOLD REQUIRE MANUAL GT');variables=old.customVariables();variables['ANNOTATION_ROLE']='SCENE_RESERVE_NOT_FULL_MANUAL_QUEUE';old.setCustomVariables(variables);assert old.write();assert len(old.mapLayers())==n;old.clear();old=None
    (OUT/'qa/qgis_provider_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8');print(json.dumps(qa,indent=2))

if __name__=='__main__':
    APP=QgsApplication([],False);APP.initQgis();main();gc.collect();APP.exitQgis()
