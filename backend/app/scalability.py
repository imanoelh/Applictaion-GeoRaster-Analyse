from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


INTERACTIVE_AREA_KM2 = 5_000.0
LARGE_AREA_KM2 = 15_000.0
# Multi-algorithm supervised comparison is useful on small AOIs but becomes a
# dominant getInfo cost well before the generic "large" surface threshold.
CLASSIFICATION_COMPARE_MAX_KM2 = 2_000.0
TARGET_CHUNK_SIDE_KM = 40.0
MAX_LOGICAL_CHUNKS = 256
ANALYSIS_CACHE_TTL_SECONDS = 24 * 60 * 60
CATALOG_CACHE_TTL_SECONDS = 60 * 60
STANDARD_STATISTICS_PIXEL_BUDGET = 10_000_000
LARGE_STATISTICS_PIXEL_BUDGET = 3_000_000
VERY_LARGE_STATISTICS_PIXEL_BUDGET = 1_500_000


@dataclass(frozen=True)
class ChunkPlan:
    rows: int
    columns: int
    count: int
    side_km: float
    strategy: str


def surface_policy(area_km2: float, native_scale_m: int = 10) -> dict[str, Any]:
    """Return a non-blocking execution policy for an AOI.

    Earth Engine evaluates images lazily and already serves web-map tiles.  The
    policy therefore changes execution/statistics behaviour instead of rejecting
    a valid geometry at an arbitrary area threshold.
    """
    area = max(float(area_km2 or 0), 0.0)
    estimated_pixels = int((area * 1_000_000) / max(native_scale_m**2, 1))
    if area > LARGE_AREA_KM2:
        level = "very_large"
        message = "Very large AOI: queued processing, adaptive chunks and cached results will be used."
    elif area > INTERACTIVE_AREA_KM2:
        level = "large"
        message = "Large AOI: processing is supported and may take longer; adaptive chunks will be used."
    else:
        level = "standard"
        message = "AOI suitable for interactive processing."

    # Keep native resolution for the raster/tile result. Only aggregate
    # reductions (statistics, histogram and class areas) use a bounded pixel
    # budget. Large AOIs need a smaller budget so one atomic GEE response can
    # contain the map and its complete statistics within an interactive delay.
    if area > LARGE_AREA_KM2:
        statistics_pixel_budget = VERY_LARGE_STATISTICS_PIXEL_BUDGET
    elif area > INTERACTIVE_AREA_KM2:
        statistics_pixel_budget = LARGE_STATISTICS_PIXEL_BUDGET
    else:
        statistics_pixel_budget = STANDARD_STATISTICS_PIXEL_BUDGET
    statistics_scale_m = native_scale_m
    if estimated_pixels > statistics_pixel_budget:
        statistics_scale_m = max(
            native_scale_m,
            int(math.ceil(math.sqrt(area * 1_000_000 / statistics_pixel_budget))),
        )

    return {
        "level": level,
        "status": "async" if area > LARGE_AREA_KM2 else "warning" if area > INTERACTIVE_AREA_KM2 else "ok",
        "message": message,
        "area_km2": round(area, 2),
        "estimated_native_pixels": estimated_pixels,
        "native_scale_m": native_scale_m,
        "statistics_scale_m": statistics_scale_m,
        "statistics_pixel_budget": statistics_pixel_budget,
        "async_recommended": area > LARGE_AREA_KM2,
        "blocked": False,
    }


def _adaptive_unsupervised_sample_budget(area_km2: float, level: str) -> int:
    """Grow KMeans training samples with AOI size without unbounded GEE cost.

    Uses a sqrt(area) law so density decays slowly instead of collapsing to a
    fixed 1500–3000 pixel budget on large heterogeneous AOIs. Small AOIs keep a
    high ceiling so the UI default (5000) is never clipped downward.
    """
    area = max(float(area_km2 or 0), 1.0)
    target = int(140.0 * math.sqrt(area))
    if level == "very_large":
        # A very large AOI must use a stricter bounded training budget than a
        # merely large AOI.  This keeps KMeans memory/transfer cost monotonic
        # once the workflow switches to the most defensive execution policy.
        return max(5_000, min(target, 8_000))
    if level == "large":
        return max(4_500, min(target, 10_000))
    if area > CLASSIFICATION_COMPARE_MAX_KM2:
        return max(5_000, min(max(target, 5_000), 9_000))
    # Small / mid interactive AOIs: preserve historical high budget.
    return max(5_000, min(max(target, 5_000), 20_000))


def _adaptive_sample_scale_m(native_scale_m: int, stats_scale: int, level: str, area_km2: float) -> int:
    """Keep training sample scale close to native; coarsen only when necessary."""
    native = max(int(native_scale_m), 1)
    stats = max(int(stats_scale), native)
    if level == "very_large":
        # Preserve usable spectral signatures while the separate sample-count
        # ceiling and tileScale bound the cost of enormous AOIs.
        return max(native, min(stats, 30), 20)
    if level == "large":
        return max(native, min(stats, 25), 15)
    if area_km2 > CLASSIFICATION_COMPARE_MAX_KM2:
        return max(native, 15)
    return native


def classification_cost_policy(area_km2: float, native_scale_m: int = 10) -> dict[str, Any]:
    """Extra execution knobs for supervised/unsupervised classification only.

    Native classification tiles stay at sensor scale. Sampling budgets, tileScale,
    cluster-mean scale and multi-algorithm comparison are adjusted so large AOIs
    stay interactive without changing the selected classifier math.

    v2 (adaptive density): unsupervised sample counts grow with sqrt(area) and
    training sample_scale stays closer to native resolution so quality does not
    collapse on heterogeneous landscapes.
    """
    policy = surface_policy(area_km2, native_scale_m)
    area = float(policy["area_km2"])
    level = policy["level"]
    stats_scale = int(policy["statistics_scale_m"])
    sample_scale_m = _adaptive_sample_scale_m(native_scale_m, stats_scale, level, area)
    max_unsupervised_samples = _adaptive_unsupervised_sample_budget(area, level)

    if level == "very_large":
        max_samples_per_class = 180
        tile_scale = 8
        apply_focal_mode = False
        recommended_clusters = 8
    elif level == "large":
        max_samples_per_class = 200
        tile_scale = 6
        apply_focal_mode = False
        recommended_clusters = 8
    elif area > CLASSIFICATION_COMPARE_MAX_KM2:
        max_samples_per_class = 220
        tile_scale = 4
        apply_focal_mode = True
        recommended_clusters = 7
    else:
        max_samples_per_class = 500
        tile_scale = 4
        apply_focal_mode = True
        recommended_clusters = 6

    return {
        **policy,
        "max_samples_per_class": max_samples_per_class,
        "max_unsupervised_samples": max_unsupervised_samples,
        "tile_scale": tile_scale,
        "allow_algorithm_comparison": area <= CLASSIFICATION_COMPARE_MAX_KM2,
        "cluster_stats_scale_m": max(stats_scale, sample_scale_m),
        "sample_scale_m": int(sample_scale_m),
        "apply_focal_mode": apply_focal_mode,
        # A light 3x3 majority filter is retained for unsupervised clusters to
        # reduce isolated salt-and-pepper pixels. The supervised cost policy is
        # deliberately unchanged.
        "apply_unsupervised_focal_mode": True,
        "recommended_clusters": recommended_clusters,
        "sampling_strategy": "adaptive_density_v2",
    }


def adaptive_chunk_plan(bbox: list[float], area_km2: float) -> ChunkPlan:
    """Plan a bounded grid covering bbox=[south, west, north, east]."""
    if len(bbox) != 4 or bbox == [0, 0, 0, 0] or area_km2 <= 350:
        return ChunkPlan(1, 1, 1, TARGET_CHUNK_SIDE_KM, "single")
    south, west, north, east = (float(value) for value in bbox)
    mean_lat = math.radians((south + north) / 2)
    width_km = abs(east - west) * 111.32 * max(math.cos(mean_lat), 0.25)
    height_km = abs(north - south) * 110.57
    side_km = TARGET_CHUNK_SIDE_KM
    rows = max(1, math.ceil(height_km / side_km))
    columns = max(1, math.ceil(width_km / side_km))
    if rows * columns > MAX_LOGICAL_CHUNKS:
        side_km = math.sqrt(max(width_km * height_km, 1.0) / MAX_LOGICAL_CHUNKS)
        rows = max(1, math.ceil(height_km / side_km))
        columns = max(1, math.ceil(width_km / side_km))
        while rows * columns > MAX_LOGICAL_CHUNKS:
            side_km *= 1.05
            rows = max(1, math.ceil(height_km / side_km))
            columns = max(1, math.ceil(width_km / side_km))
    return ChunkPlan(rows, columns, rows * columns, round(side_km, 2), "adaptive_grid")


def cache_timestamp_is_fresh(timestamp: str | None, ttl_seconds: int = ANALYSIS_CACHE_TTL_SECONDS) -> bool:
    if not timestamp:
        return False
    try:
        value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= ttl_seconds
    except (TypeError, ValueError):
        return False
