"""Freeze source-derived contracts before any GOLD predictions."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
from discover_14A10_models import ROOT,OUT
from prepare_14A9B_datasets import BASE,GOLD,AL,sha,dump
def main():
 if (OUT/'protocol.json').exists():raise RuntimeError('Protocol already frozen')
 for d in ['qa','smoke','predictions','metrics','overlays','logs']:(OUT/d).mkdir(exist_ok=True)
 hashes={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()};expected=json.loads((AL/'qa/GOLD_HASHES_AFTER.json').read_text());assert all(hashes.get(p)==h for p,h in expected.items());dump(OUT/'qa/GOLD_BEFORE.json',hashes)
 specs=[dict(model='UNET_DIST3',path=str((OUT/'sources/nilsho01__unet-effb4-dist3-buildings/model.onnx').relative_to(ROOT)),preprocessing='RGB_DIV255_IMAGENET',tile_size=256,stride=256,threshold=.5,output='SIGMOID_MASK_EDT_BOUNDARY',postprocessing='WATERSHED_DISTANCE_SEEDS_GT05',min_area_m2=0.,description='Native256 grid, four tiles; stitched heads before global watershed; no 479px filter'),
 dict(model='SEGFORMER_F',path='backend/data/models/building/experimental/benchmark_13Q0B/model_f_segformer/best_segformer.pth',preprocessing='RGB_DIV255',tile_size=512,stride=512,threshold=.5,output='SIGMOID_BINARY_BILINEAR_512',postprocessing='CONNECTED_COMPONENTS_8_MIN4',min_area_m2=0.,description='Historical F weights; newly reproducible on GOLD via sandbox transformers'),
 dict(model='DINO_S_SEMANTIC',path='backend/data/models/building/experimental/benchmark_13Q0B/model_g_dinov3s/model.onnx',preprocessing='RGB_DIV255_IMAGENET',tile_size=256,stride=192,threshold=.4371,output='SIGMOID_CHANNEL0',postprocessing='SEMANTIC_COMPONENTS_4',min_area_m2=2.6465,description='Graph SHA matches published HOT S graph. Semantic channel0 adapter only; not full upstream watershed/regularization'),
 dict(model='DINO_FAST',path=str((OUT/'sources/LundAISociety__hot-models/v0.4.1-fast-distilled/onnx/model_fp32.onnx').relative_to(ROOT)),preprocessing='RAW_RGB_UINT8_HWC',tile_size=512,stride=512,threshold=None,output='UINT8_4_MAPS',postprocessing='BLOCKED_VECTOR_ENCODING_AND_FLOW_CONTRACT',min_area_m2=0.,description='Smoke forward only. No invented decoding of quantized vector channels; no GOLD benchmark without complete contract')]
 for s in specs:s['sha256']=sha(ROOT/s['path'])
 protocol=dict(models=specs,smoke_patch='14A9B_AL_01_R00256_C02304',gold_patches=json.loads((BASE/'qa/14A8_model_shootout/14A8_frozen_protocol.json').read_text())['patches'],matching='Maximum-cardinality one-to-one IoU>=0.30, then maximum IoU',small='<=50m2',medium='>50 to200m2',large='>200m2',tuning_gold=False,training=False,production_modified=False,threads=4,near_boundary_tolerance_px=1)
 dump(OUT/'protocol.json',protocol);(OUT/'protocol.sha256').write_text(sha(OUT/'protocol.json'));print('FROZEN',len(specs),'SMOKE_CANDIDATES')
if __name__=='__main__':main()
