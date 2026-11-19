from __future__ import annotations

import csv, json, re, subprocess, tempfile, shutil, sqlite3
from pathlib import Path
from shapely.geometry import shape, box, Point
from shapely.validation import explain_validity
from shapely import make_valid
from shapely.wkb import dumps
import rasterio

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
WORK=BASE/'annotations/ground_truth_layers_14A1C_WORKING.gpkg'
CAND=BASE/'annotations/ground_truth_layers_14A1D3_CANDIDATE.gpkg'
TMP=ROOT/'.codex_14a1d3_tmp'; TMP.mkdir(exist_ok=True)
EXE=r'C:\Program Files\PostgreSQL\17\bin\ogr2ogr.exe'
TARGETS={'14A_001_residential':{'24','25'},'14A_003_dense_urban':{'3','12','15','20'}}
LAYERS={p:p+'_ground_truth' for p in TARGETS}
BOUNDS={}; records=[]
for patch,bids in TARGETS.items():
    with tempfile.TemporaryDirectory() as td:
        gj=Path(td)/'x.geojson'; subprocess.run([EXE,'-f','GeoJSON',str(gj),str(WORK),LAYERS[patch]],check=True,stdout=subprocess.DEVNULL)
        fs=json.loads(gj.read_text(encoding='utf-8'))['features']
    with rasterio.open(BASE/'images'/(patch+'_v2.tif')) as r:
        rb=box(*r.bounds); BOUNDS[patch]=r.bounds; px=r.res[0]
    for f in fs:
        bid=str(f['properties'].get('building_id',''))
        if bid not in bids: continue
        g=shape(f['geometry']); reason=explain_validity(g)
        kind='OUT_OF_BOUNDS' if bid in {'24','25','12','20'} else 'SELF_INTERSECTION'
        cand=g.intersection(rb) if kind=='OUT_OF_BOUNDS' else make_valid(g)
        records.append({'patch_id':patch,'building_id':bid,'kind':kind,'original_wkb':dumps(g,hex=True),'candidate_wkb':dumps(cand,hex=True),'reason':reason,'area_before':g.area,'area_after':cand.area,'area_delta_percent':(cand.area-g.area)/g.area*100 if g.area else 0,'centroid_shift_m':g.centroid.distance(cand.centroid),'valid_after':cand.is_valid,'empty_after':cand.is_empty,'parts_after':len(cand.geoms) if hasattr(cand,'geoms') else 1})
        if kind=='OUT_OF_BOUNDS':
            coords=[]
            for ring in ([g.exterior.coords] + [x.coords for x in g.interiors]) if g.geom_type=='Polygon' else []:
                coords.extend(list(ring))
            for i,(x,y) in enumerate(coords):
                p=Point(x,y)
                if not rb.covers(p):
                    d=p.distance(rb)
                    # nearest boundary label
                    labels={'left':abs(x-rb.bounds[0]),'right':abs(x-rb.bounds[2]),'bottom':abs(y-rb.bounds[1]),'top':abs(y-rb.bounds[3])}
                    records[-1].setdefault('vertices',[]).append({'index':i,'x':x,'y':y,'boundary':min(labels,key=labels.get),'distance_m':d,'distance_px':d/px})
        else:
            m=re.search(r'Self-intersection\[([^ ]+) ([^\]]+)\]',reason); ix=float(m.group(1)) if m else None; iy=float(m.group(2)) if m else None
            coords=list(g.exterior.coords) if g.geom_type=='Polygon' else []
            nearest=sorted([(i,Point(x,y).distance(Point(ix,iy))) for i,(x,y) in enumerate(coords)],key=lambda z:z[1])[:2] if ix is not None else []
            records[-1]['intersection_x']=ix; records[-1]['intersection_y']=iy; records[-1]['vertex_indices']=';'.join(str(i) for i,_ in nearest); records[-1]['crossing_segments']=1
(BASE/'qa/14A1D3_candidate_wkb.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
with (BASE/'qa/14A1D3_out_of_bounds_vertices.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['patch_id','building_id','vertex_index','x','y','nearest_raster_boundary','distance_outside_m','distance_outside_px'])
    for r in records:
        for v in r.get('vertices',[]): w.writerow([r['patch_id'],r['building_id'],v['index'],v['x'],v['y'],v['boundary'],v['distance_m'],v['distance_px']])
with (BASE/'qa/14A1D3_self_intersection_details.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['patch_id','building_id','invalidity_reason','intersection_x','intersection_y','vertex_indices','crossing_segments'])
    for r in records:
        if r['kind']=='SELF_INTERSECTION': w.writerow([r['patch_id'],r['building_id'],r['reason'],r['intersection_x'],r['intersection_y'],r['vertex_indices'],r['crossing_segments']])
print(json.dumps(records,indent=2))
