from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "georaster.db"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS analyses (
              id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              analysis_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              message TEXT,
              result_json TEXT,
              FOREIGN KEY (analysis_id) REFERENCES analyses(id)
            );

            CREATE TABLE IF NOT EXISTS exports (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              kind TEXT NOT NULL,
              filename TEXT NOT NULL,
              content_type TEXT NOT NULL,
              bytes BLOB NOT NULL,
              FOREIGN KEY (run_id) REFERENCES runs(id)
            );

            CREATE TABLE IF NOT EXISTS processing_cache (
              cache_key TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              params_json TEXT NOT NULL,
              result_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS landcover_classes (
              id TEXT PRIMARY KEY,
              project_id TEXT,
              code INTEGER NOT NULL,
              name TEXT NOT NULL,
              description TEXT,
              color TEXT NOT NULL,
              sort_order INTEGER DEFAULT 0,
              is_active INTEGER DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS training_samples (
              id TEXT PRIMARY KEY,
              project_id TEXT,
              class_id TEXT,
              user_id TEXT,
              geometry_json TEXT NOT NULL,
              geometry_type TEXT,
              usage TEXT DEFAULT 'training',
              quality_status TEXT DEFAULT 'valid',
              source TEXT,
              properties_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (class_id) REFERENCES landcover_classes(id)
            );

            CREATE TABLE IF NOT EXISTS classification_models (
              id TEXT PRIMARY KEY,
              project_id TEXT,
              name TEXT,
              algorithm TEXT NOT NULL,
              algorithm_params_json TEXT,
              input_bands_json TEXT,
              samples_hash TEXT,
              aoi_hash TEXT,
              cache_key TEXT UNIQUE,
              gee_asset_id TEXT,
              model_metadata_json TEXT,
              status TEXT DEFAULT 'trained',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS classification_results (
              id TEXT PRIMARY KEY,
              project_id TEXT,
              model_id TEXT,
              run_id TEXT,
              aoi_json TEXT,
              classified_tile_url TEXT,
              classified_asset_id TEXT,
              palette_json TEXT,
              class_stats_json TEXT,
              mode TEXT DEFAULT 'gee',
              status TEXT DEFAULT 'completed',
              created_at TEXT NOT NULL,
              FOREIGN KEY (model_id) REFERENCES classification_models(id)
            );

            CREATE TABLE IF NOT EXISTS async_jobs (
              job_id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS validation_metrics (
              id TEXT PRIMARY KEY,
              result_id TEXT,
              model_id TEXT,
              confusion_matrix_json TEXT,
              overall_accuracy REAL,
              kappa REAL,
              producer_accuracy_json TEXT,
              user_accuracy_json TEXT,
              omission_error_json TEXT,
              commission_error_json TEXT,
              validation_samples_count INTEGER,
              created_at TEXT NOT NULL,
              FOREIGN KEY (result_id) REFERENCES classification_results(id),
              FOREIGN KEY (model_id) REFERENCES classification_models(id)
            );
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(exports)").fetchall()}
        if "file_path" not in columns:
            conn.execute("ALTER TABLE exports ADD COLUMN file_path TEXT")


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def json_loads(text: str) -> Any:
    return json.loads(text)


def fetch_one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    cur = conn.execute(sql, tuple(params))
    return cur.fetchone()


def fetch_all(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    cur = conn.execute(sql, tuple(params))
    return cur.fetchall()
