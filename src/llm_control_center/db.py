from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, Text


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


metadata = MetaData()

projects_table = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False, unique=True),
    Column("description", Text, nullable=False),
    Column("created_at", String, nullable=False),
)

api_keys_table = Table(
    "api_keys",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, ForeignKey("projects.id"), nullable=False),
    Column("name", String, nullable=False),
    Column("key_hash", String, nullable=False, unique=True),
    Column("prefix", String, nullable=False),
    Column("scopes", Text, nullable=False),
    Column("created_at", String, nullable=False),
)

usage_logs_table = Table(
    "usage_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trace_id", String, nullable=False),
    Column("project_id", String, ForeignKey("projects.id"), nullable=False),
    Column("model_alias", String, nullable=False),
    Column("provider", String, nullable=False),
    Column("provider_model", String, nullable=False),
    Column("status", String, nullable=False),
    Column("latency_ms", Integer, nullable=False),
    Column("prompt_tokens", Integer, nullable=False),
    Column("completion_tokens", Integer, nullable=False),
    Column("total_tokens", Integer, nullable=False),
    Column("workflow", String, nullable=True),
    Column("session_id", String, nullable=True),
    Column("user_id", String, nullable=True),
    Column("tags", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("created_at", String, nullable=False),
)


class Store:
    """Database-agnostic persistence layer using SQLAlchemy Core.

    Supports SQLite (dev/testing) and PostgreSQL (production).
    """

    def __init__(self, database_url: str) -> None:
        self._engine = sa.create_engine(database_url)
        self._lock = __import__("threading").RLock()

    def close(self) -> None:
        with self._lock:
            self._engine.dispose()

    def initialize(self) -> None:
        with self._lock:
            metadata.create_all(self._engine)

    @contextmanager
    def _locked_connection(self) -> Iterator[sa.engine.Connection]:
        with self._lock:
            conn = self._engine.connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    @staticmethod
    def _row_to_dict(row: sa.engine.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row._mapping)

    def create_project(self, name: str, description: str) -> dict[str, Any]:
        project = {
            "id": f"prj_{uuid.uuid4().hex}",
            "name": name,
            "description": description,
            "created_at": utc_now(),
        }
        with self._locked_connection() as conn:
            conn.execute(projects_table.insert().values(**project))
        return project

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._locked_connection() as conn:
            row = conn.execute(
                projects_table.select().where(projects_table.c.id == project_id)
            ).fetchone()
        return self._row_to_dict(row)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._locked_connection() as conn:
            rows = conn.execute(
                projects_table.select().order_by(projects_table.c.id)
            ).fetchall()
        return [dict(row._mapping) for row in rows]

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
        with self._locked_connection() as conn:
            conn.execute(api_keys_table.insert().values(**key))
        key["scopes"] = scopes
        return key

    def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        with self._locked_connection() as conn:
            row = conn.execute(
                api_keys_table.select().where(api_keys_table.c.key_hash == key_hash)
            ).fetchone()
        key = self._row_to_dict(row)
        if key:
            key["scopes"] = json.loads(key["scopes"])
        return key

    def list_api_keys(self, project_id: str) -> list[dict[str, Any]]:
        with self._locked_connection() as conn:
            rows = conn.execute(
                api_keys_table.select()
                .where(api_keys_table.c.project_id == project_id)
                .order_by(api_keys_table.c.id)
            ).fetchall()
        result = []
        for row in rows:
            key = dict(row._mapping)
            key["scopes"] = json.loads(key["scopes"])
            key.pop("key_hash", None)
            result.append(key)
        return result

    def revoke_api_key(self, project_id: str, key_id: str) -> bool:
        with self._locked_connection() as conn:
            result = conn.execute(
                api_keys_table.delete().where(
                    sa.and_(
                        api_keys_table.c.id == key_id,
                        api_keys_table.c.project_id == project_id,
                    )
                )
            )
            return result.rowcount > 0

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
        workflow: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        created_at = utc_now()
        tags_json = json.dumps(tags) if tags else None
        values = {
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
            "workflow": workflow,
            "session_id": session_id,
            "user_id": user_id,
            "tags": tags_json,
            "error": error,
            "created_at": created_at,
        }
        with self._locked_connection() as conn:
            result = conn.execute(usage_logs_table.insert().values(**values))
            row_id = result.inserted_primary_key[0]
        return {
            "id": row_id,
            **values,
            "tags": tags if tags is not None else [],
        }

    def list_usage_logs(
        self,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._locked_connection() as conn:
            query = usage_logs_table.select().order_by(usage_logs_table.c.id.desc())
            if project_id:
                query = query.where(usage_logs_table.c.project_id == project_id)
            query = query.limit(limit)
            rows = conn.execute(query).fetchall()
        result = []
        for row in rows:
            row_dict = dict(row._mapping)
            tags = row_dict.get("tags")
            row_dict["tags"] = json.loads(tags) if tags else []
            result.append(row_dict)
        return result


SQLiteStore = Store
