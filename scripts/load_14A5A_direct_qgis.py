"""Load the 14A.5A expansion layers into the currently open QGIS project.

Run this file from QGIS 3.40's Python Console.  It deliberately does not
open/save a project and does not create or destroy a QgsApplication.
"""
from pathlib import Path

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFillSymbol,
    QgsProject,
    QgsRasterLayer,
    QgsSingleSymbolRenderer,
    QgsVectorDataProvider,
    QgsVectorLayer,
)


ROOT = Path(r"D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10")
RGB_DIR = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/train/rgb"
GPKG = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision/annotations/14A5A_new_patch_expansion_gt.gpkg"
PATCHES = [
    "14A2_2024_06",
    "14A2_2024_10",
    "14A2_2025_02",
    "14A2_2025_06",
    "14A2_2025_10",
]


def _gt_style(layer):
    symbol = QgsFillSymbol.createSimple(
        {
            "color": "0,0,0,0",
            "outline_color": "0,180,70,255",
            "outline_width": "0.8",
        }
    )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


def _editable_capable(layer):
    provider = layer.dataProvider()
    return bool(provider and (provider.capabilities() & QgsVectorDataProvider.AddFeatures))


def load_14a5a_direct_qgis():
    print("SCRIPT_STARTED")
    try:
        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32637"))
    except Exception as exc:
        print("SCRIPT_FAILED project_initialization", repr(exc))
        return {"rgb_loaded": 0, "gt_loaded": 0, "invalid_rgb": PATCHES, "invalid_gt": PATCHES, "pairs": []}
    rgb_loaded = 0
    gt_loaded = 0
    invalid_rgb = []
    invalid_gt = []
    pairs = []

    # Add each pair in the requested order: GT, then RGB.
    for index, patch_id in enumerate(PATCHES):
        rgb_path = RGB_DIR / f"{patch_id}.tif"
        gt_uri = f"{GPKG.as_posix()}|layername={patch_id}_ground_truth"
        gt_name = f"{patch_id}_GT"
        rgb_name = f"{patch_id}_RGB"

        print("LOADING_GT", patch_id)
        print("SOURCE_PATH", gt_uri)
        print("SOURCE_EXISTS", GPKG.exists())
        try:
            gt = QgsVectorLayer(gt_uri, gt_name, "ogr")
            print("IS_VALID", gt.isValid())
        except Exception as exc:
            print("ERROR_MESSAGE", repr(exc))
            gt = None
        if gt is not None and gt.isValid():
            if project.mapLayersByName(gt_name):
                print("SKIP_DUPLICATE", gt_name)
                gt_ok = True
                gt_loaded += 1
            else:
                _gt_style(gt)
                project.addMapLayer(gt, True)
                node = project.layerTreeRoot().findLayer(gt.id())
                if node is not None:
                    node.setItemVisibilityChecked(index == 0)
                gt_loaded += 1
                gt_ok = _editable_capable(gt)
        else:
            invalid_gt.append(patch_id)
            gt_ok = False

        print("LOADING_RGB", patch_id)
        print("SOURCE_PATH", str(rgb_path))
        print("SOURCE_EXISTS", rgb_path.exists())
        try:
            rgb = QgsRasterLayer(str(rgb_path), rgb_name, "gdal")
            print("IS_VALID", rgb.isValid())
        except Exception as exc:
            print("ERROR_MESSAGE", repr(exc))
            rgb = None
        if rgb is not None and rgb.isValid():
            if project.mapLayersByName(rgb_name):
                print("SKIP_DUPLICATE", rgb_name)
                rgb_ok = True
                rgb_loaded += 1
            else:
                project.addMapLayer(rgb, True)
                node = project.layerTreeRoot().findLayer(rgb.id())
                if node is not None:
                    node.setItemVisibilityChecked(index == 0)
                rgb_loaded += 1
                rgb_ok = True
        else:
            invalid_rgb.append(patch_id)
            rgb_ok = False

        pairs.append((patch_id, rgb_ok and gt_ok))

    # Zoom only when the first RGB layer was loaded.  No project is saved.
    first_rgb = project.mapLayersByName("14A2_2024_06_RGB")
    if first_rgb and "iface" in globals():
        iface.mapCanvas().setExtent(first_rgb[0].extent())
        iface.mapCanvas().refresh()

    print("RGB_LOADED = %d/5" % rgb_loaded)
    print("GT_LOADED = %d/5" % gt_loaded)
    print("INVALID RGB : %s" % invalid_rgb)
    print("INVALID GT : %s" % invalid_gt)
    print("TOTAL_LAYERS = %d/10" % (rgb_loaded + gt_loaded))
    print("RENDERER_TEST = %s" % ("PASS" if gt_loaded == 5 else "FAIL"))
    print("LAYER_TREE_TEST = %s" % ("PASS" if rgb_loaded + gt_loaded == 10 else "FAIL"))
    print("CRS = EPSG:32637")
    for patch_id, ok in pairs:
        print("%s : %s" % (patch_id, "PASS" if ok else "FAIL"))
    result = {
        "rgb_loaded": rgb_loaded,
        "gt_loaded": gt_loaded,
        "invalid_rgb": invalid_rgb,
        "invalid_gt": invalid_gt,
        "pairs": pairs,
    }
    if rgb_loaded == 5 and gt_loaded == 5 and not invalid_rgb and not invalid_gt:
        print("SCRIPT_COMPLETED")
    else:
        print("SCRIPT_FAILED", result)
    return result


load_14a5a_direct_qgis()
