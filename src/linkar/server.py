from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from urllib.parse import parse_qs, unquote

from wsgiref.simple_server import make_server

from linkar.assets import resolve_asset_refs
from linkar.core import (
    collect_run_outputs,
    describe_template,
    generate_methods,
    inspect_run,
    inspect_runtime,
    list_project_runs,
    list_templates,
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


def error_status(exc: LinkarError) -> str:
    if isinstance(exc, (ProjectValidationError, TemplateValidationError, ParameterResolutionError)):
        return "400 Bad Request"
    if isinstance(exc, AssetResolutionError):
        return "404 Not Found"
    if isinstance(exc, ExecutionError):
        return "422 Unprocessable Entity"
    return "500 Internal Server Error"


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
        "template": template.id,
        "params": params,
        "param_provenance": provenance,
        "missing_required": missing_required,
        "warnings": warnings,
        "ready": not missing_required,
    }


def make_app() -> WSGIApp:
    def app(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "")
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)

        try:
            if method == "GET" and path == "/health":
                return json_response(start_response, "200 OK", {"ok": True})

            if method == "GET" and path == "/templates":
                templates = list_templates(
                    pack_refs=query_values(query, "pack"),
                    project=query_value(query, "project"),
                )
                return success_response(start_response, {"templates": templates})

            if method == "GET" and path.startswith("/templates/"):
                template_ref = unquote(path.removeprefix("/templates/"))
                if not template_ref:
                    return not_found(start_response)
                template = describe_template(
                    template_ref,
                    pack_refs=query_values(query, "pack"),
                    project=query_value(query, "project"),
                )
                return success_response(start_response, template)

            if method == "GET" and path == "/projects/runs":
                runs = list_project_runs(project=query_value(query, "project"))
                return success_response(start_response, {"runs": runs})

            if method == "GET" and path == "/projects/assets":
                assets = resolve_project_assets(project=query_value(query, "project"))
                return success_response(start_response, {"assets": assets})

            if method == "GET" and path.startswith("/runs/"):
                suffix = unquote(path.removeprefix("/runs/"))
                if suffix.endswith("/runtime"):
                    run_ref = suffix.removesuffix("/runtime")
                    if not run_ref:
                        return not_found(start_response)
                    runtime = inspect_runtime(run_ref, project=query_value(query, "project"))
                    return success_response(start_response, runtime)
                if suffix.endswith("/outputs"):
                    run_ref = suffix.removesuffix("/outputs")
                    if not run_ref:
                        return not_found(start_response)
                    metadata = inspect_run(run_ref, project=query_value(query, "project"))
                    return success_response(start_response, {"outputs": metadata.get("outputs", {})})
                run_ref = suffix
                if not run_ref:
                    return not_found(start_response)
                metadata = inspect_run(run_ref, project=query_value(query, "project"))
                return success_response(start_response, metadata)

            if method == "GET" and path == "/methods":
                text = generate_methods(project=query_value(query, "project"))
                return success_response(start_response, {"text": text})

            if method == "POST" and path == "/resolve":
                payload = load_json_body(environ)
                return success_response(start_response, preview_resolution(payload))

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


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = make_app()
    with make_server(host, port, app) as httpd:
        httpd.serve_forever()
