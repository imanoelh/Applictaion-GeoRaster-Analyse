from pathlib import Path
import numpy as np, torch, rasterio
from PIL import Image,ImageDraw
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path('.'); BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'; C=ROOT/'backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth'; C2=ROOT/'backend/data/models/model_c2_experimental/final_model_c2.pth'; C3=ROOT/'backend/data/models/model_c3_experimental/final_model_c3.pth'
def st(p):
 s=torch.load(p,map_location='cpu',weights_only=True); s=s.get('state_dict',s); return {k[6:] if k.startswith('model.') else k:v for k,v in s.items()}
def mdl(p):
 m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True); m.classifier=DeepLabHead(2048,1); m.load_state_dict(st(p),strict=True); m.eval(); return m
def rgb(p):
 with rasterio.open(p) as d: x=d.read((1,2,3)).astype('float32')
 mn,mx=x.min(),x.max(); return (x-mn)/(mx-mn)
models=[mdl(C),mdl(C2),mdl(C3)]; panels=[]
for pid in ['14A_001_residential','14A_003_dense_urban']:
 x=rgb(BASE/'images'/f'{pid}.tif'); gt=rasterio.open(BASE/'masks/ground_truth_final'/f'{pid}.tif').read(1).astype(bool); imgs=[Image.open(BASE/'images'/f'{pid}.tif').convert('RGB').resize((256,256)),Image.fromarray((gt*255).astype('uint8')).convert('RGB').resize((256,256))]
 preds=[]
 for m in models:
  with torch.inference_mode(): preds.append((torch.sigmoid(m(torch.from_numpy(x[None]))['out'])[0,0].numpy()>=.5))
 imgs += [Image.fromarray((p*255).astype('uint8')).convert('RGB').resize((256,256)) for p in preds]
 em=Image.new('RGB',(256,256),'black'); a=np.array(imgs[0]);
 for p,c in zip(preds,[(255,128,0),(180,0,255),(0,255,0)]):
  q=np.array(Image.fromarray(p.astype('uint8')).resize((256,256),Image.Resampling.NEAREST)).astype(bool); a[q]=c
 imgs.append(Image.fromarray(a)); panels.append((pid,imgs))
out=BASE/'14A2_expansion/qa/14A3B_MODEL_C_C2_C3_contact_sheet.png'; sheet=Image.new('RGB',(1536,512),'white'); d=ImageDraw.Draw(sheet)
labels=['RGB','GT','MODEL_C','MODEL_C2','MODEL_C3','OVERLAY']
for i,(pid,imgs) in enumerate(panels):
 for j,z in enumerate(imgs): sheet.paste(z,(j*256,i*256)); d.text((j*256+4,i*256+4),labels[j],fill='yellow')
 d.text((4,i*256+240),pid,fill='yellow')
sheet.save(out); print(out)
