from __future__ import annotations
import json,time,sys
from pathlib import Path
import numpy as np, rasterio, onnxruntime as ort, torch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test'; OLD=ROOT/'backend/data/models/building/experimental/benchmark_13L/outputs'; Q0=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B'; OUT=ROOT/'backend/data/models/building/experimental/benchmark_13Q1_FINAL'; OUT.mkdir(parents=True,exist_ok=True)
PIDS=['GT_2024_difficult_02','GT_2024_industrial_02','GT_2024_residential_02','GT_2025_difficult_02','GT_2025_industrial_02','GT_2025_residential_02']
def scores(p,g):
 p=p.astype(bool);g=g.astype(bool);tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum());i=tp/(tp+fp+fn) if tp+fp+fn else 1.;d=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.;pr=tp/(tp+fp) if tp+fp else 0.;rc=tp/(tp+fn) if tp+fn else 0.;return dict(iou=i,dice=d,precision=pr,recall=rc,f1=d,tp=tp,fp=fp,fn=fn)
def main():
 sys.path.insert(0,str(ROOT/'backend')); import segmentation_models_pytorch as smp
 from transformers import SegformerConfig,SegformerForSemanticSegmentation
 f=Q0/'model_f_segformer/best_segformer.pth'; sd=torch.load(f,map_location='cpu',weights_only=True); sd={k[6:] if k.startswith('model.') else k:v for k,v in sd.items()}; cfg=SegformerConfig(num_labels=1,hidden_sizes=[32,64,160,256],depths=[2,2,2,2],num_attention_heads=[1,2,5,8],decoder_hidden_size=256); t=time.perf_counter(); fm=SegformerForSemanticSegmentation(cfg); res=fm.load_state_dict(sd,strict=True); fload=time.perf_counter()-t;fm.eval()
 gpath=Q0/'model_g_dinov3s/model.onnx'; gs=ort.InferenceSession(str(gpath),providers=['CPUExecutionProvider']); gdiag={}
 hpath=ROOT/'backend/data/models/building/experimental/benchmark_13L/hotosm_unet_instance/unet_bldg_instance.pth'; t=time.perf_counter(); hm=smp.Unet(encoder_name='resnet34',encoder_weights=None,in_channels=3,classes=3).eval(); hm.load_state_dict(torch.load(hpath,map_location='cpu',weights_only=True),strict=True); hload=time.perf_counter()-t
 rows=[]; loads={'MODEL_F_seconds':fload,'MODEL_H_seconds':hload}
 for pid in PIDS:
  with rasterio.open(BASE/'images'/(pid+'.tif')) as src: rgb=src.read((1,2,3)); hwc=np.moveaxis(rgb,0,-1); profile=src.profile.copy()
  with rasterio.open(BASE/'qa_13M1A/masks'/(pid+'_ground_truth_mask.tif')) as src: gt=src.read(1)>0
  # F: documented training pipeline uses RGB uint8 scaled to [0,1].
  x=torch.from_numpy(rgb.astype('float32')/255.).unsqueeze(0); t=time.perf_counter()
  with torch.inference_mode(): flog=fm(pixel_values=x).logits; flog=torch.nn.functional.interpolate(flog,size=(512,512),mode='bilinear',align_corners=False)
  fp=torch.sigmoid(flog[0,0]).numpy(); ft=time.perf_counter()-t
  # G: official README does not identify which of its three logits is building; retain diagnostics only.
  tile=rgb[:,:256,:256].astype('float32')/255.; t=time.perf_counter(); gy=gs.run(None,{'image':tile[None]})[0]; gtime=time.perf_counter()-t; gdiag[pid]={'shape':list(gy.shape),'min':float(gy.min()),'max':float(gy.max()),'mean_channels':gy.mean((0,2,3)).tolist(),'smoke_seconds':gtime,'semantics':'UNRESOLVED_THREE_LOGIT_CHANNELS'}
  # C/H archived masks are the same six-patch predictions used by 13L.
  with rasterio.open(OLD/'model_c/probability'/(pid+'.tif')) as src: cp=src.read(1)
  with rasterio.open(OLD/'hotosm_unet_resnet34/probability'/(pid+'.tif')) as src: hp=src.read(1)
  for model,prob,sec in [('MODEL_C',cp,None),('MODEL_F',fp,ft),('MODEL_H',hp,None)]:
   pred=prob>=.5; rows.append({'patch_id':pid,'model':model,'inference_seconds':sec,**scores(pred,gt)})
   d=OUT/model.lower(); (d/'probability').mkdir(parents=True,exist_ok=True); (d/'binary').mkdir(parents=True,exist_ok=True); (d/'overlay').mkdir(parents=True,exist_ok=True)
   p=profile.copy();p.update(driver='GTiff',count=1,dtype='float32',nodata=None,compress='deflate');
   with rasterio.open(d/'probability'/(pid+'.tif'),'w',**p) as dst: dst.write(prob.astype('float32'),1)
   p.update(dtype='uint8');
   with rasterio.open(d/'binary'/(pid+'.tif'),'w',**p) as dst: dst.write(pred.astype('uint8'),1)
   im=Image.fromarray(hwc.astype('uint8'),'RGB').convert('RGBA'); c=np.zeros((*pred.shape,4),dtype=np.uint8); c[pred]=(255,35,20,100); Image.alpha_composite(im,Image.fromarray(c,'RGBA')).convert('RGB').save(d/'overlay'/(pid+'.png'))
 summary={}
 for model in ('MODEL_C','MODEL_F','MODEL_H'):
  rr=[r for r in rows if r['model']==model]; summary[model]={k:float(np.mean([r[k] for r in rr])) for k in ('iou','dice','precision','recall','f1')}
 (OUT/'patch_metrics.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(OUT/'model_g_output_diagnostics.json').write_text(json.dumps(gdiag,indent=2),encoding='utf-8');(OUT/'environment.json').write_text(json.dumps({'python':sys.version,'torch':torch.__version__,'transformers':'4.46.3 isolated','onnxruntime':ort.__version__,'model_g_semantics':'UNRESOLVED'},indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
