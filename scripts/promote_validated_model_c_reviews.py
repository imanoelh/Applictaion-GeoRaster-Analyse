"""Promote only explicitly human-validated review layers to annotation truth."""
from __future__ import annotations

import json
from pathlib import Path

import rasterio
from shapely.geometry import box, shape


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"


def main() -> int:
    promoted, skipped, errors = [], [], []
    for meta_path in sorted((DATA / "metadata").glob("GT_*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("review_status") != "VALIDATED":
            skipped.append(meta["patch_id"])
            continue
        pid = meta["patch_id"]
        reviewer = str(meta.get("reviewer") or "").strip()
        if not reviewer:
            errors.append(f"{pid}: VALIDATED review requires reviewer in metadata")
            continue
        review_path = DATA / "review" / f"{pid}_review.geojson"
        target_path = DATA / "annotations" / f"{pid}.geojson"
        if not review_path.is_file() or not target_path.is_file():
            errors.append(f"{pid}: review or annotation file is missing")
            continue
        current = json.loads(target_path.read_text(encoding="utf-8"))
        annotation_status = meta.get("annotation_status", "NOT_ANNOTATED")
        if current.get("features") or annotation_status != "NOT_ANNOTATED":
            errors.append(f"{pid}: refusing to overwrite existing human annotation")
            continue
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review.get("metadata", {}).get("review_status") not in ("NOT_REVIEWED", "IN_REVIEW", "REVIEWED", "VALIDATED"):
            errors.append(f"{pid}: invalid review layer status")
            continue
        try:
            with rasterio.open(DATA / meta["image"]) as image:
                bounds = box(*image.bounds)
                image_crs = image.crs
        except Exception as exc:
            errors.append(f"{pid}: cannot read image reference: {exc}")
            continue
        new_features = []
        ids = set()
        for i, feature in enumerate(review.get("features", [])):
            props = dict(feature.get("properties") or {})
            try:
                geom = shape(feature["geometry"])
            except Exception as exc:
                errors.append(f"{pid}: invalid review geometry #{i}: {exc}")
                break
            building_id = str(props.get("building_id") or props.get("building_ref_id") or "").strip()
            if props.get("review_status") not in ("REVIEWED", "VALIDATED"):
                errors.append(f"{pid}: feature #{i} has not been individually reviewed")
                break
            if not building_id or building_id in ids or geom.geom_type not in ("Polygon", "MultiPolygon") or geom.is_empty or not geom.is_valid or geom.area <= 0 or not bounds.covers(geom):
                errors.append(f"{pid}: invalid/duplicate/out-of-bounds geometry or ID at feature #{i}")
                break
            ids.add(building_id)
            props.update({
                "building_ref_id": building_id,
                "patch_id": pid,
                "date": str(meta["source_date"]),
                "source": meta["source_raster"],
                "annotation_status": "VALIDATED",
                "annotator": reviewer,
                "preannotation_source": "MODEL_C_PREANNOTATION" if props.get("source") == "MODEL_C_PREANNOTATION" else None,
                "candidate_source": props.get("source"),
                "review_status": "VALIDATED",
            })
            new_features.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})
        else:
            final_fc = {
                "type": "FeatureCollection",
                "name": pid,
                "crs": {"type": "name", "properties": {"name": image_crs.to_string()}},
                "metadata": {"patch_id": pid, "date": str(meta["source_date"]),
                             "source": meta["source_raster"], "annotation_status": "VALIDATED",
                             "annotator": reviewer, "preannotation_source": "MODEL_C_PREANNOTATION",
                             "model_id": "spacenet2_deeplab", "human_validated": True,
                             "review_status": "VALIDATED"},
                "features": new_features,
            }
            target_path.write_text(json.dumps(final_fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            review.setdefault("metadata", {})["review_status"] = "VALIDATED"
            review["metadata"]["reviewer"] = reviewer
            review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            meta["annotation_status"] = "VALIDATED"
            meta["annotator"] = reviewer
            meta["building_count"] = len(new_features)
            meta["reviewed_at"] = meta.get("reviewed_at")
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            promoted.append(pid)
    result = {"promoted": promoted, "skipped_not_explicitly_validated": skipped, "errors": errors,
              "automatic_validation": False, "human_validation_required": True}
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
