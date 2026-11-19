from __future__ import annotations
import json,os,sys,subprocess
from pathlib import Path
import numpy as np,rasterio
from rasterio.windows import Window
from rasterio.features import shapes
from shapely.geometry import shape,mapping

ROOT=Path(__file__).resolve().parents[1]; BACKEND=ROOT/'backend'; BASE=BACKEND/'data/fine_tuning/buildings/maxar_v2_high_precision'; OUT=BASE/'14A2_expansion'; EXE=r'C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe'; OUT.mkdir(exist_ok=True)
for p in ['train/rgb','train/metadata','val/rgb','val/metadata','test_locked','annotations','pseudo_labels/model_c/probability','pseudo_labels/model_c/mask','pseudo_labels/model_c/geojson','pseudo_labels/model_c/overlays','qa']: (OUT/p).mkdir(parents=True,exist_ok=True)
sources={'2024':ROOT/'test-data/validation-results/maxar_rgb_derivatives/maxar_2024_rgb_p2p98.tif','2025':ROOT/'test-data/validation-results/maxar_rgb_derivatives/maxar_2025_rgb_p2p98.tif'}
# Keep new cells away from the locked 13M/13Q bottom-right area and the two pilot
# patches in column 0.  The resulting ten cells per source year provide 20 new
# patches while preserving a strict spatial holdout.
cells=[(0,3),(1,0),(1,1),(1,2),(1,3),(2,0),(2,1),(2,2),(2,3),(3,2)]; valcells={(2,0),(2,1)}; rows=[]; excluded=[]
sys.path.insert(0,str(BACKEND)); os.environ.setdefault('SPACENET2_ORT_INTRA_THREADS','8');os.environ.setdefault('SPACENET2_ORT_INTER_THREADS','2')
from app.ai.models.spacenet2_deeplab_adapter import SpaceNet2DeepLabAdapter
from app.ai.services.tiling_service import TilingService
MODEL=BACKEND/'data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth'; SHA='170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555'; adapter=SpaceNet2DeepLabAdapter(MODEL,expected_sha256=SHA,engine='onnxruntime');adapter.load()
for year,src_path in sources.items():
 with rasterio.open(src_path) as src:
  for col,row in cells:
   patch=f'14A2_{year}_{row*4+col+1:02d}'; split='val' if (col,row) in valcells else 'train'; win=Window(col*512,row*512,512,512); prof=src.profile.copy(); prof.update(width=512,height=512,transform=rasterio.windows.transform(win,src.transform),count=3,dtype='uint8',compress='deflate'); rgb=src.read((1,2,3),window=win)
   img=OUT/split/'rgb'/(patch+'.tif');
   with rasterio.open(img,'w',**prof) as d:d.write(rgb)
   tiles=list(adapter.prepare_inference_tiles(TilingService().iter_tiles(img,raster_id='14A2-'+patch,tile_size=512,overlap_ratio=0,min_valid_pixel_ratio=.05,preprocessing_profile='rgb_orthophoto_uint8_v1',band_indexes=(1,2,3)),img,raster_id='14A2-'+patch,band_indexes=(1,2,3))); prob=adapter.predict(tiles[0]).probability_map; binary=(prob>=.5).astype('uint8'); q=prof.copy();q.update(count=1,dtype='float32',nodata=0,compress='deflate');
   with rasterio.open(OUT/'pseudo_labels/model_c/probability'/(patch+'.tif'),'w',**q) as d:d.write(prob.astype('float32'),1)
   q.update(dtype='uint8');
   with rasterio.open(OUT/'pseudo_labels/model_c/mask'/(patch+'.tif'),'w',**q) as d:d.write(binary,1)
   feats=[{'type':'Feature','geometry':mapping(shape(g)),'properties':{'prediction_id':i+1,'patch_id':patch,'label_source':'MODEL_C_PSEUDO_LABEL','status':'PREANNOTATED','threshold':.5}} for i,(g,v) in enumerate(shapes(binary,mask=binary.astype(bool),transform=prof['transform'],connectivity=8)) if shape(g).area>0];(OUT/'pseudo_labels/model_c/geojson'/(patch+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':feats},indent=2),encoding='utf-8')
   from PIL import Image
   im=Image.fromarray(np.moveaxis(rgb,0,-1)).convert('RGBA'); ov=Image.new('RGBA',(512,512),(255,50,30,0)); ov.putalpha(Image.fromarray((binary*105).astype('uint8'))); Image.alpha_composite(im,ov).convert('RGB').save(OUT/'pseudo_labels/model_c/overlays'/(patch+'.png'))
   rows.append({'patch_id':patch,'split':split,'year':year,'cell':[col,row],'scene_type':['RESIDENTIAL','DENSE_URBAN','INDUSTRIAL','COMMERCIAL'][col%4],'annotation_status':'PENDING','review_status':'NOT_REVIEWED','label_source':'MODEL_C_PSEUDO_LABEL','building_count':0,'pseudo_candidates':len(feats),'bounds':[src.bounds.left+col*512*src.res[0],src.bounds.bottom+(3-row)*512*abs(src.res[1]),src.bounds.left+(col+1)*512*src.res[0],src.bounds.bottom+(4-row)*512*abs(src.res[1])]})
adapter.close(); (OUT/'manifests').mkdir(exist_ok=True); (OUT/'manifests/dataset_manifest.json').write_text(json.dumps({'dataset':'14A2_high_precision_building_training_expansion','patches':rows,'locked_test_reference':{'legacy_13M_13Q':True,'pilot_14A_001_14A_003':True},'training_started':False},indent=2),encoding='utf-8'); print(json.dumps({'patches':len(rows),'train':sum(r['split']=='train' for r in rows),'val':sum(r['split']=='val' for r in rows),'pseudo':len(rows)},indent=2))
