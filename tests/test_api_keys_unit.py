from __future__ import annotations

import pytest

from llm_control_center.config import Settings
from llm_control_center.db import Store
from llm_control_center.errors import AuthenticationError
from llm_control_center.services.api_keys import ApiKeyService


class TestApiKeyService:
    def test_create_project_key_nonexistent_project(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        settings = Settings(api_key_pepper="test-pepper")
        service = ApiKeyService(store=store, settings=settings)
        try:
            with pytest.raises(AuthenticationError, match="project not found"):
                service.create_project_key(
                    project_id="nonexistent",
                    name="key",
                    scopes=["chat:write"],
                )
        finally:
            store.close()

    def test_authenticate_invalid_key(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        settings = Settings(api_key_pepper="test-pepper")
        service = ApiKeyService(store=store, settings=settings)
        try:
            with pytest.raises(AuthenticationError, match="invalid API key"):
                service.authenticate("invalid_key_12345")
        finally:
            store.close()

    def test_create_and_authenticate_roundtrip(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        settings = Settings(api_key_pepper="test-pepper")
        service = ApiKeyService(store=store, settings=settings)
        try:
            project = store.create_project("proj1", "desc")
            project_id = project["id"]
            raw_key, key_info = service.create_project_key(
                project_id=project_id,
                name="test-key",
                scopes=["chat:write"],
            )
            authenticated = service.authenticate(raw_key)
            assert authenticated["project_id"] == project_id
            assert authenticated["id"] == key_info["id"]
        finally:
            store.close()
