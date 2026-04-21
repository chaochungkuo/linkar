from __future__ import annotations

import json
import os
import secrets
import time
from collections.abc import Callable, Iterable
from html import escape
from urllib.parse import parse_qs, unquote

from wsgiref.simple_server import make_server

from linkar import __version__
from linkar.assets import resolve_asset_refs
from linkar.core import (
    collect_run_outputs,
    describe_template,
    inspect_run,
    inspect_runtime,
    list_configured_packs,
    list_project_runs,
    list_templates,
    latest_project_run,
    load_template,
    preview_params_detailed,
    render_template,
    resolve_project_assets,
    run_template,
    test_template,
)
from linkar.errors import (
    AssetResolutionError,
    ExecutionError,
    LinkarError,
    ParameterResolutionError,
    ProjectValidationError,
    TemplateValidationError,
)
from linkar.runtime.projects import discover_project, load_project
from linkar.runtime.shared import normalize_binding_ref, preferred_pack_ref_for_assets, unique_assets
from linkar.runtime.templates import combined_configured_pack_entries

StartResponse = Callable[[str, list[tuple[str, str]]], object]
WSGIApp = Callable[[dict, StartResponse], Iterable[bytes]]
ALL_API_ROLES = ("read", "resolve", "execute")
RESOLVE_TOKEN_TTL_SECONDS = 15 * 60


def json_response(
    start_response: StartResponse,
    status: str,
    payload: dict | list,
) -> list[bytes]:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def success_response(start_response: StartResponse, payload: dict | list) -> list[bytes]:
    return json_response(start_response, "200 OK", {"ok": True, "data": payload})


def html_response(start_response: StartResponse, status: str, body: str) -> list[bytes]:
    encoded = body.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(encoded))),
        ],
    )
    return [encoded]


def error_status(exc: LinkarError) -> str:
    if isinstance(exc, (ProjectValidationError, TemplateValidationError, ParameterResolutionError)):
        return "400 Bad Request"
    if isinstance(exc, AssetResolutionError):
        return "404 Not Found"
    if isinstance(exc, ExecutionError):
        return "422 Unprocessable Entity"
    return "500 Internal Server Error"


def parse_api_token_specs(specs: list[str]) -> dict[str, set[str]]:
    tokens: dict[str, set[str]] = {}
    for chunk in specs:
        entry = chunk.strip()
        if not entry:
            continue
        token, _, roles_part = entry.partition(":")
        token = token.strip()
        if not token:
            continue
        roles = {role.strip() for role in roles_part.split(",") if role.strip()} if roles_part else set(ALL_API_ROLES)
        tokens[token] = roles or set(ALL_API_ROLES)
    return tokens


def load_api_tokens_from_env() -> dict[str, set[str]]:
    configured = os.environ.get("LINKAR_API_TOKENS", "").strip()
    if not configured:
        return {}
    return parse_api_token_specs(configured.split(";"))


def unauthorized_response(start_response: StartResponse, message: str = "Missing or invalid bearer token") -> list[bytes]:
    return json_response(
        start_response,
        "401 Unauthorized",
        {"ok": False, "error": {"code": "unauthorized", "message": message}},
    )


def forbidden_response(start_response: StartResponse, message: str = "Insufficient API role for this route") -> list[bytes]:
    return json_response(
        start_response,
        "403 Forbidden",
        {"ok": False, "error": {"code": "forbidden", "message": message}},
    )


def parse_bearer_token(environ: dict) -> str | None:
    header = (environ.get("HTTP_AUTHORIZATION") or "").strip()
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def authenticate_request(
    environ: dict,
    configured_tokens: dict[str, set[str]],
    *,
    required_role: str | None,
) -> tuple[dict[str, object] | None, list[bytes] | None]:
    if not configured_tokens:
        return {"subject": "anonymous", "roles": list(ALL_API_ROLES), "auth_required": False}, None

    token = parse_bearer_token(environ)
    if token is None or token not in configured_tokens:
        return None, unauthorized_response

    roles = configured_tokens[token]
    if required_role is not None and required_role not in roles:
        return None, forbidden_response
    return {"subject": "token", "roles": sorted(roles), "auth_required": True}, None


def query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    return values[0] if values else None


def query_values(query: dict[str, list[str]], key: str) -> list[str]:
    return query.get(key) or []


def load_json_body(environ: dict) -> dict:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    raw_body = environ["wsgi.input"].read(length) if length else b"{}"
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectValidationError(f"Request body must be valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ProjectValidationError("Request body must be a JSON object")
    return payload


def not_found(start_response: StartResponse) -> list[bytes]:
    return json_response(
        start_response,
        "404 Not Found",
        {"ok": False, "error": {"code": "not_found", "message": "Route not found"}},
    )


def preview_resolution(payload: dict) -> dict:
    details = resolve_preview_details(payload)
    return {
        "template": details["template"].id,
        "params": details["params"],
        "param_provenance": details["param_provenance"],
        "missing_required": details["missing_required"],
        "warnings": details["warnings"],
        "ready": not details["missing_required"],
    }


def resolve_preview_details(payload: dict) -> dict:
    template_ref = payload.get("template")
    if not isinstance(template_ref, str) or not template_ref:
        raise ProjectValidationError("Request field 'template' is required")

    project_value = payload.get("project")
    if isinstance(project_value, str):
        project_obj = load_project(project_value)
    elif project_value is None:
        project_obj = discover_project()
    else:
        project_obj = project_value

    configured_entries, active_entry = combined_configured_pack_entries(project_obj)
    explicit_pack_assets = resolve_asset_refs(payload.get("pack_refs"))
    combined_pack_assets = unique_assets(explicit_pack_assets + [entry.asset for entry in configured_entries])
    preferred_pack_ref = preferred_pack_ref_for_assets(explicit_pack_assets, active_entry)
    template = load_template(
        template_ref,
        pack_assets=combined_pack_assets,
        preferred_pack_ref=preferred_pack_ref,
    )
    selected_binding_ref = normalize_binding_ref(payload.get("binding_ref"))
    if selected_binding_ref is None and template.pack_root is not None:
        for entry in configured_entries:
            if entry.asset.root == template.pack_root:
                selected_binding_ref = normalize_binding_ref(entry.binding)
                break
    params, provenance, missing_required, warnings = preview_params_detailed(
        template,
        cli_params=payload.get("params"),
        project=project_obj,
        binding_ref=selected_binding_ref,
    )
    return {
        "project": project_obj,
        "template": template,
        "params": params,
        "param_provenance": provenance,
        "missing_required": missing_required,
        "warnings": warnings,
        "binding_ref": selected_binding_ref,
    }


def preview_resolution_v1(payload: dict) -> dict:
    return preview_resolution_v1_with_tokens(payload, resolve_tokens=None, subject="anonymous")


def preview_resolution_v1_with_tokens(
    payload: dict,
    *,
    resolve_tokens: dict[str, dict] | None,
    subject: str,
) -> dict:
    details = resolve_preview_details(payload)
    template = details["template"]
    project_obj = details["project"]
    missing_required = details["missing_required"]

    unresolved_params = []
    for key in missing_required:
        param_spec = template.params.get(key) or {}
        unresolved_params.append(
            {
                "name": key,
                "required": True,
                "type": param_spec.get("type", "any"),
                "description": param_spec.get("description"),
            }
        )

    resolve_token = None
    if not missing_required and resolve_tokens is not None:
        resolve_token = issue_resolve_token(
            resolve_tokens,
            subject=subject,
            template_ref=template.id,
            project_ref=str(project_obj.root) if project_obj is not None else None,
            params=details["params"],
            outdir=payload.get("outdir"),
            pack_refs=payload.get("pack_refs") or ([template.pack_ref] if project_obj is None and template.pack_ref else None),
            binding_ref=details["binding_ref"],
        )

    return {
        "template": {
            "id": template.id,
            "version": template.version,
            "description": template.description,
            "path": str(template.root),
            "pack": {
                "ref": template.pack_ref,
                "revision": template.pack_revision,
            },
            "run": {
                "entry": template.run_entry,
                "command": template.run_command,
                "mode": template.run_mode,
                "verbose_by_default": template.run_verbose_by_default,
            },
            "params": template.params,
            "outputs": template.outputs,
        },
        "project": (
            {
                "id": project_obj.data.get("id"),
                "path": str(project_obj.root),
            }
            if project_obj is not None
            else None
        ),
        "resolved_params": details["params"],
        "param_provenance": details["param_provenance"],
        "unresolved_params": unresolved_params,
        "warnings": details["warnings"],
        "expected_outputs": template.outputs,
        "confirmation": {
            "required": not missing_required,
            "reason": "Execution changes project state and may consume compute resources." if not missing_required else None,
            "level": "execute" if not missing_required else None,
        },
        "resolve_token": resolve_token,
        "ready": not missing_required,
    }


def prune_expired_resolve_tokens(resolve_tokens: dict[str, dict]) -> None:
    now = time.time()
    expired = [token for token, record in resolve_tokens.items() if record.get("expires_at", 0) <= now]
    for token in expired:
        resolve_tokens.pop(token, None)


def issue_resolve_token(
    resolve_tokens: dict[str, dict],
    *,
    subject: str,
    template_ref: str,
    project_ref: str | None,
    params: dict,
    outdir: str | None,
    pack_refs: list[str] | None,
    binding_ref: str | None,
) -> str:
    prune_expired_resolve_tokens(resolve_tokens)
    token = secrets.token_urlsafe(24)
    resolve_tokens[token] = {
        "subject": subject,
        "template": template_ref,
        "project": project_ref,
        "params": params,
        "outdir": outdir,
        "pack_refs": pack_refs,
        "binding_ref": binding_ref,
        "expires_at": time.time() + RESOLVE_TOKEN_TTL_SECONDS,
    }
    return token


def consume_resolve_token(
    resolve_tokens: dict[str, dict],
    *,
    token: str,
    subject: str,
    template_ref: str,
) -> dict:
    prune_expired_resolve_tokens(resolve_tokens)
    record = resolve_tokens.get(token)
    if record is None:
        raise ProjectValidationError("Resolve token is invalid or expired")
    if record.get("subject") != subject:
        raise ProjectValidationError("Resolve token does not belong to this authenticated subject")
    if record.get("template") != template_ref:
        raise ProjectValidationError("Resolve token does not match the requested template")
    resolve_tokens.pop(token, None)
    return record


def runtime_status_payload(run_ref: str, project: str | None = None) -> dict:
    runtime = inspect_runtime(run_ref, project=project)
    if runtime.get("finished_at"):
        status = "succeeded" if runtime.get("success") else "failed"
    else:
        status = "running"
    return {
        "kind": "run_status",
        "instance_id": run_ref,
        "status": status,
        "started_at": runtime.get("started_at"),
        "finished_at": runtime.get("finished_at"),
        "returncode": runtime.get("returncode"),
        "success": runtime.get("success"),
        "duration_seconds": runtime.get("duration_seconds"),
        "warnings": runtime.get("warnings") or [],
        "command": runtime.get("command"),
        "cwd": runtime.get("cwd"),
    }


def current_project_summary(project_ref: str | None = None) -> dict:
    if project_ref is not None:
        project_obj = load_project(project_ref)
    else:
        project_obj = discover_project()
    if project_obj is None:
        raise ProjectValidationError("No Linkar project found. Pass ?project=/path/to/project or run inside a project directory.")
    runs = list_project_runs(project=project_obj)
    return {
        "kind": "project",
        "id": project_obj.data.get("id"),
        "path": str(project_obj.root),
        "active_pack": project_obj.data.get("active_pack"),
        "packs": list_configured_packs(project=project_obj),
        "author": project_obj.data.get("author"),
        "run_count": len(runs),
        "recent_runs": [
            {
                "instance_id": entry.get("instance_id"),
                "template": entry.get("id"),
                "path": entry.get("path"),
            }
            for entry in runs[-5:]
        ],
    }


def normalize_run_summary(entry: dict) -> dict:
    summary = dict(entry)
    summary["kind"] = "run_summary"
    if "template" not in summary and "id" in summary:
        summary["template"] = summary["id"]
    return summary


def normalize_asset_summary(entry: dict) -> dict:
    summary = dict(entry)
    summary["kind"] = "asset"
    return summary


def normalize_template_summary(entry: dict) -> dict:
    summary = dict(entry)
    summary["kind"] = "template_summary"
    return summary


def collection_payload(kind: str, items_key: str, items: list[dict]) -> dict:
    return {
        "kind": kind,
        "items": items,
        items_key: items,
        "count": len(items),
    }


def v1_routes_document() -> list[dict[str, object]]:
    return [
        {"path": "/v1", "method": "GET", "kind": "service", "role": "read", "description": "Service discovery and API capabilities."},
        {"path": "/v1/health", "method": "GET", "kind": "health", "role": "none", "description": "Lightweight health check."},
        {"path": "/v1/schema", "method": "GET", "kind": "schema", "role": "read", "description": "Canonical route and capability document for agents."},
        {"path": "/v1/docs", "method": "GET", "kind": "docs", "role": "read", "description": "Live HTML documentation for the running local API server."},
        {"path": "/v1/projects/current", "method": "GET", "kind": "project", "role": "read", "description": "Summary of the current or selected Linkar project."},
        {"path": "/v1/projects/current/runs", "method": "GET", "kind": "run_collection", "role": "read", "description": "Recorded runs for the current or selected project."},
        {"path": "/v1/projects/current/runs/latest", "method": "GET", "kind": "run_summary", "role": "read", "description": "Newest matching recorded run for a project-scoped run_ref query."},
        {"path": "/v1/projects/current/assets", "method": "GET", "kind": "asset_collection", "role": "read", "description": "Resolved pack assets visible to the current or selected project."},
        {"path": "/v1/templates", "method": "GET", "kind": "template_collection", "role": "read", "description": "Available templates for the selected project or pack scope."},
        {"path": "/v1/templates/{template_id}", "method": "GET", "kind": "template", "role": "read", "description": "Template detail and declared contract."},
        {"path": "/v1/templates/{template_id}:resolve", "method": "POST", "kind": "resolve", "role": "resolve", "description": "Resolve params, provenance, warnings, and confirmation requirements."},
        {"path": "/v1/templates/{template_id}:run", "method": "POST", "kind": "run_submission", "role": "execute", "description": "Run a template directly or via a resolve token."},
        {"path": "/v1/templates/{template_id}:render", "method": "POST", "kind": "render_submission", "role": "execute", "description": "Render a runnable template bundle without executing it."},
        {"path": "/v1/templates/{template_id}:test", "method": "POST", "kind": "test_submission", "role": "execute", "description": "Run the template test workflow."},
        {"path": "/v1/runs/{instance_id}", "method": "GET", "kind": "run", "role": "read", "description": "Detailed run metadata and provenance."},
        {"path": "/v1/runs:collect", "method": "POST", "kind": "run_collect", "role": "execute", "description": "Refresh outputs for a run_ref and report whether the project ledger was updated."},
        {"path": "/v1/runs/{instance_id}/outputs", "method": "GET", "kind": "run_outputs", "role": "read", "description": "Collected outputs for a run."},
        {"path": "/v1/runs/{instance_id}/status", "method": "GET", "kind": "run_status", "role": "read", "description": "Compact runtime status for a run."},
        {"path": "/v1/runs/{instance_id}/runtime", "method": "GET", "kind": "run_runtime", "role": "read", "description": "Full recorded runtime metadata for a run."},
    ]


def v1_schema_document(identity: dict[str, object], *, auth_enabled: bool) -> dict:
    return {
        "kind": "schema",
        "service": "linkar",
        "api_version": "v1",
        "auth": {
            "enabled": auth_enabled,
            "scheme": "bearer" if auth_enabled else "optional",
            "roles": list(ALL_API_ROLES),
            "identity": identity,
        },
        "conventions": {
            "collections": {
                "items_field": "items",
                "count_field": "count",
                "compatibility_fields": ["templates", "runs", "assets"],
            },
            "detail_kind_field": "kind",
            "resolve_token_ttl_seconds": RESOLVE_TOKEN_TTL_SECONDS,
        },
        "routes": v1_routes_document(),
    }


def v1_docs_html(identity: dict[str, object], *, auth_enabled: bool) -> str:
    schema = v1_schema_document(identity, auth_enabled=auth_enabled)
    route_rows = "\n".join(
        (
            "<tr>"
            f"<td><code>{escape(str(route['method']))}</code></td>"
            f"<td><code>{escape(str(route['path']))}</code></td>"
            f"<td>{escape(str(route['role']))}</td>"
            f"<td>{escape(str(route['kind']))}</td>"
            f"<td>{escape(str(route['description']))}</td>"
            "</tr>"
        )
        for route in schema["routes"]
    )
    roles = ", ".join(schema["auth"]["roles"])
    compatibility = ", ".join(schema["conventions"]["collections"]["compatibility_fields"])
    current_identity = escape(json.dumps(schema["auth"]["identity"], sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Linkar Local API v1</title>
    <style>
      :root {{
        color-scheme: light dark;
        --bg: #07131f;
        --panel: #0d1d2d;
        --muted: #9fb3c8;
        --text: #eaf2fb;
        --accent: #8ae234;
        --border: #27415b;
      }}
      body {{
        margin: 0;
        padding: 2rem;
        font-family: ui-sans-serif, system-ui, sans-serif;
        background: var(--bg);
        color: var(--text);
      }}
      main {{
        max-width: 1120px;
        margin: 0 auto;
      }}
      h1, h2 {{ margin-top: 0; }}
      p, li {{ line-height: 1.5; }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin: 1rem 0 1.5rem;
      }}
      .lede {{ color: var(--muted); max-width: 72ch; }}
      code {{ font-family: ui-monospace, monospace; }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
      }}
      th, td {{
        border-top: 1px solid var(--border);
        padding: 0.75rem;
        text-align: left;
        vertical-align: top;
      }}
      th {{ color: var(--accent); }}
      a {{ color: var(--accent); }}
    </style>
  </head>
  <body>
    <main>
      <h1>Linkar Local API v1</h1>
      <p class="lede">
        Live reference for the running Linkar server. For machine-readable discovery use
        <code>/v1</code> and <code>/v1/schema</code>.
      </p>
      <section class="panel">
        <h2>Auth</h2>
        <p>Enabled: <strong>{str(schema['auth']['enabled']).lower()}</strong></p>
        <p>Scheme: <code>{escape(str(schema['auth']['scheme']))}</code></p>
        <p>Roles: <code>{escape(roles)}</code></p>
        <p>Current identity: <code>{current_identity}</code></p>
      </section>
      <section class="panel">
        <h2>Conventions</h2>
        <ul>
          <li>Collections expose <code>items</code> and <code>count</code>.</li>
          <li>Compatibility keys remain available: <code>{escape(compatibility)}</code>.</li>
          <li>Major detail responses expose a <code>kind</code> field.</li>
          <li>Resolve token TTL: <code>{schema['conventions']['resolve_token_ttl_seconds']}</code> seconds.</li>
        </ul>
      </section>
      <section class="panel">
        <h2>Routes</h2>
        <table>
          <thead>
            <tr>
              <th>Method</th>
              <th>Path</th>
              <th>Role</th>
              <th>Kind</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {route_rows}
          </tbody>
        </table>
      </section>
    </main>
  </body>
</html>
"""


def normalized_path(path: str) -> str:
    if path == "/v1":
        return path
    if path.startswith("/v1/"):
        return path.removeprefix("/v1")
    return path


def make_app(*, api_tokens: dict[str, set[str]] | None = None) -> WSGIApp:
    configured_tokens = api_tokens if api_tokens is not None else load_api_tokens_from_env()
    resolve_tokens: dict[str, dict] = {}

    def app(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        raw_path = environ.get("PATH_INFO", "")
        path = normalized_path(raw_path)
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)

        try:
            if method == "GET" and raw_path in {"/health", "/v1/health"}:
                return json_response(start_response, "200 OK", {"ok": True})

            required_role = "read" if method == "GET" else "execute"
            if raw_path in {"/resolve", "/v1/resolve"} or raw_path.startswith("/v1/templates/") and raw_path.endswith(":resolve"):
                required_role = "resolve"

            identity, auth_error_factory = authenticate_request(
                environ,
                configured_tokens,
                required_role=required_role,
            )
            if auth_error_factory is not None:
                return auth_error_factory(start_response)
            auth_subject = parse_bearer_token(environ) if configured_tokens else "anonymous"

            if method == "GET" and raw_path == "/v1":
                return success_response(
                    start_response,
                    {
                        "kind": "service",
                        "service": "linkar",
                        "api_version": "v1",
                        "linkar_version": __version__,
                        "features": {
                            "projects": True,
                            "templates": True,
                            "resolve": True,
                            "run": True,
                            "render": True,
                            "events": False,
                        },
                        "auth": {
                            "enabled": bool(configured_tokens),
                            "scheme": "bearer" if configured_tokens else "optional",
                            "roles": list(ALL_API_ROLES),
                        },
                        "routes": v1_routes_document(),
                        "identity": identity,
                    },
                )

            if method == "GET" and raw_path == "/v1/schema":
                return success_response(
                    start_response,
                    v1_schema_document(identity, auth_enabled=bool(configured_tokens)),
                )

            if method == "GET" and raw_path == "/v1/docs":
                return html_response(
                    start_response,
                    "200 OK",
                    v1_docs_html(identity, auth_enabled=bool(configured_tokens)),
                )

            if method == "GET" and path == "/templates":
                templates = list_templates(
                    pack_refs=query_values(query, "pack"),
                    project=query_value(query, "project"),
                )
                if raw_path.startswith("/v1/"):
                    templates = [normalize_template_summary(item) for item in templates]
                    payload = collection_payload("template_collection", "templates", templates)
                else:
                    payload = {"templates": templates}
                return success_response(start_response, payload)

            if method == "GET" and raw_path == "/v1/projects/current":
                return success_response(start_response, current_project_summary(query_value(query, "project")))

            if method == "GET" and raw_path == "/v1/projects/current/runs":
                runs = list_project_runs(project=query_value(query, "project"))
                runs = [normalize_run_summary(entry) for entry in runs]
                return success_response(start_response, collection_payload("run_collection", "runs", runs))

            if method == "GET" and raw_path == "/v1/projects/current/runs/latest":
                run_ref = query_value(query, "run_ref")
                if not run_ref:
                    raise ProjectValidationError("Query field 'run_ref' is required")
                run_entry = latest_project_run(run_ref, project=query_value(query, "project"))
                return success_response(start_response, normalize_run_summary(run_entry))

            if method == "GET" and raw_path == "/v1/projects/current/assets":
                assets = resolve_project_assets(project=query_value(query, "project"))
                assets = [normalize_asset_summary(entry) for entry in assets]
                return success_response(start_response, collection_payload("asset_collection", "assets", assets))

            if method == "GET" and path.startswith("/templates/"):
                template_ref = unquote(path.removeprefix("/templates/"))
                if not template_ref:
                    return not_found(start_response)
                template = describe_template(
                    template_ref,
                    pack_refs=query_values(query, "pack"),
                    project=query_value(query, "project"),
                )
                if raw_path.startswith("/v1/"):
                    template = {"kind": "template", **template}
                return success_response(start_response, template)

            if method == "GET" and path == "/projects/runs":
                runs = list_project_runs(project=query_value(query, "project"))
                if raw_path.startswith("/v1/"):
                    runs = [normalize_run_summary(entry) for entry in runs]
                    payload = collection_payload("run_collection", "runs", runs)
                else:
                    payload = {"runs": runs}
                return success_response(start_response, payload)

            if method == "GET" and path == "/projects/assets":
                assets = resolve_project_assets(project=query_value(query, "project"))
                return success_response(start_response, {"assets": assets})

            if method == "GET" and path.startswith("/runs/"):
                suffix = unquote(path.removeprefix("/runs/"))
                if suffix.endswith("/status"):
                    run_ref = suffix.removesuffix("/status")
                    if not run_ref:
                        return not_found(start_response)
                    status_payload = runtime_status_payload(run_ref, project=query_value(query, "project"))
                    return success_response(start_response, status_payload)
                if suffix.endswith("/runtime"):
                    run_ref = suffix.removesuffix("/runtime")
                    if not run_ref:
                        return not_found(start_response)
                    runtime = inspect_runtime(run_ref, project=query_value(query, "project"))
                    if raw_path.startswith("/v1/"):
                        runtime = {"kind": "run_runtime", **runtime}
                    return success_response(start_response, runtime)
                if suffix.endswith("/outputs"):
                    run_ref = suffix.removesuffix("/outputs")
                    if not run_ref:
                        return not_found(start_response)
                    metadata = inspect_run(run_ref, project=query_value(query, "project"))
                    outputs_payload = {"outputs": metadata.get("outputs", {})}
                    if raw_path.startswith("/v1/"):
                        outputs_payload["kind"] = "run_outputs"
                        outputs_payload["instance_id"] = run_ref
                    return success_response(start_response, outputs_payload)
                run_ref = suffix
                if not run_ref:
                    return not_found(start_response)
                metadata = inspect_run(run_ref, project=query_value(query, "project"))
                if raw_path.startswith("/v1/"):
                    metadata = {"kind": "run", **metadata}
                return success_response(start_response, metadata)

            if method == "POST" and raw_path == "/v1/runs:collect":
                payload = load_json_body(environ)
                run_ref = payload.get("run_ref")
                if not isinstance(run_ref, str) or not run_ref:
                    raise ProjectValidationError("Request field 'run_ref' is required")
                result = collect_run_outputs(
                    run_ref,
                    project=payload.get("project"),
                )
                result["kind"] = "run_collect"
                return success_response(start_response, result)

            if method == "POST" and path == "/resolve":
                payload = load_json_body(environ)
                return success_response(start_response, preview_resolution(payload))

            if method == "POST" and raw_path.startswith("/v1/templates/") and raw_path.endswith(":resolve"):
                template_ref = unquote(raw_path.removeprefix("/v1/templates/").removesuffix(":resolve"))
                if not template_ref:
                    return not_found(start_response)
                payload = load_json_body(environ)
                payload["template"] = template_ref
                return success_response(
                    start_response,
                    preview_resolution_v1_with_tokens(payload, resolve_tokens=resolve_tokens, subject=auth_subject),
                )

            if method == "POST" and raw_path.startswith("/v1/templates/") and raw_path.endswith(":run"):
                template_ref = unquote(raw_path.removeprefix("/v1/templates/").removesuffix(":run"))
                if not template_ref:
                    return not_found(start_response)
                payload = load_json_body(environ)
                resolve_token = payload.get("resolve_token")
                if resolve_token is not None:
                    if not isinstance(resolve_token, str) or not resolve_token:
                        raise ProjectValidationError("Request field 'resolve_token' must be a non-empty string")
                    if payload.get("confirm") is not True:
                        raise ProjectValidationError("Request field 'confirm' must be true when using a resolve token")
                    record = consume_resolve_token(
                        resolve_tokens,
                        token=resolve_token,
                        subject=auth_subject,
                        template_ref=template_ref,
                    )
                    result = run_template(
                        template_ref,
                        params=record.get("params"),
                        project=record.get("project"),
                        outdir=record.get("outdir"),
                        pack_refs=record.get("pack_refs"),
                        binding_ref=record.get("binding_ref"),
                    )
                    return success_response(start_response, result)
                result = run_template(
                    template_ref,
                    params=payload.get("params"),
                    project=payload.get("project"),
                    outdir=payload.get("outdir"),
                    pack_refs=payload.get("pack_refs"),
                    binding_ref=payload.get("binding_ref"),
                )
                return success_response(start_response, result)

            if method == "POST" and raw_path.startswith("/v1/templates/") and raw_path.endswith(":render"):
                template_ref = unquote(raw_path.removeprefix("/v1/templates/").removesuffix(":render"))
                if not template_ref:
                    return not_found(start_response)
                payload = load_json_body(environ)
                result = render_template(
                    template_ref,
                    params=payload.get("params"),
                    project=payload.get("project"),
                    outdir=payload.get("outdir"),
                    pack_refs=payload.get("pack_refs"),
                    binding_ref=payload.get("binding_ref"),
                )
                return success_response(start_response, result)

            if method == "POST" and raw_path.startswith("/v1/templates/") and raw_path.endswith(":test"):
                template_ref = unquote(raw_path.removeprefix("/v1/templates/").removesuffix(":test"))
                if not template_ref:
                    return not_found(start_response)
                payload = load_json_body(environ)
                result = test_template(
                    template_ref,
                    project=payload.get("project"),
                    outdir=payload.get("outdir"),
                    pack_refs=payload.get("pack_refs"),
                )
                return success_response(start_response, result)

            if method == "POST" and path == "/run":
                payload = load_json_body(environ)
                template = payload.get("template")
                if not isinstance(template, str) or not template:
                    raise ProjectValidationError("Request field 'template' is required")
                result = run_template(
                    template,
                    params=payload.get("params"),
                    project=payload.get("project"),
                    outdir=payload.get("outdir"),
                    pack_refs=payload.get("pack_refs"),
                    binding_ref=payload.get("binding_ref"),
                )
                return success_response(start_response, result)

            if method == "POST" and path == "/render":
                payload = load_json_body(environ)
                template = payload.get("template")
                if not isinstance(template, str) or not template:
                    raise ProjectValidationError("Request field 'template' is required")
                result = render_template(
                    template,
                    params=payload.get("params"),
                    project=payload.get("project"),
                    outdir=payload.get("outdir"),
                    pack_refs=payload.get("pack_refs"),
                    binding_ref=payload.get("binding_ref"),
                )
                return success_response(start_response, result)

            if method == "POST" and path == "/collect":
                payload = load_json_body(environ)
                run_ref = payload.get("run_ref")
                if not isinstance(run_ref, str) or not run_ref:
                    raise ProjectValidationError("Request field 'run_ref' is required")
                result = collect_run_outputs(
                    run_ref,
                    project=payload.get("project"),
                )
                return success_response(start_response, result)

            if method == "POST" and path == "/test":
                payload = load_json_body(environ)
                template = payload.get("template")
                if not isinstance(template, str) or not template:
                    raise ProjectValidationError("Request field 'template' is required")
                result = test_template(
                    template,
                    project=payload.get("project"),
                    outdir=payload.get("outdir"),
                    pack_refs=payload.get("pack_refs"),
                )
                return success_response(start_response, result)

            return not_found(start_response)
        except LinkarError as exc:
            return json_response(
                start_response,
                error_status(exc),
                {"ok": False, "error": {"code": exc.code, "message": str(exc)}},
            )

    return app


def serve(host: str = "127.0.0.1", port: int = 8000, *, api_tokens: dict[str, set[str]] | None = None) -> None:
    app = make_app(api_tokens=api_tokens)
    with make_server(host, port, app) as httpd:
        httpd.serve_forever()
