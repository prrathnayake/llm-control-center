from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from llm_control_center.api.deps import require_admin
from llm_control_center.errors import AuthenticationError, ProjectConflictError
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
        return request.app.state.project_service.create_project(
            name=payload.name, description=payload.description
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_admin)],
)
def list_projects(request: Request) -> list[dict]:
    return request.app.state.project_service.list_projects()


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_admin)],
)
def get_project(project_id: str, request: Request) -> dict:
    project = request.app.state.project_service.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project not found: {project_id}",
        )
    return project


@router.get(
    "/projects/{project_id}/api-keys",
    response_model=list[ApiKeyResponse],
    dependencies=[Depends(require_admin)],
)
def list_project_api_keys(project_id: str, request: Request) -> list[dict]:
    return request.app.state.project_service.list_api_keys(project_id)


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


@router.delete(
    "/projects/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def revoke_project_api_key(project_id: str, key_id: str, request: Request) -> None:
    success = request.app.state.project_service.revoke_api_key(project_id=project_id, key_id=key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key not found: {key_id}",
        )


@router.get("/usage", response_model=UsageLogsResponse, dependencies=[Depends(require_admin)])
async def list_usage(
    request: Request,
    project_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    endpoint: str | None = None,
    status: str | None = None,
    workflow: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
) -> dict:
    await request.app.state.usage_service.flush()
    logs = request.app.state.project_service.list_usage_logs(
        project_id=project_id,
        limit=limit,
        endpoint=endpoint,
        status=status,
        workflow=workflow,
        session_id=session_id,
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
    )
    return {"data": logs}
