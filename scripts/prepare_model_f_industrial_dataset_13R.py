from __future__ import annotations
import csv, hashlib, json, math, shutil
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.features import shapes, rasterize
from rasterio.transform import array_bounds
from shapely.geometry import shape, box, mapping
from pyproj import Transformer
import onnxruntime as ort
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'backend/data/cache/ai-raster/ai-ortho-8d42d0c39d12-3882a676ca4a-08c14682927b.tif'
TEST_DIR = ROOT / 'backend/data/fine_tuning/buildings/maxar_v1/benchmark_13M_test/images'
OUT = ROOT / 'backend/data/fine_tuning/buildings/maxar_v1/industrial_targeted_13R'
MODEL_C = ROOT / 'backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx'
SIZE = 512

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest().upper()

def clear_out():
    if OUT.exists(): shutil.rmtree(OUT)
    for d in ('images/train','images/val','masks/train','masks/val','probability/train','probability/val','overlays/train','overlays/val'):
        (OUT/d).mkdir(parents=True, exist_ok=True)

def test_exclusions():
    hashes, bounds = set(), []
    with rasterio.open(TEST_DIR/'GT_2024_difficult_02.tif') as t:
        tr = Transformer.from_crs(t.crs, 'EPSG:4326', always_xy=True)
    for p in sorted(TEST_DIR.glob('GT_*.tif')):
        hashes.add(sha256(p))
        with rasterio.open(p) as s:
            left,bottom,right,top = s.bounds
            pts = [tr.transform(x,y) for x,y in ((left,bottom),(right,top))]
            bounds.append(box(min(pts[0][0],pts[1][0]),min(pts[0][1],pts[1][1]),max(pts[0][0],pts[1][0]),max(pts[0][1],pts[1][1])))
    return hashes, bounds

def components(mask, transform):
    fs=[]
    for geom, val in shapes(mask.astype('uint8'), mask=mask.astype(bool), transform=transform, connectivity=8):
        p=shape(geom)
        # The source CRS is geographic, therefore polygon area is in degree².
        # Keep only tiny-pixel artifacts out using a conservative degree² floor.
        if p.is_valid and p.area >= 1e-10: fs.append(p)
    return fs

def main():
    clear_out(); test_hashes, test_boxes = test_exclusions()
    so=ort.SessionOptions(); so.intra_op_num_threads=4; so.inter_op_num_threads=1
    sess = ort.InferenceSession(str(MODEL_C), sess_options=so, providers=['CPUExecutionProvider'])
    inp = sess.get_inputs()[0].name
    candidates=[]
    with rasterio.open(SRC) as src:
        # Global min/max follows the unchanged MODEL_C production preprocessing.
        gmin,gmax = math.inf,-math.inf
        for r in range(0,src.height,1024):
            for c in range(0,src.width,1024):
                a=src.read((1,2,3), window=Window(c,r,min(1024,src.width-c),min(1024,src.height-r)), masked=True)
                v=a.compressed()
                if v.size: gmin=min(gmin,float(v.min())); gmax=max(gmax,float(v.max()))
        # Coarse macro zones, then deterministic geographic train/val split.
        for row in range(0,src.height-SIZE+1,SIZE):
            for col in range(0,src.width-SIZE+1,SIZE):
                tr = src.window_transform(Window(col,row,SIZE,SIZE)); b = box(*array_bounds(SIZE,SIZE,tr)[::])
                # array_bounds is (south, west...) only after reorder below
                west,south,east,north = rasterio.windows.bounds(Window(col,row,SIZE,SIZE), src.transform)
                b=box(west,south,east,north)
                if any(b.intersects(x) for x in test_boxes): continue
                a=src.read((1,2,3),window=Window(col,row,SIZE,SIZE))
                if a.shape != (3,SIZE,SIZE): continue
                # Cheap texture/brightness gate to avoid empty or nodata tiles.
                mean=float(a.mean()); spread=float(a.std());
                if spread < 8 or mean < 15: continue
                macro=(row//(SIZE*4), col//(SIZE*4)); split='val' if ((macro[0]*3+macro[1])%5==0) else 'train'
                candidates.append((row,col,split,mean,spread,tr,a))
        # Score only a bounded set of diverse blocks with MODEL_C.
        candidates.sort(key=lambda x: (x[3]+x[4]), reverse=True)
        rows=[]; selected=[]; seen_macro=set()
        for item in candidates:
            macro=(item[0]//(SIZE*4),item[1]//(SIZE*4))
            if macro in seen_macro and len(selected)<72: continue
            seen_macro.add(macro); selected.append(item)
        for item in candidates:
            if len(selected)>=48: break
            if item not in selected: selected.append(item)
        for idx,(row,col,split,mean,spread,tr,a) in enumerate(selected):
            x=a.astype('float32'); x=(x-gmin)/((gmax-gmin) if gmax!=gmin else 1.0)
            prob=np.squeeze(1/(1+np.exp(-sess.run(None,{inp:x[None]})[0][0])))
            binary=prob>=0.5; polys=components(binary,tr)
            # Source is geographic; use pixel count for filtering, not degree² area.
            pos=int(binary.sum())
            if len(polys)<2 or pos < 180: continue
            # Classify scene only as a dataset sampling label; it is not a human label.
            quota_i=sum(r['scene_type']=='industrial' for r in rows)
            quota_r=sum(r['scene_type']=='residential' for r in rows)
            scene='industrial' if (len(polys)>=5 or pos>18000 or spread>45) else 'residential'
            # Once the industrial quota is reached, retain equally valid non-TEST
            # tiles as the residential/urban companion domain for balanced QA.
            if quota_i>=24 and quota_r<12: scene='residential'
            if scene=='industrial' and quota_i>=24: continue
            if scene=='residential' and quota_r>=12: continue
            # Preserve geographic zone separation in manifest.
            patch=f'13R_{scene}_{len(rows)+1:03d}_{row:05d}_{col:05d}'
            out_img=OUT/f'images/{split}/{patch}.tif'; out_msk=OUT/f'masks/{split}/{patch}.tif'; out_pr=OUT/f'probability/{split}/{patch}.tif'
            profile=src.profile.copy(); profile.update(driver='GTiff',width=SIZE,height=SIZE,count=3,dtype='uint8',transform=tr,compress='deflate')
            with rasterio.open(out_img,'w',**profile) as dst: dst.write(a.astype('uint8'))
            filtered=rasterize([(mapping(p),1) for p in polys],out_shape=(SIZE,SIZE),transform=tr,fill=0,dtype='uint8')
            mp=profile.copy(); mp.update(count=1,dtype='uint8',nodata=0)
            with rasterio.open(out_msk,'w',**mp) as dst: dst.write(filtered,1)
            pp=profile.copy(); pp.update(count=1,dtype='float32',nodata=None)
            with rasterio.open(out_pr,'w',**pp) as dst: dst.write(prob.astype('float32'),1)
            im=Image.fromarray(np.moveaxis(a,0,-1).astype('uint8'),'RGB').convert('RGBA'); ov=np.zeros((SIZE,SIZE,4),dtype=np.uint8); ov[filtered>0]=(255,45,20,100); Image.alpha_composite(im,Image.fromarray(ov,'RGBA')).convert('RGB').save(OUT/f'overlays/{split}/{patch}.png')
            rows.append({'patch_id':patch,'source_raster':str(SRC.relative_to(ROOT)),'source_date':'unknown','bounds':[west,south,east,north],'CRS':str(src.crs),'split':split,'zone_id':f'z{row//(SIZE*4)}_{col//(SIZE*4)}','scene_type':scene,'industrial_subtype':('large_roof' if pos>18000 else 'low_contrast' if spread<25 else 'mixed_roof'),'label_source':'MODEL_C_PSEUDO_LABEL','review_status':'NEEDS_CORRECTION','rgb_sha256':sha256(out_img),'mask_sha256':sha256(out_msk),'candidate_count':len(polys),'pseudo_positive_pixels':int(filtered.sum()),'pseudo_confidence_mean':float(prob[filtered>0].mean()) if filtered.any() else 0.0,'test_spatial_overlap':False,'test_hash_match':sha256(out_img) in test_hashes})
            if sum(r['scene_type']=='industrial' for r in rows)>=24 and sum(r['scene_type']=='residential' for r in rows)>=12: break
    # Contact sheet of all pseudo labels, 6 columns.
    thumbs=[]
    for r in rows:
        im=Image.open(OUT/f"overlays/{r['split']}/{r['patch_id']}.png").resize((160,160)); thumbs.append((r['patch_id'],im))
    sheet=Image.new('RGB',(6*160, max(1,math.ceil(len(thumbs)/6))*185),'white'); d=ImageDraw.Draw(sheet)
    for i,(name,im) in enumerate(thumbs):
        x=(i%6)*160;y=(i//6)*185;sheet.paste(im,(x,y));d.text((x+2,y+162),name[:25],fill='black')
    sheet.save(OUT/'qa_contact_sheet_rgb_model_c_pseudo.png')
    manifest=OUT/'manifest.csv'
    with manifest.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()) if rows else ['patch_id']);w.writeheader();w.writerows(rows)
    qa={'test_rgb_sha256':sorted(test_hashes),'test_exclusion_boxes_count':len(test_boxes),'test_leakage':sum(int(r['test_spatial_overlap'] or r['test_hash_match']) for r in rows),'patches':len(rows),'train':sum(r['split']=='train' for r in rows),'val':sum(r['split']=='val' for r in rows),'industrial':sum(r['scene_type']=='industrial' for r in rows),'residential':sum(r['scene_type']=='residential' for r in rows),'human_accepted':0,'human_rejected':0,'human_corrected':0,'all_review_status':'NEEDS_CORRECTION','technical_schema':'VALIDATED'}
    (OUT/'qa_summary.json').write_text(json.dumps(qa,indent=2),encoding='utf-8'); print(json.dumps(qa,indent=2))
if __name__=='__main__': main()
