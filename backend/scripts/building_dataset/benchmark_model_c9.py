"""Controlled intermediate MODEL_C9 benchmark; production remains untouched."""
from __future__ import annotations
import json, os, time
from pathlib import Path
import torch
from torch.utils.data import DataLoader
try:
    from .train_model_c9 import BuildingDataset, make_model, run_epoch, evaluate_threshold
except ImportError:
    from train_model_c9 import BuildingDataset, make_model, run_epoch, evaluate_threshold


def rss_mib() -> float | None:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def load_c8_weights(model: torch.nn.Module, checkpoint: Path) -> None:
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = state.get("state_dict", state)
    state = {k.removeprefix("module."): v for k, v in state.items()}
    current = model.state_dict()
    model.load_state_dict({k: v for k, v in state.items() if k in current and tuple(current[k].shape) == tuple(v.shape)}, strict=False)


def timed_eval(model, loader, device, *, amp=False):
    started = time.perf_counter(); metrics = run_epoch(model, loader, device, None); return metrics, time.perf_counter() - started


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--dataset", "--dataset-root", dest="dataset", type=Path, required=True); ap.add_argument("--output", type=Path, default=Path("backend/data/fine_tuning/buildings/model_c9_benchmark")); ap.add_argument("--epochs", type=int, default=3); ap.add_argument("--batch-size", type=int, default=4); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--device", default="auto"); ap.add_argument("--amp", action="store_true"); ap.add_argument("--num-workers", type=int, default=2); ap.add_argument("--pin-memory", action=argparse.BooleanOptionalAction, default=True); ap.add_argument("--c8-checkpoint", type=Path); ap.add_argument("--train-limit", type=int, default=256); ap.add_argument("--val-limit", type=int, default=64); ap.add_argument("--test-limit", type=int, default=64); args = ap.parse_args()
    torch.manual_seed(args.seed); args.output.mkdir(parents=True, exist_ok=True); device = torch.device("cuda" if args.device in {"auto","cuda"} and torch.cuda.is_available() else "cpu"); amp=bool(args.amp and device.type=="cuda"); torch.set_num_threads(min(4 if device.type=="cuda" else 2, os.cpu_count() or 2))
    train = BuildingDataset(args.dataset, "train", augment=True, limit=args.train_limit); val = BuildingDataset(args.dataset, "val", limit=args.val_limit); test = BuildingDataset(args.dataset, "test", limit=args.test_limit)
    loader_kw={"num_workers":args.num_workers,"pin_memory":bool(args.pin_memory and device.type=="cuda"),"persistent_workers":bool(args.num_workers>0)}; loaders = {"train": DataLoader(train, batch_size=args.batch_size, shuffle=True, **loader_kw), "val": DataLoader(val, batch_size=1, shuffle=False, **loader_kw), "test": DataLoader(test, batch_size=1, shuffle=False, **loader_kw)}
    model = make_model(); c8_path = args.c8_checkpoint or Path("backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline/models/MODEL_C8_HYBRID_epoch2.pth"); load_c8_weights(model, c8_path); model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4); history=[]; best=-1.0; total_started=time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        started=time.perf_counter(); tr=run_epoch(model, loaders["train"], device, optimizer, amp=amp); va, val_seconds=timed_eval(model, loaders["val"], device, amp=amp); epoch_seconds=time.perf_counter()-started
        row={"epoch":epoch,"train_loss":tr["loss"],"val_loss":va["loss"],"iou":va["iou"],"dice":va["dice"],"precision":va["precision"],"recall":va["recall"],"f1":va["f1"],"epoch_seconds":epoch_seconds,"validation_seconds":val_seconds,"rss_mib":rss_mib()}; history.append(row); print(json.dumps(row),flush=True)
        if va["dice"] > best: best=va["dice"]; torch.save({"model_state_dict":model.state_dict(),"epoch":epoch,"validation":va,"seed":args.seed}, args.output/"MODEL_C9_BENCHMARK_best.pth")
    (args.output/"training_history.json").write_text(json.dumps(history, indent=2))
    model.load_state_dict(torch.load(args.output/"MODEL_C9_BENCHMARK_best.pth", map_location=device, weights_only=True)["model_state_dict"])
    threshold, threshold_metrics = evaluate_threshold(model, loaders["val"], device); c9_test, test_seconds = timed_eval(model, loaders["test"], device, amp=amp)
    c8 = make_model(); load_c8_weights(c8, c8_path); c8.to(device); c8_test, c8_seconds = timed_eval(c8, loaders["test"], device, amp=amp)
    avg_epoch=sum(r["epoch_seconds"] for r in history)/len(history); projection=avg_epoch*(2832/256)*20
    report={"model":"MODEL_C9","status":"EXPERIMENTAL","subset":{"train":len(train),"val":len(val),"test":len(test),"seed":args.seed,"selection":"first sorted records per existing split"},"architecture":"torchvision DeepLabV3 ResNet50","initialization":"C8 compatible weights, read-only","device":str(device),"torch_version":torch.__version__,"cuda_available":torch.cuda.is_available(),"cuda_version":torch.version.cuda,"gpu_name":torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,"vram_total_mib":torch.cuda.get_device_properties(0).total_memory/(1024*1024) if torch.cuda.is_available() else None,"amp":amp,"torch_threads":torch.get_num_threads(),"batch_size":args.batch_size,"workers":args.num_workers,"pin_memory":bool(args.pin_memory and device.type=="cuda"),"epochs":args.epochs,"history":history,"best_epoch":max(history,key=lambda r:r["dice"])["epoch"],"best_validation_threshold":threshold,"validation_threshold_metrics":threshold_metrics,"c9_test_metrics":c9_test,"c8_test_metrics":c8_test,"c9_test_seconds":test_seconds,"c8_test_seconds":c8_seconds,"average_epoch_seconds":avg_epoch,"projected_full_20_epoch_seconds":projection,"projected_full_20_epoch_hours":projection/3600,"rss_mib":rss_mib()}; (args.output/"MODEL_C9_BENCHMARK_REPORT.json").write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
