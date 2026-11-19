from pathlib import Path
import json, time
import numpy as np
from PIL import Image, ImageDraw
import rasterio, torch
from torch.utils.data import Dataset, DataLoader
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; EXP=BASE/'14A2_expansion'; MASKS=EXP/'masks/seed_gt_fixed_candidate'; CKPT=ROOT/'backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth'; OUT=ROOT/'backend/data/models/model_c3_experimental'; OUT.mkdir(parents=True,exist_ok=True); QA=EXP/'qa'; QA.mkdir(exist_ok=True)
PIDS=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']; LOCKED=['14A_001_residential','14A_003_dense_urban']; torch.set_num_threads(4)
BASE_C={'IoU':0.1312,'Recall':0.1465,'BoundaryF1@1px':0.0640,'ObjectF1':0.1728,'FalsePositives':27,'MissedBuildings':40}; BASE_C2={'IoU':0.1483,'Recall':0.1703,'BoundaryF1@1px':0.1757,'ObjectF1':0.1607,'FalsePositives':34,'MissedBuildings':40}
def load_rgb(p):
    with rasterio.open(p) as ds: x=ds.read((1,2,3)).astype('float32')
    mn=float(x.min()); mx=float(x.max()); return np.zeros_like(x) if mx==mn else (x-mn)/(mx-mn)
def load_state(p):
    s=torch.load(p,map_location='cpu',weights_only=True); s=s.get('state_dict',s); return {k[6:] if k.startswith('model.') else k:v for k,v in s.items()}
def model_from(s):
    m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True); m.classifier=DeepLabHead(2048,1); m.load_state_dict(s,strict=True); return m
def dilate(a):
    z=np.zeros_like(a,bool)
    for dy in (-1,0,1):
        for dx in (-1,0,1): z|=np.roll(np.roll(a,dy,0),dx,1)
    return z
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
def score(p,g):
    p=p.astype(bool); g=g.astype(bool); tp=int((p&g).sum()); fp=int((p&~g).sum()); fn=int((~p&g).sum()); iou=tp/(tp+fp+fn+1e-9); dice=2*tp/(2*tp+fp+fn+1e-9); rec=tp/(tp+fn+1e-9); prec=tp/(tp+fp+1e-9); pb=boundary(p); gb=boundary(g); q=dilate(pb); r=dilate(gb); bf=float(2*((pb&r).sum()+(gb&q).sum())/(pb.sum()+gb.sum()+1e-9)); npred=comps(p); ngt=comps(g); return {'IoU':iou,'Dice':dice,'Precision':prec,'Recall':rec,'F1':dice,'BoundaryF1@1px':bf,'ObjectF1':2*min(npred,ngt)/(npred+ngt+1e-9),'FalsePositives':max(0,npred-min(npred,ngt)),'MissedBuildings':max(0,ngt-min(npred,ngt)),'PredictedBuildings':npred,'GTBuildings':ngt}
class Crops(Dataset):
    def __init__(self):
        self.items=[]
        for pid in PIDS:
            x=load_rgb(EXP/'train/rgb'/f'{pid}.tif'); y=rasterio.open(MASKS/f'{pid}.tif').read(1).astype('float32'); cand=[]
            for yy in (0,256):
                for xx in (0,256): cand.append((float(y[yy:yy+256,xx:xx+256].mean()),x[:,yy:yy+256,xx:xx+256],y[yy:yy+256,xx:xx+256]))
            cand.sort(key=lambda z:z[0]); self.items.extend([(pid,cand[0][1],cand[0][2],0),(pid,cand[-1][1],cand[-1][2],1)])
    def __len__(self): return len(self.items)
    def __getitem__(self,i):
        pid,x,y,_=self.items[i]; return torch.from_numpy(x.copy()),torch.from_numpy(y[None].copy()),pid
def train_loss(kind, model, dl, epochs=2):
    for p in model.backbone.parameters(): p.requires_grad=False
    for p in model.classifier.parameters(): p.requires_grad=True
    for p in model.aux_classifier.parameters(): p.requires_grad=True
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-5,weight_decay=1e-4); hist=[]; best=1e9; best_ep=0
    for ep in range(1,epochs+1):
        if ep==2:
            for p in model.backbone.layer4.parameters(): p.requires_grad=True
            opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=5e-6,weight_decay=1e-4)
        model.train()
        for m in model.modules():
            if isinstance(m,torch.nn.modules.batchnorm._BatchNorm): m.eval()
        total=0.; rec=[]
        for x,y,pid in dl:
            opt.zero_grad(); out=model(x)['out']; bce=torch.nn.functional.binary_cross_entropy_with_logits(out,y); prob=torch.sigmoid(out); inter=(prob*y).sum((2,3)); dice=1-((2*inter+1)/(prob.sum((2,3))+y.sum((2,3))+1)).mean(); loss=bce+dice if kind=='BCE_DICE' else 0.5*bce+dice; loss.backward(); opt.step(); total+=float(loss.item()); rec.append(score((prob.detach().numpy()[0,0]>=.5),y.numpy()[0,0]))
        row={'epoch':ep,'train_loss':total/len(dl),'IoU':float(np.mean([z['IoU'] for z in rec])),'Recall':float(np.mean([z['Recall'] for z in rec]))}; hist.append(row)
        if row['train_loss']<best: best=row['train_loss']; best_ep=ep; torch.save({'state_dict':model.state_dict(),'epoch':ep,'loss':kind},OUT/f'best_model_c3_{kind}.pth')
    return hist,best_ep,best
state=load_state(CKPT); ds=Crops(); dl=DataLoader(ds,batch_size=1,shuffle=False,num_workers=0); configs={}; selected=None
for kind in ('BCE_DICE','WEIGHTED_BCE_DICE'):
    m=model_from(state); hist,be,b=train_loss(kind,m,dl); configs[kind]={'history':hist,'best_epoch':be,'best_train_loss':b,'resolution':'256x256 crops','positive_crops':5,'negative_crops':5}
    if selected is None or b<selected[0]: selected=(b,kind,be)
kind=selected[1]; best_state=torch.load(OUT/f'best_model_c3_{kind}.pth',map_location='cpu',weights_only=True)['state_dict']; torch.save({'state_dict':best_state,'source':'MODEL_C','selected_loss':kind,'best_epoch':selected[2]},OUT/'final_model_c3.pth')
(OUT/'training_config.json').write_text(json.dumps({'source':'MODEL_C','resolution':'256x256 native crops','crop_strategy':'2 positive/negative quadrant crops per patch','batch_size':1,'gradient_accumulation':1,'configs':configs,'selected_config':kind,'seed_patches':PIDS,'locked_benchmark_excluded_from_tuning':True},indent=2),encoding='utf-8'); (QA/'14A3B_training_config_comparison.json').write_text(json.dumps(configs,indent=2),encoding='utf-8')
m=model_from(best_state); m.eval(); bench={}; panels=[]
for pid in LOCKED:
    x=load_rgb(BASE/'images'/f'{pid}.tif'); gt=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype('uint8')
    with torch.inference_mode(): prob=torch.sigmoid(m(torch.from_numpy(x[None]))['out'])[0,0].numpy()
    pred=prob>=.5; z=score(pred,gt); z['patch_id']=pid; bench[pid]=z; im=Image.open(BASE/'images'/f'{pid}.tif').convert('RGB').resize((256,256)); g=Image.fromarray((gt*255).astype('uint8')).convert('RGB').resize((256,256)); p=Image.fromarray((pred*255).astype('uint8')).convert('RGB').resize((256,256)); a=np.array(im); em=np.zeros_like(gt,dtype='uint8'); em[(pred&~gt.astype(bool))]=1; em[(~pred&gt.astype(bool))]=2; em=np.array(Image.fromarray(em).resize((256,256),Image.Resampling.NEAREST)); a[em==1]=[255,0,0]; a[em==2]=[0,0,255]; panels.append((pid,im,g,p,Image.fromarray(a)))
globalm={k:float(np.mean([v[k] for v in bench.values()])) for k in ['IoU','Dice','Precision','Recall','F1','BoundaryF1@1px','ObjectF1']}; globalm.update({k:int(sum(v[k] for v in bench.values())) for k in ['FalsePositives','MissedBuildings']})
decision='MODEL_C3_CLEAR_IMPROVEMENT' if globalm['Recall']>BASE_C2['Recall'] and globalm['ObjectF1']>=BASE_C2['ObjectF1'] and globalm['FalsePositives']<=BASE_C2['FalsePositives'] else ('MODEL_C3_PARTIAL_IMPROVEMENT' if globalm['Recall']>BASE_C2['Recall'] else 'MODEL_C3_NO_IMPROVEMENT')
(QA/'14A3B_model_c3_metrics.json').write_text(json.dumps({'patches':bench,'global':globalm},indent=2),encoding='utf-8'); (QA/'14A3B_model_c_c2_c3_comparison.json').write_text(json.dumps({'MODEL_C':BASE_C,'MODEL_C2':BASE_C2,'MODEL_C3':globalm,'decision':decision,'production_promotion':'NO'},indent=2),encoding='utf-8')
sheet=Image.new('RGB',(1280,256*len(panels)),'white'); d=ImageDraw.Draw(sheet)
for i,(pid,im,g,p,e) in enumerate(panels):
    for j,z in enumerate((im,g,im,p,e)): sheet.paste(z,(j*256,i*256))
    d.text((4,i*256+4),pid,fill='yellow')
sheet.save(QA/'14A3B_MODEL_C_C2_C3_contact_sheet.png'); print(json.dumps({'selected_loss':kind,'best_epoch':selected[2],'metrics':globalm,'decision':decision},indent=2))
