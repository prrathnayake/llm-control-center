from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


class SQLiteStore:
    """Small persistence layer for the MVP.

    This intentionally avoids ORM complexity while keeping database access isolated.
    Production can replace this class with a PostgreSQL-backed implementation.
    """

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// URLs are supported by the MVP store")
        db_path = database_url.replace("sqlite:///", "", 1)
        self.path = Path(db_path)
        if self.path.parent != Path(""):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = RLock()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def initialize(self) -> None:
        with self._locked_cursor() as cursor:
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    prefix TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    model_alias TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                """
            )

    @contextmanager
    def _locked_cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cursor.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    def create_project(self, name: str, description: str) -> dict[str, Any]:
        project = {
            "id": f"prj_{uuid.uuid4().hex}",
            "name": name,
            "description": description,
            "created_at": utc_now(),
        }
        with self._locked_cursor() as cursor:
            cursor.execute(
                "INSERT INTO projects(id, name, description, created_at) VALUES(?, ?, ?, ?)",
                (project["id"], project["name"], project["description"], project["created_at"]),
            )
        return project

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._locked_cursor() as cursor:
            row = cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._row_to_dict(row)

    def create_api_key(
        self,
        *,
        project_id: str,
        name: str,
        key_hash: str,
        prefix: str,
        scopes: list[str],
    ) -> dict[str, Any]:
        key = {
            "id": f"key_{uuid.uuid4().hex}",
            "project_id": project_id,
            "name": name,
            "key_hash": key_hash,
            "prefix": prefix,
            "scopes": json.dumps(scopes),
            "created_at": utc_now(),
        }
        with self._locked_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO api_keys(id, project_id, name, key_hash, prefix, scopes, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key["id"],
                    key["project_id"],
                    key["name"],
                    key["key_hash"],
                    key["prefix"],
                    key["scopes"],
                    key["created_at"],
                ),
            )
        key["scopes"] = scopes
        return key

    def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        with self._locked_cursor() as cursor:
            row = cursor.execute(
                "SELECT * FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
        key = self._row_to_dict(row)
        if key:
            key["scopes"] = json.loads(key["scopes"])
        return key

    def insert_usage_log(
        self,
        *,
        trace_id: str,
        project_id: str,
        model_alias: str,
        provider: str,
        provider_model: str,
        status: str,
        latency_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        error: str | None,
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self._locked_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO usage_logs(
                    trace_id, project_id, model_alias, provider, provider_model, status,
                    latency_ms, prompt_tokens, completion_tokens, total_tokens, error, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    project_id,
                    model_alias,
                    provider,
                    provider_model,
                    status,
                    latency_ms,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    error,
                    created_at,
                ),
            )
            row_id = cursor.lastrowid
        return {
            "id": row_id,
            "trace_id": trace_id,
            "project_id": project_id,
            "model_alias": model_alias,
            "provider": provider,
            "provider_model": provider_model,
            "status": status,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "error": error,
            "created_at": created_at,
        }

    def list_usage_logs(
        self,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._locked_cursor() as cursor:
            if project_id:
                rows = cursor.execute(
                    """
                    SELECT * FROM usage_logs
                    WHERE project_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (project_id, limit),
                ).fetchall()
            else:
                rows = cursor.execute(
                    "SELECT * FROM usage_logs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(row) for row in rows]
