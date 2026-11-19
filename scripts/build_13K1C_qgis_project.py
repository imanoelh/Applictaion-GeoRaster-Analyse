"""Create the QGIS assisted-review project for the fixed 13K.1C pilot."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsBookmark,
    QgsContrastEnhancement,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsFillSymbol,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsReferencedRectangle,
    QgsRasterLayer,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
    QgsVectorDataProvider,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
PROJECT_PATH = DATA / "qgis/13K1C_assisted_review.qgz"
PILOT = [
    ("01_DENSE", "GT_2024_residential_02", 36),
    ("02_MEDIUM", "GT_2024_dense_02", 15),
    ("03_ZERO_CANDIDATE", "GT_2024_difficult_01", 0),
]
QGIS_PREFIX = Path(r"C:\Program Files\QGIS 3.40.14\apps\qgis-ltr")


def main() -> None:
    if not QGIS_PREFIX.is_dir():
        raise SystemExit(f"QGIS_PREFIX_PATH missing: {QGIS_PREFIX}")
    QgsApplication.setPrefixPath(str(QGIS_PREFIX), True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        priority_path = DATA / "metadata/review_priority.csv"
        with priority_path.open(encoding="utf-8-sig", newline="") as stream:
            priority = {row["patch_id"]: row for row in csv.DictReader(stream)}

        project = QgsProject.instance()
        project.clear()
        project.setTitle("GeoRaster — 13K.1C Assisted Review Pilot")
        first_extent = None
        first_crs = None
        bookmarks = []

        for group_name, patch_id, expected_count in PILOT:
            if patch_id not in priority or int(priority[patch_id]["candidate_count"]) != expected_count:
                raise RuntimeError(f"Pilot selection/count mismatch for {patch_id}")

            metadata_path = DATA / f"metadata/{patch_id}.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            image_path = DATA / metadata["image"]
            review_path = DATA / f"review/{patch_id}_review.geojson"
            if not image_path.is_file() or not review_path.is_file():
                raise FileNotFoundError(f"Missing RGB or review GeoJSON for {patch_id}")

            group = project.layerTreeRoot().addGroup(group_name)
            rgb = QgsRasterLayer(str(image_path), f"PATCH_RGB — {patch_id}", "gdal")
            review = QgsVectorLayer(str(review_path), f"REVIEW_BUILDINGS — {patch_id}", "ogr")
            if not rgb.isValid() or not review.isValid():
                raise RuntimeError(f"QGIS could not load RGB/review layer for {patch_id}")
            if (rgb.width(), rgb.height()) != (512, 512):
                raise RuntimeError(f"RGB dimensions are not 512x512 for {patch_id}")
            if rgb.crs().authid() != metadata["crs"]:
                raise RuntimeError(f"RGB CRS does not match metadata for {patch_id}")

            extent = rgb.extent()
            expected_bounds = metadata["bounds"]
            actual_bounds = [extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()]
            if any(abs(a - b) > 1e-6 for a, b in zip(actual_bounds, expected_bounds)):
                raise RuntimeError(f"RGB bounds mismatch for {patch_id}: {actual_bounds}")
            provider_capabilities = review.dataProvider().capabilities()
            edit_capabilities = {
                "change_attributes": QgsVectorDataProvider.ChangeAttributeValues,
                "change_geometry": QgsVectorDataProvider.ChangeGeometries,
                "add_features": QgsVectorDataProvider.AddFeatures,
                "delete_features": QgsVectorDataProvider.DeleteFeatures,
            }
            missing_capabilities = [name for name, flag in edit_capabilities.items()
                                    if not provider_capabilities & flag]
            if missing_capabilities:
                raise RuntimeError(f"Review layer editing is incomplete for {patch_id}: {missing_capabilities}")

            provider = rgb.dataProvider()
            renderer = QgsMultiBandColorRenderer(provider, 1, 2, 3)
            for band, setter in ((1, renderer.setRedContrastEnhancement),
                                 (2, renderer.setGreenContrastEnhancement),
                                 (3, renderer.setBlueContrastEnhancement)):
                enhancement = QgsContrastEnhancement(provider.dataType(band))
                enhancement.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
                enhancement.setMinimumValue(0)
                enhancement.setMaximumValue(255)
                setter(enhancement)
            rgb.setRenderer(renderer)

            review.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
                "color": "255,35,35,32",
                "outline_color": "255,35,35,255",
                "outline_width": "0.55",
                "joinstyle": "round",
            })))
            fields = {review.fields().at(i).name(): i for i in range(review.fields().count())}
            if "review_status" in fields:
                review.setEditorWidgetSetup(fields["review_status"], QgsEditorWidgetSetup(
                    "ValueMap", {"map": [
                        {"NOT_REVIEWED": "NOT_REVIEWED"},
                        {"IN_REVIEW": "IN_REVIEW"},
                        {"REVIEWED": "REVIEWED"},
                        {"VALIDATED": "VALIDATED"},
                    ]},
                ))
            aliases = {
                "building_id": "building_id",
                "source": "source",
                "review_status": "review_status",
                "confidence_mean": "confidence_mean",
                "area_m2": "area_m2",
            }
            for name, alias in aliases.items():
                if name in fields:
                    review.setFieldAlias(fields[name], alias)
            new_feature_defaults = {
                "building_id": f"concat('{patch_id}_MANUAL_', uuid())",
                "patch_id": f"'{patch_id}'",
                "date": f"'{metadata['source_date']}'",
                "source": "'MANUAL_ADDITION'",
                "review_status": "'NOT_REVIEWED'",
                "area_m2": "round($area, 2)",
            }
            for name, expression in new_feature_defaults.items():
                if name in fields:
                    review.setDefaultValueDefinition(fields[name], QgsDefaultValue(expression, False))
            # REVIEW_BUILDINGS is above PATCH_RGB in the drawing stack.
            project.addMapLayer(review, False)
            project.addMapLayer(rgb, False)
            group.addLayer(review)
            group.addLayer(rgb)

            if first_extent is None:
                first_extent, first_crs = extent, rgb.crs()
            bookmark = QgsBookmark()
            bookmark.setName(group_name)
            bookmark.setGroup("13K.1C Pilot")
            bookmark.setExtent(QgsReferencedRectangle(extent, rgb.crs()))
            bookmarks.append(bookmark)

        for bookmark in bookmarks:
            project.bookmarkManager().addBookmark(bookmark)
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(first_extent, first_crs))
        PROJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not project.write(str(PROJECT_PATH)):
            raise RuntimeError(f"Failed to write QGIS project: {PROJECT_PATH}")

        # Re-open the saved artifact and verify the expected group/layer structure.
        check = QgsProject.instance()
        if not check.read(str(PROJECT_PATH)):
            raise RuntimeError("Saved QGIS project could not be reopened")
        root_children = {node.name(): node for node in check.layerTreeRoot().children()}
        for group_name, _, _ in PILOT:
            group = root_children.get(group_name)
            if group is None or len(group.children()) != 2:
                raise RuntimeError(f"Saved project is missing the expected group/layers: {group_name}")
        if len(check.bookmarkManager().bookmarks()) != 3:
            raise RuntimeError("Saved project does not contain all three bookmarks")
        print(json.dumps({
            "project": str(PROJECT_PATH), "groups": [x[0] for x in PILOT],
            "patches": [{"patch_id": pid, "candidate_count": count,
                         "rgb": True, "review_layer": True, "editable": True,
                         "editing_operations": ["add_vertices", "move_vertices", "delete_features",
                                                "create_features", "change_geometry", "change_attributes"]}
                        for _, pid, count in PILOT],
            "bookmarks": len(check.bookmarkManager().bookmarks()),
            "first_patch_zoom": PILOT[0][1], "saved_and_reopened": True,
        }, indent=2))
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
