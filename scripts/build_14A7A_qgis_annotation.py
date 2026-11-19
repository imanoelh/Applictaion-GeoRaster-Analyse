"""Standalone QGIS 3.40 builder/validation. Never run inside an existing QGIS console."""
from pathlib import Path
import json, shutil, tempfile, time
from collections import Counter
from osgeo import ogr,osr
from qgis.PyQt.QtCore import QVariant,QSize
from qgis.PyQt.QtGui import QColor,QFont
from qgis.core import (Qgis,QgsApplication,QgsProject,QgsRasterLayer,QgsVectorLayer,QgsCoordinateReferenceSystem,
    QgsSingleSymbolRenderer,QgsFillSymbol,QgsDefaultValue,QgsEditorWidgetSetup,QgsMultiBandColorRenderer,
    QgsPalLayerSettings,QgsTextFormat,QgsVectorLayerSimpleLabeling,QgsRectangle,QgsReferencedRectangle,QgsBookmark,
    QgsMapSettings,QgsMapRendererParallelJob,QgsVectorDataProvider,QgsFeature,QgsGeometry,QgsFieldConstraints)

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
OUT=BASE/'14A7_validation_expansion'
REFERENCE=BASE/'qgis/14A5A_ANNOTATION_FINAL_VALIDATED.qgz'
GPKG=OUT/'gt_vector/14A7_independent_validation_gt.gpkg'
PROJECT=OUT/'qgis/14A7_INDEPENDENT_VALIDATION_ANNOTATION.qgz'

def dump(name,x):(OUT/'qa'/name).write_text(json.dumps(x,indent=2),encoding='utf-8')
def style_gt(layer,patch=None):
    layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':'0,190,80,255','outline_width':'0.55','outline_width_unit':'MM'})))
    for field,expr in [('source',"'MANUAL'"),('review_status',"'UNREVIEWED'"),('building_id','uuid()')]:
        layer.setDefaultValueDefinition(layer.fields().indexFromName(field),QgsDefaultValue(expr))
    if patch:
        layer.setDefaultValueDefinition(layer.fields().indexFromName('patch_id'),QgsDefaultValue("'"+patch['patch_id']+"'"))
        layer.setDefaultValueDefinition(layer.fields().indexFromName('scene_type'),QgsDefaultValue("'"+patch['scene_type']+"'"))
    settings=QgsPalLayerSettings();settings.fieldName='patch_id';fmt=QgsTextFormat();fmt.setFont(QFont('Arial'));fmt.setSize(8);fmt.setColor(QColor('darkgreen'));settings.setFormat(fmt)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings));layer.setLabelsEnabled(True)
    for field in ('patch_id','building_id','source','review_status'):
        layer.setFieldConstraint(layer.fields().indexFromName(field),QgsFieldConstraints.ConstraintNotNull)

def main():
    if 'iface' in globals():raise RuntimeError('Standalone command only; no QgsApplication inside QGIS Desktop')
    app=APPLICATION
    manifest=json.loads((OUT/'manifests/14A7_validation_manifest.json').read_text())
    patches=[r for r in manifest['candidates'] if r['eligible']=='YES']
    if len(patches)!=14:raise RuntimeError('Expected audited 14-patch selection')
    if not GPKG.exists():
        driver=ogr.GetDriverByName('GPKG');ds=driver.CreateDataSource(str(GPKG));srs=osr.SpatialReference();srs.ImportFromEPSG(32637)
        lyr=ds.CreateLayer('buildings_gt',srs,ogr.wkbPolygon,options=['GEOMETRY_NAME=geom','FID=fid','SPATIAL_INDEX=YES'])
        for name in ('patch_id','building_id','scene_type','source','review_status'):
            f=ogr.FieldDefn(name,ogr.OFTString);f.SetWidth(128)
            if name=='source':f.SetDefault("'MANUAL'")
            if name=='review_status':f.SetDefault("'UNREVIEWED'")
            if lyr.CreateField(f)!=0:raise RuntimeError('Cannot create field '+name)
        ds=None
    proj=QgsProject();started=time.perf_counter()
    if not proj.read(str(REFERENCE)):raise RuntimeError('Functional reference cannot be read: '+proj.error())
    reference=dict(path=str(REFERENCE.relative_to(ROOT)),layers=len(proj.mapLayers()),crs=proj.crs().authid(),load_seconds=time.perf_counter()-started)
    proj.removeAllMapLayers();proj.layerTreeRoot().removeAllChildren()
    for b in list(proj.bookmarkManager().bookmarks()):proj.bookmarkManager().removeBookmark(b.id())
    proj.annotationManager().clear()
    if hasattr(proj.mainAnnotationLayer(),'clear'):proj.mainAnnotationLayer().clear()
    proj.setTitle('GeoRaster 14A.7A — INDEPENDENT VALIDATION — MANUAL ANNOTATION ONLY')
    proj.setCrs(QgsCoordinateReferenceSystem('EPSG:32637'))
    proj.setFilePathStorage(Qgis.FilePathType.Absolute)
    root=proj.layerTreeRoot()
    all_gt=QgsVectorLayer(GPKG.as_posix()+'|layername=buildings_gt','buildings_gt','ogr')
    if not all_gt.isValid() or all_gt.featureCount()!=0:raise RuntimeError('GT must be a valid empty Polygon layer; never overwrite human annotations')
    style_gt(all_gt)
    all_gt.setEditorWidgetSetup(all_gt.fields().indexFromName('patch_id'),QgsEditorWidgetSetup('ValueMap',{'map':[{p['patch_id']:p['patch_id']} for p in patches]}))
    proj.addMapLayer(all_gt,False);gt_node=root.addLayer(all_gt);gt_node.setItemVisibilityChecked(False)
    groups={};all_layers=[];first_layers=[]
    for i,p in enumerate(patches):
        category=p['scene_type']
        if category not in groups:groups[category]=root.addGroup(category)
        group=groups[category].addGroup(p['patch_id']);group.setExpanded(i==0)
        gt=QgsVectorLayer(GPKG.as_posix()+'|layername=buildings_gt',p['patch_id']+'_GT_MANUAL','ogr')
        if not gt.setSubsetString('"patch_id" = \''+p['patch_id']+'\''):raise RuntimeError('GT subset failed')
        style_gt(gt,p);proj.addMapLayer(gt,False);group.addLayer(gt).setItemVisibilityChecked(True)
        rgb=QgsRasterLayer(str(ROOT/p['rgb_path']),p['patch_id']+'_RGB','gdal')
        if not rgb.isValid():raise RuntimeError('RGB provider failed '+p['patch_id'])
        for band in (1,2,3):rgb.dataProvider().setUseSourceNoDataValue(band,False)
        rgb.setRenderer(QgsMultiBandColorRenderer(rgb.dataProvider(),1,2,3));proj.addMapLayer(rgb,False);group.addLayer(rgb).setItemVisibilityChecked(True)
        group.setItemVisibilityChecked(i==0)
        if i==0:first_layers=[gt,rgb]
        all_layers.extend([gt,rgb])
        bm=QgsBookmark();bm.setName(p['patch_id']);bm.setGroup(category);rect=QgsRectangle(*p['bounds_32637']);rect.scale(1.07)
        bm.setExtent(QgsReferencedRectangle(rect,proj.crs()));proj.bookmarkManager().addBookmark(bm)
    footprints=QgsVectorLayer(str(OUT/'qa/14A7A_patch_footprints.geojson'),'PATCH_BOUNDS_NOT_BUILDING_GT','ogr')
    footprints.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':'0,110,230,255','outline_width':'0.3','outline_style':'dash'})))
    label=QgsPalLayerSettings();label.fieldName='patch_id';fmt=QgsTextFormat();fmt.setFont(QFont('Arial'));fmt.setSize(9);fmt.setColor(QColor('blue'));label.setFormat(fmt);footprints.setLabeling(QgsVectorLayerSimpleLabeling(label));footprints.setLabelsEnabled(True)
    proj.addMapLayer(footprints,False);root.addLayer(footprints).setItemVisibilityChecked(True)
    rect=QgsRectangle(*patches[0]['bounds_32637']);rect.scale(1.08)
    proj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(rect,proj.crs()))
    # Native project persistence only: no handcrafted QGIS XML or archive.
    proj.setFileName(str(PROJECT))
    if not proj.write():raise RuntimeError('Project write failed: '+proj.error())
    info=dict(qgis_version=Qgis.QGIS_VERSION,reference=reference,project=str(PROJECT.relative_to(ROOT)),project_crs=proj.crs().authid(),expected_rgb=14,expected_gt_aliases=15,
              actual_map_layers=len(proj.mapLayers()),bookmarks=len(proj.bookmarkManager().bookmarks()),provider_tests=[],project_write='PASS',project_open='NOT_RUN',project_reopen='NOT_RUN',editing_test='NOT_RUN')
    for lyr in [all_gt]+all_layers:
        entry=dict(name=lyr.name(),provider=lyr.providerType(),valid=lyr.isValid(),source=lyr.source(),crs=lyr.crs().authid())
        if isinstance(lyr,QgsVectorLayer):
            entry.update(feature_count=lyr.featureCount(),wkb_type=lyr.wkbType(),add_features_capability=bool(lyr.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures))
            if not entry['add_features_capability'] or not lyr.startEditing():raise RuntimeError('GT editing failed '+lyr.name())
            entry['editing_entered']=lyr.isEditable();lyr.rollBack()
        info['provider_tests'].append(entry)
    # Test feature persistence only in a temporary GPKG copy, never in the annotation dataset.
    with tempfile.TemporaryDirectory(prefix='georaster_14A7A_edit_') as temp:
        copy=Path(temp)/'gt_edit_test.gpkg';shutil.copy2(GPKG,copy)
        test=QgsVectorLayer(copy.as_posix()+'|layername=buildings_gt','QA_ONLY','ogr')
        if not test.startEditing():raise RuntimeError('Temporary-copy editing failed')
        b=patches[0]['bounds_32637'];geom=QgsGeometry.fromRect(QgsRectangle(b[0]+5,b[1]+5,b[0]+10,b[1]+10));f=QgsFeature(test.fields());f.setGeometry(geom)
        for k,v in dict(patch_id='QA_ONLY',building_id='QA_ONLY',scene_type='QA_ONLY',source='QA_TEST_NOT_GT',review_status='UNREVIEWED').items():f[k]=v
        if not test.addFeature(f) or not test.commitChanges():raise RuntimeError('Temporary-copy persistence failed')
        reloaded=QgsVectorLayer(copy.as_posix()+'|layername=buildings_gt','QA_ONLY_REOPEN','ogr')
        if reloaded.featureCount()!=1:raise RuntimeError('Temporary feature not persisted')
        test=None;reloaded=None
    info['editing_test']='PASS_TEMPORARY_COPY_PERSISTENCE_AND_ORIGINAL_REMAINS_EMPTY'
    for pass_name in ('project_open','project_reopen'):
        reopened=QgsProject();t=time.perf_counter()
        if not reopened.read(str(PROJECT)):raise RuntimeError('Project reload failed')
        bad=[l.name() for l in reopened.mapLayers().values() if not l.isValid()]
        if bad or len(reopened.mapLayers())!=30:raise RuntimeError('Broken/missing project layers '+str(bad))
        counts=[l.featureCount() for l in reopened.mapLayers().values() if isinstance(l,QgsVectorLayer) and 'buildings_gt' in l.source()]
        if counts!=[0]*15:raise RuntimeError('Human GT must remain empty')
        info[pass_name]='PASS';info[pass_name+'_seconds']=time.perf_counter()-t;reopened.clear()
    settings=QgsMapSettings();settings.setLayers(first_layers+[footprints]);settings.setDestinationCrs(proj.crs());settings.setExtent(rect);settings.setOutputSize(QSize(1024,768));settings.setBackgroundColor(QColor('white'))
    job=QgsMapRendererParallelJob(settings);job.start();job.waitForFinished();img=job.renderedImage()
    if img.isNull() or not img.save(str(OUT/'qa/14A7A_qgis_initial_view.png')):raise RuntimeError('QGIS map rendering failed')
    info.update(render_test='PASS',broken_sources=0,gt_initial_features=all_gt.featureCount(),gt_editable=True,desktop_open='NOT_EXECUTED',project_load_method='QGIS 3.40.14 QgsProject API; full 14A5A functional reference settings retained')
    # Standard OGR reader also validates recovered TRAIN archive, never loaded into validation project.
    recovered=BASE/'annotations/14A5B_recovered_copy.gpkg';ds=ogr.Open(str(recovered));total=0;valid_geoms=0
    if ds is None:raise RuntimeError('Recovered TRAIN archive not readable with GDAL')
    for layer in ds:
        total+=layer.GetFeatureCount()
        for f in layer:
            g=f.GetGeometryRef()
            if g is not None and not g.IsEmpty() and g.IsValid():valid_geoms+=1
    ds=None;info['recovered_train_ogr']=dict(feature_count=total,valid_geometry_count=valid_geoms,in_validation_project=False)
    if (total,valid_geoms)!=(85,85):raise RuntimeError('Recovered TRAIN reader check failed')
    dump('14A7A_qgis_provider_project_qa.json',info);print(json.dumps(info,indent=2))
    # This is our standalone process only, never a running user QGIS process.
    proj.clear();all_layers.clear();first_layers.clear();job=None;app.processEvents()

if __name__=='__main__':
    APPLICATION=QgsApplication([],False);APPLICATION.initQgis()
    main()
    import gc
    gc.collect()
    APPLICATION.exitQgis()
