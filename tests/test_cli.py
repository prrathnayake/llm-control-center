from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from llm_control_center.cli import GatewayClient, _copy_to_clipboard, main


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_client():
    client = MagicMock(spec=GatewayClient)
    return client


class TestCLIHelp:
    def test_main_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "LLM Control Center CLI" in result.output

    def test_project_help(self, runner):
        result = runner.invoke(main, ["project", "--help"])
        assert result.exit_code == 0
        assert "Manage projects" in result.output

    def test_key_help(self, runner):
        result = runner.invoke(main, ["key", "--help"])
        assert result.exit_code == 0
        assert "Manage API keys" in result.output


class TestProjectCommands:
    def test_project_create(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.create_project.return_value = {
                "id": "prj_abc123",
                "name": "my-project",
                "description": "Test project",
                "created_at": "2025-01-01T00:00:00",
            }
            MockClient.return_value = mock_instance
            result = runner.invoke(
                main,
                ["--url", "http://localhost:8080", "--token", "test-token",
                 "project", "create", "my-project", "--description", "Test project"],
            )
            assert result.exit_code == 0
            assert "prj_abc123" in result.output
            assert "my-project" in result.output

    def test_project_list(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.list_projects.return_value = [
                {
                    "id": "prj_abc123",
                    "name": "project-1",
                    "description": "First",
                    "created_at": "2025-01-01T00:00:00",
                },
                {
                    "id": "prj_def456",
                    "name": "project-2",
                    "description": "Second",
                    "created_at": "2025-01-02T00:00:00",
                },
            ]
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["project", "list"])
            assert result.exit_code == 0
            assert "project-1" in result.output
            assert "project-2" in result.output

    def test_project_list_empty(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.list_projects.return_value = []
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["project", "list"])
            assert result.exit_code == 0
            assert "No projects found" in result.output


class TestKeyCommands:
    def test_key_create(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.create_api_key.return_value = {
                "api_key": "llmcc_test_key_12345",
                "key": {
                    "id": "key_abc123",
                    "project_id": "prj_abc123",
                    "name": "my-key",
                    "prefix": "llmcc_test_key_",
                    "scopes": ["chat:write"],
                    "created_at": "2025-01-01T00:00:00",
                },
            }
            MockClient.return_value = mock_instance
            result = runner.invoke(
                main,
                ["key", "create", "prj_abc123", "--name", "my-key"],
            )
            assert result.exit_code == 0
            assert "llmcc_test_key_12345" in result.output
            assert "API Key Created Successfully" in result.output
            assert "my-key" in result.output

    def test_key_create_with_scopes(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.create_api_key.return_value = {
                "api_key": "llmcc_test_key_67890",
                "key": {
                    "id": "key_def456",
                    "project_id": "prj_abc123",
                    "name": "multi-scope-key",
                    "prefix": "llmcc_test_key_",
                    "scopes": ["chat:write", "models:read"],
                    "created_at": "2025-01-01T00:00:00",
                },
            }
            MockClient.return_value = mock_instance
            result = runner.invoke(
                main,
                ["key", "create", "prj_abc123", "--name", "multi-scope-key",
                 "--scopes", "chat:write,models:read"],
            )
            assert result.exit_code == 0
            assert "chat:write, models:read" in result.output

    def test_key_list(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.list_api_keys.return_value = [
                {
                    "id": "key_abc123",
                    "name": "key-1",
                    "prefix": "llmcc_",
                    "scopes": ["chat:write"],
                    "created_at": "2025-01-01T00:00:00",
                },
            ]
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["key", "list", "prj_abc123"])
            assert result.exit_code == 0
            assert "key-1" in result.output
            assert "key_abc123" in result.output

    def test_key_list_empty(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.list_api_keys.return_value = []
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["key", "list", "prj_abc123"])
            assert result.exit_code == 0
            assert "No API keys found" in result.output

    def test_key_revoke_with_force(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.revoke_api_key.return_value = True
            MockClient.return_value = mock_instance
            result = runner.invoke(
                main, ["key", "revoke", "prj_abc123", "key_abc123", "--force"]
            )
            assert result.exit_code == 0
            assert "revoked successfully" in result.output

    def test_key_revoke_not_found(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.revoke_api_key.return_value = False
            MockClient.return_value = mock_instance
            result = runner.invoke(
                main, ["key", "revoke", "prj_abc123", "key_nonexistent", "--force"]
            )
            assert result.exit_code == 0
            assert "not found" in result.output


class TestUsageCommand:
    def test_usage(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.list_usage.return_value = [
                {
                    "id": 1,
                    "trace_id": "tr_abc123",
                    "model_alias": "default-chat",
                    "status": "success",
                    "latency_ms": 150,
                    "total_tokens": 25,
                },
            ]
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["usage"])
            assert result.exit_code == 0
            assert "tr_abc123" in result.output
            assert "default-chat" in result.output

    def test_usage_empty(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.list_usage.return_value = []
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["usage"])
            assert result.exit_code == 0
            assert "No usage logs found" in result.output


class TestHealthCommand:
    def test_health(self, runner):
        with patch("llm_control_center.cli.GatewayClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.health_check.return_value = {"status": "ok"}
            MockClient.return_value = mock_instance
            result = runner.invoke(main, ["health"])
            assert result.exit_code == 0
            assert "ok" in result.output


class TestCopyToClipboard:
    def test_copy_returns_false_on_failure(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError("no such command")
            assert _copy_to_clipboard("test") is False
