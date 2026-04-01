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
    outdir = Path(payload["outdir"])
    assert (outdir / "greeting.txt").read_text().strip() == "Hello, Server"

    status, _, runs_payload = call_app(
        app,
        method="GET",
        path="/projects/runs",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert len(runs_payload["runs"]) == 1
    instance_id = runs_payload["runs"][0]["instance_id"]

    status, _, inspect_payload = call_app(
        app,
        method="GET",
        path=f"/runs/{instance_id}",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert inspect_payload["template"] == "simple_echo"
    assert inspect_payload["params"]["name"] == "Server"

    status, _, templates_payload = call_app(
        app,
        method="GET",
        path="/templates",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert any(item["id"] == "simple_echo" for item in templates_payload["templates"])

    status, _, assets_payload = call_app(
        app,
        method="GET",
        path="/projects/assets",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert assets_payload["assets"][0]["pack_ref"] == str(ROOT / "examples" / "packs" / "basic")

    status, _, methods_payload = call_app(
        app,
        method="GET",
        path="/methods",
        query=f"project={project_dir}",
    )
    assert status == "200 OK"
    assert "simple_echo" in methods_payload["text"]


def test_server_returns_typed_error_payloads(tmp_path: Path) -> None:
    app = make_app()

    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=b"{bad json",
    )
    assert status == "400 Bad Request"
    assert payload["error"] == "invalid_project"

    status, _, payload = call_app(
        app,
        method="POST",
        path="/run",
        body=json.dumps({"project": str(tmp_path)}).encode("utf-8"),
    )
    assert status == "400 Bad Request"
    assert payload["error"] == "invalid_project"

    status, _, payload = call_app(
        app,
        method="GET",
        path="/templates",
        query="pack=/definitely/missing",
    )
    assert status == "404 Not Found"
    assert payload["error"] == "asset_resolution_error"


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
    assert payload["error"] == "param_resolution_error"
    assert "Missing required param: name" in payload["message"]
    assert "--name VALUE" in payload["message"]


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
    outdir = Path(payload["outdir"])
    assert outdir.parent.name == "runs"
    assert (outdir / "greeting.txt").read_text().strip() == "Hello, EphemeralServer"
