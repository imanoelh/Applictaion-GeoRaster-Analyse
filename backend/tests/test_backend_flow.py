from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    from app import db, main
    from app.platform_store import PlatformSettingsStore
    IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on local env consistency
    TestClient = None  # type: ignore[assignment]
    db = None  # type: ignore[assignment]
    main = None  # type: ignore[assignment]
    PlatformSettingsStore = None  # type: ignore[assignment]
    IMPORT_ERROR = exc


GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-6.9, 34.0], [-6.8, 34.0], [-6.8, 34.1], [-6.9, 34.1], [-6.9, 34.0]]],
}


class BackendFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"FastAPI integration stack unavailable in this environment: {IMPORT_ERROR}")
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(cls._tmp.name)

        db.DATA_DIR = root / "data"
        db.DB_PATH = db.DATA_DIR / "georaster.db"

        main.UPLOADS_DIR = root / "uploads"
        main.EXPORTS_DIR = root / "exports"
        main.REPORTS_DIR = main.EXPORTS_DIR / "reports"
        main.MAP_LAYOUTS_DIR = main.EXPORTS_DIR / "map-layouts"
        main.PLATFORM_UPLOAD_DIR = main.UPLOADS_DIR / "platform"
        main.PLATFORM_CONFIG_PATH = root / "data" / "platform_settings.json"
        main.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        main.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        main.MAP_LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
        main.PLATFORM_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        main.PLATFORM_SETTINGS_STORE = PlatformSettingsStore(config_path=main.PLATFORM_CONFIG_PATH, upload_dir=main.PLATFORM_UPLOAD_DIR)

        cls._client = TestClient(main.app)
        cls.client = cls._client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client.__exit__(None, None, None)
        try:
            cls._tmp.cleanup()
        except PermissionError:
            pass

    def _analysis_payload(self) -> dict[str, object]:
        return {
            "name": "Canonical NDVI",
            "objective": "vegetation",
            "description": "Flow test",
            "geometry": GEOMETRY,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "sensor": "sentinel-2",
            "resolution": "auto",
            "cloud_max": 20,
            "index": "NDVI",
            "analysis_type": "spectral_index",
        }

    def test_mock_cache_is_not_reused_when_gee_is_available(self) -> None:
        self.assertFalse(main._should_reuse_cached_result({"mode": "mock"}, gee_enabled=True))
        self.assertTrue(main._should_reuse_cached_result({"mode": "gee"}, gee_enabled=True))
        self.assertFalse(main._should_reuse_cached_result({"mode": "mock"}, gee_enabled=False))
        self.assertFalse(main._should_reuse_cached_result({"mode": "gee", "tiles_stale": True}, gee_enabled=True))

    def test_export_timeout_helper_raises_timeout_error(self) -> None:
        with self.assertRaises(TimeoutError):
            main._call_with_timeout(lambda: __import__("time").sleep(1), 0.05, "Timeout GEE")

    def test_mock_analysis_run_is_blocked_when_gee_is_unavailable(self) -> None:
        original = main.gee_status
        main.gee_status = lambda: {"enabled": False, "error": "unavailable"}
        try:
            create_response = self.client.post("/api/analyses", json=self._analysis_payload())
            self.assertEqual(create_response.status_code, 200)
            analysis_id = create_response.json()["item"]["id"]
            run_response = self.client.post(f"/api/analyses/{analysis_id}/run")
            self.assertEqual(run_response.status_code, 503)
            self.assertIn("Mock results are not returned", run_response.json()["detail"])
        finally:
            main.gee_status = original

    def test_tile_refresh_reports_stored_fallback_error(self) -> None:
        create_response = self.client.post("/api/analyses", json=self._analysis_payload())
        self.assertEqual(create_response.status_code, 200)
        analysis = create_response.json()["item"]
        run_id = "run-tile-refresh-fallback"
        stored_url = "https://earthengine.googleapis.com/expired/{z}/{x}/{y}"
        result = {
            "mode": "gee",
            "tiles": {"index_tile_url": stored_url, "rgb_tile_url": None},
            "comparison_layers": [],
            "analysis": analysis,
        }
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO runs (id, analysis_id, created_at, updated_at, status, message, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, analysis["id"], "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "succeeded", "stored", db.json_dumps(result)),
            )
            cache_key = main.cache_key_for_analysis(analysis)
            conn.execute(
                "INSERT INTO processing_cache (cache_key, created_at, updated_at, params_json, result_json) VALUES (?, ?, ?, ?, ?)",
                (cache_key, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", db.json_dumps(analysis), db.json_dumps(result)),
            )
        original = main.create_run_tile_urls

        def fail_refresh(*_args: object, **_kwargs: object) -> dict:
            raise RuntimeError("GEE tile URL expired")

        main.create_run_tile_urls = fail_refresh
        try:
            response = self.client.get(f"/api/runs/{run_id}/tiles?refresh=true")
            self.assertEqual(response.status_code, 200)
            item = response.json()["item"]
            self.assertEqual(item["source"], "stored_fallback")
            self.assertFalse(item["refreshed"])
            self.assertIn("expired", str(item["refresh_error"]).lower())
            self.assertEqual(item["index_tile_url"], stored_url)
            with db.connect() as conn:
                stored_run = db.json_loads(
                    db.fetch_one(conn, "SELECT result_json FROM runs WHERE id = ?", (run_id,))["result_json"]
                )
                cached = db.json_loads(
                    db.fetch_one(conn, "SELECT result_json FROM processing_cache WHERE cache_key = ?", (main.cache_key_for_analysis(analysis),))["result_json"]
                )
            self.assertTrue(stored_run.get("tiles_stale"))
            self.assertTrue(cached.get("tiles_stale"))
            self.assertFalse(main._should_reuse_cached_result(cached, gee_enabled=True))
        finally:
            main.create_run_tile_urls = original

    def test_analysis_job_survives_in_memory_clear_via_sqlite(self) -> None:
        job_id = "job-persist-restart"
        main._set_analysis_job(
            job_id,
            status="completed",
            progress_percent=100,
            message="Analyse terminee",
            run={"id": "run-persist-1"},
            error=None,
        )
        with main.ANALYSIS_JOBS_LOCK:
            main.ANALYSIS_JOBS.pop(job_id, None)
        response = self.client.get(f"/api/jobs/analyses/{job_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["run"]["id"], "run-persist-1")

    def test_stale_processing_job_is_failed_after_simulated_restart(self) -> None:
        job_id = "job-stale-restart"
        main._set_analysis_job(
            job_id,
            status="processing",
            progress_percent=10,
            message="Analyse en cours de traitement",
        )
        with main.ANALYSIS_JOBS_LOCK:
            main.ANALYSIS_JOBS.pop(job_id, None)
        failed = main._fail_interrupted_async_jobs()
        self.assertGreaterEqual(failed, 1)
        response = self.client.get(f"/api/jobs/analyses/{job_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "failed")
        self.assertIn("restart", str(payload["error"]).lower())

    def test_catalog_job_interrupted_uses_error_status(self) -> None:
        job_id = "catalog-stale-restart"
        main._set_gee_catalog_job(job_id, status="running", progress_percent=40)
        with main.GEE_CATALOG_JOBS_LOCK:
            main.GEE_CATALOG_JOBS.pop(job_id, None)
        main._fail_interrupted_async_jobs()
        response = self.client.get(f"/api/gee/jobs/{job_id}/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "error")

    def test_area_from_geometry_uses_geojson_when_bbox_is_missing(self) -> None:
        area = main.area_from_bbox_ha({"geojson": GEOMETRY})
        self.assertGreater(area, 9000)
        self.assertLess(area, 11000)

    def test_area_prefers_geojson_over_bbox_for_imported_polygon(self) -> None:
        triangle = {
            "type": "Polygon",
            "coordinates": [[[49.72, 25.41], [49.74, 25.41], [49.72, 25.43], [49.72, 25.41]]],
        }
        area = main.area_from_bbox_ha({
            "bbox": [[25.41, 49.72], [25.43, 49.74]],
            "geojson": triangle,
        })
        self.assertGreater(area, 200)
        self.assertLess(area, 240)

    def test_platform_settings_projection_persistence(self) -> None:
        update_response = self.client.put(
            "/api/settings/platform",
            json={
                "projection_mode": "manual",
                "manual_crs": "EPSG:9358",
                "default_basemap": "terrain",
                "user_profile": {
                    "name": "Imane",
                    "email": "imane19elhamri@gmail.com",
                },
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["projection_mode"], "manual")
        self.assertEqual(updated["manual_crs"], "EPSG:9358")
        self.assertEqual(updated["default_basemap"], "terrain")
        self.assertEqual(updated["coordinate_reference"]["effective"]["analysis_crs"], "EPSG:9358")

        read_response = self.client.get("/api/settings/platform")
        self.assertEqual(read_response.status_code, 200)
        read_back = read_response.json()
        self.assertEqual(read_back["user_profile"]["name"], "Imane")
        self.assertEqual(read_back["manual_crs"], "EPSG:9358")

    def test_supervised_class_and_sample_crud_with_geometry_validation(self) -> None:
        classes_response = self.client.get("/api/classification/classes?project_id=default")
        self.assertEqual(classes_response.status_code, 200)
        classes = classes_response.json()["items"]
        self.assertGreaterEqual(len(classes), 2)
        first_class_id = classes[0]["id"]
        second_class_id = classes[1]["id"]

        duplicate_name_response = self.client.post(
            "/api/classification/classes",
            json={
                "project_id": "default",
                "code": 999,
                "name": str(classes[0]["name"]).lower(),
                "color": "#123456",
            },
        )
        self.assertEqual(duplicate_name_response.status_code, 409)

        invalid_response = self.client.post(
            "/api/classification/samples",
            json={
                "project_id": "default",
                "class_id": first_class_id,
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1]]]},
                "usage": "training",
            },
        )
        self.assertEqual(invalid_response.status_code, 422)

        point_response = self.client.post(
            "/api/classification/samples",
            json={
                "project_id": "default",
                "class_id": first_class_id,
                "geometry": {"type": "Point", "coordinates": [-6.85, 34.05]},
                "usage": "training",
                "source": "draw_point",
            },
        )
        self.assertEqual(point_response.status_code, 200)
        point = point_response.json()["item"]
        self.assertEqual(point["geometry_type"], "Point")
        self.assertEqual(point["class_id"], first_class_id)

        polygon_response = self.client.post(
            "/api/classification/samples",
            json={
                "project_id": "default",
                "class_id": first_class_id,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-6.88, 34.02], [-6.84, 34.02], [-6.84, 34.06]]],
                },
                "usage": "validation",
                "source": "draw_polygon",
            },
        )
        self.assertEqual(polygon_response.status_code, 200)
        polygon = polygon_response.json()["item"]
        self.assertEqual(polygon["geometry"]["coordinates"][0][0], polygon["geometry"]["coordinates"][0][-1])

        update_response = self.client.put(
            f"/api/classification/samples/{point['id']}",
            json={"class_id": second_class_id, "usage": "validation"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["item"]["class_id"], second_class_id)
        self.assertEqual(update_response.json()["item"]["usage"], "validation")

        delete_response = self.client.delete(f"/api/classification/samples/{point['id']}")
        self.assertEqual(delete_response.status_code, 200)
        delete_class_response = self.client.delete(
            f"/api/classification/classes/{first_class_id}/samples?project_id=default"
        )
        self.assertEqual(delete_class_response.status_code, 200)
        self.assertGreaterEqual(delete_class_response.json()["samples_deleted"], 1)

    def test_analysis_run_cache_export_history_and_delete_flow(self) -> None:
        self.client.put("/api/settings/platform", json={"projection_mode": "automatic", "manual_crs": None})
        create_response = self.client.post("/api/analyses", json=self._analysis_payload())
        self.assertEqual(create_response.status_code, 200)
        analysis = create_response.json()["item"]
        analysis_id = analysis["id"]
        self.assertEqual(analysis["spatial_reference"]["analysis_crs"], "EPSG:9356")
        self.assertEqual(analysis["spatial_reference"]["selection_mode"], "automatic")

        first_run_response = self.client.post(f"/api/analyses/{analysis_id}/run")
        gee_enabled = bool(self.client.get("/api/gee/status").json()["item"]["enabled"])
        if not gee_enabled:
            self.assertEqual(first_run_response.status_code, 503)
            self.assertIn("Mock results are not returned", first_run_response.json()["detail"])
            return
        self.assertEqual(first_run_response.status_code, 200)
        first_run_id = first_run_response.json()["item"]["id"]

        first_result_response = self.client.get(f"/api/runs/{first_run_id}/result")
        self.assertEqual(first_result_response.status_code, 200)
        first_result = first_result_response.json()["item"]
        self.assertFalse(first_result["cached"])
        self.assertEqual(first_result["analysis"]["sensor"], "sentinel-2")
        self.assertEqual(first_result["spatial_reference"]["analysis_crs"], "EPSG:9356")

        second_run_response = self.client.post(f"/api/analyses/{analysis_id}/run")
        self.assertEqual(second_run_response.status_code, 200)
        second_run_id = second_run_response.json()["item"]["id"]

        second_result_response = self.client.get(f"/api/runs/{second_run_id}/result")
        self.assertEqual(second_result_response.status_code, 200)
        second_result = second_result_response.json()["item"]
        self.assertTrue(second_result["cached"])

        export_response = self.client.post(f"/api/runs/{second_run_id}/export", json={"kind": "stats_json"})
        self.assertEqual(export_response.status_code, 200)
        export_id = export_response.json()["item"]["id"]
        outside_export_path = Path(self._tmp.name) / "outside-export.json"
        outside_export_path.write_text("do not delete", encoding="utf-8")
        with db.connect() as conn:
            conn.execute(
                "UPDATE exports SET file_path = ? WHERE id = ?",
                (str(outside_export_path), export_id),
            )

        download_response = self.client.get(f"/api/exports/{export_id}/download")
        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment;", download_response.headers.get("content-disposition", ""))

        history_response = self.client.get("/api/history")
        self.assertEqual(history_response.status_code, 200)
        history_items = history_response.json()["items"]
        self.assertTrue(any(item["analysis_id"] == analysis_id for item in history_items))
        target = next(item for item in history_items if item["analysis_id"] == analysis_id)
        self.assertEqual(target["analysis"]["spatial_reference"]["analysis_crs"], "EPSG:9356")

        delete_response = self.client.delete(f"/api/analyses/{analysis_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["runs_deleted"], 2)
        self.assertTrue(outside_export_path.exists())

        history_after_delete = self.client.get("/api/history")
        self.assertEqual(history_after_delete.status_code, 200)
        self.assertFalse(any(item["analysis_id"] == analysis_id for item in history_after_delete.json()["items"]))


if __name__ == "__main__":
    unittest.main()
