from __future__ import annotations

import pytest
import sqlalchemy as sa

from llm_control_center.db import Store


class TestStoreURLValidation:
    def test_rejects_mysql_url(self):
        with pytest.raises((sa.exc.ArgumentError, ModuleNotFoundError)):
            Store("mysql://localhost/db")


class TestStoreUsageLogs:
    def test_list_usage_logs_with_project_id(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        try:
            project = store.create_project("proj1", "desc1")
            project_id = project["id"]
            store.insert_usage_log(
                trace_id="tr_1",
                project_id=project_id,
                model_alias="default-chat",
                provider="mock",
                provider_model="mock-smart",
                status="success",
                latency_ms=100,
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                error=None,
            )
            store.insert_usage_log(
                trace_id="tr_2",
                project_id="other-project",
                model_alias="default-chat",
                provider="mock",
                provider_model="mock-smart",
                status="success",
                latency_ms=200,
                prompt_tokens=20,
                completion_tokens=10,
                total_tokens=30,
                error=None,
            )
            logs = store.list_usage_logs(project_id=project_id)
            assert len(logs) == 1
            assert logs[0]["trace_id"] == "tr_1"
        finally:
            store.close()

    def test_list_usage_logs_without_project_id(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        try:
            project = store.create_project("proj1", "desc1")
            project_id = project["id"]
            for i in range(3):
                store.insert_usage_log(
                    trace_id=f"tr_{i}",
                    project_id=project_id,
                    model_alias="default-chat",
                    provider="mock",
                    provider_model="mock-smart",
                    status="success",
                    latency_ms=100,
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    error=None,
                )
            logs = store.list_usage_logs()
            assert len(logs) == 3
        finally:
            store.close()

    def test_list_usage_logs_respects_limit(self, tmp_path):
        store = Store(f"sqlite:///{tmp_path}/test.db")
        store.initialize()
        try:
            project = store.create_project("proj1", "desc1")
            project_id = project["id"]
            for i in range(5):
                store.insert_usage_log(
                    trace_id=f"tr_{i}",
                    project_id=project_id,
                    model_alias="default-chat",
                    provider="mock",
                    provider_model="mock-smart",
                    status="success",
                    latency_ms=100,
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    error=None,
                )
            logs = store.list_usage_logs(limit=2)
            assert len(logs) == 2
        finally:
            store.close()
