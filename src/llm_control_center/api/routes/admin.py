from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from llm_control_center.api.deps import require_admin
from llm_control_center.errors import AuthenticationError
from llm_control_center.schemas import (
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    CreateProjectRequest,
    ProjectResponse,
    UsageLogsResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/projects", response_model=ProjectResponse, dependencies=[Depends(require_admin)])
def create_project(payload: CreateProjectRequest, request: Request) -> dict:
    try:
        return request.app.state.store.create_project(payload.name, payload.description)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project with name '{payload.name}' already exists",
        ) from exc


@router.post(
    "/projects/{project_id}/api-keys",
    response_model=CreateApiKeyResponse,
    dependencies=[Depends(require_admin)],
)
def create_project_api_key(
    project_id: str,
    payload: CreateApiKeyRequest,
    request: Request,
) -> dict:
    try:
        raw_key, key = request.app.state.api_key_service.create_project_key(
            project_id=project_id,
            name=payload.name,
            scopes=payload.scopes,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"api_key": raw_key, "key": ApiKeyResponse(**key).model_dump()}


@router.get("/usage", response_model=UsageLogsResponse, dependencies=[Depends(require_admin)])
def list_usage(
    request: Request,
    project_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    logs = request.app.state.store.list_usage_logs(project_id=project_id, limit=limit)
    return {"data": logs}
