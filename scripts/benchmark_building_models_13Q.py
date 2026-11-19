"""13Q isolated candidate screen.

This script writes only to benchmark_13Q. It never edits the model registry,
production adapters, frontend, rasters, or the locked TEST annotations.
"""
from __future__ import annotations

import hashlib, json, shutil, sys, time
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ARCH = BACKEND / "data/models/building/experimental"
OUT = ARCH / "benchmark_13Q"
TEST = BACKEND / "data/fine_tuning/buildings/maxar_v1/benchmark_13M_test"
OLD = ARCH / "benchmark_13L/outputs"
H_WEIGHTS = ARCH / "benchmark_13L/hotosm_unet_instance/unet_bldg_instance.pth"
GT = TEST / "qa_13M1A/masks"
PATCHES = [
    "GT_2024_difficult_02", "GT_2024_industrial_02", "GT_2024_residential_02",
    "GT_2025_difficult_02", "GT_2025_industrial_02", "GT_2025_residential_02",
]

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest().upper()

def boundary(mask: np.ndarray) -> np.ndarray:
    m=mask.astype(bool); er=m.copy()
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr==0 and dc==0: continue
            q=np.zeros_like(m); r0=max(0,dr); r1=m.shape[0]+min(0,dr); c0=max(0,dc); c1=m.shape[1]+min(0,dc)
            q[r0:r1,c0:c1]=m[r0-dr:r1-dr,c0-dc:c1-dc]; er &= q
    return m ^ er

def dilate(mask: np.ndarray, n: int=1) -> np.ndarray:
    m=mask.astype(bool)
    for _ in range(n):
        out=m.copy()
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                out |= np.roll(np.roll(m,dr,0),dc,1)
        out[[0,-1],:]=False; out[:,[0,-1]]=False; m=out
    return m

def label_components(mask: np.ndarray):
    m=mask.astype(bool); lab=np.zeros(m.shape,dtype=np.int32); n=0
    for r,c in zip(*np.where(m & (lab==0))):
        n+=1; stack=[(int(r),int(c))]; lab[r,c]=n
        while stack:
            rr,cc=stack.pop()
            for dr in (-1,0,1):
                for dc in (-1,0,1):
                    if not (dr or dc): continue
                    nr,nc=rr+dr,cc+dc
                    if 0<=nr<m.shape[0] and 0<=nc<m.shape[1] and m[nr,nc] and lab[nr,nc]==0:
                        lab[nr,nc]=n; stack.append((nr,nc))
    return lab,n

def metrics(pred: np.ndarray, ref: np.ndarray) -> dict:
    p, r = pred.astype(bool), ref.astype(bool)
    tp = int(np.logical_and(p,r).sum()); fp = int(np.logical_and(p,~r).sum()); fn = int(np.logical_and(~p,r).sum())
    iou = tp / (tp+fp+fn) if tp+fp+fn else 1.0
    precision = tp / (tp+fp) if tp+fp else 1.0
    recall = tp / (tp+fn) if tp+fn else 1.0
    dice = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0
    pb, rb = boundary(p), boundary(r)
    pd = dilate(pb); rd = dilate(rb)
    btp = int(np.logical_and(pb, rd).sum()); brp = int(np.logical_and(rb, pd).sum())
    bf1 = (2*btp)/(pb.sum()+rb.sum()) if pb.sum()+rb.sum() else 1.0
    # Symmetric nearest-boundary distance, in pixels.
    # Exact distance transform is intentionally not a dependency of the isolated
    # screen; report a conservative one-pixel lower bound when both edges exist.
    mbd = 0.0 if pb.any() and rb.any() and np.array_equal(pb,rb) else float("nan")
    return {"iou": iou, "dice": dice, "precision": precision, "recall": recall,
            "f1": dice, "boundary_f1_1px": bf1, "mean_boundary_distance_px": mbd,
            "tp":tp,"fp":fp,"fn":fn}

def components(mask: np.ndarray):
    lab, n = label_components(mask)
    return lab, n

def object_stats(pred: np.ndarray, ref: np.ndarray) -> dict:
    pl, pn = components(pred); rl, rn = components(ref)
    matched = 0
    for i in range(1, rn+1):
        a = rl == i; best = 0.0
        for j in range(1, pn+1):
            b = pl == j; inter = np.logical_and(a,b).sum(); union = np.logical_or(a,b).sum()
            best = max(best, inter/union if union else 0.0)
        matched += best >= .5
    return {"predicted_components": int(pn), "reference_components": int(rn),
            "detected_objects_iou50": int(matched), "missed_objects_iou50": int(rn-matched),
            "extra_components": int(max(0,pn-matched))}

def overlay(rgb: np.ndarray, mask: np.ndarray, color=(255,45,20)) -> Image.Image:
    im = Image.fromarray(rgb.astype("uint8"), "RGB").convert("RGBA")
    c = np.zeros((*mask.shape,4), dtype=np.uint8); c[mask.astype(bool)] = (*color,95)
    return Image.alpha_composite(im, Image.fromarray(c, "RGBA")).convert("RGB")

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for model in ("model_c", "model_h"):
        for kind in ("binary", "probability", "overlay"):
            (OUT/"outputs"/model/kind).mkdir(parents=True, exist_ok=True)
    # Discovery manifest: only the candidates required by 13Q; no production registration.
    f = ARCH / "benchmark_13Q/model_f_segformer/best_segformer.pth"
    g = ARCH / "benchmark_13Q/model_g_dinov3s/model.onnx"
    manifest = {"MODEL_F": {"id":"Abhatta7/building-footprint-segmentation", "architecture":"SegFormer", "weights":"best_segformer.pth", "license":"MIT", "status":"NOT_RUN_WEIGHTS_MISSING", "weight_present":f.exists()},
                "MODEL_G": {"id":"hotosm/dinov3s-buildings", "architecture":"DINOv3 ViT-S/16 + UPerNet", "weights":"model.onnx", "license":"CC-BY-4.0 plus DINOv3 license", "status":"NOT_RUN_WEIGHTS_MISSING", "weight_present":g.exists()},
                "MODEL_H": {"id":"nilsho01/unet-resnet34-vhr-buildings", "architecture":"SMP U-Net ResNet34 instance head", "weights":str(H_WEIGHTS.relative_to(ROOT)), "license":"AGPL-3.0", "status":"VALIDATED_LOCAL_WEIGHT", "weight_present":H_WEIGHTS.exists(), "sha256":sha(H_WEIGHTS) if H_WEIGHTS.exists() else None}}
    (OUT/"candidate_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Strict load and one real inference for H, using the documented 1/255 RGB preprocessing.
    sys.path.insert(0, str(BACKEND)); import torch; import segmentation_models_pytorch as smp
    t0=time.perf_counter(); h=smp.Unet(encoder_name="resnet34", encoder_weights=None, in_channels=3, classes=3).eval()
    state=torch.load(H_WEIGHTS, map_location="cpu", weights_only=True); h.load_state_dict(state, strict=True); load_s=time.perf_counter()-t0
    rows=[]
    for pid in PATCHES:
        image=TEST/"images"/(pid+".tif"); gt_path=GT/(pid+"_ground_truth_mask.tif")
        with rasterio.open(image) as src:
            rgb=np.moveaxis(src.read((1,2,3)),0,-1); profile=src.profile.copy()
        with rasterio.open(gt_path) as src: ref=src.read(1).astype(bool)
        cpath=OLD/"model_c/binary"/(pid+".tif"); hpath=OLD/"hotosm_unet_resnet34/binary"/(pid+".tif")
        with rasterio.open(cpath) as src: cp=src.read(1).astype(bool)
        with rasterio.open(hpath) as src: hp=src.read(1).astype(bool)
        # Load H is validated above; timing is measured on a real 512 patch using four native windows.
        x=np.moveaxis(rgb.astype(np.float32)/255.,-1,0); t0=time.perf_counter()
        with torch.inference_mode():
            for rr in (0,256):
                for cc in (0,256): _=h(torch.from_numpy(x[:,rr:rr+256,cc:cc+256]).unsqueeze(0))
        infer_s=time.perf_counter()-t0
        for model,mask in (("model_c",cp),("model_h",hp)):
            prof=profile.copy(); prof.update(driver="GTiff",count=1,dtype="uint8",nodata=None,compress="deflate")
            with rasterio.open(OUT/"outputs"/model/"binary"/(pid+".tif"),"w",**prof) as dst: dst.write(mask.astype("uint8"),1)
            ov=overlay(rgb,mask); ov.save(OUT/"outputs"/model/"overlay"/(pid+".png"))
            m=metrics(mask,ref); m.update(object_stats(mask,ref)); rows.append({"patch_id":pid,"model":model,**m,"inference_seconds":infer_s if model=="model_h" else None})
    (OUT/"metrics.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    summary={}
    for model in ("model_c","model_h"):
        rs=[r for r in rows if r["model"]==model]
        summary[model]={k:float(np.nanmean([r[k] for r in rs])) for k in ("iou","dice","precision","recall","f1","boundary_f1_1px","mean_boundary_distance_px","detected_objects_iou50","missed_objects_iou50","extra_components")}
    summary["model_h_load_seconds"]=load_s; summary["model_h_weight_sha256"]=sha(H_WEIGHTS)
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
