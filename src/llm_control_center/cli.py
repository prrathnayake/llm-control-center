from __future__ import annotations

import subprocess
import sys
from typing import Any

import click
import httpx

_DEFAULT_BASE_URL = "http://localhost:8080"
_DEFAULT_ADMIN_TOKEN = "change-me-admin-token"


class GatewayClient:
    """HTTP client for the LLM Control Center admin API."""

    def __init__(self, base_url: str, admin_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Admin-Token": self.admin_token},
            timeout=10.0,
        )

    def close(self) -> None:
        self._client.close()

    def _handle_error(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            click.echo(f"Error ({response.status_code}): {detail}", err=True)
            raise SystemExit(1)

    def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        response = self._client.post(
            "/admin/projects",
            json={"name": name, "description": description},
        )
        self._handle_error(response)
        return response.json()

    def list_projects(self) -> list[dict[str, Any]]:
        response = self._client.get("/admin/projects")
        self._handle_error(response)
        return response.json()

    def create_api_key(
        self, project_id: str, name: str, scopes: list[str]
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/admin/projects/{project_id}/api-keys",
            json={"name": name, "scopes": scopes},
        )
        self._handle_error(response)
        return response.json()

    def list_api_keys(self, project_id: str) -> list[dict[str, Any]]:
        response = self._client.get(f"/admin/projects/{project_id}/api-keys")
        self._handle_error(response)
        return response.json()

    def revoke_api_key(self, project_id: str, key_id: str) -> bool:
        response = self._client.delete(f"/admin/projects/{project_id}/api-keys/{key_id}")
        if response.status_code == 204:
            return True
        self._handle_error(response)
        return False

    def list_usage(
        self, project_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if project_id:
            params["project_id"] = project_id
        response = self._client.get("/admin/usage", params=params)
        self._handle_error(response)
        return response.json().get("data", [])

    def list_models(self) -> list[dict[str, Any]]:
        response = self._client.get(
            "/v1/models",
            headers={"Authorization": "Bearer dummy"},
        )
        if response.status_code == 401:
            click.echo(
                "Error: The /v1/models endpoint requires a project API key, not admin token.",
                err=True,
            )
            raise SystemExit(1)
        self._handle_error(response)
        return response.json().get("data", [])

    def health_check(self) -> dict[str, Any]:
        response = self._client.get("/health")
        self._handle_error(response)
        return response.json()


def _copy_to_clipboard(text: str) -> bool:
    """Try to copy text to clipboard. Returns True if successful."""
    try:
        if sys.platform == "darwin":
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(input=text.encode())
            return proc.returncode == 0
        elif sys.platform == "linux":
            try:
                proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                proc.communicate(input=text.encode())
                return proc.returncode == 0
            except FileNotFoundError:
                proc = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
                proc.communicate(input=text.encode())
                return proc.returncode == 0
        elif sys.platform == "win32":
            proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            proc.communicate(input=text.encode())
            return proc.returncode == 0
    except Exception:
        pass
    return False


def _print_api_key_card(api_key: str, key_info: dict[str, Any]) -> None:
    """Display the API key with security warning."""
    click.echo()
    click.echo(click.style("  API Key Created Successfully", fg="green", bold=True))
    click.echo(click.style("  " + "=" * 50, fg="green"))
    click.echo()
    click.echo(f"  Project ID:  {key_info['project_id']}")
    click.echo(f"  Key ID:      {key_info['id']}")
    click.echo(f"  Key Name:    {key_info['name']}")
    click.echo(f"  Scopes:      {', '.join(key_info['scopes'])}")
    click.echo(f"  Created:     {key_info['created_at']}")
    click.echo()
    click.echo(click.style("  " + "-" * 50, fg="yellow"))
    click.echo(
        click.style(
            "  Your API Key (copy it now - it won't be shown again):",
            fg="yellow",
            bold=True,
        )
    )
    click.echo()
    click.echo(click.style(f"  {api_key}", fg="cyan", bold=True))
    click.echo()
    click.echo(click.style("  " + "-" * 50, fg="yellow"))
    click.echo()

    if _copy_to_clipboard(api_key):
        click.echo(click.style("  Copied to clipboard!", fg="green"))
    else:
        click.echo(click.style("  Select and copy the key above manually.", fg="yellow"))

    click.echo()
    click.echo(
        click.style(
            "  WARNING: This key will not be shown again. Store it securely.",
            fg="red",
            bold=True,
        )
    )
    click.echo()


def _get_client(ctx: click.Context) -> GatewayClient:
    """Get the gateway client from context."""
    return ctx.obj["client"]


@click.group()
@click.option(
    "--url",
    envvar="LLM_CC_URL",
    default=_DEFAULT_BASE_URL,
    help="Gateway URL.",
    show_default=True,
)
@click.option(
    "--token",
    envvar="LLM_CC_ADMIN_TOKEN",
    default=_DEFAULT_ADMIN_TOKEN,
    help="Admin token for authentication.",
    show_default=True,
)
@click.pass_context
def main(ctx: click.Context, url: str, token: str) -> None:
    """LLM Control Center CLI - Manage projects and API keys."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = GatewayClient(url, token)


@main.group()
def project() -> None:
    """Manage projects."""


@project.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Project description.")
@click.pass_context
def project_create(ctx: click.Context, name: str, description: str) -> None:
    """Create a new project."""
    client = _get_client(ctx)
    result = client.create_project(name, description)
    click.echo(f"Project created: {result['id']}")
    click.echo(f"  Name:        {result['name']}")
    click.echo(f"  Description: {result['description']}")
    click.echo(f"  Created:     {result['created_at']}")


@project.command("list")
@click.pass_context
def project_list(ctx: click.Context) -> None:
    """List all projects."""
    client = _get_client(ctx)
    projects = client.list_projects()
    if not projects:
        click.echo("No projects found.")
        return

    click.echo(f"{'ID':<40} {'Name':<25} {'Description':<40} {'Created':<20}")
    click.echo("-" * 125)
    for p in projects:
        click.echo(
            f"{p['id']:<40} "
            f"{p['name']:<25} "
            f"{p['description']:<40} "
            f"{p['created_at']:<20}"
        )


@main.group()
def key() -> None:
    """Manage API keys."""


@key.command("create")
@click.argument("project_id")
@click.option("--name", "-n", required=True, help="Key name.")
@click.option(
    "--scopes",
    "-s",
    default="chat:write",
    help="Comma-separated scopes (e.g., chat:write,models:read).",
    show_default=True,
)
@click.option("--copy/--no-copy", default=True, help="Auto-copy key to clipboard.")
@click.pass_context
def key_create(
    ctx: click.Context, project_id: str, name: str, scopes: str, copy: bool
) -> None:
    """Create an API key for a project.

    The key is shown only once. Copy it immediately.
    """
    client = _get_client(ctx)
    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    result = client.create_api_key(project_id, name, scope_list)
    _print_api_key_card(result["api_key"], result["key"])


@key.command("list")
@click.argument("project_id")
@click.pass_context
def key_list(ctx: click.Context, project_id: str) -> None:
    """List API keys for a project (shows metadata only, not the key values)."""
    client = _get_client(ctx)
    keys = client.list_api_keys(project_id)
    if not keys:
        click.echo("No API keys found for this project.")
        return

    click.echo(f"{'ID':<40} {'Name':<20} {'Prefix':<20} {'Scopes':<30} {'Created':<20}")
    click.echo("-" * 130)
    for k in keys:
        scopes = ", ".join(k.get("scopes", []))
        click.echo(
            f"{k['id']:<40} "
            f"{k['name']:<20} "
            f"{k['prefix']:<20} "
            f"{scopes:<30} "
            f"{k['created_at']:<20}"
        )


@key.command("revoke")
@click.argument("project_id")
@click.argument("key_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation.")
@click.pass_context
def key_revoke(ctx: click.Context, project_id: str, key_id: str, force: bool) -> None:
    """Revoke (delete) an API key.

    This action is irreversible.
    """
    if not force:
        click.confirm(
            f"Are you sure you want to revoke key {key_id}?",
            abort=True,
        )
    client = _get_client(ctx)
    success = client.revoke_api_key(project_id, key_id)
    if success:
        click.echo(click.style(f"Key {key_id} revoked successfully.", fg="green"))
    else:
        click.echo(click.style(f"Key {key_id} not found.", fg="red"))


@main.command()
@click.option("--project", "-p", default=None, help="Filter by project ID.")
@click.option("--limit", "-l", default=20, help="Number of logs to show.", show_default=True)
@click.pass_context
def usage(ctx: click.Context, project: str | None, limit: int) -> None:
    """View recent usage logs."""
    client = _get_client(ctx)
    logs = client.list_usage(project, limit)
    if not logs:
        click.echo("No usage logs found.")
        return

    header = (
        f"{'ID':<8} {'Trace ID':<20} {'Model':<15} "
        f"{'Status':<10} {'Latency':<10} {'Tokens':<8}"
    )
    click.echo(header)
    click.echo("-" * 80)
    for log in logs:
        click.echo(
            f"{log['id']:<8} "
            f"{log['trace_id']:<20} "
            f"{log['model_alias']:<15} "
            f"{log['status']:<10} "
            f"{log['latency_ms']:<10} "
            f"{log['total_tokens']:<8}"
        )


@main.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check gateway health."""
    client = _get_client(ctx)
    result = client.health_check()
    click.echo(f"Status: {result.get('status', 'unknown')}")


@main.command()
@click.pass_context
def models(ctx: click.Context) -> None:
    """List available model aliases."""
    client = _get_client(ctx)
    models_data = client.list_models()
    if not models_data:
        click.echo("No models available.")
        return

    click.echo(f"{'Alias':<20} {'Provider':<20} {'Capabilities':<30}")
    click.echo("-" * 70)
    for m in models_data:
        caps = m.get("capabilities", {})
        cap_str = ", ".join(k for k, v in caps.items() if v)
        click.echo(f"{m['id']:<20} {m['provider']:<20} {cap_str:<30}")


if __name__ == "__main__":
    main()
