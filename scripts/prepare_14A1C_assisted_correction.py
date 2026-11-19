from __future__ import annotations

import csv
import copy
import json
import re
import shutil
import sqlite3
import subprocess
import tarfile
import uuid
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import shape, mapping, Point, box
from shapely.validation import explain_validity
from shapely import make_valid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision"
ANN = BASE / "annotations"
QA = BASE / "qa"
QGIS = BASE / "qgis"
SRC_GPKG = ANN / "ground_truth_14A.gpkg"
WORK_GPKG = ANN / "ground_truth_layers_14A1C_WORKING.gpkg"
DIAG_GPKG = QA / "14A1C_diagnostics.gpkg"
TMP = ROOT / ".codex_14a1c_tmp"
TMP.mkdir(exist_ok=True)
QA.mkdir(exist_ok=True)

PATCHES = {
    "14A_001_residential": {
        "layer": "14A_001_residential_ground_truth",
        "bounds": (582091.8914781093, 2368001.637367532, 582271.0914781092, 2368180.8373675323),
        "self_points": {"6": (582097.614432917, 2368145.83392099)},
    },
    "14A_003_dense_urban": {
        "layer": "14A_003_dense_urban_ground_truth",
        "bounds": (582091.8914781093, 2367732.8373675323, 582271.0914781092, 2367912.0373675325),
        "self_points": {
            "3": (582156.969647095, 2367823.75954675),
            "8": (582221.559513531, 2367831.16064443),
            "11": (582110.285597831, 2367763.70444503),
            "13": (582189.796602216, 2367884.64835664),
            "15": (582147.529093455, 2367898.43804841),
        },
    },
}
OOB = {
    "14A_001_residential": {"6", "24", "25"},
    "14A_003_dense_urban": {"12", "20", "22"},
}
INVALID = {
    "14A_001_residential": {"6"},
    "14A_003_dense_urban": {"3", "8", "11", "13", "15"},
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def export_geojson(patch: str, out: Path) -> None:
    if out.exists(): out.unlink()
    run([r"C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe", "-f", "GeoJSON", str(out), str(SRC_GPKG), PATCHES[patch]["layer"]])


def copy_working_gpkg() -> None:
    if WORK_GPKG.exists(): WORK_GPKG.unlink()
    src = sqlite3.connect(str(SRC_GPKG))
    dst = sqlite3.connect(str(WORK_GPKG))
    try:
        src.backup(dst)
        dst.commit()
    finally:
        src.close(); dst.close()


def write_geojson(path: Path, features: list[dict], geom_type: str) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "name": path.stem, "crs": {"type": "name", "properties": {"name": "EPSG:32637"}}, "features": features}, indent=2), encoding="utf-8")


def build_diagnostics() -> tuple[int, int, int]:
    invalid_features: list[dict] = []
    oob_features: list[dict] = []
    point_features: list[dict] = []
    suggested: list[dict] = []
    total = 0
    for patch, meta in PATCHES.items():
        src = TMP / f"{patch}.geojson"
        export_geojson(patch, src)
        data = json.loads(src.read_text(encoding="utf-8"))
        patch_box = box(*meta["bounds"])
        for feat in data["features"]:
            bid = str(feat.get("properties", {}).get("building_id", feat.get("id", "")))
            geom = shape(feat["geometry"])
            total += 1
            props = dict(feat.get("properties") or {})
            props.update({"patch_id": patch, "building_id": bid, "source": "ORIGINAL_GT"})
            if bid in INVALID[patch]:
                props.update({"error_type": "INVALID_GEOMETRY;SELF_INTERSECTION", "reason": explain_validity(geom)})
                invalid_features.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
                x, y = meta["self_points"][bid]
                point_features.append({"type": "Feature", "properties": {"patch_id": patch, "building_id": bid, "error_type": "SELF_INTERSECTION", "source": "ORIGINAL_GT"}, "geometry": mapping(Point(x, y))})
            if bid in OOB[patch]:
                props.update({"error_type": "OUT_OF_BOUNDS", "reason": "partially_outside_patch_bounds"})
                oob_features.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
                # Suggested geometry is deliberately kept separate from the working GT.
                # make_valid is used only to create a visual suggestion for invalid OOB input.
                clip_source = make_valid(geom) if not geom.is_valid else geom
                suggested.append({"type": "Feature", "properties": {**props, "source": "SUGGESTED_CLIP_ONLY", "recommended_action": "CLIP_TO_PATCH_BOUNDARY"}, "geometry": mapping(clip_source.intersection(patch_box))})
    inv = TMP / "invalid.geojson"; oob = TMP / "oob.geojson"; pts = TMP / "error_points.geojson"; sug = QA / "14A1C_suggested_clips.geojson"
    write_geojson(inv, invalid_features, "Polygon"); write_geojson(oob, oob_features, "Polygon"); write_geojson(pts, point_features, "Point"); write_geojson(sug, suggested, "Polygon")
    if DIAG_GPKG.exists(): DIAG_GPKG.unlink()
    ogr = r"C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe"
    run([ogr, "-f", "GPKG", str(DIAG_GPKG), str(inv), "-nln", "INVALID_DIAGNOSTIC", "-nlt", "PROMOTE_TO_MULTI", "-a_srs", "EPSG:32637"])
    run([ogr, "-update", "-f", "GPKG", str(DIAG_GPKG), str(oob), "-nln", "OUT_OF_BOUNDS_DIAGNOSTIC", "-nlt", "PROMOTE_TO_MULTI", "-a_srs", "EPSG:32637"])
    run([ogr, "-update", "-f", "GPKG", str(DIAG_GPKG), str(pts), "-nln", "ERROR_POINTS", "-nlt", "POINT", "-a_srs", "EPSG:32637"])
    return total, len(invalid_features), len(oob_features)


def write_csv() -> int:
    rows = []
    for patch in PATCHES:
        for bid in sorted(INVALID[patch] | OOB[patch], key=int):
            # Keep one actionable row per error class so a feature with two
            # problems (14A_001/building 6) is not reduced to a single action.
            if bid in INVALID[patch]:
                rows.append({"patch_id": patch, "feature_id": bid, "building_id": bid, "error_type": "INVALID_GEOMETRY;SELF_INTERSECTION", "recommended_action": "REMOVE_SELF_INTERSECTION", "bookmark_name": f"{patch}__{bid}__SELF_INTERSECTION", "requires_visual_review": "YES"})
            if bid in OOB[patch]:
                rows.append({"patch_id": patch, "feature_id": bid, "building_id": bid, "error_type": "OUT_OF_BOUNDS", "recommended_action": "CLIP_TO_PATCH_BOUNDARY", "bookmark_name": f"{patch}__{bid}__OUT_OF_BOUNDS", "requires_visual_review": "YES"})
    out = QA / "14A1C_manual_correction_list.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return len(rows)


def build_qa_script() -> None:
    p = ROOT / "scripts/qa_14A1C_ground_truth.py"
    p.write_text('''from pathlib import Path\nimport argparse, json, subprocess, tempfile\nfrom shapely.geometry import shape, box\nfrom shapely.wkb import dumps\nimport rasterio\n\nPATCHES={"14A_001_residential": "14A_001_residential_ground_truth", "14A_003_dense_urban": "14A_003_dense_urban_ground_truth"}\nROOT=Path(__file__).resolve().parents[1]\nBASE=ROOT/"backend/data/fine_tuning/buildings/maxar_v2_high_precision"\ndef main():\n ap=argparse.ArgumentParser(); ap.add_argument("--gpkg", default=str(BASE/"annotations/ground_truth_layers_14A1C_WORKING.gpkg")); ap.add_argument("--out", default=str(BASE/"qa/14A1C_post_manual_qa.json")); args=ap.parse_args(); report={"layers":{},"passed":True}\n for patch,layer in PATCHES.items():\n  with tempfile.TemporaryDirectory() as td:\n   gj=Path(td)/"x.geojson"; subprocess.run([r"C:\\Program Files\\PostgreSQL\\17\\bin\\ogr2ogr.exe","-f","GeoJSON",str(gj),args.gpkg,layer],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)\n   fs=json.loads(gj.read_text())["features"]\n  tif=BASE/"images"/(patch+"_v2.tif");\n  with rasterio.open(tif) as r: bounds=box(*r.bounds); crs=str(r.crs); shape_ok=(r.width,r.height)==(512,512)\n  invalid=empty=oob=dups=0; seen=set()\n  for f in fs:\n   g=shape(f["geometry"]); empty += int(g.is_empty or g.area<=0); invalid += int(not g.is_valid); oob += int(not bounds.covers(g)); key=dumps(g,hex=True); dups += int(key in seen); seen.add(key)\n  ok=not any([invalid,empty,oob,dups]) and shape_ok; report["layers"][patch]={"feature_count":len(fs),"invalid":invalid,"empty_or_zero_area":empty,"out_of_bounds":oob,"duplicates":dups,"raster_crs":crs,"mask_shape":shape_ok,"passed":ok}; report["passed"]=report["passed"] and ok\n Path(args.out).write_text(json.dumps(report,indent=2),encoding="utf-8"); print(json.dumps(report,indent=2)); return 0 if report["passed"] else 1\nif __name__=="__main__": raise SystemExit(main())\n''', encoding="utf-8")


def qgs_add_layer(root, template, layer_id, name, source):
    ml = copy.deepcopy(template); ml.set("id", layer_id)
    for child in ml:
        if child.tag == "layername": child.text = name
        elif child.tag == "datasource": child.text = source
    root.find("projectlayers").append(ml)
    return ml


def build_qgis_project() -> int:
    src_qgs = ROOT / ".codex-qgs/14A_building_ground_truth.qgs"
    text = src_qgs.read_text(encoding="utf-8")
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, count=1)
    root = ET.fromstring(text)
    projectlayers = root.find("projectlayers")
    gt_template = next(x for x in projectlayers if x.findtext("layername") == "14A_001_residential_ground_truth")
    for ml in projectlayers:
        ds = ml.find("datasource")
        if ds is not None and "ground_truth_14A.gpkg|layername=" in (ds.text or ""):
            ds.text = ds.text.replace("ground_truth_14A.gpkg", "ground_truth_layers_14A1C_WORKING.gpkg")
    # Update existing tree references to working GT.
    for e in root.iter("layer-tree-layer"):
        src = e.get("source", "")
        if "ground_truth_14A.gpkg" in src: e.set("source", src.replace("ground_truth_14A.gpkg", "ground_truth_layers_14A1C_WORKING.gpkg"))
    diag_defs = [("invalid", "INVALID_DIAGNOSTIC", "INVALID_DIAGNOSTIC"), ("oob", "OUT_OF_BOUNDS_DIAGNOSTIC", "OUT_OF_BOUNDS_DIAGNOSTIC"), ("points", "ERROR_POINTS", "ERROR_POINTS")]
    layer_ids=[]
    for suffix,name,ln in diag_defs:
        lid = f"14A1C_{suffix}_{uuid.uuid4().hex[:8]}"; layer_ids.append((lid,name))
        qgs_add_layer(root, gt_template, lid, name, f"../qa/14A1C_diagnostics.gpkg|layername={ln}")
    tree = root.find("layer-tree-group")
    group = ET.Element("layer-tree-group", {"name":"14A1C_CORRECTION_DIAGNOSTICS", "checked":"Qt::Checked", "expanded":"1", "groupLayer":""})
    for lid,name in layer_ids:
        ET.SubElement(group, "layer-tree-layer", {"id":lid, "name":name, "checked":"Qt::Checked", "expanded":"1", "source":f"../qa/14A1C_diagnostics.gpkg|layername={name}", "providerKey":"ogr"})
    tree.append(group)
    legend = root.find("legend")
    lg = ET.SubElement(legend, "legendgroup", {"name":"14A1C_CORRECTION_DIAGNOSTICS", "open":"true"})
    for lid,name in layer_ids: ET.SubElement(lg, "legendlayer", {"name":name, "checked":"Qt::Checked", "open":"true", "id":lid})
    bm = root.find("Bookmarks")
    if bm is None: bm = ET.SubElement(root, "Bookmarks")
    for patch in PATCHES:
        for bid in sorted(INVALID[patch] | OOB[patch], key=int):
            kind = "SELF_INTERSECTION" if bid in INVALID[patch] else "OUT_OF_BOUNDS"
            b = ET.SubElement(bm, "Bookmark", {"id":uuid.uuid4().hex, "name":f"{patch}__{bid}__{kind}", "group":"14A1C_ASSISTED_CORRECTION"})
            x1,y1,x2,y2 = PATCHES[patch]["bounds"]
            ET.SubElement(b,"extent",{"xmin":str(x1),"ymin":str(y1),"xmax":str(x2),"ymax":str(y2)})
            ET.SubElement(b,"spatialrefsys",{"authid":"EPSG:32637"})
    out_qgs = TMP / "14A1C_ground_truth_FIX.qgs"
    ET.ElementTree(root).write(out_qgs, encoding="utf-8", xml_declaration=True)
    out_qgz = QGIS / "14A1C_ground_truth_FIX.qgz"
    if out_qgz.exists(): out_qgz.unlink()
    shutil.copy(ROOT / ".codex-qgs/JDdLfu_styles.db", TMP / "JDdLfu_styles.db")
    with tarfile.open(out_qgz, "w:gz") as tf:
        tf.add(out_qgs, arcname="14A1C_ground_truth_FIX.qgs")
        tf.add(TMP / "JDdLfu_styles.db", arcname="JDdLfu_styles.db")
    return len(layer_ids)


def main():
    copy_working_gpkg()
    total, invalid, oob = build_diagnostics()
    rows = write_csv(); build_qa_script(); layers = build_qgis_project()
    print(json.dumps({"total":total,"invalid":invalid,"oob":oob,"unique_problem_features":rows,"diagnostic_layers":layers,"working_gpkg":str(WORK_GPKG),"qgz":str(QGIS/"14A1C_ground_truth_FIX.qgz")}, indent=2))

if __name__ == "__main__": main()
