from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from llm_control_center.config import Settings


@dataclass(frozen=True)
class ProjectPrincipal:
    project_id: str
    api_key_id: str
    scopes: set[str]

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            from llm_control_center.errors import AuthorizationError

            raise AuthorizationError(f"missing scope: {scope}")


def generate_api_key(prefix: str = "llmcc") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str, settings: Settings) -> str:
    material = f"{settings.api_key_pepper}:{raw_key}".encode()
    return hashlib.sha256(material).hexdigest()


def secure_compare(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)


def api_key_prefix(raw_key: str) -> str:
    return raw_key[:16]
