"""Live timing probe for supervised/unsupervised classification cost policy.

Runs against the local backend GEE session. Safe defaults: small AOI +
require_user_samples=False (WorldCover) so no UI samples are required.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gee_client import (
    compute_supervised_classification,
    compute_unsupervised_classification,
    compute_sentinel2_index,
    gee_status,
)


def _aoi(south: float, west: float, north: float, east: float) -> dict:
    return {
        "bbox": [south, west, north, east],
        "geojson": {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]],
        },
    }


def _area_ha(south: float, west: float, north: float, east: float) -> int:
    import math

    mean_lat = math.radians((south + north) / 2)
    width_km = abs(east - west) * 111.32 * max(math.cos(mean_lat), 0.25)
    height_km = abs(north - south) * 110.57
    return max(1, int(width_km * height_km * 100))


SCENARIOS = [
    ("small", 24.70, 46.60, 24.78, 46.70),       # ~80 km2
    ("medium", 24.40, 46.20, 24.90, 46.90),      # ~several thousand km2-ish
]


def main() -> int:
    status = gee_status()
    print("GEE enabled:", status.get("enabled"), flush=True)
    if not status.get("enabled"):
        print("SKIP: GEE unavailable")
        return 0

    rows = []
    for label, south, west, north, east in SCENARIOS:
        aoi = _aoi(south, west, north, east)
        surface_ha = _area_ha(south, west, north, east)
        area_km2 = surface_ha / 100.0
        base = {
            "sensor": "sentinel-2",
            "source": "gee",
            "date_start": "2024-06-01",
            "date_end": "2024-06-30",
            "max_cloud_pct": 40,
            "image_method": "median",
            "aoi": aoi,
        }

        # Unsupervised
        u_analysis = {
            **base,
            "analysis_type": "unsupervised_classification",
            "index": "UNSUPERVISED_CLASSIFICATION",
            "unsupervised_options": {"clusters_count": 4, "samples_count": 2000, "seed": 91},
        }
        t0 = time.perf_counter()
        u_result = compute_unsupervised_classification(u_analysis, surface_ha)
        u_ms = round((time.perf_counter() - t0) * 1000, 1)
        rows.append(
            {
                "aoi": label,
                "area_km2": round(area_km2, 1),
                "type": "unsupervised",
                "ms": u_ms,
                "perf": (u_result.get("performance") or {}),
                "classes": len(u_result.get("classes") or []),
                "tile": bool((u_result.get("tiles") or {}).get("index_tile_url")),
                "level": ((u_result.get("stats") or {}).get("processing_policy") or {}).get("level"),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

        # Supervised (WorldCover fallback path)
        s_analysis = {
            **base,
            "analysis_type": "supervised_classification",
            "index": "SUPERVISED_CLASSIFICATION",
            "supervised_options": {
                "algorithm": "random_forest",
                "trees": 100,
                "samples_per_class": 80,
                "compare_algorithms": True,
                "require_user_samples": False,
                "project_id": "default",
            },
        }
        t0 = time.perf_counter()
        s_result = compute_supervised_classification(s_analysis, surface_ha)
        s_ms = round((time.perf_counter() - t0) * 1000, 1)
        rows.append(
            {
                "aoi": label,
                "area_km2": round(area_km2, 1),
                "type": "supervised",
                "ms": s_ms,
                "perf": (s_result.get("performance") or {}),
                "classes": len(s_result.get("classes") or []),
                "tile": bool((s_result.get("tiles") or {}).get("index_tile_url")),
                "compare_count": len(s_result.get("algorithm_comparison") or []),
                "compare_note": (s_result.get("quality_summary") or {}).get("compare_note"),
                "level": ((s_result.get("stats") or {}).get("processing_policy") or {}).get("level"),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    # NDVI regression on small AOI
    south, west, north, east = SCENARIOS[0][1:]
    ndvi_analysis = {
        "sensor": "sentinel-2",
        "source": "gee",
        "date_start": "2024-06-01",
        "date_end": "2024-06-30",
        "max_cloud_pct": 40,
        "image_method": "median",
        "index": "NDVI",
        "aoi": _aoi(south, west, north, east),
    }
    t0 = time.perf_counter()
    ndvi = compute_sentinel2_index(ndvi_analysis, _area_ha(south, west, north, east))
    ndvi_ms = round((time.perf_counter() - t0) * 1000, 1)
    print(
        json.dumps(
            {
                "type": "ndvi_regression",
                "ms": ndvi_ms,
                "tile": bool((ndvi.get("tiles") or {}).get("index_tile_url")),
                "mode": ndvi.get("mode"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
