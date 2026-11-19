from __future__ import annotations

import csv
import shutil
from pathlib import Path

from qgis.core import QgsApplication, QgsProject, QgsBookmark, QgsRectangle, QgsReferencedRectangle

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision"
SRC = BASE / "qgis/14A1C_ground_truth_FIX_REBUILT.qgz"
OUT = BASE / "qgis/14A1C_ground_truth_FIX_REBUILT_V2.qgz"
CSV = BASE / "qa/14A1C_manual_correction_list.csv"

app = QgsApplication([], False)
app.initQgis()
project = QgsProject.instance()
if not project.read(str(SRC)):
    raise RuntimeError(project.error())

manager = project.bookmarkManager()
for bookmark in list(manager.bookmarks()):
    if bookmark.name().startswith("14A_003_dense_urban__"):
        manager.removeBookmark(bookmark.id())

gt = project.mapLayersByName("14A_003_dense_urban_ground_truth")[0]
rgb = project.mapLayersByName("14A_003_dense_urban_RGB")[0]
tree_layer = project.layerTreeRoot().findLayer(rgb.id())
if tree_layer is not None and not tree_layer.isVisible():
    tree_layer.setItemVisibilityChecked(True)

added = 0
for row in csv.DictReader(CSV.open(encoding="utf-8")):
    if row["patch_id"] != "14A_003_dense_urban":
        continue
    building_id = row["building_id"]
    feature = next((f for f in gt.getFeatures() if str(f["building_id"]) == building_id), None)
    if feature is None:
        raise RuntimeError(f"Missing building_id={building_id}")
    bounds = feature.geometry().boundingBox()
    margin = max(bounds.width(), bounds.height(), 1.0) * 0.50
    extent = QgsRectangle(bounds.xMinimum() - margin, bounds.yMinimum() - margin, bounds.xMaximum() + margin, bounds.yMaximum() + margin)
    bookmark = QgsBookmark()
    bookmark.setName(row["bookmark_name"])
    bookmark.setGroup("14A1C_ASSISTED_CORRECTION")
    bookmark.setExtent(QgsReferencedRectangle(extent, project.crs()))
    manager.addBookmark(bookmark)
    added += 1

if added != 8:
    raise RuntimeError(f"Expected 8 14A_003 bookmarks, got {added}")
if OUT.exists():
    OUT.unlink()
if not project.write(str(OUT)):
    raise RuntimeError("Failed to write V2 project")

project.clear()
if not project.read(str(OUT)):
    raise RuntimeError(project.error())
names = {b.name() for b in project.bookmarkManager().bookmarks()}
expected = {row["bookmark_name"] for row in csv.DictReader(CSV.open(encoding="utf-8")) if row["patch_id"] == "14A_003_dense_urban"}
assert expected <= names
assert project.crs().authid() == "EPSG:32637"
assert len(project.mapLayersByName("14A_003_dense_urban_RGB")) == 1
assert project.mapLayersByName("14A_003_dense_urban_RGB")[0].isValid()
assert project.mapLayersByName("14A_003_dense_urban_ground_truth")[0].isValid()
print("PROJECT_READ=SUCCESS")
print("BOOKMARKS_REPAIRED=", len(expected))
print("TOTAL_BOOKMARKS=", len(project.bookmarkManager().bookmarks()))
print("CRS=", project.crs().authid())
app.exitQgis()
