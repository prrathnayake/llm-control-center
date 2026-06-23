from __future__ import annotations

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.errors import ProviderNotFoundError
from llm_control_center.providers.registry import ProviderRegistry
from llm_control_center.routing import ModelRouter
from llm_control_center.schemas import PublicModel


class ModelsService:
    """Application service for listing exposed model aliases."""

    def __init__(self, *, router: ModelRouter, providers: ProviderRegistry) -> None:
        self.router = router
        self.providers = providers

    def list_models(self, *, principal: ProjectPrincipal) -> list[PublicModel]:
        # Enforce scope in the service layer for consistency with ChatService.
        principal.require_scope("models:read")
        models: list[PublicModel] = []
        for route in self.router.list_aliases():
            try:
                provider = self.providers.get(route.provider)
            except ProviderNotFoundError:
                continue
            models.append(
                PublicModel(
                    id=route.alias,
                    provider=route.provider,
                    capabilities=provider.capabilities,
                )
            )
        return models