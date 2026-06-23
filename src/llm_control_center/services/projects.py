from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from llm_control_center.db import Store
from llm_control_center.errors import ProjectConflictError


class ProjectService:
    """Application service for project + project-scoped admin operations."""

    def __init__(self, *, store: Store) -> None:
        self.store = store

    def create_project(self, *, name: str, description: str = "") -> dict[str, Any]:
        try:
            return self.store.create_project(name, description)
        except sa.exc.IntegrityError as exc:
            raise ProjectConflictError(
                f"project with name '{name}' already exists"
            ) from exc

    def list_projects(self) -> list[dict[str, Any]]:
        return self.store.list_projects()

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self.store.get_project(project_id)

    def list_api_keys(self, project_id: str) -> list[dict[str, Any]]:
        return self.store.list_api_keys(project_id)

    def revoke_api_key(self, *, project_id: str, key_id: str) -> bool:
        return self.store.revoke_api_key(project_id, key_id)

    def list_usage_logs(
        self, *, project_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return self.store.list_usage_logs(project_id=project_id, limit=limit)