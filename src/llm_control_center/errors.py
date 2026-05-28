from __future__ import annotations


class LLMControlCenterError(Exception):
    """Base application error."""


class AuthenticationError(LLMControlCenterError):
    """Raised when authentication fails."""


class AuthorizationError(LLMControlCenterError):
    """Raised when a caller lacks a required permission."""


class UnknownModelError(LLMControlCenterError):
    """Raised when a requested public model alias is not configured."""


class ProviderNotFoundError(LLMControlCenterError):
    """Raised when a route references an unregistered provider."""


class ProviderExecutionError(LLMControlCenterError):
    """Raised when a provider call fails."""
