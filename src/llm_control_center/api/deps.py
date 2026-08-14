from __future__ import annotations

import secrets

import structlog
from fastapi import Header, HTTPException, Request, status

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.config import Settings
from llm_control_center.errors import AuthenticationError
from llm_control_center.services.api_keys import ApiKeyService

logger = structlog.stdlib.get_logger(__name__)


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    settings: Settings = request.app.state.settings
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        logger.warning("auth_failed", auth_type="admin_token", reason="invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")
    logger.debug("auth_success", auth_type="admin_token")


def require_project_principal(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ProjectPrincipal:
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("auth_failed", auth_type="api_key", reason="missing bearer token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    raw_key = authorization.removeprefix("Bearer ").strip()
    key = getattr(request.state, "authenticated_api_key", None)
    if not isinstance(key, dict):
        api_key_service: ApiKeyService = request.app.state.api_key_service
        try:
            key = api_key_service.authenticate(raw_key)
        except AuthenticationError as exc:
            logger.warning("auth_failed", auth_type="api_key", reason=str(exc))
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    logger.debug("auth_success", auth_type="api_key", project_id=key["project_id"])
    return ProjectPrincipal(
        project_id=key["project_id"],
        api_key_id=key["id"],
        scopes=set(key["scopes"]),
    )
