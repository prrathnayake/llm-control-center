from __future__ import annotations

import asyncio

import pytest

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.db import Store
from llm_control_center.errors import AuthorizationError, ProjectConflictError
from llm_control_center.providers.mock import MockProvider
from llm_control_center.providers.registry import ProviderRegistry
from llm_control_center.routing import ModelRouter
from llm_control_center.schemas import ChatCompletionRequest, ChatMessage, Usage
from llm_control_center.services.chat import ChatService
from llm_control_center.services.models import ModelsService
from llm_control_center.services.projects import ProjectService
from llm_control_center.services.usage import UsageService


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


class TestUsageService:
    def test_worker_survives_failed_write_and_flush_completes(self):
        class FailOnceStore:
            def __init__(self) -> None:
                self.calls = 0
                self.records: list[dict] = []

            def insert_usage_log(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("simulated database outage")
                self.records.append(kwargs)
                return kwargs

        async def exercise() -> None:
            store = FailOnceStore()
            service = UsageService(store=store, queue_size=2)  # type: ignore[arg-type]
            usage = Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2)

            await service.start()
            await service.record_async(
                trace_id="tr_failed",
                project_id="prj_1",
                model_alias="default-chat",
                provider="mock",
                provider_model="mock-smart",
                status="success",
                latency_ms=1,
                usage=usage,
            )
            await service.record_async(
                trace_id="tr_written",
                project_id="prj_1",
                model_alias="default-chat",
                provider="mock",
                provider_model="mock-smart",
                status="success",
                latency_ms=1,
                usage=usage,
            )

            await asyncio.wait_for(service.flush(), timeout=1)
            assert service._worker is not None
            assert not service._worker.done()
            assert store.calls == 3
            assert [record["trace_id"] for record in store.records] == [
                "tr_failed",
                "tr_written",
            ]
            await service.stop()

        asyncio.run(exercise())


def test_cancelled_provider_call_records_terminal_usage() -> None:
    class BlockingProvider:
        name = "blocking"
        capabilities = MockProvider.capabilities

        def __init__(self) -> None:
            self.started = asyncio.Event()

        async def chat(self, request):
            self.started.set()
            await asyncio.Event().wait()

        async def respond(self, request):
            raise AssertionError("not used")

    class UsageDouble:
        def __init__(self) -> None:
            self.rows: list[dict] = []

        async def record_async(self, **kwargs):
            self.rows.append(kwargs)

    async def exercise() -> None:
        provider = BlockingProvider()
        usage = UsageDouble()
        service = ChatService(
            router=ModelRouter(
                {"default": {"provider": "blocking", "provider_model": "model"}},
                "default",
            ),
            providers=ProviderRegistry([provider]),  # type: ignore[list-item]
            usage_service=usage,  # type: ignore[arg-type]
        )
        task = asyncio.create_task(
            service.complete(
                principal=ProjectPrincipal(
                    project_id="prj", api_key_id="key", scopes={"chat:write"}
                ),
                request=ChatCompletionRequest(
                    messages=[ChatMessage(role="user", content="wait")]
                ),
            )
        )
        await provider.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert len(usage.rows) == 1
        assert usage.rows[0]["status"] == "cancelled"
        assert usage.rows[0]["error"] == "request cancelled"

    asyncio.run(exercise())

def test_durable_spool_replays_after_restart(tmp_path):
        class StoreDouble:
            def __init__(self, *, fail: bool) -> None:
                self.fail = fail
                self.records: list[dict] = []

            def insert_usage_log(self, **kwargs):
                if self.fail:
                    raise RuntimeError("offline")
                self.records.append(kwargs)
                return kwargs

        async def exercise() -> None:
            spool = tmp_path / "usage-spool.sqlite3"
            failed_store = StoreDouble(fail=True)
            first = UsageService(
                store=failed_store,  # type: ignore[arg-type]
                spool_path=spool,
            )
            first._persist_spooled(
                "spool-before-crash",
                {
                    "trace_id": "tr_replay",
                    "project_id": "prj_1",
                    "model_alias": "default-chat",
                    "provider": "mock",
                    "provider_model": "mock-smart",
                    "status": "success",
                    "latency_ms": 1,
                    "usage": Usage(total_tokens=1),
                },
            )

            recovered_store = StoreDouble(fail=False)
            second = UsageService(
                store=recovered_store,  # type: ignore[arg-type]
                spool_path=spool,
            )
            await second.start()
            await second.flush()
            await second.stop()

            assert [row["trace_id"] for row in recovered_store.records] == [
                "tr_replay"
            ]
            with second._connect_spool() as connection:
                assert connection.execute(
                    "SELECT COUNT(*) FROM usage_spool"
                ).fetchone()[0] == 0

        asyncio.run(exercise())
