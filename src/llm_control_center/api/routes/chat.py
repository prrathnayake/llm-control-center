from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from llm_control_center.api.deps import require_project_principal
from llm_control_center.auth import ProjectPrincipal
from llm_control_center.errors import (
    AuthorizationError,
    ProviderExecutionError,
    ProviderNotFoundError,
    UnknownModelError,
)
from llm_control_center.schemas import ChatCompletionRequest, ChatCompletionResponse, ModelsResponse

router = APIRouter(prefix="/v1", tags=["llm"])


@router.get("/models", response_model=ModelsResponse)
def list_models(
    request: Request,
    principal: ProjectPrincipal = Depends(require_project_principal),
) -> dict:
    principal.require_scope("chat:write")
    models = []
    for route in request.app.state.router.list_aliases():
        provider = request.app.state.providers.get(route.provider)
        models.append(
            {
                "id": route.alias,
                "provider": route.provider,
                "capabilities": provider.capabilities.model_dump(),
            }
        )
    return {"data": models}


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    principal: ProjectPrincipal = Depends(require_project_principal),
) -> ChatCompletionResponse:
    if payload.stream:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="streaming endpoint is planned; send stream=false for this MVP",
        )
    try:
        return await request.app.state.chat_service.complete(
            principal=principal,
            request=payload,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except UnknownModelError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except ProviderExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
