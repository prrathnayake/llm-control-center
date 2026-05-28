from __future__ import annotations

from dataclasses import dataclass

from llm_control_center.errors import UnknownModelError


@dataclass(frozen=True)
class ModelRoute:
    alias: str
    provider: str
    provider_model: str


class ModelRouter:
    def __init__(self, routes: dict[str, dict[str, str]], default_alias: str) -> None:
        self._routes = routes
        self._default_alias = default_alias

    def resolve(self, alias: str | None) -> ModelRoute:
        model_alias = alias or self._default_alias
        route = self._routes.get(model_alias)
        if route is None:
            raise UnknownModelError(f"unknown model alias: {model_alias}")
        return ModelRoute(
            alias=model_alias,
            provider=route["provider"],
            provider_model=route["provider_model"],
        )

    def list_aliases(self) -> list[ModelRoute]:
        return [self.resolve(alias) for alias in sorted(self._routes)]
