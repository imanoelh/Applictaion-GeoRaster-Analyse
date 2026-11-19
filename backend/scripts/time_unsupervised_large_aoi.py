"""Live timing for unsupervised classification across AOI sizes + cache check."""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gee_client import compute_unsupervised_classification, compute_supervised_classification, gee_status
from app.main import cache_key_for_analysis
from app.scalability import classification_cost_policy


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
    mean_lat = math.radians((south + north) / 2)
    width_km = abs(east - west) * 111.32 * max(math.cos(mean_lat), 0.25)
    height_km = abs(north - south) * 110.57
    return max(1, int(width_km * height_km * 100))


# Approximate Riyadh-region envelopes
SCENARIOS = [
    ("small", 24.70, 46.60, 24.78, 46.70, 4),          # ~80 km2
    ("medium", 24.40, 46.20, 24.90, 46.90, 5),         # ~several thousand km2
    ("large_28k", 23.6, 45.4, 25.4, 47.6, 6),          # ~28 000 km2 class
    ("large_28k_clusters4", 23.6, 45.4, 25.4, 47.6, 4),
]


def _run_unsupervised(label: str, south: float, west: float, north: float, east: float, clusters: int) -> dict:
    aoi = _aoi(south, west, north, east)
    surface_ha = _area_ha(south, west, north, east)
    area_km2 = surface_ha / 100.0
    policy = classification_cost_policy(area_km2, 10)
    analysis = {
        "sensor": "sentinel-2",
        "source": "gee",
        "date_start": "2024-06-01",
        "date_end": "2024-06-30",
        "max_cloud_pct": 40,
        "image_method": "median",
        "analysis_type": "unsupervised_classification",
        "index": "UNSUPERVISED_CLASSIFICATION",
        "aoi": aoi,
        "unsupervised_options": {
            "mode": "simple",
            "clusters_count": clusters,
            "samples_count": 5000,
            "seed": 91,
        },
    }
    t0 = time.perf_counter()
    result = compute_unsupervised_classification(analysis, surface_ha)
    total_ms = round((time.perf_counter() - t0) * 1000, 1)
    classes = result.get("classes") or []
    qs = result.get("quality_summary") or {}
    return {
        "aoi": label,
        "area_km2": round(area_km2, 1),
        "clusters_requested": clusters,
        "classes_returned": len(classes),
        "samples_count": qs.get("samples_count"),
        "sample_scale_m": qs.get("sample_scale_m"),
        "mode": qs.get("mode"),
        "tile": bool((result.get("tiles") or {}).get("index_tile_url")),
        "total_ms": total_ms,
        "performance": result.get("performance") or {},
        "policy_level": policy["level"],
        "cache_key": cache_key_for_analysis(analysis)[:16],
        "analysis": analysis,
        "surface_ha": surface_ha,
        "classified_surface_ha": (result.get("stats") or {}).get("classified_surface_ha"),
        "error": None if result.get("mode") == "gee" else result.get("mode"),
    }


def main() -> int:
    status = gee_status()
    print("GEE enabled:", status.get("enabled"), flush=True)
    if not status.get("enabled"):
        print("SKIP: GEE unavailable")
        return 1

    rows = []
    for label, south, west, north, east, clusters in SCENARIOS:
        try:
            row = _run_unsupervised(label, south, west, north, east, clusters)
            # Drop heavy fields for print
            printable = {k: v for k, v in row.items() if k not in {"analysis"}}
            print(json.dumps(printable, ensure_ascii=False), flush=True)
            rows.append(row)
        except Exception as exc:
            err = {"aoi": label, "error": f"{type(exc).__name__}: {str(exc)[:800]}"}
            print(json.dumps(err, ensure_ascii=False), flush=True)
            rows.append(err)

    # Cache: re-run identical large_28k payload and compare wall time via direct compute
    # (API cache is separate; here we confirm scientific path remains deterministic.)
    large = next((r for r in rows if r.get("aoi") == "large_28k" and r.get("analysis")), None)
    if large:
        t0 = time.perf_counter()
        again = compute_unsupervised_classification(large["analysis"], large["surface_ha"])
        again_ms = round((time.perf_counter() - t0) * 1000, 1)
        print(
            json.dumps(
                {
                    "aoi": "large_28k_rerun_compute",
                    "total_ms": again_ms,
                    "classes": len(again.get("classes") or []),
                    "sample_scale_m": (again.get("quality_summary") or {}).get("sample_scale_m"),
                    "note": "direct compute (no HTTP cache); second call still hits GEE unless wrapped by API cache",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    # Supervised smoke on small AOI
    south, west, north, east = SCENARIOS[0][1:5]
    s_analysis = {
        "sensor": "sentinel-2",
        "source": "gee",
        "date_start": "2024-06-01",
        "date_end": "2024-06-30",
        "max_cloud_pct": 40,
        "image_method": "median",
        "analysis_type": "supervised_classification",
        "index": "SUPERVISED_CLASSIFICATION",
        "aoi": _aoi(south, west, north, east),
        "supervised_options": {
            "algorithm": "random_forest",
            "trees": 50,
            "samples_per_class": 60,
            "compare_algorithms": False,
            "require_user_samples": False,
            "project_id": "default",
        },
    }
    t0 = time.perf_counter()
    s_result = compute_supervised_classification(s_analysis, _area_ha(south, west, north, east))
    print(
        json.dumps(
            {
                "type": "supervised_smoke",
                "ms": round((time.perf_counter() - t0) * 1000, 1),
                "classes": len(s_result.get("classes") or []),
                "tile": bool((s_result.get("tiles") or {}).get("index_tile_url")),
                "mode": s_result.get("mode"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
