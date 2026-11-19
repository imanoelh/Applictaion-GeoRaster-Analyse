"""Finalize only the three pilot patches after explicit human validation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend/data/fine_tuning/buildings/maxar_v1"
PILOT = ("GT_2024_residential_02", "GT_2024_dense_02", "GT_2024_difficult_01")


def main() -> int:
    errors = []
    for patch_id in PILOT:
        metadata_path = DATA / f"metadata/{patch_id}.json"
        review_path = DATA / f"review/{patch_id}_review.geojson"
        if not metadata_path.is_file() or not review_path.is_file():
            errors.append(f"{patch_id}: metadata or review GeoJSON is missing")
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if metadata.get("review_status") != "VALIDATED":
            errors.append(f"{patch_id}: set metadata review_status to VALIDATED only after human review")
        if not str(metadata.get("reviewer") or "").strip():
            errors.append(f"{patch_id}: metadata reviewer is required")
        for index, feature in enumerate(review.get("features", [])):
            status = (feature.get("properties") or {}).get("review_status")
            if status not in ("REVIEWED", "VALIDATED"):
                errors.append(f"{patch_id}: feature {index} is not marked REVIEWED/VALIDATED")
                break
        if review.get("metadata", {}).get("human_validation_required") is not True:
            errors.append(f"{patch_id}: review-layer provenance is unexpected")
    if errors:
        print("Human review prerequisites are not satisfied; no files were changed:")
        print("\n".join(f"- {error}" for error in errors))
        return 2

    python = sys.executable
    commands = (
        [python, str(ROOT / "scripts/promote_validated_model_c_reviews.py")],
        [python, str(ROOT / "scripts/building_annotation_workflow.py"), "--dataset", str(DATA)],
    )
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
