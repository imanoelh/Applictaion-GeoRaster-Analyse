"""Build a clean QGIS project for the locked, prediction-free 13M test set."""
from __future__ import annotations

import json
from pathlib import Path

from qgis.core import (
    QgsApplication, QgsBookmark, QgsContrastEnhancement, QgsFillSymbol,
    QgsMultiBandColorRenderer, QgsProject, QgsReferencedRectangle,
    QgsRasterLayer, QgsSingleSymbolRenderer, QgsVectorLayer,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test"
PROJECT_PATH = DATA / "qgis/13M_locked_test_ground_truth.qgz"
QGIS_PREFIX = Path(r"C:\Program Files\QGIS 3.40.14\apps\qgis-ltr")


def main() -> None:
    manifest = json.loads((DATA / "metadata/manifest.json").read_text(encoding="utf-8"))
    if manifest["patch_count"] != 6 or not manifest["training_use_prohibited"]:
        raise RuntimeError("Expected the fixed six-patch test-only manifest")
    QgsApplication.setPrefixPath(str(QGIS_PREFIX), True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        project = QgsProject.instance()
        project.clear()
        project.setTitle("GeoRaster - 13M Locked TEST Ground Truth Annotation")
        project.setCrs(__import__("qgis.core", fromlist=["QgsCoordinateReferenceSystem"]).QgsCoordinateReferenceSystem("EPSG:32637"))
        first_extent = None
        first_crs = None
        group_names = []
        bookmarks = []
        annotation_layer_info = []

        for index, patch_id in enumerate(manifest["patch_ids"], 1):
            meta = json.loads((DATA / "metadata" / f"{patch_id}.json").read_text(encoding="utf-8"))
            image_path = DATA / meta["image"]
            annotation_path = DATA / meta["annotation"]
            group_name = f"{index:02d}_{patch_id}_TEST_LOCKED"
            group_names.append(group_name)
            group = project.layerTreeRoot().addGroup(group_name)
            rgb = QgsRasterLayer(str(image_path), f"RGB_TEST_LOCKED_{patch_id}", "gdal")
            annotation = QgsVectorLayer(str(annotation_path), f"HUMAN_GROUND_TRUTH_EMPTY_{patch_id}", "ogr")
            if not rgb.isValid() or not annotation.isValid():
                raise RuntimeError(f"QGIS could not read source/template for {patch_id}")
            if (rgb.width(), rgb.height()) != (512, 512) or rgb.crs().authid() != "EPSG:32637":
                raise RuntimeError(f"Unexpected RGB grid for {patch_id}")
            if annotation.featureCount() != 0:
                raise RuntimeError(f"Ground-truth template for {patch_id} must remain empty")
            annotation_layer_info.append({
                "patch_id": patch_id,
                "fields": [field.name() for field in annotation.fields()],
                "provider_capabilities": annotation.dataProvider().capabilitiesString(),
            })
            provider = rgb.dataProvider()
            renderer = QgsMultiBandColorRenderer(provider, 1, 2, 3)
            for band, setter in ((1, renderer.setRedContrastEnhancement),
                                 (2, renderer.setGreenContrastEnhancement),
                                 (3, renderer.setBlueContrastEnhancement)):
                enhancement = QgsContrastEnhancement(provider.dataType(band))
                enhancement.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
                enhancement.setMinimumValue(0); enhancement.setMaximumValue(255)
                setter(enhancement)
            rgb.setRenderer(renderer)
            annotation.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
                "color": "0,190,230,25", "outline_color": "0,180,220,255",
                "outline_width": "0.45", "joinstyle": "round",
            })))
            # Layer tree order is top-first: human polygons above the untouched RGB.
            project.addMapLayer(annotation, False)
            project.addMapLayer(rgb, False)
            group.addLayer(annotation)
            group.addLayer(rgb)
            if first_extent is None:
                first_extent, first_crs = rgb.extent(), rgb.crs()
            bookmark = QgsBookmark()
            bookmark.setName(patch_id)
            bookmark.setGroup("13M TEST LOCKED")
            bookmark.setExtent(QgsReferencedRectangle(rgb.extent(), rgb.crs()))
            bookmarks.append(bookmark)

        for bookmark in bookmarks:
            project.bookmarkManager().addBookmark(bookmark)
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(first_extent, first_crs))
        project.setTitle("GeoRaster - 13M Locked TEST Ground Truth Annotation (NO MODEL OUTPUTS)")
        PROJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not project.write(str(PROJECT_PATH)):
            raise RuntimeError(f"Failed to write QGIS project: {PROJECT_PATH}")

        check = QgsProject.instance()
        if not check.read(str(PROJECT_PATH)):
            raise RuntimeError("Saved 13M project could not be reopened")
        children = {node.name(): node for node in check.layerTreeRoot().children()}
        for name in group_names:
            node = children.get(name)
            if node is None or len(node.children()) != 2:
                raise RuntimeError(f"Saved project group incomplete: {name}")
        layers = list(check.mapLayers().values())
        if len(layers) != 12 or len(check.bookmarkManager().bookmarks()) != 6:
            raise RuntimeError("Saved project has unexpected layer or bookmark count")
        if any("pre_annotations" in lyr.source().lower() or "benchmark_13l" in lyr.source().lower() for lyr in layers):
            raise RuntimeError("Model-prediction layer unexpectedly included in QGIS project")
        print(json.dumps({"project": str(PROJECT_PATH), "patch_count": 6, "groups": len(group_names),
                          "rgb_layers": 6, "empty_human_annotation_layers": 6,
                          "annotation_layer_info": annotation_layer_info,
                          "bookmarks": len(check.bookmarkManager().bookmarks()),
                          "model_prediction_layers": 0, "saved_and_reopened": True}, indent=2))
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
