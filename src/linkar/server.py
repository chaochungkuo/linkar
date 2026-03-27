from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from urllib.parse import parse_qs, unquote

from wsgiref.simple_server import make_server

from linkar.core import (
    generate_methods,
    inspect_run,
    list_project_runs,
    list_templates,
    resolve_project_assets,
    run_template,
)
from linkar.errors import (
    AssetResolutionError,
    ExecutionError,
    LinkarError,
    ParameterResolutionError,
    ProjectValidationError,
    TemplateValidationError,
)

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
    return json_response(start_response, "404 Not Found", {"error": "not_found"})


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
                return json_response(start_response, "200 OK", {"templates": templates})

            if method == "GET" and path == "/projects/runs":
                runs = list_project_runs(project=query_value(query, "project"))
                return json_response(start_response, "200 OK", {"runs": runs})

            if method == "GET" and path == "/projects/assets":
                assets = resolve_project_assets(project=query_value(query, "project"))
                return json_response(start_response, "200 OK", {"assets": assets})

            if method == "GET" and path.startswith("/runs/"):
                run_ref = unquote(path.removeprefix("/runs/"))
                if not run_ref:
                    return not_found(start_response)
                metadata = inspect_run(run_ref, project=query_value(query, "project"))
                return json_response(start_response, "200 OK", metadata)

            if method == "GET" and path == "/methods":
                text = generate_methods(project=query_value(query, "project"))
                return json_response(start_response, "200 OK", {"text": text})

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
                return json_response(start_response, "200 OK", result)

            return not_found(start_response)
        except LinkarError as exc:
            return json_response(
                start_response,
                error_status(exc),
                {"error": exc.code, "message": str(exc)},
            )

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = make_app()
    with make_server(host, port, app) as httpd:
        httpd.serve_forever()
