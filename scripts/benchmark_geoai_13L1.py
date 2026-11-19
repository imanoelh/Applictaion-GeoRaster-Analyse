"""Run the official GeoAI WHU helper on the fixed 13L Maxar patches.

All generated files stay in backend/data/models/building/experimental/benchmark_13L1.
No source image, production code, or MODEL_C file is modified.
"""
from __future__ import annotations

import json
import os
import time
import ctypes
from pathlib import Path
from ctypes import wintypes

import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import mapping, shape
from shapely import make_valid
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
OUT = ROOT / "backend/data/models/building/experimental/benchmark_13L1"
MODEL_C = ROOT / "backend/data/models/building/experimental/benchmark_13L/outputs/model_c"
REPO = "giswqs/whu-building-unetplusplus-efficientnet-b4"


def polygonize(mask_path: Path, output_path: Path, patch_id: str) -> int:
    with rasterio.open(mask_path) as src:
        mask = src.read(1).astype(bool)
        transform, crs = src.transform, src.crs
    features = []
    for geom, value in shapes(mask.astype("uint8"), mask=mask, transform=transform, connectivity=8):
        if value:
            poly = shape(geom)
            if not poly.is_valid:
                poly = make_valid(poly)
            features.append({"type": "Feature", "geometry": mapping(poly), "properties": {
                "id": len(features) + 1, "patch_id": patch_id, "model_id": "geoai_whu_raw",
            }})
    output_path.write_text(json.dumps({"type": "FeatureCollection", "name": patch_id,
        "crs": {"type": "name", "properties": {"name": crs.to_string() if crs else ""}},
        "features": features}, indent=2) + "\n", encoding="utf-8")
    return len(features)


def main() -> int:
    # Reuse the exact 13L checkpoint/config from a local Hub cache, with offline mode
    # preventing an accidental re-download of files already present in the project.
    local_model_dir = ROOT / "backend/data/models/building/experimental/benchmark_13L/whu_unetplusplus"
    metadata_file = local_model_dir / ".cache/huggingface/download/model.pth.metadata"
    revision = metadata_file.read_text(encoding="utf-8").splitlines()[0].strip()
    repo_cache = OUT / "hf_home/hub/models--giswqs--whu-building-unetplusplus-efficientnet-b4"
    snapshot = repo_cache / "snapshots" / revision
    snapshot.mkdir(parents=True, exist_ok=True)
    (repo_cache / "refs").mkdir(parents=True, exist_ok=True)
    (repo_cache / "refs/main").write_text(revision, encoding="utf-8")
    for filename in ("model.pth", "config.json"):
        cached_file = snapshot / filename
        if not cached_file.exists():
            os.link(local_model_dir / filename, cached_file)
    os.environ["HF_HOME"] = str(OUT / "hf_home")
    os.environ["HF_HUB_OFFLINE"] = "1"

    import geoai

    os.environ.setdefault("OMP_NUM_THREADS", "8")
    out = OUT / "outputs/whu_geoai"
    for folder in ("binary", "probability", "raw_polygons", "overlays"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    patches = []
    for p in sorted((DATA / "metadata").glob("*.json")):
        meta = json.loads(p.read_text(encoding="utf-8"))
        if meta.get("patch_id") and meta.get("image"):
            patches.append(meta)
    patches.sort(key=lambda m: m["patch_id"])
    if len(patches) != 16:
        raise RuntimeError(f"Expected 16 fixed 13L patches, found {len(patches)}")

    results = []
    for meta in patches:
        pid = meta["patch_id"]
        image_path = DATA / meta["image"]
        mask_path = out / "binary" / f"{pid}.tif"
        prob_path = out / "probability" / f"{pid}.tif"
        t0 = time.perf_counter()
        geoai.timm_segmentation_from_hub(
            input_path=str(image_path), output_path=str(mask_path), repo_id=REPO,
            window_size=512, overlap=0, batch_size=1, device="cpu", quiet=True,
            probability_path=str(prob_path), probability_threshold=0.5,
            save_class_probabilities=False,
        )
        inference_sec = time.perf_counter() - t0
        with rasterio.open(mask_path) as src:
            mask = src.read(1)
            profile = src.profile.copy()
            if (src.width, src.height) != (512, 512) or not set(np.unique(mask)).issubset({0, 1}):
                raise RuntimeError(f"{pid}: unexpected GeoAI mask grid/values")
        raw_path = out / "raw_polygons" / f"{pid}.geojson"
        polygon_count = polygonize(mask_path, raw_path, pid)

        # Visual evidence uses the exact source patch and the fixed mask grid.
        with rasterio.open(image_path) as src:
            rgb = np.moveaxis(src.read((1, 2, 3)), 0, -1)
        rgba = Image.fromarray(rgb.astype("uint8"), "RGB").convert("RGBA")
        overlay = Image.new("RGBA", rgba.size, (255, 40, 25, 0))
        alpha = Image.fromarray((mask.astype(bool) * 100).astype("uint8"))
        overlay.putalpha(alpha)
        Image.alpha_composite(rgba, overlay).convert("RGB").save(out / "overlays" / f"{pid}.png")
        results.append({"patch_id": pid, "split": meta.get("split", "unknown"),
            "geoai_whu_seconds_including_model_load": inference_sec,
            "geoai_whu_polygon_count": polygon_count,
            "geoai_whu_positive_pixels": int(mask.sum()),
            "mask_width": profile["width"], "mask_height": profile["height"],
            "mask_crs": str(profile.get("crs")), "mask_transform": tuple(profile["transform"]),
        })
        print(f"{pid}: {inference_sec:.2f}s, {polygon_count} components")

    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    counters = PROCESS_MEMORY_COUNTERS(); counters.cb = ctypes.sizeof(counters)
    peak_rss = None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            peak_rss = int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError):
        pass
    summary = {"geoai_version": geoai.__version__, "patches": len(results),
        "mean_seconds_including_load": float(np.mean([r["geoai_whu_seconds_including_model_load"] for r in results])),
        "process_peak_working_set_bytes": peak_rss,
        "memory_scope": "Combined Windows process peak (interpreter + GeoAI + model), not model-only.",
        "outputs": str(out)}
    (OUT / "outputs/whu_geoai/summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
