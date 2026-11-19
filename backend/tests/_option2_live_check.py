import json

from app import db
from app.gee_client import compute_sentinel2_index, gee_status


ANALYSIS_ID = "ded6d62c-6bd4-43b7-a6ec-9caa1be7c095"

with db.connect() as conn:
    row = conn.execute(
        "SELECT payload_json FROM analyses WHERE id = ?",
        (ANALYSIS_ID,),
    ).fetchone()

if row is None:
    raise RuntimeError(f"Analysis {ANALYSIS_ID} not found")

payload = json.loads(row["payload_json"])
result = compute_sentinel2_index(payload, surface_ha=95)

print(
    json.dumps(
        {
            "gee": gee_status(),
            "mode": result.get("mode"),
            "active_comparison_layer": result.get("active_comparison_layer"),
            "raw_stats": result.get("stats"),
            "layers": [
                {
                    "key": layer.get("key"),
                    "title": layer.get("title"),
                    "stats": layer.get("stats"),
                    "classes": layer.get("classes"),
                    "tile_present": bool(
                        (layer.get("tiles") or {}).get("index_tile_url")
                    ),
                }
                for layer in result.get("comparison_layers") or []
            ],
            "rgb_tile_present": bool(
                (result.get("tiles") or {}).get("rgb_tile_url")
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
)
