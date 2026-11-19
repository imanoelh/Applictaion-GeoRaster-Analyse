from __future__ import annotations

import math
import random
from typing import Any


def _with_mock_notice(result: dict[str, Any], message: str = "Mock analysis result. Use live GEE mode for operational analysis.") -> dict[str, Any]:
    result["mode"] = "mock"
    result["warning"] = message
    result["mock"] = {
        "enabled": True,
        "operational": False,
        "reason": "gee_unavailable_or_test_mode",
    }
    quality_summary = result.setdefault("quality_summary", {})
    if isinstance(quality_summary, dict):
        quality_summary.setdefault("mode", "mock")
        quality_summary.setdefault("warning", message)
    return result


def compute_mock_index(index_id: str, surface_ha: int = 1245) -> dict[str, Any]:
    if index_id == "SUPERVISED_CLASSIFICATION":
        return _with_mock_notice(compute_mock_supervised_classification(surface_ha=surface_ha))
    if index_id == "UNSUPERVISED_CLASSIFICATION":
        return _with_mock_notice(compute_mock_unsupervised_classification(surface_ha=surface_ha))
    if index_id == "OSI_SAR":
        return _with_mock_notice(compute_mock_osi_sar(surface_ha=surface_ha), "Mock OSI-SAR result. Use live Sentinel-1 GEE mode for operational analysis.")
    if index_id.startswith("CHANGE_"):
        return _with_mock_notice(compute_mock_change_detection(index_id, surface_ha=surface_ha), "Mock change-detection result. Use live GEE mode for operational analysis.")

    seeds = {"NDVI": 42, "NDBI": 126, "NDWI": 84, "BSI": 168, "SAVI": 210}
    rng = random.Random(seeds.get(index_id, 42))
    if index_id == "NDVI":
        mean = 0.42 + rng.random() * 0.1
        std = 0.12 + rng.random() * 0.06
        vmin, vmax = -0.20, 0.80
        palette = ["#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837"]
        class_defs = [
            ("Water / negative values", "#67001f"),
            ("Bare soil / very dry desert", "#b2182b"),
            ("Very low vegetation activity", "#d6604d"),
            ("Very sparse vegetation", "#f4a582"),
            ("Low vegetation", "#fddbc7"),
            ("Moderate vegetation", "#d9ef8b"),
            ("Dense vegetation", "#1a9850"),
            ("Very dense vegetation", "#006837"),
        ]
    elif index_id == "NDBI":
        mean = 0.05 + rng.random() * 0.18
        std = 0.10 + rng.random() * 0.07
        vmin, vmax = -0.35, 0.35
        palette = ["#f2eadf", "#f5b66f", "#ef6c3e", "#ff2a2a"]
        class_defs = [
            ("Non bati", palette[0]),
            ("Faible artificialisation", palette[1]),
            ("Bati probable", palette[2]),
            ("Bati dense", palette[3]),
        ]
    elif index_id == "NDWI":
        mean = -0.18 + rng.random() * 0.12
        std = 0.10 + rng.random() * 0.08
        vmin, vmax = -0.50, 0.50
        palette = ["#8C510A", "#BF812D", "#DFC27D", "#F6E8C3", "#F5F5F5", "#C7EAE5", "#80CDC1", "#35978F", "#01665E"]
        class_defs = [
            ("Strong negative NDWI response / probable dry land", palette[0]),
            ("Negative NDWI response", palette[2]),
            ("Transition / weak water response", palette[4]),
            ("Water-compatible NDWI response", palette[6]),
            ("Strong water response", palette[8]),
        ]
    elif index_id == "BSI":
        mean = 0.18 + rng.random() * 0.18
        std = 0.12 + rng.random() * 0.08
        vmin, vmax = -0.4, 0.4
        palette = ["#006837", "#31a354", "#78c679", "#c2e699", "#ffffcc", "#fed98e", "#fe9929", "#d95f0e", "#993404"]
        class_defs = [
            ("Very negative BSI value", palette[0]),
            ("Negative BSI value", palette[2]),
            ("Transition", palette[4]),
            ("Probable bare soil", palette[6]),
            ("Strong bare-soil / dry signature", palette[8]),
        ]
    else:
        mean = 0.28 + rng.random() * 0.16
        std = 0.11 + rng.random() * 0.06
        vmin, vmax = -0.20, 0.80
        palette = ["#8C510A", "#BF812D", "#DFC27D", "#F6E8C3", "#FFFFBF", "#D9EF8B", "#A6D96A", "#66BD63", "#1A9850", "#006837"]
        class_defs = [
            ("No / very sparse vegetation", palette[0]),
            ("Low vegetation", palette[2]),
            ("Moderate vegetation", palette[4]),
            ("Dense vegetation", palette[6]),
            ("Very dense vegetation", palette[9]),
        ]

    stats = {
        "min": round(vmin, 3),
        "max": round(vmax, 3),
        "mean": round(mean, 3),
        "std": round(std, 3),
        "pixels": int(surface_ha * 100),
        "surface_ha": surface_ha,
    }

    histogram = []
    for i in range(24):
        value = vmin + (i * (vmax - vmin)) / 24
        distance = value - mean
        count = int(2400 * math.exp(-(distance * distance) / (2 * (std**2))) + rng.random() * 150)
        histogram.append({"bin": round(value, 3), "count": max(0, count)})

    classes = []
    remaining = surface_ha
    for i, (name, color) in enumerate(class_defs):
        if i == len(class_defs) - 1:
            class_surface = remaining
        else:
            class_surface = max(0, int((surface_ha / len(class_defs)) + rng.randint(-80, 80)))
            remaining = max(0, remaining - class_surface)
        classes.append(
            {
                "name": name,
                "surface_ha": class_surface,
                "pct": round((class_surface / surface_ha) * 100, 1) if surface_ha else 0,
                "color": color,
            }
        )

    return _with_mock_notice({"stats": stats, "histogram": histogram, "classes": classes, "palette": palette})


def compute_mock_supervised_classification(surface_ha: int = 1245) -> dict[str, Any]:
    rng = random.Random(314)
    class_defs = [
        (1, "Water", "#2b83ba"),
        (2, "Dense vegetation / trees", "#1a9850"),
        (3, "Crops / low vegetation", "#a6d96a"),
        (4, "Built-up area", "#d7191c"),
        (5, "Bare soil / sand", "#dfc27d"),
        (6, "Wetland", "#80cdc1"),
        (7, "Mangrove / specific vegetation", "#01665e"),
        (8, "Snow / ice", "#ffffff"),
    ]
    weights = [3, 8, 14, 20, 48, 3, 3, 1]
    remaining = surface_ha
    classes = []
    for i, ((code, name, color), weight) in enumerate(zip(class_defs, weights)):
        if i == len(class_defs) - 1:
            area = remaining
        else:
            area = max(0, round(surface_ha * (weight + rng.uniform(-1.5, 1.5)) / 100, 2))
            remaining = max(0, round(remaining - area, 2))
        classes.append(
            {
                "code": code,
                "name": name,
                "surface_ha": area,
                "pct": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": color,
            }
        )

    palette = [item[2] for item in class_defs]
    return {
        "analysis_type": "supervised_classification",
        "stats": {
            "total_area_ha": surface_ha,
            "surface_ha": surface_ha,
            "classes_count": len(class_defs),
            "training_samples_count": 720,
            "validation_samples_count": 308,
        },
        "histogram": [{"bin": item["name"], "count": int(item["surface_ha"] * 100)} for item in classes],
        "classes": classes,
        "palette": palette,
        "accuracy": {
            "overall_accuracy": 0.87,
            "kappa": 0.82,
            "confusion_matrix": [],
        },
        "quality_summary": {
            "coverage_percent": 94,
            "training_samples_count": 720,
            "validation_samples_count": 308,
            "classifier": "Random Forest",
            "trees": 100,
            "reference": "ESA WorldCover v200",
        },
    }


def compute_mock_unsupervised_classification(surface_ha: int = 1245) -> dict[str, Any]:
    rng = random.Random(512)
    class_defs = [
        (1, "Water", "#2b83ba"),
        (2, "Dense vegetation", "#1a9850"),
        (3, "Crops / low vegetation", "#a6d96a"),
        (4, "Built-up area", "#d7191c"),
        (5, "Bare soil / sand", "#dfc27d"),
        (6, "Wetland / mixed class", "#80cdc1"),
        (7, "Uninterpreted cluster", "#bdbdbd"),
    ]
    weights = [2, 9, 12, 24, 45, 5, 3]
    remaining = surface_ha
    classes = []
    for i, ((code, name, color), weight) in enumerate(zip(class_defs, weights)):
        if i == len(class_defs) - 1:
            area = remaining
        else:
            area = max(0, round(surface_ha * (weight + rng.uniform(-1.5, 1.5)) / 100, 2))
            remaining = max(0, round(remaining - area, 2))
        classes.append(
            {
                "code": code,
                "name": name,
                "surface_ha": area,
                "pct": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": color,
            }
        )

    return {
        "analysis_type": "unsupervised_classification",
        "stats": {
            "total_area_ha": surface_ha,
            "surface_ha": surface_ha,
            "classes_count": 6,
            "samples_count": 2400,
        },
        "histogram": [{"bin": item["name"], "count": int(item["surface_ha"] * 100)} for item in classes],
        "classes": classes,
        "palette": [item[2] for item in class_defs],
        "quality_summary": {
            "samples_count": 2400,
            "coverage_percent": 92,
            "cluster_method": "KMeans",
            "clusters_count": 6,
        },
    }


def compute_mock_osi_sar(surface_ha: int = 1245) -> dict[str, Any]:
    rng = random.Random(901)
    class_defs = [
        (0, "Normal water", "#1f78b4", 92),
        (1, "Oil-spill suspect", "#d7191c", 8),
    ]
    classes = []
    remaining = surface_ha
    for i, (code, name, color, weight) in enumerate(class_defs):
        if i == len(class_defs) - 1:
            area = remaining
        else:
            area = max(0, round(surface_ha * (weight + rng.uniform(-1.2, 1.2)) / 100, 2))
            remaining = max(0, round(remaining - area, 2))
        classes.append(
            {
                "code": code,
                "name": name,
                "surface_ha": area,
                "pct": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "color": color,
            }
        )

    suspect_surface = round(sum(item["surface_ha"] for item in classes if int(item["code"]) > 0), 2)
    return {
        "analysis_type": "oil_spill_suspect_index",
        "stats": {
            "surface_ha": surface_ha,
            "total_area_ha": surface_ha,
            "suspect_surface_ha": suspect_surface,
            "suspect_pct": round((suspect_surface / surface_ha) * 100, 1) if surface_ha else 0,
            "mean_vv_db": -17.8,
            "mean_vh_db": -25.4,
            "mean_local_contrast_db": 2.9,
            "classes_count": len(class_defs),
            "pixels": int(surface_ha * 100),
            "images_count": 1,
        },
        "histogram": [{"bin": item["name"], "count": int(item["surface_ha"] * 100)} for item in classes],
        "classes": classes,
        "palette": [item[2] for item in class_defs],
        "quality_summary": {
            "collection": "COPERNICUS/S1_GRD",
            "instrument_mode": "IW",
            "polarizations": "VV,VH",
            "available_images": 4,
            "images_count": 1,
            "selection_mode": "single_scene",
            "logic": "AND",
            "gee_strict_validation": True,
            "warning": "OSI-SAR is a dark-target suspect detector, not a confirmed oil spill. Mock result only.",
        },
        "interpretation": "OSI-SAR – Oil Spill Suspect maps Sentinel-1 dark-target candidates over water. This is not a confirmed oil spill.",
    }


def compute_mock_change_detection(index_id: str, surface_ha: int = 1245) -> dict[str, Any]:
    base = index_id.replace("CHANGE_", "")
    rng = random.Random(700 + sum(ord(ch) for ch in index_id))
    palettes = {
        "NDVI": ["#a50026", "#f46d43", "#fee08b", "#a6d96a", "#1a9850"],
        "NDWI": ["#f2c46d", "#b8e65c", "#56e66f", "#22bff0", "#003bff"],
        "NDBI": ["#2166AC", "#92C5DE", "#F7F7F7", "#F46D43", "#A50026"],
        "BSI": ["#f5ecd9", "#e4c58d", "#c99a5d", "#9f6d3c", "#6f4422"],
        "SAVI": ["#8c510a", "#d8b365", "#f6e8c3", "#d9ef8b", "#a6d96a", "#006837"],
    }
    names = {
        "NDVI": ["Strong vegetation loss", "Moderate vegetation loss", "Stable area", "Moderate vegetation gain", "Strong vegetation gain"],
        "NDWI": ["Water/moisture disappearance", "Moisture decrease", "Stable area", "Moisture increase", "Probable water appearance"],
        "NDBI": ["Strong NDBI decrease", "Moderate NDBI decrease", "Stable area", "Moderate NDBI increase", "Strong NDBI increase"],
        "BSI": ["Strong bare-soil decrease", "Moderate bare-soil decrease", "Stable area", "Moderate bare-soil increase", "Strong bare-soil increase"],
        "SAVI": ["Strong vegetation-cover loss", "Moderate vegetation-cover loss", "Stable area", "Low vegetation-cover gain", "Moderate vegetation-cover gain", "Strong vegetation-cover gain"],
    }
    weights = [10, 15, 40, 12, 14, 9] if base == "SAVI" else [11, 16, 42, 20, 11]
    remaining = surface_ha
    classes = []
    for i, (name, color, weight) in enumerate(zip(names.get(base, names["NDVI"]), palettes.get(base, palettes["NDVI"]), weights)):
        if i == len(names.get(base, names["NDVI"])) - 1:
            area = remaining
        else:
            area = max(0, round(surface_ha * (weight + rng.uniform(-3, 3)) / 100, 2))
            remaining = max(0, round(remaining - area, 2))
        classes.append(
            {
                "code": i + 1,
                "name": name,
                "surface_ha": area,
                "pct": round((area / surface_ha) * 100, 1) if surface_ha else 0,
                "pixels": int(area * 100),
                "mean_change": round((-0.35 + i * 0.175) + rng.uniform(-0.02, 0.02), 3),
                "min": round(-0.5 + i * 0.2, 3),
                "max": round(-0.3 + i * 0.2, 3),
                "color": color,
            }
        )
    return {
        "analysis_type": f"change_detection_{base.lower()}",
        "stats": {
            "min": -0.62,
            "max": 0.58,
            "mean": round(rng.uniform(-0.05, 0.08), 3),
            "std": round(rng.uniform(0.11, 0.19), 3),
            "surface_ha": surface_ha,
            "pixels": int(surface_ha * 100),
            "classes_count": len(classes),
        },
        "histogram": [{"bin": item["name"], "count": item["pixels"]} for item in classes],
        "classes": classes,
        "palette": palettes.get(base, palettes["NDVI"]),
        "quality_summary": {
            "period_1_images_count": 6,
            "period_2_images_count": 8,
            "cloud_max": 20,
            "method": f"Delta {base} from matched satellite mosaics",
            "warning": "Mock change-detection result. Use GEE mode for operational analysis.",
        },
        "interpretation": f"{base} Change Detection compares period 2 against period 1. Red/brown classes indicate decrease, neutral classes indicate stability, and green/blue/orange classes indicate increase depending on the selected index.",
        "comparison_layers": [
            {
                "key": f"{base.lower()}_period_1",
                "index": base,
                "title": f"{base} - Period 1",
                "stats": {"min": 0.02, "max": 0.38, "mean": 0.14, "std": 0.07, "surface_ha": surface_ha, "pixels": int(surface_ha * 100)},
                "histogram": [{"bin": 0.1, "count": 40}, {"bin": 0.2, "count": 60}],
                "classes": [],
                "legend": [],
                "palette": palettes.get(base, palettes["NDVI"]) if base != "NDVI" else ["#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837"],
                "tiles": {"index_tile_url": None, "rgb_tile_url": None},
            },
            {
                "key": f"{base.lower()}_period_2",
                "index": base,
                "title": f"{base} - Period 2",
                "stats": {"min": 0.03, "max": 0.41, "mean": 0.16, "std": 0.08, "surface_ha": surface_ha, "pixels": int(surface_ha * 100)},
                "histogram": [{"bin": 0.1, "count": 35}, {"bin": 0.2, "count": 65}],
                "classes": [],
                "legend": [],
                "palette": palettes.get(base, palettes["NDVI"]) if base != "NDVI" else ["#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837"],
                "tiles": {"index_tile_url": None, "rgb_tile_url": None},
            },
            {
                "key": f"{base.lower()}_change",
                "index": index_id,
                "title": f"{base} Change - Period 2 minus Period 1",
                "stats": {
                    "min": -0.62,
                    "max": 0.58,
                    "mean": round(rng.uniform(-0.05, 0.08), 3),
                    "std": round(rng.uniform(0.11, 0.19), 3),
                    "surface_ha": surface_ha,
                    "pixels": int(surface_ha * 100),
                },
                "histogram": [{"bin": item["name"], "count": item["pixels"]} for item in classes],
                "classes": classes,
                "legend": classes,
                "palette": palettes.get(base, palettes["NDVI"]),
                "tiles": {"index_tile_url": None, "rgb_tile_url": None},
            },
        ],
        "active_comparison_layer": f"{base.lower()}_change",
    }
