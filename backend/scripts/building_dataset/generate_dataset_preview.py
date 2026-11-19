"""Generate small RGB/mask contact previews for georaster_building_v1."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw


def generate_preview(dataset: Path, *, count: int = 20, seed: int = 42) -> list[str]:
    manifest_path = dataset / "metadata" / "dataset_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = list(payload.get("records", []))
    random.Random(seed).shuffle(records)
    output = dataset / "metadata" / "previews"
    output.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for item in records[:count]:
        with rasterio.open(dataset / item["image_path"]) as image_src:
            rgb = np.moveaxis(image_src.read((1, 2, 3)), 0, -1)
        with rasterio.open(dataset / item["mask_path"]) as mask_src:
            mask = mask_src.read(1)
        rgb = np.clip(rgb, 0, 255).astype(np.uint8, copy=False)
        base = Image.fromarray(rgb, mode="RGB").convert("RGBA")
        overlay = Image.new("RGBA", base.size, (220, 0, 0, 0))
        alpha = Image.fromarray(np.where(mask == 255, 110, 0).astype(np.uint8), mode="L")
        overlay.putalpha(alpha)
        result = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(result)
        draw.rectangle((0, 0, result.width - 1, result.height - 1), outline=(0, 255, 0, 255), width=2)
        target = output / f"{item['tile_id']}.png"
        result.save(target)
        written.append(str(target))
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps({"previews": generate_preview(args.dataset, count=args.count, seed=args.seed)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
