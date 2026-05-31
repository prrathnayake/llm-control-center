from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.config import Settings
from llm_control_center.errors import AuthenticationError
from llm_control_center.services.api_keys import ApiKeyService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_api_key_service(request: Request) -> ApiKeyService:
    return request.app.state.api_key_service


def get_chat_service(request: Request):
    return request.app.state.chat_service


def get_router(request: Request):
    return request.app.state.router


def get_providers(request: Request):
    return request.app.state.providers


def get_store(request: Request):
    return request.app.state.store


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    settings: Settings = request.app.state.settings
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


def require_project_principal(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProjectPrincipal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    raw_key = authorization.removeprefix("Bearer ").strip()
    api_key_service: ApiKeyService = request.app.state.api_key_service
    try:
        key = api_key_service.authenticate(raw_key)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return ProjectPrincipal(
        project_id=key["project_id"],
        api_key_id=key["id"],
        scopes=set(key["scopes"]),
    )
