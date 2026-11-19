from pathlib import Path
import json, hashlib, time, math, csv
import numpy as np
from PIL import Image, ImageDraw
import rasterio

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion'
SEED_MASKS=EXP/'masks/seed_gt_fixed_candidate'
CKPT=ROOT/'backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth'
OUT=ROOT/'backend/data/models/model_c2_experimental'; OUT.mkdir(parents=True,exist_ok=True)
QA=EXP/'qa'; QA.mkdir(exist_ok=True)
PATCHES=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']
LOCKED=['14A_001_residential','14A_003_dense_urban']
BASELINE=json.loads((ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A1E_model_c_metrics.json').read_text())

import torch
from torch.utils.data import Dataset, DataLoader
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead

torch.set_num_threads(4)
def sha256(p):
    h=hashlib.sha256();
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def build_model(state):
    m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True); m.classifier=DeepLabHead(2048,1); m.load_state_dict(state,strict=True); return m
def load_state(path):
    ck=torch.load(path,map_location='cpu',weights_only=True)
    if isinstance(ck,dict) and 'state_dict' in ck: ck=ck['state_dict']
    if any(k.startswith('model.') for k in ck): ck={k[6:]:v for k,v in ck.items()}
    return ck
def load_rgb(path):
    with rasterio.open(path) as ds:
        x=ds.read((1,2,3)).astype('float32'); mn=float(np.nanmin(x)); mx=float(np.nanmax(x));
    x=np.zeros_like(x,dtype='float32') if mx==mn else (x-mn)/(mx-mn)
    return np.nan_to_num(x),mn,mx
class SeedDS(Dataset):
    def __init__(self):
        self.items=[]
        for pid in PATCHES:
            rp=EXP/'train/rgb'/f'{pid}.tif'; mp=SEED_MASKS/f'{pid}.tif'; x,_,_=load_rgb(rp); y=rasterio.open(mp).read(1).astype('float32'); self.items.append((pid,x,y))
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        pid,x,y=self.items[i]; x=x.copy(); y=y.copy(); k=i%4
        if k==1: x=x[:,:,::-1].copy(); y=y[:,::-1].copy()
        elif k==2: x=x[:,::-1,:].copy(); y=y[::-1,:].copy()
        elif k==3: x=np.rot90(x,1,axes=(1,2)).copy(); y=np.rot90(y,1).copy()
        xt=torch.from_numpy(x[None]); yt=torch.from_numpy(y[None,None])
        xt=torch.nn.functional.interpolate(xt,size=(128,128),mode='bilinear',align_corners=False)[0]
        yt=torch.nn.functional.interpolate(yt,size=(128,128),mode='nearest')[0]
        return xt,yt,pid
def dice_loss(logits,target):
    p=torch.sigmoid(logits); inter=(p*target).sum((2,3)); den=p.sum((2,3))+target.sum((2,3)); return (1-(2*inter+1)/(den+1)).mean()
def dilate(a):
    z=np.zeros_like(a,bool)
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            z |= np.roll(np.roll(a,dy,0),dx,1)
    return z
def boundary(a): return a & ~((np.roll(a,1,0)&np.roll(a,-1,0)&np.roll(a,1,1)&np.roll(a,-1,1)))
def components(a):
    seen=np.zeros_like(a,bool); out=0; h,w=a.shape
    for y,x in zip(*np.where(a)):
        if seen[y,x]: continue
        out+=1; stack=[(int(y),int(x))]; seen[y,x]=1
        while stack:
            yy,xx=stack.pop()
            for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<h and 0<=nx<w and a[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1; stack.append((ny,nx))
    return out
def metrics(pred,gt):
    p=pred.astype(bool); g=gt.astype(bool); tp=int((p&g).sum()); fp=int((p&~g).sum()); fn=int((~p&g).sum());
    iou=tp/(tp+fp+fn) if tp+fp+fn else 1.; dice=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.; prec=tp/(tp+fp) if tp+fp else 0.; rec=tp/(tp+fn) if tp+fn else 0.
    pb=boundary(p); gb=boundary(g); dp=dilate(pb); dg=dilate(gb)
    def bf(t):
        q=pb.copy(); r=gb.copy()
        for _ in range(t): q=dilate(q); r=dilate(r)
        return float(2*((pb&r).sum()+(gb&q).sum())/(pb.sum()+gb.sum()+1e-9))
    npred=components(p); ngt=components(g); matches=0
    # Object matching by connected-component IoU, using local flood fills.
    def masks(a):
        seen=np.zeros_like(a,bool); result=[]; h,w=a.shape
        for y,x in zip(*np.where(a)):
            if seen[y,x]: continue
            stack=[(int(y),int(x))]; seen[y,x]=1; pts=[]
            while stack:
                yy,xx=stack.pop(); pts.append((yy,xx))
                for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny,nx=yy+dy,xx+dx
                    if 0<=ny<h and 0<=nx<w and a[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1; stack.append((ny,nx))
            result.append(np.array(pts))
        return result
    gm=masks(g); pm=masks(p)
    for aa in gm:
        ar=set(map(tuple,aa)); best=0
        for bb in pm:
            br=set(map(tuple,bb)); inter=len(ar&br); union=len(ar|br); best=max(best,inter/union if union else 0)
        matches += int(best>=.30)
    op=matches/npred if npred else 0.; orc=matches/ngt if ngt else 0.; of=2*op*orc/(op+orc) if op+orc else 0.
    return {'TP':tp,'FP':fp,'FN':fn,'TN':int((~p&~g).sum()),'IoU':iou,'Dice':dice,'Precision':prec,'Recall':rec,'F1':dice,'BoundaryF1@1px':bf(1),'BoundaryF1@2px':bf(2),'BoundaryF1@3px':bf(3),'MeanBoundaryDistancePx':None,'MeanBoundaryDistanceM':None,'ObjectPrecision':op,'ObjectRecall':orc,'ObjectF1':of,'MissedBuildings':int(ngt-matches),'FalsePositiveBuildings':int(npred-matches),'PredictedBuildings':int(npred),'GTBuildings':int(ngt)}

state=load_state(CKPT); model=build_model(state); torch.save({'state_dict':state,'source':'MODEL_C','sha256':sha256(CKPT)},OUT/'initial_model_c2.pth')
for p in model.backbone.parameters(): p.requires_grad=False
for p in model.classifier.parameters(): p.requires_grad=True
for p in model.aux_classifier.parameters(): p.requires_grad=True
opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-5,weight_decay=1e-4)
ds=SeedDS(); dl=DataLoader(ds,batch_size=1,shuffle=False,num_workers=0)
history=[]; best=float('inf'); best_epoch=0; epochs=2; started=time.perf_counter()
for ep in range(1,epochs+1):
    if ep==2:
        for p in model.backbone.layer4.parameters(): p.requires_grad=True
        opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=5e-6,weight_decay=1e-4)
    model.train()
    for module in model.modules():
        if isinstance(module, torch.nn.modules.batchnorm._BatchNorm): module.eval()
    total=0.; sums={'IoU':0.,'Dice':0.,'Precision':0.,'Recall':0.}
    for x,y,pid in dl:
        opt.zero_grad(); out=model(x)['out']; bce=torch.nn.functional.binary_cross_entropy_with_logits(out,y); loss=bce+dice_loss(out,y); loss.backward(); opt.step(); total+=float(loss.item()); pred=(torch.sigmoid(out).detach().numpy()[:,0]>=.5); mm=metrics(pred[0],y.numpy()[0,0]);
        for k in sums: sums[k]+=mm[k]
    row={'epoch':ep,'train_loss':total/len(dl),'validation_loss':None,'IoU':sums['IoU']/len(dl),'Dice':sums['Dice']/len(dl),'Precision':sums['Precision']/len(dl),'Recall':sums['Recall']/len(dl)}; history.append(row)
    if row['train_loss']<best: best=row['train_loss']; best_epoch=ep; torch.save({'state_dict':model.state_dict(),'epoch':ep,'source':'MODEL_C','loss':'BCE + Dice','learning_rate':5e-6 if ep>=2 else 2e-5},OUT/'best_model_c2.pth')
torch.save({'state_dict':model.state_dict(),'epoch':epochs,'source':'MODEL_C'},OUT/'final_model_c2.pth')
(OUT/'training_config.json').write_text(json.dumps({'source_checkpoint':str(CKPT),'source_sha256':sha256(CKPT),'epochs':epochs,'training_resolution':'128x128 CPU conservation; source masks remain 512x512','loss':'BCE + Dice','building_weight':1.0,'background_weight':1.0,'phase1':'classifier and aux head; frozen backbone','phase2':'layer4 unfrozen; lr=5e-6','augmentations':['horizontal_flip','vertical_flip','rotation_90'],'seed_patches':PATCHES},indent=2),encoding='utf-8')
(QA/'14A3_training_history.json').write_text(json.dumps({'history':history,'best_epoch':best_epoch,'elapsed_s':time.perf_counter()-started},indent=2),encoding='utf-8')

# locked benchmark using final model and approved masks
model.eval(); bench={}
contact=[]
for pid in LOCKED:
    rgb=EXP.parent/'images'/f'{pid}.tif'; gtpath=EXP.parent/'masks/ground_truth_final'/f'{pid}.tif'
    x,_,_=load_rgb(rgb); gt=rasterio.open(gtpath).read(1).astype('uint8');
    with torch.inference_mode(): prob=torch.sigmoid(model(torch.from_numpy(x[None]))['out'])[0,0].numpy()
    pred=prob>=.5; mm=metrics(pred,gt); mm['patch_id']=pid; bench[pid]=mm
    im=Image.open(rgb).convert('RGB').resize((256,256)); gtim=Image.fromarray((gt*255).astype('uint8')).convert('RGB').resize((256,256)); pim=Image.fromarray((pred*255).astype('uint8')).convert('RGB').resize((256,256)); err=im.copy(); a=np.array(err); gb=gt.astype(bool); em=np.zeros_like(gb,dtype='uint8'); em[(pred&~gb)]=1; em[(~pred&gb)]=2; em=np.array(Image.fromarray(em).resize((256,256),Image.Resampling.NEAREST)); a[em==1]=[255,0,0]; a[em==2]=[0,0,255]; contact.append((pid,im,gtim,pim,Image.fromarray(a)))
globalm={k:(None if k=='MeanBoundaryDistancePx' else float(np.mean([b[k] for b in bench.values()]))) for k in ['IoU','Dice','Precision','Recall','F1','BoundaryF1@1px','BoundaryF1@2px','BoundaryF1@3px','MeanBoundaryDistancePx','ObjectF1']}; globalm.update({k:int(sum(b[k] for b in bench.values())) for k in ['MissedBuildings','FalsePositiveBuildings']})
comparison={'model_c_baseline':BASELINE['global'],'model_c2':{'patches':bench,'global':globalm},'production_promotion':'NO','decision':'MODEL_C2_PARTIAL_IMPROVEMENT' if globalm['Recall']>BASELINE['global']['pixel']['Recall'] else 'MODEL_C2_NO_IMPROVEMENT'}
(QA/'14A3_model_c2_metrics.json').write_text(json.dumps({'patches':bench,'global':globalm},indent=2),encoding='utf-8'); (QA/'14A3_model_c_vs_c2_comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(1024,256*len(contact)),'white'); d=ImageDraw.Draw(sheet)
for i,(pid,im,g,p,e) in enumerate(contact):
    for j,z in enumerate((im,g,p,e)): sheet.paste(z,(j*256,i*256));
    d.text((4,i*256+4),pid,fill='yellow')
sheet.save(QA/'14A3_MODEL_C_vs_C2_contact_sheet.png')
print(json.dumps({'epochs':epochs,'best_epoch':best_epoch,'benchmarks':globalm,'decision':comparison['decision']},indent=2))
