"""Offline guard for future development/training consumers; no production imports.

All records must provide patch_id, rgb_sha256 and bounds_32637. Fails closed when
provenance is missing. This does not automatically intercept unrelated scripts.
"""
from pathlib import Path
import json

LOCK=Path(__file__).resolve().parents[1]/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set/manifest/GOLD_SET_LOCK.json'

def assert_non_gold_development_records(records,lock_path=LOCK):
    lock=json.loads(Path(lock_path).read_text(encoding='utf-8'))
    if not lock.get('GOLD_SET_LOCKED'):raise ValueError('Gold lock missing')
    gold=lock['patches']
    for record in records:
        pid=record.get('patch_id');digest=record.get('rgb_sha256',record.get('sha256'));a=record.get('bounds_32637')
        if not pid or not digest or not a or len(a)!=4:raise ValueError('Missing required provenance; refuse training/calibration: '+str(pid))
        if a[0]>=a[2] or a[1]>=a[3]:raise ValueError('Invalid metric bounds')
        for g in gold:
            b=g['bounds_32637']
            overlap=a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
            if pid==g['patch_id'] or digest==g['sha256'] or overlap:
                raise ValueError('GOLD_SET_LOCKED: refuse development/training use: '+pid)
    return True
