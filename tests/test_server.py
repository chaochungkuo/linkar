from __future__ import annotations

import io
import json
from pathlib import Path

import yaml

from linkar.core import init_project
from linkar.server import make_app


ROOT = Path(__file__).resolve().parents[1]


def call_app(
    app,
    *,
    method: str,
    path: str,
    query: str = "",
    body: bytes = b"",
    content_type: str = "application/json",
) -> tuple[str, dict[str, str], dict]:
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
    chunks = app(environ, start_response)
    raw = b"".join(chunks)
    headers = dict(headers_holder)
    payload = json.loads(raw.decode("utf-8"))
    return status_holder[0], headers, payload


def test_server_health_endpoint() -> None:
    app = make_app()
    status, headers, payload = call_app(app, method="GET", path="/health")

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert payload == {"ok": True}


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
        path=f"/runs/{instance_id}",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert inspect_payload["data"]["template"] == "simple_echo"
    assert inspect_payload["data"]["params"]["name"] == "Server"

    status, _, outputs_payload = call_app(
        app,
        method="GET",
        path=f"/runs/{instance_id}/outputs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert outputs_payload["data"]["outputs"] == inspect_payload["data"]["outputs"]

    status, _, runtime_payload = call_app(
        app,
        method="GET",
        path=f"/runs/{instance_id}/runtime",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert runtime_payload["data"]["success"] is True

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

    status, _, methods_payload = call_app(
        app,
        method="GET",
        path="/methods",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert "simple_echo" in methods_payload["data"]["text"]


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
