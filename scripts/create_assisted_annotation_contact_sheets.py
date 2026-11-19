"""Build split-wise visual review sheets: RGB, AI proposal, human labels, mask."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.features import rasterize
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"


def paint(rgb: np.ndarray, binary: np.ndarray, color: tuple[int, int, int], alpha: int = 110) -> Image.Image:
    base = Image.fromarray(rgb).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay.putdata([(color[0], color[1], color[2], alpha if v else 0) for v in binary.reshape(-1)])
    return Image.alpha_composite(base, overlay).convert("RGB")


def read_fc(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"features": []}


def main() -> None:
    out = DATA / "metadata/visual_qa_13k1b"
    out.mkdir(parents=True, exist_ok=True)
    metas = []
    for p in sorted((DATA / "metadata").glob("GT_*.json")):
        metas.append(json.loads(p.read_text(encoding="utf-8")))
    for split in ("train", "val", "test"):
        selected = [m for m in metas if m["split"] == split]
        cw, ch, header, footer, cols = 145, 145, 30, 28, 4
        page = Image.new("RGB", (cols * cw, header + len(selected) * (ch + footer)), "white")
        draw = ImageDraw.Draw(page)
        for i, title in enumerate(("RGB", "MODEL_C PRE-ANNOTATION", "HUMAN FINAL", "BINARY MASK")):
            draw.text((i * cw + 3, 9), title, fill="black")
        for row, m in enumerate(sorted(selected, key=lambda x: x["patch_id"])):
            pid = m["patch_id"]
            y = header + row * (ch + footer)
            image_path = DATA / m["image"]
            with rasterio.open(image_path) as src:
                rgb = np.moveaxis(src.read((1, 2, 3)), 0, -1)
                transform, height, width = src.transform, src.height, src.width
            base = Image.fromarray(rgb).resize((cw, ch))
            page.paste(base, (0, y))

            pre_path = DATA / "pre_annotations" / f"{pid}_model_c.geojson"
            pre = read_fc(pre_path)
            pre_geoms = [f["geometry"] for f in pre.get("features", []) if f.get("geometry")]
            if pre_geoms:
                arr = rasterize([(shape(g), 1) for g in pre_geoms], out_shape=(height, width), transform=transform,
                                fill=0, all_touched=False, dtype="uint8")
                pre_image = paint(rgb, arr, (255, 36, 36)).resize((cw, ch))
            else:
                pre_image = base.copy()
            page.paste(pre_image, (cw, y))

            human = read_fc(DATA / "annotations" / f"{pid}.geojson")
            human_geoms = [f["geometry"] for f in human.get("features", []) if f.get("geometry")]
            if human_geoms:
                arr = rasterize([(shape(g), 1) for g in human_geoms], out_shape=(height, width), transform=transform,
                                fill=0, all_touched=False, dtype="uint8")
                human_image = paint(rgb, arr, (32, 90, 255)).resize((cw, ch))
            else:
                human_image = base.copy()
            page.paste(human_image, (2 * cw, y))

            mask_ref = m.get("mask")
            mask_path = DATA / mask_ref if mask_ref else None
            if mask_path and mask_path.is_file():
                with rasterio.open(mask_path) as src:
                    arr = src.read(1)
                mask_image = paint(rgb, arr, (0, 225, 65)).resize((cw, ch))
            else:
                mask_image = base.copy()
            page.paste(mask_image, (3 * cw, y))
            draw.text((2, y + ch + 5), f"{pid} | {len(pre_geoms)} candidates | {m.get('review_status', 'NOT_REVIEWED')}", fill="black")
            if not pre_geoms:
                draw.text((cw + 20, y + ch // 2), "0 candidates", fill=(200, 0, 0))
            if not human_geoms:
                draw.text((2 * cw + 24, y + ch // 2), "not annotated", fill=(200, 0, 0))
            if not mask_path or not mask_path.is_file():
                draw.text((3 * cw + 30, y + ch // 2), "no validated mask", fill=(200, 0, 0))
        page.save(out / f"{split}_rgb_preannotation_final_mask.jpg", quality=91)


if __name__ == "__main__":
    main()
