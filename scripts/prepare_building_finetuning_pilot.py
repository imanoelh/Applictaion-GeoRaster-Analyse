"""Prepare an annotation-ready pilot from the reviewed Maxar patch catalog.

This utility copies RGB patches and empty human-annotation GeoJSON templates.
It deliberately does not create masks or use model predictions as labels.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.enums import ColorInterp
from rasterio.windows import Window


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "test-data/building-ground-truth/patch_catalog.json"
OUT = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
QA = OUT / "metadata/visual_qa"


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for folder in ("images", "masks", "geojson", "metadata", "splits"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for year, year_data in catalog["dates"].items():
        for item in year_data["patches"]:
            patch_id = item["patch_id"]
            source_raster = ROOT / item["source_raster"].replace("\\", "/")
            source_geojson = ROOT / item["annotation_file"].replace("\\", "/")
            image_path = OUT / "images" / f"{patch_id}.tif"
            geojson_path = OUT / "geojson" / f"{patch_id}.geojson"
            w = item["window"]
            window = Window(w["col_off"], w["row_off"], w["width"], w["height"])
            with rasterio.open(source_raster) as src:
                if (src.width, src.height) != (2048, 2048) or src.count < 3:
                    raise ValueError(f"Unexpected source raster: {source_raster}")
                data = src.read((1, 2, 3), window=window)
                profile = src.profile.copy()
                profile.update(width=512, height=512, count=3, transform=src.window_transform(window),
                               compress="deflate", predictor=2)
                with rasterio.open(image_path, "w", **profile) as dst:
                    dst.write(data)
                    dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
            geojson_path.write_bytes(source_geojson.read_bytes())

            with rasterio.open(image_path) as ds:
                bounds = [float(v) for v in ds.bounds]
                crs = f"EPSG:{ds.crs.to_epsg()}" if ds.crs and ds.crs.to_epsg() else ds.crs.to_string() if ds.crs else None
                resolution = [float(v) for v in ds.res]
                rgb = np.moveaxis(ds.read((1, 2, 3)), 0, -1)
                if (ds.width, ds.height, ds.count) != (512, 512, 3):
                    raise ValueError(f"Unexpected patch shape/bands: {patch_id}")
                if ds.colorinterp[:3] != (ColorInterp.red, ColorInterp.green, ColorInterp.blue):
                    raise ValueError(f"Image bands not marked RGB: {patch_id}")

            split = "val" if item["split"].lower() == "validation" else item["split"].lower()
            metadata = {
                "patch_id": patch_id,
                "source_raster": item["source_raster"],
                "source_date": year,
                "bounds": bounds,
                "crs": crs,
                "resolution": resolution,
                "width": 512,
                "height": 512,
                "context_proposal": item.get("context"),
                "context_status": item.get("context_status", "PROPOSED_REVIEW_REQUIRED"),
                "split": split,
                "spatial_group": f"x{item['window']['col_off']}_y{item['window']['row_off']}",
                "building_count": None,
                "annotator": None,
                "annotation_status": "NOT_ANNOTATED",
                "image": f"images/{patch_id}.tif",
                "mask": None,
                "geojson": f"geojson/{patch_id}.geojson",
                "source_ground_truth_template": str(source_geojson.relative_to(ROOT)).replace("\\", "/"),
                "mask_note": "No mask is created until human annotation is reviewed.",
            }
            (OUT / "metadata" / f"{patch_id}.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            rows.append({"id": patch_id, "split": split, "image": rgb,
                         "context": item.get("context", "context review pending")})

    # Candidate lists are spatially grouped according to the catalog: the same
    # footprint in 2024 and 2025 always belongs to the same split.
    for split in ("train", "val", "test"):
        names = sorted(row["id"] for row in rows if row["split"] == split)
        (OUT / "splits" / f"{split}.txt").write_text("".join(f"{name}\n" for name in names), encoding="utf-8")

    make_sheet(rows, QA / "images_contact_sheet.jpg", "RGB IMAGE PATCHES — inspect context before annotation")
    make_sheet(rows, QA / "overlay_contact_sheet.jpg", "ANNOTATION OVERLAY — none yet; empty templates are not masks", stamp="ANNOTATION PENDING")
    make_sheet(rows, QA / "contours_contact_sheet.jpg", "BUILDING CONTOURS — human review required", stamp="NO HUMAN CONTOURS")
    print(f"Prepared {len(rows)} image patches; masks intentionally absent.")


def make_sheet(rows: list[dict], path: Path, title: str, stamp: str | None = None) -> None:
    columns, cell_w, cell_h, label_h = 4, 240, 190, 32
    page = Image.new("RGB", (columns * cell_w, 48 + ((len(rows) + columns - 1) // columns) * (cell_h + label_h)), "white")
    draw = ImageDraw.Draw(page)
    draw.text((12, 12), title, fill="black")
    for i, row in enumerate(sorted(rows, key=lambda x: x["id"])):
        x, y = (i % columns) * cell_w, 48 + (i // columns) * (cell_h + label_h)
        im = Image.fromarray(row["image"]).resize((cell_w, cell_h))
        page.paste(im, (x, y))
        if stamp:
            draw.rectangle((x, y + cell_h - 24, x + cell_w, y + cell_h), fill=(245, 190, 80))
            draw.text((x + 5, y + cell_h - 20), stamp, fill=(30, 20, 10))
        draw.text((x + 4, y + cell_h + 5), f"{row['id']} | {row['split'].upper()}", fill="black")
    page.save(path, quality=90)


if __name__ == "__main__":
    main()
