from __future__ import annotations

from llm_control_center.auth import api_key_prefix, generate_api_key, hash_api_key
from llm_control_center.config import Settings
from llm_control_center.db import SQLiteStore
from llm_control_center.errors import AuthenticationError


class ApiKeyService:
    def __init__(self, *, store: SQLiteStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    def create_project_key(
        self,
        *,
        project_id: str,
        name: str,
        scopes: list[str],
    ) -> tuple[str, dict]:
        if self.store.get_project(project_id) is None:
            raise AuthenticationError("project not found")
        raw_key = generate_api_key()
        key = self.store.create_api_key(
            project_id=project_id,
            name=name,
            key_hash=hash_api_key(raw_key, self.settings),
            prefix=api_key_prefix(raw_key),
            scopes=scopes,
        )
        key.pop("key_hash", None)
        return raw_key, key

    def authenticate(self, raw_key: str) -> dict:
        key_hash = hash_api_key(raw_key, self.settings)
        key = self.store.get_api_key_by_hash(key_hash)
        if key is None:
            raise AuthenticationError("invalid API key")
        return key
