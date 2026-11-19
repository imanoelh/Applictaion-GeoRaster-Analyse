import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
old=json.loads((BASE/'14A2_expansion/manifests/dataset_manifest.json').read_text(encoding='utf-8'))
entries=[]
for x in old['patches']:
    y=dict(x); y['source_manifest']='14A2_expansion/manifests/dataset_manifest.json'; entries.append(y)
for p in ['14A2_2024_06','14A2_2024_10','14A2_2025_02','14A2_2025_06','14A2_2025_10']:
    rgb=BASE/'14A2_expansion/train/rgb'/f'{p}.tif'; mask=BASE/'14A5B_fixed_masks'/f'{p}.tif'
    entries.append({'patch_id':p,'split':'train','scene_type':'HIGH_PRECISION_GT','annotation_status':'VALIDATED','review_status':'VALIDATED','label_source':'MANUAL_FIXED_14A5B','rgb':str(rgb),'mask':str(mask),'rgb_sha256':hashlib.sha256(rgb.read_bytes()).hexdigest(),'mask_sha256':hashlib.sha256(mask.read_bytes()).hexdigest()})
out={'dataset':'14A6_enriched_high_precision_buildings','entries':entries,'counts':{'total':len(entries),'train':sum(x.get('split')=='train' for x in entries),'val':sum(x.get('split')=='val' for x in entries),'locked_test_excluded':True},'new_gt_features':85,'hard_negatives_included':'REFERENCED_EXISTING_VALIDATED_MANIFEST_ONLY'}
path=BASE/'14A6_enriched_manifest.json'; path.write_text(json.dumps(out,indent=2),encoding='utf-8'); print(path); print(out['counts'])
