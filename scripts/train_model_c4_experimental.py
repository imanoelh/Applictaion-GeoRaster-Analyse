from pathlib import Path
import json,random,numpy as np,torch,rasterio,onnx
from torch.utils.data import Dataset,DataLoader
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision';EXP=BASE/'14A2_expansion';OUT=ROOT/'backend/data/models/model_c4_experimental';OUT.mkdir(exist_ok=True);META=json.loads((EXP/'crops_14A3D/crop_manifest.json').read_text());torch.set_num_threads(4)
def load_state(p):
 s=torch.load(p,map_location='cpu',weights_only=True);s=s.get('state_dict',s);return s
def make(s):
 m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);m.classifier=DeepLabHead(2048,1);m.load_state_dict(s,strict=True);return m
def rgb(p):
 with rasterio.open(p) as d:x=d.read((1,2,3)).astype('float32')
 mn,mx=x.min(),x.max();return np.zeros_like(x) if mx==mn else (x-mn)/(mx-mn)
class DS(Dataset):
 def __init__(self,items):self.items=items
 def __len__(self):return len(self.items)
 def __getitem__(self,i):
  r=self.items[i];x=rgb(EXP/'train/rgb'/f"{r['patch_id']}.tif")[:,r['y']:r['y']+256,r['x']:r['x']+256];y=rasterio.open(EXP/'masks/seed_gt_fixed_candidate'/f"{r['patch_id']}.tif").read(1)[r['y']:r['y']+256,r['x']:r['x']+256].astype('float32');return torch.from_numpy(x.copy()),torch.from_numpy(y[None].copy())
# balanced representative set
pos=[r for r in META if r['type'].startswith('POSITIVE')];neg=[r for r in META if r['type'].startswith('NEGATIVE')];items=pos[::max(1,len(pos)//30)][:30]+neg*4;items=items[:40];m=make(load_state(ROOT/'backend/data/models/model_c3_experimental/final_model_c3.pth'));torch.save({'state_dict':m.state_dict(),'source':'MODEL_C3'},OUT/'initial_model_c4.pth')
for p in m.backbone.parameters():p.requires_grad=False
for p in m.classifier.parameters():p.requires_grad=True
for p in m.aux_classifier.parameters():p.requires_grad=True
opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=1e-5,weight_decay=1e-4);dl=DataLoader(DS(items),batch_size=1,shuffle=True,num_workers=0);m.train()
for mod in m.modules():
 if isinstance(mod,torch.nn.modules.batchnorm._BatchNorm):mod.eval()
total=0
for x,y in dl:
 opt.zero_grad();o=m(x)['out'];b=torch.nn.functional.binary_cross_entropy_with_logits(o,y);q=torch.sigmoid(o);inter=(q*y).sum((2,3));d=1-((2*inter+1)/(q.sum((2,3))+y.sum((2,3))+1)).mean();loss=.5*b+d;loss.backward();opt.step();total+=float(loss)
m.eval();torch.save({'state_dict':m.state_dict(),'source':'MODEL_C3','loss':'Weighted BCE + Dice','epochs':1},OUT/'final_model_c4.pth');(OUT/'training_config.json').write_text(json.dumps({'source':'MODEL_C3','resolution':'256x256 native crops','crops_used':len(items),'positive_crops':sum(r['type'].startswith('POSITIVE') for r in items),'negative_crops':sum(r['type'].startswith('NEGATIVE') for r in items),'loss':'Weighted BCE + Dice','epochs':1,'weight_decay':1e-4},indent=2),encoding='utf-8');
class W(torch.nn.Module):
 def __init__(self,m):super().__init__();self.m=m
 def forward(self,x):return self.m(x)['out']
out=OUT/'model_c4.onnx';torch.onnx.export(W(m),torch.randn(1,3,512,512),str(out),input_names=['image'],output_names=['out'],opset_version=17,dynamic_axes={'image':{0:'batch'},'out':{0:'batch'}});print(json.dumps({'crops':len(items),'loss':float(total/len(dl)),'onnx':str(out)}))
