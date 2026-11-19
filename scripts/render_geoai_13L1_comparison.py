"""Render the fixed 13L comparison from already generated rasters only."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend/data/models/building/experimental/benchmark_13L1"
BASE = ROOT / "backend/data/models/building/experimental/benchmark_13L/outputs"


def main() -> None:
    results = json.loads((OUT / "outputs/whu_geoai/results.json").read_text(encoding="utf-8"))
    cell, label_h = 256, 24
    columns = ["RGB", "MODEL_C (ONNX)", "WHU GeoAI RAW",
               "WHU ORTHOGONALIZED (NOT RUN)", "DIST3 (REJECTED)"]
    sheet = Image.new("RGB", (len(columns) * cell, len(results) * (cell + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    csv_rows = {row["patch_id"]: row for row in csv.DictReader(
        (BASE / "benchmark_results_13L.csv").open(encoding="utf-8-sig"))}
    for row_idx, item in enumerate(results):
        pid = item["patch_id"]
        y = row_idx * (cell + label_h)
        labels = [f"{pid} | RGB",
                  f"{pid} | MODEL_C ({csv_rows[pid]['model_c_polygons']} components)",
                  f"{pid} | WHU GeoAI raw ({item['geoai_whu_polygon_count']} components)",
                  f"{pid} | WHU orthogonalized: NOT RUN",
                  f"{pid} | DIST3: REJECTED, not downloaded"]
        paths = [BASE / "rgb" / f"{pid}.png",
                 BASE / "model_c/overlay" / f"{pid}.png",
                 OUT / "outputs/whu_geoai/overlays" / f"{pid}.png",
                 None, None]
        for col, (path, label) in enumerate(zip(paths, labels)):
            x = col * cell
            draw.text((x + 3, y + 4), label, fill="black")
            if path is not None:
                image = Image.open(path).convert("RGB")
                sheet.paste(image.resize((cell, cell)), (x, y + label_h))
            else:
                draw.rectangle((x, y + label_h, x + cell - 1, y + label_h + cell - 1), fill=(235, 235, 235))
                draw.text((x + 18, y + label_h + 100),
                          "GeoAI runtime dependencies\nnot installed in this\nbenchmark environment"
                          if "orthogonalized" in label else
                          "Unresolved training data\nattribution; model not\ndownloaded or executed",
                          fill=(60, 60, 60), spacing=6)
    target = OUT / "outputs/contact_sheet_13L1.png"
    sheet.save(target)
    print(target)


if __name__ == "__main__":
    main()
