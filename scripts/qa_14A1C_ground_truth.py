from pathlib import Path
import argparse, json, subprocess, tempfile
from shapely.geometry import shape, box
from shapely.wkb import dumps
import rasterio

PATCHES={"14A_001_residential": "14A_001_residential_ground_truth", "14A_003_dense_urban": "14A_003_dense_urban_ground_truth"}
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"backend/data/fine_tuning/buildings/maxar_v2_high_precision"
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--gpkg", default=str(BASE/"annotations/ground_truth_layers_14A1C_WORKING.gpkg")); ap.add_argument("--out", default=str(BASE/"qa/14A1C_post_manual_qa.json")); args=ap.parse_args(); report={"layers":{},"passed":True}
 for patch,layer in PATCHES.items():
  with tempfile.TemporaryDirectory() as td:
   gj=Path(td)/"x.geojson"; subprocess.run([r"C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe","-f","GeoJSON",str(gj),args.gpkg,layer],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
   fs=json.loads(gj.read_text())["features"]
  tif=BASE/"images"/(patch+"_v2.tif");
  with rasterio.open(tif) as r: bounds=box(*r.bounds); crs=str(r.crs); shape_ok=(r.width,r.height)==(512,512)
  invalid=empty=oob=dups=0; seen=set()
  for f in fs:
   g=shape(f["geometry"]); empty += int(g.is_empty or g.area<=0); invalid += int(not g.is_valid); oob += int(not bounds.covers(g)); key=dumps(g,hex=True); dups += int(key in seen); seen.add(key)
  ok=not any([invalid,empty,oob,dups]) and shape_ok; report["layers"][patch]={"feature_count":len(fs),"invalid":invalid,"empty_or_zero_area":empty,"out_of_bounds":oob,"duplicates":dups,"raster_crs":crs,"mask_shape":shape_ok,"passed":ok}; report["passed"]=report["passed"] and ok
 Path(args.out).write_text(json.dumps(report,indent=2),encoding="utf-8"); print(json.dumps(report,indent=2)); return 0 if report["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
