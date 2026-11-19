from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, model_validator

from .results_schemas import BuildingAnalysisResult


BuildingExportFormat = Literal["geojson", "csv", "metadata", "zip"]


class BuildingExportRequest(BaseModel):
    format: BuildingExportFormat
    result: BuildingAnalysisResult

    @model_validator(mode="after")
    def validate_analysis_id(self) -> "BuildingExportRequest":
        if not re.fullmatch(r"building-analysis-[0-9a-f]{32}", self.result.analysis_id):
            raise ValueError("analysis_id Building invalide")
        return self
