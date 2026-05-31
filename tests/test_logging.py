from __future__ import annotations

import json
import logging

from llm_control_center.logging_config import configure_logging, disable_logging


class TestStructuredLogging:
    def test_configure_logging_json_format(self, capsys):
        configure_logging(level="DEBUG", json_format=True)
        logger = logging.getLogger("test_module")
        logger.warning("test_event", extra={"key": "value"})

        captured = capsys.readouterr()
        lines = [line for line in captured.out.splitlines() if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[-1])
        assert parsed["event"] == "test_event"

    def test_configure_logging_console_format(self, capsys):
        configure_logging(level="INFO", json_format=False)
        logger = logging.getLogger("test_module")
        logger.warning("test_event")

        captured = capsys.readouterr()
        assert "test_event" in captured.out

    def test_disable_logging(self):
        disable_logging()
        logger = logging.getLogger("test_module")
        logger.info("this should not raise")


class TestCorrelationIdMiddleware:
    def test_request_gets_correlation_id(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 32

    def test_request_preserves_existing_id(self, client):
        custom_id = "test-custom-id-12345"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id
