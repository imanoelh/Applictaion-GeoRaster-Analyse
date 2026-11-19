"""Run this in the QGIS Python Console to load one RGB patch and its review layer.

The script only adds layers to the current project; it does not clear or save it.
"""
from pathlib import Path
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

dataset = Path(r"D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10\backend\data\fine_tuning\buildings\maxar_v1")
image_path, _ = QFileDialog.getOpenFileName(None, "Select a 512x512 RGB patch", str(dataset / "images"), "GeoTIFF (*.tif)")
if image_path:
    patch_id = Path(image_path).stem
    review_path = dataset / "review" / f"{patch_id}_review.geojson"
    raster_layer = QgsRasterLayer(image_path, f"RGB — {patch_id}")
    vector_layer = QgsVectorLayer(str(review_path), f"MODEL_C pre-annotation — {patch_id}", "ogr")
    if not raster_layer.isValid() or not vector_layer.isValid():
        QMessageBox.critical(None, "GeoRaster annotation", f"Could not load image or review layer:\n{review_path}")
    else:
        project = QgsProject.instance()
        project.addMapLayer(raster_layer)
        project.addMapLayer(vector_layer)
        project.viewSettings().setDefaultViewExtent(raster_layer.extent())
        QMessageBox.information(None, "GeoRaster annotation", f"Loaded {patch_id}. Save review features to:\n{review_path}")
