"""Isolated MODEL_C9 DeepLabV3/ResNet50 experiment on GeoRaster Building v1."""
from __future__ import annotations

import argparse, json, random, time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead


def seed_everything(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


def select_device(requested: str = "auto") -> torch.device:
    """Select CUDA when requested/available, otherwise safely fall back to CPU."""
    if requested in {"auto", "cuda"} and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class BuildingDataset(Dataset):
    def __init__(self, root: Path, split: str, *, augment: bool = False, limit: int | None = None) -> None:
        payload = json.loads((root / "metadata" / "dataset_manifest.json").read_text())
        self.root, self.augment = root, augment
        self.records = [r for r in payload["records"] if r["split"] == split]
        self.records.sort(key=lambda r: r["tile_id"])
        if limit is not None: self.records = self.records[:limit]
    def __len__(self) -> int: return len(self.records)
    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        item = self.records[idx]
        with rasterio.open(self.root / item["image_path"]) as src: image = src.read((1,2,3)).astype("float32") / 255.0
        with rasterio.open(self.root / item["mask_path"]) as src: mask = (src.read(1) > 0).astype("float32")
        image = torch.from_numpy(image); mask = torch.from_numpy(mask).unsqueeze(0)
        if self.augment:
            k = random.randrange(8)
            if k & 1: image, mask = torch.flip(image, (-1,)), torch.flip(mask, (-1,))
            if k & 2: image, mask = torch.flip(image, (-2,)), torch.flip(mask, (-2,))
            if k & 4: image, mask = image.rot90(1, (-2,-1)), mask.rot90(1, (-2,-1))
        return image, mask


def make_model() -> nn.Module:
    model = deeplabv3_resnet50(weights=None, weights_backbone=None, aux_loss=True)
    model.classifier = DeepLabHead(2048, 1)
    model.aux_classifier = nn.Sequential(nn.Conv2d(1024, 1, 3, padding=1), nn.ReLU(), nn.Conv2d(1, 1, 1))
    return model


def dice_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    probs = torch.sigmoid(logits); smooth = 1.0
    inter = (probs * target).sum((1,2,3)); denom = probs.sum((1,2,3)) + target.sum((1,2,3))
    return (1 - ((2 * inter + smooth) / (denom + smooth))).mean()


def metrics(logits: torch.Tensor, target: torch.Tensor, threshold: float = .5) -> dict[str, float]:
    pred = torch.sigmoid(logits) >= threshold; truth = target >= .5
    tp = (pred & truth).sum().item(); fp = (pred & ~truth).sum().item(); fn = (~pred & truth).sum().item(); tn = (~pred & ~truth).sum().item()
    iou = tp / max(1, tp + fp + fn); dice = 2*tp / max(1, 2*tp + fp + fn); precision = tp / max(1, tp+fp); recall = tp / max(1, tp+fn)
    return {"iou": iou, "dice": dice, "precision": precision, "recall": recall, "f1": 2*precision*recall/max(1e-9, precision+recall), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def run_epoch(model: nn.Module, loader: DataLoader, device: torch.device, optimizer: Any | None, *, amp: bool = False, scaler: Any | None = None) -> dict[str, float]:
    train = optimizer is not None; model.train(train)
    if train:
        # DeepLab's ASPP contains 1×1 BatchNorm tensors; freeze running-stat
        # updates so batch_size=1 remains valid on the constrained CPU host.
        for module in model.modules():
            if isinstance(module, nn.modules.batchnorm._BatchNorm): module.eval()
    total_loss = 0.0; accum = {k: 0.0 for k in ("iou","dice","precision","recall","f1")}; counts = {"tp":0,"fp":0,"fn":0,"tn":0}
    for image, target in loader:
        image, target = image.to(device), target.to(device)
        if train: optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(train), torch.autocast(device_type="cuda", dtype=torch.float16, enabled=bool(amp and device.type == "cuda")):
            out = model(image)["out"]; loss = .5 * nn.functional.binary_cross_entropy_with_logits(out, target) + .5 * dice_loss(out, target)
            if train:
                if scaler is not None and scaler.is_enabled(): scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()
                else: loss.backward(); optimizer.step()
        total_loss += float(loss.detach()); m = metrics(out.detach(), target)
        for k in accum: accum[k] += m[k]
        for k in counts: counts[k] += int(m[k])
    n = max(1, len(loader)); return {"loss": total_loss/n, **{k:v/n for k,v in accum.items()}, **counts}


def evaluate_threshold(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, dict[str,float]]:
    best = (0.5, {"f1": -1.0})
    for threshold in (0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70):
        model.eval(); aggregate = {"tp":0,"fp":0,"fn":0,"tn":0}
        with torch.inference_mode():
            for image,target in loader:
                m=metrics(model(image.to(device))["out"],target.to(device),threshold)
                for k in aggregate: aggregate[k]+=m[k]
        p=aggregate["tp"]/max(1,aggregate["tp"]+aggregate["fp"]); r=aggregate["tp"]/max(1,aggregate["tp"]+aggregate["fn"]); f=2*p*r/max(1e-9,p+r)
        if f > best[1]["f1"]: best=(threshold,{**aggregate,"precision":p,"recall":r,"f1":f})
    return best


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--dataset", "--dataset-root", dest="dataset", type=Path, required=True); ap.add_argument("--output",type=Path,default=Path("backend/data/fine_tuning/buildings/model_c9")); ap.add_argument("--epochs",type=int,default=20); ap.add_argument("--batch-size",type=int,default=1); ap.add_argument("--lr",type=float,default=1e-4); ap.add_argument("--seed",type=int,default=42); ap.add_argument("--device",default="auto"); ap.add_argument("--amp",action="store_true"); ap.add_argument("--num-workers",type=int,default=0); ap.add_argument("--pin-memory",action=argparse.BooleanOptionalAction,default=True); ap.add_argument("--c8-checkpoint",type=Path); ap.add_argument("--limit-train",type=int); ap.add_argument("--limit-val",type=int); ap.add_argument("--limit-test",type=int); args=ap.parse_args()
    seed_everything(args.seed); device=select_device(args.device); amp=bool(args.amp and device.type == "cuda"); args.output.mkdir(parents=True,exist_ok=True)
    train=BuildingDataset(args.dataset,"train",augment=True,limit=args.limit_train); val=BuildingDataset(args.dataset,"val",limit=args.limit_val); test=BuildingDataset(args.dataset,"test",limit=args.limit_test)
    loader_kw={"num_workers":args.num_workers,"pin_memory":bool(args.pin_memory and device.type=="cuda"),"persistent_workers":bool(args.num_workers>0)}; loaders={"train":DataLoader(train,batch_size=args.batch_size,shuffle=True,**loader_kw),"val":DataLoader(val,batch_size=1,shuffle=False,**loader_kw),"test":DataLoader(test,batch_size=1,shuffle=False,**loader_kw)}
    model=make_model(); c8=args.c8_checkpoint or Path("backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline/models/MODEL_C8_HYBRID_epoch2.pth"); init="C8 checkpoint" if c8.is_file() else "random initialization"; 
    if c8.is_file():
        state=torch.load(c8,map_location="cpu",weights_only=True); state=state.get("state_dict",state)
        state={k.removeprefix("module."): v for k,v in state.items()}
        compatible={k:v for k,v in state.items() if k in model.state_dict() and tuple(model.state_dict()[k].shape)==tuple(v.shape)}
        if compatible:
            model.load_state_dict(compatible,strict=False)
            init="C8 compatible weights (backbone and main classifier); C9 auxiliary head initialized separately"
        else: init="C8 checkpoint incompatible; random initialization"
    model.to(device); opt=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=1e-4); scaler=torch.amp.GradScaler("cuda", enabled=amp) if hasattr(torch,"amp") else torch.cuda.amp.GradScaler(enabled=amp); history=[]; best=-1
    started=time.perf_counter()
    for epoch in range(1,args.epochs+1):
        tr=run_epoch(model,loaders["train"],device,opt,amp=amp,scaler=scaler); va=run_epoch(model,loaders["val"],device,None,amp=amp); row={"epoch":epoch,"train":tr,"val":va}; history.append(row); print(json.dumps(row),flush=True)
        if va["dice"]>best: best=va["dice"]; torch.save({"model_state_dict":model.state_dict(),"epoch":epoch,"validation":va,"seed":args.seed},args.output/"MODEL_C9_best.pth")
        torch.save({"model_state_dict":model.state_dict(),"epoch":epoch},args.output/f"MODEL_C9_epoch{epoch:02d}.pth")
    (args.output/"training_history.json").write_text(json.dumps(history,indent=2)); model.load_state_dict(torch.load(args.output/"MODEL_C9_best.pth",map_location=device,weights_only=True)["model_state_dict"]); threshold,valm=evaluate_threshold(model,loaders["val"],device); testm=run_epoch(model,loaders["test"],device,None); report={"model":"MODEL_C9","status":"EXPERIMENTAL","architecture":"torchvision DeepLabV3 ResNet50","initialization":init,"dataset":str(args.dataset),"device":str(device),"epochs":args.epochs,"best_validation_threshold":threshold,"validation_threshold_metrics":valm,"test_metrics":testm,"training_seconds":time.perf_counter()-started,"train_samples":len(train),"val_samples":len(val),"test_samples":len(test)}; (args.output/"MODEL_C9_TRAINING_REPORT.json").write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
