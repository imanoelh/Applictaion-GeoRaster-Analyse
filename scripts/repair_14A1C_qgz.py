from __future__ import annotations

import copy
import re
import shutil
import tarfile
import uuid
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "backend/data/fine_tuning/buildings/maxar_v2_high_precision"
QGIS = BASE / "qgis"
OLD = QGIS / "14A1C_ground_truth_FIX.qgz"
OUT = QGIS / "14A1C_ground_truth_FIX_REBUILT.qgz"
TMP = ROOT / ".codex_14a1c_rebuild"


def option(parent, name: str, value: str) -> None:
    for o in parent.findall("Option"):
        if o.get("name") == name:
            o.set("value", value)
            return
    ET.SubElement(parent, "Option", {"type": "QString", "name": name, "value": value})


def set_fill_style(maplayer, fill: str, outline: str, alpha: str = "80") -> None:
    renderer = maplayer.find("renderer-v2")
    if renderer is None:
        return
    for layer in renderer.findall(".//layer"):
        if layer.get("class") == "SimpleFill":
            opts = layer.find("Option")
            if opts is not None:
                option(opts, "color", f"{fill},{alpha},rgb:{int(fill.split(',')[0])/255},{int(fill.split(',')[1])/255},{int(fill.split(',')[2])/255},{int(alpha)/255}")
                option(opts, "outline_color", f"{outline},255,rgb:{int(outline.split(',')[0])/255},{int(outline.split(',')[1])/255},{int(outline.split(',')[2])/255},1")
                option(opts, "outline_width", "0.8")


def set_point_style(maplayer) -> None:
    old = maplayer.find("renderer-v2")
    if old is None:
        return
    renderer = ET.Element("renderer-v2", {"type": "singleSymbol", "referencescale": "-1", "forceraster": "0", "enableorderby": "0", "symbollevels": "0"})
    symbols = ET.SubElement(renderer, "symbols")
    symbol = ET.SubElement(symbols, "symbol", {"type": "marker", "name": "0", "alpha": "1", "clip_to_extent": "1", "force_rhr": "0", "is_animated": "0", "frame_rate": "10"})
    data = ET.SubElement(symbol, "data_defined_properties"); ET.SubElement(data, "Option", {"type": "Map"})
    lyr = ET.SubElement(symbol, "layer", {"class": "SimpleMarker", "pass": "0", "locked": "0", "enabled": "1"})
    opts = ET.SubElement(lyr, "Option", {"type": "Map"})
    option(opts, "color", "255,0,0,255,rgb:1,0,0,1"); option(opts, "outline_color", "120,0,0,255,rgb:0.47,0,0,1"); option(opts, "size", "4"); option(opts, "name", "circle")
    maplayer.remove(old); maplayer.insert(list(maplayer).index(maplayer.find("blendMode")) if maplayer.find("blendMode") is not None else len(list(maplayer)), renderer)


def main() -> None:
    if TMP.exists(): shutil.rmtree(TMP)
    TMP.mkdir()
    # The old file is intentionally retained. It is a gzip tar, not a ZIP/QGZ.
    with tarfile.open(OLD, "r:gz") as tf:
        tf.extractall(TMP)
    qgs = TMP / "14A1C_ground_truth_FIX.qgs"
    raw = qgs.read_text(encoding="utf-8")
    raw = re.sub(r"<!DOCTYPE[^>]*>", "", raw, count=1)
    root = ET.fromstring(raw)
    for ml in root.findall("./projectlayers/maplayer"):
        name = ml.findtext("layername", "")
        if name in {"INVALID_DIAGNOSTIC", "OUT_OF_BOUNDS_DIAGNOSTIC", "ERROR_POINTS"}:
            id_node = ml.find("id")
            if id_node is None:
                id_node = ET.SubElement(ml, "id")
            id_node.text = f"14A1C_{name}_{uuid.uuid4().hex}"
            ml.attrib.pop("id", None)
        if name.endswith("_ground_truth"):
            set_fill_style(ml, "0,255,0", "0,128,0", "40")
        elif name == "INVALID_DIAGNOSTIC":
            set_fill_style(ml, "255,0,0", "220,0,0", "70")
        elif name == "OUT_OF_BOUNDS_DIAGNOSTIC":
            set_fill_style(ml, "255,165,0", "220,110,0", "80")
        elif name == "ERROR_POINTS":
            set_point_style(ml)
        elif "MODEL_C_PSEUDO_MASK" in name:
            op = ml.find("layerOpacity")
            if op is None: op = ET.SubElement(ml, "layerOpacity")
            op.text = "0.45"
            pipe = ml.find("pipe/rasterrenderer")
            if pipe is not None:
                pipe.set("opacity", "0.45")
                pipe.set("type", "singlebandpseudocolor")
                pipe.set("band", "1")
                for child in list(pipe):
                    pipe.remove(child)
                colorramp = ET.SubElement(pipe, "rastershader")
                ramp = ET.SubElement(colorramp, "colorrampShader", {"classificationMode": "1", "clip": "0", "colorRampType": "INTERPOLATED", "minimumValue": "0", "maximumValue": "1"})
                ET.SubElement(ramp, "item", {"label": "0", "value": "0", "color": "255,255,255,0"})
                ET.SubElement(ramp, "item", {"label": "1", "value": "1", "color": "170,0,255,180"})
    out_qgs = TMP / "project.qgs"
    ET.ElementTree(root).write(out_qgs, encoding="utf-8", xml_declaration=True)
    if OUT.exists(): OUT.unlink()
    styles = TMP / "JDdLfu_styles.db"
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out_qgs, "project.qgs")
        if styles.exists(): z.write(styles, "JDdLfu_styles.db")
    shutil.rmtree(TMP)
    print(OUT)


if __name__ == "__main__":
    main()
