"""Isolated same-patch benchmark for GeoRaster building segmentation candidates.

Writes only beneath backend/data/models/building/experimental/benchmark_13L.
No production adapter, registry, post-processing, or source image is modified.
"""
from __future__ import annotations

import csv
import ctypes
import json
import os
import sys
import time
from pathlib import Path
from ctypes import wintypes

import numpy as np
import rasterio
import torch
import segmentation_models_pytorch as smp
from PIL import Image, ImageDraw
from rasterio.features import shapes
from shapely import make_valid
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = BACKEND / "data/fine_tuning/buildings/maxar_v1"
OUT = BACKEND / "data/models/building/experimental/benchmark_13L"
MODEL_C = BACKEND / "data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth"
MODEL_C_SHA = "170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555"
THRESHOLD = 0.5
DEVICE = torch.device("cpu")


def write_mask(path: Path, values: np.ndarray, profile: dict) -> None:
    p = profile.copy()
    p.update(driver="GTiff", count=1, dtype="float32" if values.dtype.kind == "f" else "uint8",
             compress="deflate", nodata=None)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(values.astype(p["dtype"], copy=False), 1)


def polygonize(mask: np.ndarray, transform, crs, out_path: Path, patch_id: str, model_id: str):
    features = []
    for geom, value in shapes(mask.astype("uint8"), mask=mask.astype(bool), transform=transform, connectivity=8):
        poly = shape(geom)
        if poly.is_empty:
            continue
        if not poly.is_valid:
            poly = make_valid(poly)
        features.append({"type": "Feature", "geometry": mapping(poly), "properties": {
            "id": len(features) + 1, "model_id": model_id, "patch_id": patch_id,
            "area_map_units2": float(poly.area), "threshold": THRESHOLD,
        }})
    fc = {"type": "FeatureCollection", "name": f"{patch_id}_{model_id}",
          "crs": {"type": "name", "properties": {"name": crs.to_string() if crs else "EPSG:3857"}},
          "features": features}
    out_path.write_text(json.dumps(fc, indent=2) + "\n", encoding="utf-8")
    return len(features)


def overlay(rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    image = Image.fromarray(rgb.astype("uint8"), "RGB").convert("RGBA")
    color = Image.new("RGBA", image.size, (255, 50, 30, 0))
    alpha = (mask.astype(bool) * 105).astype("uint8")
    color.putalpha(Image.fromarray(alpha))
    return Image.alpha_composite(image, color).convert("RGB")


def render_contact_sheet(patch_meta: list[dict], outdirs: dict[str, Path]) -> None:
    """Render a same-patch grid with RGB, probability, binary and overlay columns."""
    models = [("model_c", "MODEL_C"), ("whu_unetplusplus_efficientnetb4", "WHU U-Net++"),
              ("hotosm_unet_resnet34", "HOTOSM U-Net")]
    columns = [("RGB", None, "rgb")]
    for model_id, label in models:
        columns.extend([(f"{label} prob", model_id, "probability"),
                        (f"{label} mask", model_id, "binary"),
                        (f"{label} polygons", model_id, "overlay")])
    cell, label_h = 192, 24
    sheet = Image.new("RGB", (len(columns) * cell, len(patch_meta) * (cell + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, meta in enumerate(patch_meta):
        pid = meta["patch_id"]; y = row * (cell + label_h)
        for col, (label, model_id, kind) in enumerate(columns):
            x = col * cell
            draw.text((x + 3, y + 4), f"{pid}\n{label}", fill="black")
            if kind == "rgb":
                im = Image.open(OUT / "outputs" / "rgb" / f"{pid}.png").convert("RGB")
            elif kind == "overlay":
                im = Image.open(outdirs[model_id] / "overlay" / f"{pid}.png").convert("RGB")
            else:
                with rasterio.open(outdirs[model_id] / kind / f"{pid}.tif") as src:
                    arr = src.read(1)
                if kind == "probability":
                    arr = np.clip(arr, 0.0, 1.0)
                im = Image.fromarray((arr * 255).astype("uint8"), "L").convert("RGB")
            sheet.paste(im.resize((cell, cell)), (x, y + label_h))
    sheet.save(OUT / "outputs/contact_sheet_13L.png")


def main() -> int:
    os.environ.setdefault("SPACENET2_ORT_INTRA_THREADS", "8")
    os.environ.setdefault("SPACENET2_ORT_INTER_THREADS", "2")
    sys.path.insert(0, str(BACKEND))
    from app.ai.models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
    from app.ai.services.tiling_service import TilingService

    torch.set_num_threads(min(8, os.cpu_count() or 8))
    outdirs = {m: OUT / "outputs" / m for m in ("model_c", "whu_unetplusplus_efficientnetb4", "hotosm_unet_resnet34")}
    rgb_out = OUT / "outputs" / "rgb"
    rgb_out.mkdir(parents=True, exist_ok=True)
    for d in outdirs.values():
        for sub in ("probability", "binary", "polygons", "overlay"):
            (d / sub).mkdir(parents=True, exist_ok=True)

    whu_path = OUT / "whu_unetplusplus/model.pth"
    hot_path = OUT / "hotosm_unet_instance/unet_bldg_instance.pth"
    t0 = time.perf_counter()
    whu = smp.UnetPlusPlus(encoder_name="efficientnet-b4", encoder_weights=None, in_channels=3, classes=2).to(DEVICE).eval()
    whu_state = torch.load(whu_path, map_location="cpu", weights_only=True); whu.load_state_dict(whu_state, strict=True); whu_load = time.perf_counter() - t0
    t0 = time.perf_counter()
    hot = smp.Unet(encoder_name="resnet34", encoder_weights=None, in_channels=3, classes=3).to(DEVICE).eval()
    hot_state = torch.load(hot_path, map_location="cpu", weights_only=True); hot.load_state_dict(hot_state, strict=True); hot_load = time.perf_counter() - t0
    c_adapter = SpaceNet2DeepLabAdapter(MODEL_C, expected_sha256=MODEL_C_SHA, engine="onnxruntime")
    t0 = time.perf_counter(); c_adapter.load(); c_load = time.perf_counter() - t0

    patch_meta = []
    for p in sorted((DATA / "metadata").glob("*.json")):
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
            if meta.get("patch_id") and meta.get("image"):
                patch_meta.append(meta)
        except (json.JSONDecodeError, OSError):
            pass
    patch_meta.sort(key=lambda x: x["patch_id"])
    if len(patch_meta) != 16:
        raise RuntimeError(f"Expected 16 prepared Maxar patches, found {len(patch_meta)}")

    results = []
    # Fixed, unchanged 512x512 source patch. HOTOSM model receives its native-size
    # four non-overlapping 256x256 windows; probabilities are mosaicked exactly.
    for meta in patch_meta:
        patch_id = meta["patch_id"]
        image_path = DATA / meta["image"]
        with rasterio.open(image_path) as src:
            if (src.width, src.height) != (512, 512) or src.count < 3:
                raise RuntimeError(f"{patch_id}: unexpected image shape/bands")
            rgb_chw = src.read((1, 2, 3))
            rgb_hwc = np.moveaxis(rgb_chw, 0, -1)
            profile, transform, crs = src.profile.copy(), src.transform, src.crs
            valid = np.all(np.isfinite(rgb_chw), axis=0)
            if src.nodata is not None:
                valid &= np.all(rgb_chw != src.nodata, axis=0)

        # MODEL_C uses the production adapter and exact full-raster RGB min-max path.
        tiles = TilingService().iter_tiles(image_path, raster_id=f"benchmark-13L-{patch_id}",
            tile_size=512, overlap_ratio=0.0, min_valid_pixel_ratio=0.05,
            preprocessing_profile="rgb_orthophoto_uint8_v1", band_indexes=(1, 2, 3))
        ctiles = list(c_adapter.prepare_inference_tiles(tiles, image_path,
            raster_id=f"benchmark-13L-{patch_id}", band_indexes=(1, 2, 3)))
        t0 = time.perf_counter(); cprob = c_adapter.predict(ctiles[0]).probability_map; c_sec = time.perf_counter() - t0

        # WHU card/model config: RGB float32 in [0,1], 512 input, two logits.
        x512 = np.ascontiguousarray(rgb_chw.astype(np.float32) / 255.0)
        with torch.inference_mode():
            t0 = time.perf_counter(); wlogits = whu(torch.from_numpy(x512).unsqueeze(0)); whu_sec = time.perf_counter() - t0
        wprob = torch.softmax(wlogits, dim=1)[0, 1].cpu().numpy().astype(np.float32)

        # HOTOSM card specifies 256 RGB pixels scaled by 1/255; its first head is
        # building mask probability/logit. Use sigmoid and native-size 2x2 windows.
        hprob = np.zeros((512, 512), dtype=np.float32)
        hot_sec = 0.0
        for row in (0, 256):
            for col in (0, 256):
                crop = np.ascontiguousarray(x512[:, row:row+256, col:col+256])
                with torch.inference_mode():
                    t0 = time.perf_counter(); hout = hot(torch.from_numpy(crop).unsqueeze(0)); hot_sec += time.perf_counter() - t0
                hprob[row:row+256, col:col+256] = torch.sigmoid(hout[0, 0]).cpu().numpy()

        probs = {"model_c": cprob, "whu_unetplusplus_efficientnetb4": wprob, "hotosm_unet_resnet34": hprob}
        counts = {}
        for model_id, prob in probs.items():
            binary = ((prob >= THRESHOLD) & valid).astype(np.uint8)
            write_mask(outdirs[model_id] / "probability" / f"{patch_id}.tif", prob, profile)
            write_mask(outdirs[model_id] / "binary" / f"{patch_id}.tif", binary, profile)
            counts[model_id] = polygonize(binary, transform, crs, outdirs[model_id] / "polygons" / f"{patch_id}.geojson", patch_id, model_id)
            overlay(rgb_hwc, binary).save(outdirs[model_id] / "overlay" / f"{patch_id}.png")
        Image.fromarray(rgb_hwc.astype("uint8"), "RGB").save(rgb_out / f"{patch_id}.png")
        results.append({"patch_id": patch_id, "split": meta.get("split", "unknown"),
            "model_c_seconds": c_sec, "whu_seconds": whu_sec, "hotosm_seconds": hot_sec,
            "whu_seconds_per_512_patch": whu_sec, "hotosm_seconds_per_512_patch": hot_sec,
            "model_c_polygons": counts["model_c"], "whu_polygons": counts["whu_unetplusplus_efficientnetb4"],
            "hotosm_polygons": counts["hotosm_unet_resnet34"],
            "model_c_positive_pixels": int((probs["model_c"] >= THRESHOLD).sum()),
            "whu_positive_pixels": int((probs["whu_unetplusplus_efficientnetb4"] >= THRESHOLD).sum()),
            "hotosm_positive_pixels": int((probs["hotosm_unet_resnet34"] >= THRESHOLD).sum())})
        print(f"{patch_id}: C {c_sec:.3f}s; WHU {whu_sec:.3f}s; HOTOSM {hot_sec:.3f}s")

    render_contact_sheet(patch_meta, outdirs)

    csv_path = OUT / "outputs/benchmark_results_13L.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys())); writer.writeheader(); writer.writerows(results)
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
    summary = {"patches": len(results), "threshold": THRESHOLD, "device": "CPU",
        "engine": {"model_c": "ONNX Runtime CPU", "whu": "PyTorch CPU", "hotosm": "PyTorch CPU"},
        "load_seconds": {"model_c_onnx_session": c_load, "whu_model_weights_strict": whu_load, "hotosm_model_weights_strict": hot_load},
        "mean_seconds_per_patch": {k: float(np.mean([r[k] for r in results])) for k in ("model_c_seconds", "whu_seconds", "hotosm_seconds")},
        "memory_rss_peak_bytes": peak_rss, "memory_note": "Windows process PeakWorkingSetSize for the combined benchmark process (interpreter + all loaded models), not a per-model isolated measure.",
        "official_accuracy_metrics": "NOT COMPUTED: no human-validated ground truth patches.",
        "polygonization": "Rasterio shapes, connectivity=8, threshold=0.50, identical method for all models; not GeoRaster production postprocessing."}
    (OUT / "outputs/benchmark_summary_13L.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    c_adapter.close()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
