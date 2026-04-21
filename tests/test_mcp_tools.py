from __future__ import annotations

from pathlib import Path

import yaml

from linkar.core import init_project
from linkar.mcp_tools import (
    describe_template_tool,
    get_run_outputs_tool,
    get_run_runtime_tool,
    latest_project_run_tool,
    list_project_assets_tool,
    list_project_runs_tool,
    list_templates_tool,
    resolve_template_tool,
    run_template_tool,
)


ROOT = Path(__file__).resolve().parents[1]


def test_mcp_tools_cover_discovery_resolution_and_inspection(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init_project(project_dir)

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(ROOT / "examples" / "packs" / "basic")}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    templates = list_templates_tool(project=project_dir)
    assert any(item["id"] == "simple_echo" for item in templates["templates"])

    described = describe_template_tool(template="simple_echo", project=project_dir)
    assert described["id"] == "simple_echo"
    assert described["run"]["entry"] is None
    assert "greeting.txt" in described["run"]["command"]

    resolved = resolve_template_tool(
        template="simple_echo",
        project=project_dir,
        params={"name": "MCP"},
    )
    assert resolved["ready"] is True
    assert resolved["params"]["name"] == "MCP"

    result = run_template_tool(
        template="simple_echo",
        project=project_dir,
        params={"name": "MCP"},
    )
    assert Path(result["outdir"]).exists()

    runs = list_project_runs_tool(project=project_dir)
    assert runs["runs"][0]["instance_id"] == "simple_echo_001"

    latest = latest_project_run_tool(run_ref="simple_echo", project=project_dir)
    assert latest["run"]["instance_id"] == "simple_echo_001"

    outputs = get_run_outputs_tool(run_ref="simple_echo_001", project=project_dir)
    assert outputs["outputs"]["greeting_file"].endswith("results/greeting.txt")

    runtime = get_run_runtime_tool(run_ref="simple_echo_001", project=project_dir)
    assert runtime["success"] is True

    assets = list_project_assets_tool(project=project_dir)
    assert assets["assets"][0]["pack_ref"] == str(ROOT / "examples" / "packs" / "basic")
