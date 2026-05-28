from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_exists():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists()
    content = workflow.read_text()
    assert "ruff check" in content
    assert "pytest" in content


def test_required_docs_exist():
    required = [
        "README.md",
        "AGENTS.md",
        "docs/ARCHITECTURE.md",
        "docs/API.md",
        "docs/TESTING.md",
        "docs/OPERATIONS.md",
        "docs/adr/0001-llm-gateway.md",
    ]
    for path in required:
        assert (ROOT / path).exists(), path


def test_env_example_does_not_contain_real_secrets():
    content = (ROOT / ".env.example").read_text()
    assert "sk-" not in content
    assert "change-me" in content
