from __future__ import annotations
import csv, hashlib, json, random, time
from pathlib import Path
import numpy as np
import rasterio
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import Dataset, DataLoader
from transformers import SegformerConfig, SegformerForSemanticSegmentation

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R'
BASE=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_f_segformer/best_segformer.pth'
OUT=ROOT/'backend/data/models/building/experimental/model_f2_industrial_finetuned'; OUT.mkdir(parents=True,exist_ok=True)
LR=1e-5; WD=1e-4; EPOCHS=12; PATIENCE=4; SEED=13
torch.manual_seed(SEED); np.random.seed(SEED); random.seed(SEED)

def sha256(p):
    h=hashlib.sha256();
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest().upper()

def make_model():
    cfg=SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256)
    m=SegformerForSemanticSegmentation(cfg)
    sd=torch.load(BASE,map_location='cpu',weights_only=True)
    sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()}
    m.load_state_dict(sd,strict=True); return m

class Tiles(Dataset):
    def __init__(self, rows, augment=False): self.rows=rows; self.augment=augment
    def __len__(self): return len(self.rows)
    def __getitem__(self,i):
        r=self.rows[i]; im=DATA/'images'/r['split']/(r['patch_id']+'.tif'); ma=DATA/'masks'/r['split']/(r['patch_id']+'.tif')
        with rasterio.open(im) as s: x=s.read((1,2,3)).astype('float32')/255.0
        with rasterio.open(ma) as s: y=s.read(1).astype('float32')
        k=i%8 if self.augment else 0
        if k==1: x=x[:,:,::-1].copy(); y=y[:,::-1].copy()
        elif k==2: x=x[:,::-1,:].copy(); y=y[::-1,:].copy()
        elif k==3: x=np.rot90(x,1,axes=(1,2)).copy(); y=np.rot90(y,1).copy()
        elif k==4: x=np.rot90(x,2,axes=(1,2)).copy(); y=np.rot90(y,2).copy()
        elif k==5: x=np.rot90(x,3,axes=(1,2)).copy(); y=np.rot90(y,3).copy()
        return torch.from_numpy(x),torch.from_numpy(y[None])

def metrics(logits, y):
    p=(torch.sigmoid(F.interpolate(logits,size=y.shape[-2:],mode='bilinear',align_corners=False))>=0.5)
    t=y>=0.5; inter=(p&t).sum().item(); pp=p.sum().item(); tt=t.sum().item(); union=(p|t).sum().item()
    return {'iou':inter/union if union else 1.0,'dice':2*inter/(pp+tt) if (pp+tt) else 1.0,'precision':inter/pp if pp else 1.0,'recall':inter/tt if tt else 1.0}

def evaluate(model, loader, device):
    model.eval(); sums={'loss':0.,'iou':0.,'dice':0.,'precision':0.,'recall':0.}; n=0
    bce=nn.BCEWithLogitsLoss()
    with torch.no_grad():
        for x,y in loader:
            x=x.to(device); y=y.to(device); z=model(pixel_values=x).logits; up=F.interpolate(z,size=y.shape[-2:],mode='bilinear',align_corners=False)
            prob=torch.sigmoid(up); inter=(prob*y).sum(); dice_loss=1-(2*inter+1)/(prob.sum()+y.sum()+1); loss=bce(up,y)+dice_loss
            m=metrics(z,y); sums['loss']+=loss.item();
            for k in m:sums[k]+=m[k]
            n+=1
    return {k:v/max(n,1) for k,v in sums.items()}

def main():
    rows=[r for r in csv.DictReader(open(DATA/'manifest.csv',encoding='utf-8')) if r['review_status'] in ('ACCEPTED','HUMAN_CORRECTED') and r['patch_id'] not in {'13R_industrial_007_01024_06144','13R_residential_036_06144_04096'}]
    train=[r for r in rows if r['split']=='train']; val=[r for r in rows if r['split']=='val']
    assert len(train)==29 and len(val)==5, (len(train),len(val))
    device=torch.device('cpu'); model=make_model().to(device)
    # Baseline metrics from the untouched initialization on the exact VAL set.
    val_loader=DataLoader(Tiles(val,False),batch_size=2,shuffle=False)
    baseline=evaluate(model,val_loader,device)
    opt=torch.optim.AdamW(model.parameters(),lr=LR,weight_decay=WD); bce=nn.BCEWithLogitsLoss()
    tr_loader=DataLoader(Tiles(train,True),batch_size=2,shuffle=True)
    best=-1.; best_epoch=0; no_improve=0; history=[]; best_path=OUT/'best_model_f2.pth'; last_path=OUT/'last_model_f2.pth'
    for ep in range(1,EPOCHS+1):
        model.train(); total=0.; n=0
        for x,y in tr_loader:
            x=x.to(device); y=y.to(device); opt.zero_grad(set_to_none=True); z=model(pixel_values=x).logits; up=F.interpolate(z,size=y.shape[-2:],mode='bilinear',align_corners=False); prob=torch.sigmoid(up); inter=(prob*y).sum(); dice=1-(2*inter+1)/(prob.sum()+y.sum()+1); loss=bce(up,y)+dice; loss.backward(); opt.step(); total+=loss.item(); n+=1
        vm=evaluate(model,val_loader,device); row={'epoch':ep,'train_loss':total/max(n,1),**{'val_'+k:v for k,v in vm.items()}}; history.append(row); print(row,flush=True)
        torch.save(model.state_dict(),last_path)
        if vm['dice']>best: best=vm['dice']; best_epoch=ep; no_improve=0; torch.save(model.state_dict(),best_path)
        else: no_improve+=1
        if no_improve>=PATIENCE: break
    model.load_state_dict(torch.load(best_path,map_location='cpu',weights_only=True)); final=evaluate(model,val_loader,device)
    # Per scene type on VAL for the baseline and MODEL_F2.
    def subset_metrics(m):
        out={}
        for scene in ('industrial','residential'):
            rs=[r for r in val if r['scene_type']==scene]; out[scene]=evaluate(m,DataLoader(Tiles(rs,False),batch_size=1),device) if rs else None
        return out
    bm=make_model().to(device); base_scene=subset_metrics(bm); f2_scene=subset_metrics(model)
    metadata={'base_model':'MODEL_F','fine_tuning_dataset':'13R','train_patches':len(train),'val_patches':len(val),'test_leakage':0,'learning_rate':LR,'weight_decay':WD,'epochs_requested':EPOCHS,'epochs_run':len(history),'best_epoch':best_epoch,'architecture':'SegFormer custom configuration, num_labels=1, hidden_sizes=[32,64,160,256]','preprocessing':'RGB / 255, 512x512, official MODEL_F preprocessing','baseline_val':baseline,'best_val':final,'baseline_val_by_scene':base_scene,'model_f2_val_by_scene':f2_scene,'history':history,'original_checkpoint':str(BASE.relative_to(ROOT)),'original_checkpoint_sha256':sha256(BASE),'best_checkpoint':str(best_path.relative_to(ROOT)),'best_checkpoint_sha256':sha256(best_path)}
    (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8'); (OUT/'training_history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))
if __name__=='__main__': main()
