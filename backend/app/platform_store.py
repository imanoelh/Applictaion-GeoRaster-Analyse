from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PLATFORM_SETTINGS = {
    "platform_name": "GeoRaster",
    "logo_url": None,
    "user_profile": {
        "name": "GIS analyst",
        "email": "user@georaster.app",
    },
    "default_basemap": "osm",
    "export_format": "geotiff",
    "measurement_unit": "ha",
    "backend_connection": {
        "raster_server": "fastapi",
        "endpoint": "http://127.0.0.1:8010",
        "api_key": "",
    },
    "projection_mode": "automatic",
    "web_map_crs": "EPSG:3857",
    "analysis_crs": "AUTO_KSA_GRF17",
    "manual_crs": None,
    "simulation_3d_enabled": False,
    "simulation_3d_crs": "EPSG:9332",
}

LOGO_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/bmp": "bmp",
    "image/avif": "avif",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
}


@dataclass
class PlatformSettingsStore:
    config_path: Path
    upload_dir: Path

    def _sanitize(self, data: dict[str, Any] | None) -> dict[str, Any]:
        settings = json.loads(json.dumps(DEFAULT_PLATFORM_SETTINGS))
        if not isinstance(data, dict):
            return settings

        for key in ("platform_name", "logo_url", "default_basemap", "export_format", "measurement_unit", "projection_mode", "web_map_crs", "analysis_crs", "manual_crs", "simulation_3d_enabled", "simulation_3d_crs"):
            if key in data:
                settings[key] = data[key]

        settings["simulation_3d_enabled"] = bool(settings.get("simulation_3d_enabled", False))
        settings["simulation_3d_crs"] = "EPSG:9332"

        if isinstance(data.get("user_profile"), dict):
            settings["user_profile"].update(
                {
                    key: value
                    for key, value in data["user_profile"].items()
                    if key in settings["user_profile"]
                }
            )

        if isinstance(data.get("backend_connection"), dict):
            settings["backend_connection"].update(
                {
                    key: value
                    for key, value in data["backend_connection"].items()
                    if key in settings["backend_connection"]
                }
            )

        return settings

    def read(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return self._sanitize(None)
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return self._sanitize(None)
        return self._sanitize(data)

    def write(self, settings: dict[str, Any]) -> dict[str, Any]:
        current = self.read()
        merged = dict(current)
        merged.update({k: v for k, v in settings.items() if k in merged and k not in {"user_profile", "backend_connection"}})
        if isinstance(settings.get("user_profile"), dict):
            merged["user_profile"] = {**current["user_profile"], **settings["user_profile"]}
        if isinstance(settings.get("backend_connection"), dict):
            merged["backend_connection"] = {**current["backend_connection"], **settings["backend_connection"]}
        current = self._sanitize(merged)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        return current

    def clear_uploaded_logos(self) -> None:
        if not self.upload_dir.exists():
            return
        for path in self.upload_dir.iterdir():
            if path.is_file() and path.name.startswith("logo."):
                path.unlink(missing_ok=True)

    def resolve_logo_extension(self, content_type: str, data: bytes) -> str:
        if content_type in LOGO_CONTENT_TYPES:
            return LOGO_CONTENT_TYPES[content_type]
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if data[:3] == b"\xff\xd8\xff":
            return "jpg"
        if data[:6] in {b"GIF87a", b"GIF89a"}:
            return "gif"
        if data[:4] == b"RIFF" and b"WEBP" in data[:16]:
            return "webp"
        if data.lstrip().startswith(b"<svg"):
            return "svg"
        raise ValueError("Format logo non supporte. Utilisez PNG, JPG, GIF, WEBP, SVG, BMP, AVIF ou ICO.")
