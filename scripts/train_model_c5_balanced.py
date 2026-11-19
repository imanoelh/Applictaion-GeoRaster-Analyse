from pathlib import Path
import json, csv, shutil, hashlib
import numpy as np, torch, rasterio
from PIL import Image, ImageDraw
from torch.utils.data import Dataset, DataLoader
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead

ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; EXP=BASE/'14A2_expansion'; QA=EXP/'qa'; OUT=ROOT/'backend/data/models/model_c5_experimental'; OUT.mkdir(exist_ok=True); torch.set_num_threads(4)
def load_state(p):
    s=torch.load(p,map_location='cpu',weights_only=True); return s.get('state_dict',s)
def make(s):
    m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True); m.classifier=DeepLabHead(2048,1); m.load_state_dict(s,strict=True); return m
def rgb(p):
    with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
    mn,mx=float(x.min()),float(x.max()); return np.zeros_like(x) if mx<=mn else (x-mn)/(mx-mn)
def dice_loss(z,y):
    q=torch.sigmoid(z); inter=(q*y).sum((2,3)); return 1-((2*inter+1)/(q.sum((2,3))+y.sum((2,3))+1)).mean()
def boundary(a): return a & ~((np.roll(a,1,0)&np.roll(a,-1,0)&np.roll(a,1,1)&np.roll(a,-1,1)))
def comps(a):
    seen=np.zeros_like(a,bool); n=0; h,w=a.shape
    for y,x in zip(*np.where(a)):
        if seen[y,x]: continue
        n+=1; st=[(int(y),int(x))]; seen[y,x]=1
        while st:
            yy,xx=st.pop()
            for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<h and 0<=nx<w and a[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1; st.append((ny,nx))
    return n
def obj_match(p,g,thr=.3):
    def masks(a):
        seen=np.zeros_like(a,bool); out=[]; h,w=a.shape
        for y,x in zip(*np.where(a)):
            if seen[y,x]: continue
            st=[(int(y),int(x))]; seen[y,x]=1; pts=[]
            while st:
                yy,xx=st.pop(); pts.append((yy,xx))
                for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny,nx=yy+dy,xx+dx
                    if 0<=ny<h and 0<=nx<w and a[ny,nx] and not seen[ny,nx]: seen[ny,nx]=1; st.append((ny,nx))
            if pts: out.append(set(pts))
        return out
    pp,gg=masks(p),masks(g); pairs=[]
    for i,a in enumerate(pp):
        for j,b in enumerate(gg):
            u=a|b; pairs.append((len(a&b)/len(u) if u else 0,i,j))
    usedp=set(); usedg=set(); matched=0
    for ov,i,j in sorted(pairs,reverse=True):
        if ov>=thr and i not in usedp and j not in usedg: usedp.add(i); usedg.add(j); matched+=1
    return {'predictions':len(pp),'gt':len(gg),'matched':matched,'fp':len(pp)-matched,'missed':len(gg)-matched,'recall':matched/len(gg) if gg else 0,'precision':matched/len(pp) if pp else 0,'f1':2*matched/(len(pp)+len(gg)) if len(pp)+len(gg) else 0}
def metrics(p,g):
    tp=int((p&g).sum()); fp=int((p&~g).sum()); fn=int((~p&g).sum()); return {'pixel_iou':tp/(tp+fp+fn+1e-9),'pixel_recall':tp/(tp+fn+1e-9),'dice':2*tp/(2*tp+fp+fn+1e-9),'boundary_f1_1px':float(2*((boundary(p)&boundary(g)).sum())/(boundary(p).sum()+boundary(g).sum()+1e-9)),'object':obj_match(p,g,.3)}

manifest=json.loads((EXP/'crops_14A3D/crop_manifest.json').read_text()); pos=[r for r in manifest if r.get('type','').startswith('POSITIVE') and (EXP/'train/masks/seed_gt_fixed_candidate'/f"{r['patch_id']}.tif").exists()]
status=list(csv.DictReader((QA/'14A3E2_FIX_negative_statuses.csv').open(encoding='utf-8'))); valid_ids={r['candidate_id'] for r in status if r['qa_status']=='VALID_NEGATIVE'}
hn=json.loads((EXP/'balanced_dataset_14A3E/hard_negative_manifest.json').read_text()); neg=[r for r in hn if f"14A3E2_HN_{hn.index(r)+1:03d}" in valid_ids]
neg_png={r['crop_id']:EXP/'balanced_dataset_14A3E/hard_negatives'/f"{r['crop_id']}.png" for r in hn}
class DS(Dataset):
    def __init__(self,items): self.items=items
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        r=self.items[i]
        if r['kind']=='pos':
            x=rgb(EXP/'train/rgb'/f"{r['patch_id']}.tif")[:,r['y']:r['y']+256,r['x']:r['x']+256]; y=rasterio.open(EXP/'train/masks/seed_gt_fixed_candidate'/f"{r['patch_id']}.tif").read(1)[r['y']:r['y']+256,r['x']:r['x']+256].astype('float32')
        else:
            x=np.asarray(Image.open(neg_png[r['crop_id']]).convert('RGB')).transpose(2,0,1).astype('float32')/255.; y=np.zeros((256,256),dtype='float32')
        return torch.from_numpy(x.copy()),torch.from_numpy(y[None].copy())

# Internal validation uses one TRAIN patch, never the locked benchmark.
VALPID='14A2_2024_12'; train_pos=[r for r in pos if r['patch_id']!=VALPID]; val_arr=rgb(EXP/'train/rgb'/f'{VALPID}.tif'); val_gt=rasterio.open(EXP/'train/masks/seed_gt_fixed_candidate'/f'{VALPID}.tif').read(1).astype(bool)
def make_items(ratio):
    n=40; np_=round(n*ratio); nn=n-np_; a=[]
    for r in train_pos[::max(1,len(train_pos)//np_)][:np_]: a.append({'kind':'pos',**r})
    for i in range(nn):
        r=neg[i%len(neg)]; a.append({'kind':'neg',**r})
    return a
configs={'CONFIG_A':.60,'CONFIG_B':.50,'CONFIG_C':.40}; results={}; source=load_state(ROOT/'backend/data/models/model_c3_experimental/final_model_c3.pth')
for name,ratio in configs.items():
    m=make(source); [setattr(p,'requires_grad',False) for p in m.backbone.parameters()]; [setattr(p,'requires_grad',True) for p in m.classifier.parameters()]; [setattr(p,'requires_grad',True) for p in m.aux_classifier.parameters()]
    for mod in m.modules():
        if isinstance(mod,torch.nn.modules.batchnorm._BatchNorm): mod.eval()
    dl=DataLoader(DS(make_items(ratio)),batch_size=1,shuffle=True,num_workers=0); opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=1e-5,weight_decay=1e-4); total=0.; m.train()
    for x,y in dl:
        opt.zero_grad(); z=m(x)['out']; loss=torch.nn.functional.binary_cross_entropy_with_logits(z,y)+dice_loss(z,y); loss.backward(); opt.step(); total+=float(loss.item())
    m.eval()
    with torch.inference_mode(): z=torch.sigmoid(m(torch.from_numpy(val_arr[None]))['out'])[0,0].numpy()
    vm=metrics(z>=.5,val_gt); results[name]={'positive_fraction':ratio,'crops':40,'positive_crops':round(40*ratio),'negative_crops':40-round(40*ratio),'loss':'Weighted BCE + Dice','train_loss':total/len(dl),'internal_validation':vm}
    torch.save({'state_dict':m.state_dict(),'source':'MODEL_C3','config':name,'loss':'Weighted BCE + Dice'},OUT/f'{name.lower()}_model_c5.pth')
best_name=max(results,key=lambda k:(results[k]['internal_validation']['object']['f1'],results[k]['internal_validation']['object']['recall'],-results[k]['internal_validation']['object']['fp']))
best_state=torch.load(OUT/f'{best_name.lower()}_model_c5.pth',map_location='cpu',weights_only=True); torch.save({'state_dict':best_state['state_dict'],'source':'MODEL_C3','selected_config':best_name,'loss':'Weighted BCE + Dice'},OUT/'final_model_c5.pth')
(OUT/'training_config.json').write_text(json.dumps({'source':'MODEL_C3','resolution':'256x256 native crops','batch_size':1,'epochs':1,'loss':'Weighted BCE + Dice','configs':results,'selected_config':best_name,'val_patch':VALPID,'locked_benchmark_used_for_selection':False},indent=2),encoding='utf-8')

# Single locked benchmark after selection.
m=make(best_state['state_dict']); m.eval(); LOCKED=['14A_001_residential','14A_003_dense_urban']; bench={}; panels=[]
for pid in LOCKED:
    x=rgb(BASE/'images'/f'{pid}.tif'); g=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool)
    with torch.inference_mode(): p=torch.sigmoid(m(torch.from_numpy(x[None]))['out'])[0,0].numpy()>=.5
    bench[pid]=metrics(p,g); im=Image.fromarray((x.transpose(1,2,0)*255).clip(0,255).astype('uint8')).resize((256,256)); panels.append((pid,im))
glob={k:float(np.mean([bench[p][k] for p in LOCKED])) for k in ('pixel_iou','pixel_recall','dice','boundary_f1_1px')}; glob.update({k:sum(bench[p]['object'][k] for p in LOCKED) for k in ('predictions','matched','fp','missed')}); glob.update({'object_recall':glob['matched']/47,'object_precision':glob['matched']/glob['predictions'],'object_f1':2*glob['matched']/(glob['predictions']+47)})
c3r=.2190;c3f=.2585; decision='MODEL_C5_CLEAR_IMPROVEMENT' if glob['object_recall']>c3r and glob['object_f1']>c3f and glob['fp']<25 else ('MODEL_C5_PARTIAL_IMPROVEMENT' if glob['object_recall']>c3r or glob['object_f1']>c3f else 'MODEL_C5_NO_IMPROVEMENT')
(QA/'14A3F_config_comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8'); (QA/'14A3F_model_c5_metrics.json').write_text(json.dumps({'patches':bench,'global':glob,'selected_config':best_name,'decision':decision},indent=2),encoding='utf-8'); (QA/'14A3F_model_c3_vs_c5.json').write_text(json.dumps({'MODEL_C3_CALIBRATED':{'object_recall':c3r,'object_f1':c3f,'fp':14,'missed':37},'MODEL_C5':glob,'decision':decision,'production_promotion':'NO'},indent=2),encoding='utf-8')
sheet=Image.new('RGB',(512,256*len(panels)),'white'); d=ImageDraw.Draw(sheet)
for i,(pid,im) in enumerate(panels): sheet.paste(im,(0,i*256)); d.text((4,i*256+4),f'{pid} MODEL_C5',fill='yellow')
sheet.save(QA/'14A3F_contact_sheet.png'); print(json.dumps({'selected_config':best_name,'metrics':glob,'decision':decision},indent=2))
