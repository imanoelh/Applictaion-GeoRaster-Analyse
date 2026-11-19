from __future__ import annotations


class AIRasterError(ValueError):
    """Safe raster/preprocessing business error exposed by AI raster routes."""

    def __init__(self, code: str, message: str, *, technical_detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.technical_detail = technical_detail

    def public_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}
