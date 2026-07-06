from __future__ import annotations

import pytest

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.db import Store
from llm_control_center.errors import AuthorizationError, ProjectConflictError
from llm_control_center.providers.mock import MockProvider
from llm_control_center.providers.registry import ProviderRegistry
from llm_control_center.routing import ModelRouter
from llm_control_center.services.models import ModelsService
from llm_control_center.services.projects import ProjectService


class TestProjectService:
    def test_create_list_get_roundtrip(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        service = ProjectService(store=store)
        try:
            project = service.create_project(name="alpha", description="d")
            assert project["name"] == "alpha"
            fetched = service.get_project(project["id"])
            assert fetched is not None and fetched["id"] == project["id"]
            listed = service.list_projects()
            assert len(listed) == 1
        finally:
            store.close()

    def test_duplicate_name_raises_conflict(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        service = ProjectService(store=store)
        try:
            service.create_project(name="dup", description="d")
            with pytest.raises(ProjectConflictError, match="already exists"):
                service.create_project(name="dup", description="other")
        finally:
            store.close()

    def test_get_project_missing_returns_none(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        service = ProjectService(store=store)
        try:
            assert service.get_project("missing") is None
        finally:
            store.close()

    def test_revoke_missing_key_returns_false(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        service = ProjectService(store=store)
        try:
            assert service.revoke_api_key(project_id="prj_x", key_id="key_y") is False
        finally:
            store.close()

    def test_usage_logs_returned(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        service = ProjectService(store=store)
        try:
            assert service.list_usage_logs() == []
        finally:
            store.close()


class TestModelsService:
    def _service(self) -> ModelsService:
        router = ModelRouter(
            routes={
                "default-chat": {"provider": "mock", "provider_model": "mock-smart"},
                "broken": {"provider": "missing", "provider_model": "x"},
            },
            default_alias="default-chat",
        )
        registry = ProviderRegistry(providers=[MockProvider()])
        return ModelsService(router=router, providers=registry)

    def test_list_models_skips_unregistered_providers(self):
        service = self._service()
        principal = ProjectPrincipal(
            project_id="prj_1", api_key_id="key_1", scopes={"models:read"}
        )
        models = service.list_models(principal=principal)
        # Only the mock-backed alias is exposed; the route referencing 'missing' is skipped.
        assert [m.id for m in models] == ["default-chat"]

    def test_list_models_requires_scope(self):
        service = self._service()
        principal = ProjectPrincipal(
            project_id="prj_1", api_key_id="key_1", scopes={"chat:write"}
        )
        with pytest.raises(AuthorizationError):
            service.list_models(principal=principal)
