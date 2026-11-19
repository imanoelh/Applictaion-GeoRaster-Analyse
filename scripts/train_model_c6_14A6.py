from __future__ import annotations
import json, time
from pathlib import Path
import numpy as np
import rasterio
import torch

# Native torchvision operators are available in the audited CPU environment.
# Temporary schema registration crashes at shutdown (14A.7B); use normal ownership.
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
RGB=BASE/'14A2_expansion/train/rgb'; MASK=BASE/'14A5B_fixed_masks'
OUT=ROOT/'backend/data/models/model_c6_experimental'; OUT.mkdir(parents=True,exist_ok=True)
PATCHES=['14A2_2024_06','14A2_2024_10','14A2_2025_02','14A2_2025_06','14A2_2025_10']

def load_pair(p):
    with rasterio.open(RGB/(p+'.tif')) as d: x=d.read((1,2,3)).astype('float32'); x=(x-x.min())/max(1e-6,float(x.max()-x.min()))
    with rasterio.open(MASK/(p+'.tif')) as d: y=d.read(1).astype('float32')
    return x,y

def main():
    torch.set_num_threads(min(4,torch.get_num_threads()))
    model=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True); model.classifier=DeepLabHead(2048,1)
    source_ckpt=ROOT/'backend/data/models/model_c3_experimental/best_model_c3_WEIGHTED_BCE_DICE.pth'
    ckpt=torch.load(source_ckpt,map_location='cpu',weights_only=False)
    model.load_state_dict(ckpt.get('state_dict',ckpt),strict=True)
    model.train(); opt=torch.optim.AdamW(model.parameters(),lr=1e-5,weight_decay=1e-4)
    samples=[]
    for p in PATCHES[:-1]:
        x,y=load_pair(p)
        for r in (0,256):
            for c in (0,256): samples.append((x[:,r:r+256,c:c+256],y[r:r+256,c:c+256],p))
    losses=[]; started=time.perf_counter()
    for epoch in range(2):
        np.random.default_rng(42+epoch).shuffle(samples)
        for bi in range(0,len(samples),2):
            batch=samples[bi:bi+2]
            if len(batch)==1: batch=[batch[0],batch[0]]
            xt=torch.from_numpy(np.stack([z[0] for z in batch])); yt=torch.from_numpy(np.stack([z[1] for z in batch])).unsqueeze(1)
            opt.zero_grad(set_to_none=True); out=model(xt); logits=out['out']; target=torch.nn.functional.interpolate(yt,size=logits.shape[-2:],mode='nearest')
            bce=torch.nn.functional.binary_cross_entropy_with_logits(logits,target)
            prob=torch.sigmoid(logits); dice=1-(2*(prob*target).sum()+1)/(prob.sum()+target.sum()+1)
            loss=bce+dice; loss.backward(); opt.step(); losses.append(float(loss))
        print('epoch',epoch+1,'loss',sum(losses[-len(samples):])/len(samples),flush=True)
    path=OUT/'best_model_c6.pth'; torch.save({'state_dict':model.state_dict(),'epoch':2,'loss':losses[-1],'source':'MODEL_C3','dataset':'14A5B_FIXED'},path)
    report={'model':'MODEL_C6_HIGH_PRECISION_EXPERIMENTAL','checkpoint':str(path),'epochs':2,'train_tiles':len(samples),'best_epoch':2,'final_loss':losses[-1],'cpu_seconds':time.perf_counter()-started,'source_checkpoint':str(source_ckpt),'onnx':'SKIPPED'}
    (OUT/'training_metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
