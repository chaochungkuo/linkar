from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import yaml

from linkar.core import init_project
from linkar.server import make_app, parse_api_token_specs


ROOT = Path(__file__).resolve().parents[1]


def call_app(
    app,
    *,
    method: str,
    path: str,
    query: str = "",
    body: bytes = b"",
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> tuple[str, dict[str, str], dict | str]:
    status_holder: list[str] = []
    headers_holder: list[tuple[str, str]] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_holder.append(status)
        headers_holder.extend(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    }
    for key, value in (headers or {}).items():
        environ[key] = value
    chunks = app(environ, start_response)
    raw = b"".join(chunks)
    headers = dict(headers_holder)
    decoded = raw.decode("utf-8")
    if headers.get("Content-Type", "").startswith("application/json"):
        payload: dict | str = json.loads(decoded)
    else:
        payload = decoded
    return status_holder[0], headers, payload


def test_server_health_endpoint() -> None:
    app = make_app()
    status, headers, payload = call_app(app, method="GET", path="/health")

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert payload == {"ok": True}

    status, _, payload = call_app(app, method="GET", path="/v1/health")
    assert status == "200 OK"
    assert payload == {"ok": True}


def test_server_v1_root_and_aliases(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init_project(project_dir)

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(ROOT / "examples" / "packs" / "basic")}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    app = make_app()

    status, _, payload = call_app(app, method="GET", path="/v1")
    assert status == "200 OK"
    assert payload["data"]["kind"] == "service"
    assert payload["data"]["service"] == "linkar"
    assert payload["data"]["api_version"] == "v1"
    assert payload["data"]["linkar_version"]
    assert payload["data"]["identity"]["subject"] == "anonymous"
    assert payload["data"]["auth"]["enabled"] is False
    assert any(route["path"] == "/v1/schema" for route in payload["data"]["routes"])
    assert payload["data"]["features"]["resolve"] is True

    status, _, payload = call_app(app, method="GET", path="/v1/schema")
    assert status == "200 OK"
    assert payload["data"]["kind"] == "schema"
    assert payload["data"]["auth"]["enabled"] is False
    assert payload["data"]["conventions"]["collections"]["items_field"] == "items"
    assert any(route["path"] == "/v1/docs" for route in payload["data"]["routes"])
    assert any(route["path"] == "/v1/templates/{template_id}:resolve" for route in payload["data"]["routes"])

    status, headers, payload = call_app(app, method="GET", path="/v1/docs")
    assert status == "200 OK"
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert isinstance(payload, str)
    assert "Linkar Local API v1" in payload
    assert "/v1/schema" in payload

    status, _, payload = call_app(
        app,
        method="GET",
        path="/v1/projects/current",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert payload["data"]["kind"] == "project"
    assert payload["data"]["id"] == "project"
    assert payload["data"]["path"] == str(project_dir)
    assert payload["data"]["run_count"] == 0
    assert payload["data"]["packs"][0]["ref"] == str(ROOT / "examples" / "packs" / "basic")

    status, _, payload = call_app(
        app,
        method="GET",
        path="/v1/projects/current/runs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert payload["data"]["kind"] == "run_collection"
    assert payload["data"]["runs"] == []
    assert payload["data"]["items"] == []
    assert payload["data"]["count"] == 0

    status, _, payload = call_app(
        app,
        method="GET",
        path="/v1/projects/current/assets",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert payload["data"]["kind"] == "asset_collection"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"] == payload["data"]["assets"]
    assert payload["data"]["items"][0]["kind"] == "asset"
    assert payload["data"]["assets"][0]["pack_ref"] == str(ROOT / "examples" / "packs" / "basic")

    status, _, payload = call_app(
        app,
        method="GET",
        path="/v1/templates",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert payload["data"]["kind"] == "template_collection"
    assert payload["data"]["count"] >= 1
    assert payload["data"]["items"] == payload["data"]["templates"]
    assert all(item["kind"] == "template_summary" for item in payload["data"]["items"])
    assert any(item["id"] == "simple_echo" for item in payload["data"]["templates"])

    status, _, payload = call_app(
        app,
        method="GET",
        path="/v1/templates/simple_echo",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert payload["data"]["kind"] == "template"
    assert payload["data"]["id"] == "simple_echo"

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:resolve",
        body=json.dumps(
            {
                "project": str(project_dir),
                "params": {"name": "Versioned"},
            }
        ).encode("utf-8"),
    )
    assert status == "200 OK"
    assert payload["data"]["template"]["id"] == "simple_echo"
    assert payload["data"]["resolved_params"]["name"] == "Versioned"
    assert payload["data"]["expected_outputs"]["greeting_file"]["path"] == "greeting.txt"
    assert payload["data"]["confirmation"]["required"] is True


def test_server_optional_bearer_auth_enforces_roles() -> None:
    app = make_app(api_tokens={"reader-token": {"read"}, "resolver-token": {"read", "resolve"}})

    status, _, payload = call_app(app, method="GET", path="/v1")
    assert status == "401 Unauthorized"
    assert payload["error"]["code"] == "unauthorized"

    status, _, payload = call_app(
        app,
        method="GET",
        path="/v1",
        headers={"HTTP_AUTHORIZATION": "Bearer reader-token"},
    )
    assert status == "200 OK"
    assert payload["data"]["identity"]["roles"] == ["read"]
    assert payload["data"]["identity"]["auth_required"] is True
    assert payload["data"]["auth"]["enabled"] is True

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:resolve",
        body=json.dumps({"pack_refs": [str(ROOT / "examples" / "packs" / "basic")]}).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer reader-token"},
    )
    assert status == "403 Forbidden"
    assert payload["error"]["code"] == "forbidden"

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:resolve",
        body=json.dumps({"pack_refs": [str(ROOT / "examples" / "packs" / "basic")]}).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer resolver-token"},
    )
    assert status == "200 OK"
    assert payload["data"]["template"]["id"] == "simple_echo"
    assert payload["data"]["ready"] is False
    assert payload["data"]["unresolved_params"][0]["name"] == "name"


def test_parse_api_token_specs_supports_default_and_explicit_roles() -> None:
    parsed = parse_api_token_specs(["reader-token:read", "full-token"])

    assert parsed["reader-token"] == {"read"}
    assert parsed["full-token"] == {"read", "resolve", "execute"}


def test_server_v1_template_run_and_render_routes() -> None:
    app = make_app(api_tokens={"executor-token": {"read", "resolve", "execute"}})

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:run",
        body=json.dumps(
            {
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "Runner"},
            }
        ).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer executor-token"},
    )
    assert status == "200 OK"
    outdir = Path(payload["data"]["outdir"])
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, Runner"

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:render",
        body=json.dumps(
            {
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "Renderer"},
            }
        ).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer executor-token"},
    )
    assert status == "200 OK"
    outdir = Path(payload["data"]["outdir"])
    assert (outdir / "run.sh").exists()
    assert not (outdir / "results" / "greeting.txt").exists()

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:test",
        body=json.dumps(
            {
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
            }
        ).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer executor-token"},
    )
    assert status == "200 OK"
    assert payload["data"]["template"] == "simple_echo"
    assert Path(payload["data"]["runtime"]).exists()


def test_server_v1_resolve_token_can_be_confirmed_for_run() -> None:
    app = make_app(api_tokens={"agent-token": {"read", "resolve", "execute"}})

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:resolve",
        body=json.dumps(
            {
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "TokenRunner"},
            }
        ).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer agent-token"},
    )
    assert status == "200 OK"
    resolve_token = payload["data"]["resolve_token"]
    assert isinstance(resolve_token, str) and resolve_token

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:run",
        body=json.dumps({"resolve_token": resolve_token}).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer agent-token"},
    )
    assert status == "400 Bad Request"
    assert payload["error"]["code"] == "invalid_project"
    assert "confirm" in payload["error"]["message"]

    status, _, payload = call_app(
        app,
        method="POST",
        path="/v1/templates/simple_echo:run",
        body=json.dumps({"resolve_token": resolve_token, "confirm": True}).encode("utf-8"),
        headers={"HTTP_AUTHORIZATION": "Bearer agent-token"},
    )
    assert status == "200 OK"
    outdir = Path(payload["data"]["outdir"])
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, TokenRunner"


def test_server_run_and_inspection_endpoints(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init_project(project_dir)

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(ROOT / "examples" / "packs" / "basic")}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    app = make_app()
    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=json.dumps(
            {
                "template": "simple_echo",
                "project": str(project_dir),
                "params": {"name": "Server"},
            }
        ).encode("utf-8"),
    )

    assert status == "200 OK"
    result = payload["data"]
    outdir = Path(result["outdir"])
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, Server"

    status, _, runs_payload = call_app(
        app,
        method="GET",
        path="/projects/runs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert len(runs_payload["data"]["runs"]) == 1
    instance_id = runs_payload["data"]["runs"][0]["instance_id"]

    status, _, inspect_payload = call_app(
        app,
        method="GET",
        path=f"/v1/runs/{instance_id}",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert inspect_payload["data"]["kind"] == "run"
    assert inspect_payload["data"]["template"] == "simple_echo"
    assert inspect_payload["data"]["params"]["name"] == "Server"

    status, _, outputs_payload = call_app(
        app,
        method="GET",
        path=f"/v1/runs/{instance_id}/outputs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert outputs_payload["data"]["kind"] == "run_outputs"
    assert outputs_payload["data"]["outputs"] == inspect_payload["data"]["outputs"]

    status, _, runtime_payload = call_app(
        app,
        method="GET",
        path=f"/v1/runs/{instance_id}/runtime",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert runtime_payload["data"]["kind"] == "run_runtime"
    assert runtime_payload["data"]["success"] is True

    status, _, status_payload = call_app(
        app,
        method="GET",
        path=f"/v1/runs/{instance_id}/status",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert status_payload["data"]["kind"] == "run_status"
    assert status_payload["data"]["instance_id"] == instance_id
    assert status_payload["data"]["status"] == "succeeded"
    assert status_payload["data"]["success"] is True
    assert status_payload["data"]["finished_at"] is not None

    status, _, outputs_payload = call_app(
        app,
        method="GET",
        path=f"/v1/runs/{instance_id}/outputs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert outputs_payload["data"]["instance_id"] == instance_id
    assert outputs_payload["data"]["outputs"] == inspect_payload["data"]["outputs"]

    status, _, project_runs_payload = call_app(
        app,
        method="GET",
        path="/v1/projects/current/runs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert project_runs_payload["data"]["items"][0]["kind"] == "run_summary"
    assert project_runs_payload["data"]["items"][0]["template"] == "simple_echo"

    status, _, latest_payload = call_app(
        app,
        method="GET",
        path="/v1/projects/current/runs/latest",
        query=f"project={project_dir}&run_ref=simple_echo",
    )
    assert status == "200 OK"
    assert latest_payload["data"]["kind"] == "run_summary"
    assert latest_payload["data"]["instance_id"] == instance_id

    status, _, templates_payload = call_app(
        app,
        method="GET",
        path="/templates",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert any(item["id"] == "simple_echo" for item in templates_payload["data"]["templates"])

    status, _, template_payload = call_app(
        app,
        method="GET",
        path="/templates/simple_echo",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert template_payload["data"]["id"] == "simple_echo"
    assert template_payload["data"]["run"]["entry"] is None
    assert "greeting.txt" in template_payload["data"]["run"]["command"]

    status, _, assets_payload = call_app(
        app,
        method="GET",
        path="/projects/assets",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert assets_payload["data"]["assets"][0]["pack_ref"] == str(ROOT / "examples" / "packs" / "basic")

    status, _, collect_payload = call_app(
        app,
        method="POST",
        path="/v1/runs:collect",
        body=json.dumps({"run_ref": instance_id, "project": str(project_dir)}).encode("utf-8"),
    )
    assert status == "200 OK"
    assert collect_payload["data"]["kind"] == "run_collect"
    assert collect_payload["data"]["project_updated"] is True

def test_server_resolve_and_test_endpoints(tmp_path: Path) -> None:
    app = make_app()

    status, _, resolve_payload = call_app(
        app,
        method="POST",
        path="/resolve",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "Resolver"},
            }
        ).encode("utf-8"),
    )
    assert status == "200 OK"
    assert resolve_payload["data"]["ready"] is True
    assert resolve_payload["data"]["params"]["name"] == "Resolver"
    assert resolve_payload["data"]["missing_required"] == []
    assert resolve_payload["data"]["warnings"] == []

    status, _, missing_payload = call_app(
        app,
        method="POST",
        path="/resolve",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
            }
        ).encode("utf-8"),
    )
    assert status == "200 OK"
    assert missing_payload["data"]["ready"] is False
    assert missing_payload["data"]["missing_required"] == ["name"]

    status, _, test_payload = call_app(
        app,
        method="POST",
        path="/test",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
            }
        ).encode("utf-8"),
    )
    assert status == "200 OK"
    assert test_payload["data"]["template"] == "simple_echo"
    assert Path(test_payload["data"]["runtime"]).exists()


def test_server_returns_typed_error_payloads(tmp_path: Path) -> None:
    app = make_app()

    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=b"{bad json",
    )
    assert status == "400 Bad Request"
    assert payload["error"]["code"] == "invalid_project"

    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=json.dumps({"project": str(tmp_path)}).encode("utf-8"),
    )
    assert status == "400 Bad Request"
    assert payload["error"]["code"] == "invalid_project"

    status, _, payload = call_app(
        app,
        method="GET",
        path="/templates",
        query="pack=/definitely/missing",
    )
    assert status == "404 Not Found"
    assert payload["error"]["code"] == "asset_resolution_error"


def test_server_run_error_payload_includes_actionable_missing_param_message(tmp_path: Path) -> None:
    app = make_app()

    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
            }
        ).encode("utf-8"),
    )

    assert status == "400 Bad Request"
    assert payload["error"]["code"] == "param_resolution_error"
    assert "Missing required param: name" in payload["error"]["message"]
    assert "--name VALUE" in payload["error"]["message"]


def test_server_run_endpoint_supports_ephemeral_mode() -> None:
    app = make_app()
    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "EphemeralServer"},
            }
        ).encode("utf-8"),
    )

    assert status == "200 OK"
    outdir = Path(payload["data"]["outdir"])
    assert outdir.parent.name == "runs"
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, EphemeralServer"


def test_server_render_endpoint_stages_without_execution() -> None:
    app = make_app()
    status, _, payload = call_app(
        app,
        method="POST",
        path="/render",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "RenderedServer"},
            }
        ).encode("utf-8"),
    )

    assert status == "200 OK"
    outdir = Path(payload["data"]["outdir"])
    assert outdir.parent.name == "runs"
    assert (outdir / "run.sh").exists()
    assert not (outdir / "linkar_template.yaml").exists()
    assert not (outdir / "results" / "greeting.txt").exists()


def test_server_collect_endpoint_updates_outputs_after_manual_run() -> None:
    app = make_app()
    status, _, payload = call_app(
        app,
        method="POST",
        path="/render",
        body=json.dumps(
            {
                "template": "simple_echo",
                "pack_refs": [str(ROOT / "examples" / "packs" / "basic")],
                "params": {"name": "CollectedServer"},
            }
        ).encode("utf-8"),
    )
    assert status == "200 OK"
    outdir = Path(payload["data"]["outdir"])
    subprocess.run([str(outdir / "run.sh")], cwd=outdir, check=True)

    status, _, payload = call_app(
        app,
        method="POST",
        path="/collect",
        body=json.dumps(
            {
                "run_ref": str(outdir),
            }
        ).encode("utf-8"),
    )
    assert status == "200 OK"
    assert payload["data"]["outputs"]["greeting_file"] == str((outdir / "results" / "greeting.txt").resolve())
