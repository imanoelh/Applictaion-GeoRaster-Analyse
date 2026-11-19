"""Validate annotation-ready building patches and any human labels supplied."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("backend/data/fine_tuning/buildings/maxar_v1"))
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()
    root = args.dataset.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    entries = []
    for p in sorted((root / "metadata").glob("*.json")):
        try:
            if "patch_id" in json.loads(p.read_text(encoding="utf-8")):
                entries.append(p)
        except (OSError, json.JSONDecodeError):
            continue
    groups: dict[str, str] = {}
    extents: list[tuple[str, str, list[float]]] = []
    mask_count = 0
    reviewed_count = 0

    for meta_path in entries:
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        pid = m["patch_id"]
        image_path = root / m["image"]
        if not image_path.is_file():
            errors.append(f"{pid}: missing image")
            continue
        with rasterio.open(image_path) as image:
            if (image.width, image.height, image.count) != (512, 512, 3):
                errors.append(f"{pid}: image must be 512x512 RGB")
            if image.crs is None or image.crs.to_string() != m["crs"]:
                errors.append(f"{pid}: image CRS mismatch")
            if not np.allclose(image.bounds, m["bounds"], atol=1e-7):
                errors.append(f"{pid}: image bounds mismatch")
            if image.colorinterp[:3] != (rasterio.enums.ColorInterp.red,
                                         rasterio.enums.ColorInterp.green,
                                         rasterio.enums.ColorInterp.blue):
                errors.append(f"{pid}: RGB color interpretation mismatch")

        g = m["spatial_group"]
        old_split = groups.setdefault(g, m["split"])
        if old_split != m["split"]:
            errors.append(f"{pid}: dates for spatial group {g} split across sets")
        extents.append((pid, m["split"], m["bounds"]))

        gj_path = root / m["geojson"]
        if not gj_path.is_file():
            errors.append(f"{pid}: missing GeoJSON annotation template")
        else:
            gj = json.loads(gj_path.read_text(encoding="utf-8"))
            crs_name = gj.get("crs", {}).get("properties", {}).get("name")
            try:
                annotation_crs = rasterio.crs.CRS.from_string(crs_name) if crs_name else None
                image_crs = rasterio.crs.CRS.from_string(m["crs"])
            except Exception:
                annotation_crs = image_crs = None
            if annotation_crs is None or annotation_crs != image_crs:
                errors.append(f"{pid}: GeoJSON CRS mismatch")
            features = gj.get("features", [])
            if features:
                reviewed_count += 1
                try:
                    from shapely.geometry import shape
                    for i, feature in enumerate(features):
                        geom = shape(feature["geometry"])
                        if geom.is_empty or not geom.is_valid or geom.geom_type not in ("Polygon", "MultiPolygon"):
                            errors.append(f"{pid}: invalid building geometry #{i}")
                except ImportError:
                    warnings.append("Shapely unavailable; geometry topology not checked")

        mask_ref = m.get("mask")
        mask_path = root / mask_ref if mask_ref else None
        if mask_path and mask_path.is_file():
            mask_count += 1
            with rasterio.open(image_path) as image, rasterio.open(mask_path) as mask:
                if (mask.width, mask.height, mask.count) != (512, 512, 1):
                    errors.append(f"{pid}: mask must be one-band 512x512")
                elif not set(np.unique(mask.read(1)).tolist()).issubset({0, 1}):
                    errors.append(f"{pid}: mask values must be {{0,1}}")
                if mask.crs != image.crs or mask.transform != image.transform:
                    errors.append(f"{pid}: mask/image geospatial alignment mismatch")
        elif m.get("annotation_status") == "REVIEWED":
            errors.append(f"{pid}: reviewed annotation has no raster mask")

    # Positive-area intersection between distinct splits is spatial leakage.
    for i, (pid, split, a) in enumerate(extents):
        for pid2, split2, b in extents[i + 1:]:
            if split == split2:
                continue
            if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                errors.append(f"spatial overlap across split: {pid} / {pid2}")

    summary = {
        "dataset": str(root), "candidate_patches": len(entries), "images_validated": len(entries) - len([e for e in errors if "image" in e]),
        "masks_present": mask_count, "patches_with_annotations": reviewed_count,
        "annotation_status": "ANNOTATED" if reviewed_count else "UNANNOTATED",
        "spatial_overlap_check": "FAILED" if any("spatial" in e for e in errors) else "VALIDATED",
        "ready_for_fine_tuning": bool(entries) and not errors and mask_count == len(entries) and reviewed_count == len(entries),
        "errors": errors, "warnings": warnings,
    }
    print(json.dumps(summary, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
