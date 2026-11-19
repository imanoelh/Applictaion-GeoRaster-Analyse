from __future__ import annotations
import json,time,hashlib
from pathlib import Path
import numpy as np,rasterio,onnxruntime as ort,torch
from rasterio.windows import Window
from rasterio.features import shapes
from shapely.geometry import shape,mapping
from shapely import make_valid
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; RASTER=ROOT/'backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif'; C=ROOT/'backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx'; F=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_f_segformer/best_segformer.pth'; OUT=ROOT/'backend/data/models/building/experimental/benchmark_13Q2';OUT.mkdir(parents=True,exist_ok=True)
def poly(mask,transform,crs,path,model):
 fs=[]
 for g,v in shapes(mask.astype('uint8'),mask=mask.astype(bool),transform=transform,connectivity=8):
  p=shape(g)
  if not p.is_valid:p=make_valid(p)
  if not p.is_empty:fs.append({'type':'Feature','geometry':mapping(p),'properties':{'model':model,'area_map_units2':float(p.area)}})
 path.write_text(json.dumps({'type':'FeatureCollection','features':fs,'crs':{'type':'name','properties':{'name':str(crs)}}},indent=2),encoding='utf-8');return fs
def run():
 with rasterio.open(RASTER) as src:
  print('raster',src.width,src.height,src.crs,src.res); sizes=[2048,4096]; origins={2048:(3000,3500),4096:(2000,2500)}
  c=ort.InferenceSession(str(C),providers=['CPUExecutionProvider']);
  import sys;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend')); from transformers import SegformerConfig,SegformerForSemanticSegmentation
  sd=torch.load(F,map_location='cpu',weights_only=True);sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()};fm=SegformerForSemanticSegmentation(SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256));fm.load_state_dict(sd,strict=True);fm.eval()
  # C production uses global source min/max; compute without modifying the raster.
  gmin,gmax=float('inf'),float('-inf')
  for row in range(0,src.height,1024):
   for col in range(0,src.width,1024):
    a=src.read((1,2,3),window=Window(col,row,min(1024,src.width-col),min(1024,src.height-row)),masked=True);v=a.compressed();
    if v.size:gmin=min(gmin,float(v.min()));gmax=max(gmax,float(v.max()))
  allrows=[]
  for size in sizes:
   r0,c0=origins[size]; win=Window(c0,r0,size,size); data=src.read((1,2,3),window=win); profile=src.profile.copy(); transform=src.window_transform(win); profile.update(width=size,height=size,transform=transform,count=1)
   rgb=np.moveaxis(data,0,-1); outputs={};
   for model in ('MODEL_C','MODEL_F'):
    prob=np.zeros((size,size),np.float32); t=time.perf_counter();
    for rr in range(0,size,512):
     for cc in range(0,size,512):
      tile=data[:,rr:rr+512,cc:cc+512].astype('float32')
      if model=='MODEL_C':
       tile=(tile-gmin)/((gmax-gmin) if gmax!=gmin else 1.0); y=c.run(None,{c.get_inputs()[0].name:tile[None]})[0]; y=1/(1+np.exp(-y));p=y[0,0]
      else:
       with torch.inference_mode(): y=fm(pixel_values=torch.from_numpy(tile/255.).unsqueeze(0)).logits; y=torch.nn.functional.interpolate(y,size=(512,512),mode='bilinear',align_corners=False);p=torch.sigmoid(y[0,0]).numpy()
      prob[rr:rr+512,cc:cc+512]=p
    sec=time.perf_counter()-t; binary=prob>=.5; d=OUT/(model.lower()+f'_{size}');(d/'probability').mkdir(parents=True,exist_ok=True);(d/'binary').mkdir(parents=True,exist_ok=True);(d/'overlay').mkdir(parents=True,exist_ok=True)
    pp=profile.copy();pp.update(driver='GTiff',dtype='float32',nodata=None,compress='deflate');
    with rasterio.open(d/'probability/map.tif','w',**pp) as dst:dst.write(prob,1)
    pp.update(dtype='uint8');
    with rasterio.open(d/'binary/mask.tif','w',**pp) as dst:dst.write(binary.astype('uint8'),1)
    fs=poly(binary,transform,src.crs,d/'polygons.geojson',model); Image.fromarray(rgb.astype('uint8'),'RGB').save(d/'rgb.png'); im=Image.fromarray(rgb.astype('uint8'),'RGB').convert('RGBA');ov=np.zeros((*binary.shape,4),np.uint8);ov[binary]=(255,30,20,100);Image.alpha_composite(im,Image.fromarray(ov,'RGBA')).convert('RGB').save(d/'overlay/overlay.png')
    area=float(binary.sum()*abs(src.res[0]*src.res[1])); outputs[model]={'candidate_count':len(fs),'positive_pixels':int(binary.sum()),'total_area_m2':area,'processing_seconds':sec,'seconds_per_mp':sec/(size*size/1e6),'transform':list(transform),'crs':str(src.crs),'bounds':list(rasterio.transform.array_bounds(size,size,transform))}
   allrows.append({'size':size,'window':{'row':r0,'col':c0},'models':outputs})
 (OUT/'summary.json').write_text(json.dumps({'raster':str(RASTER.relative_to(ROOT)),'sizes':allrows,'model_c_preprocessing':'global RGB min-max','model_f_preprocessing':'RGB /255; 512 tiles; native 128 logits upsampled bilinear'},indent=2),encoding='utf-8');print(json.dumps(allrows,indent=2))
if __name__=='__main__':run()
