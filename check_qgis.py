from qgis.core import QgsVectorLayer
for p in ['backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/balanced_dataset_14A3E/target_ground_truth_14A3E.gpkg','backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/annotations/14A3E2_TARGET_GT_FIXED.gpkg']:
 print('FILE',p)
 for pid in ['14A2_2024_11','14A2_2025_12','14A2_2024_14','14A2_2025_15']:
  l=QgsVectorLayer(p+'|layername='+pid+'_TARGET_GT',pid,'ogr'); print(pid,l.isValid(),l.featureCount())
