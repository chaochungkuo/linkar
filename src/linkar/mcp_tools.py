from __future__ import annotations

from pathlib import Path
from typing import Any

from linkar.core import (
    collect_run_outputs,
    describe_template,
    inspect_run,
    inspect_runtime,
    list_project_runs,
    list_templates,
    latest_project_run,
    render_template,
    resolve_project_assets,
    run_template,
    test_template,
)
from linkar.server import preview_resolution


def list_templates_tool(
    *,
    project: str | Path | None = None,
    pack_refs: list[str | Path] | None = None,
) -> dict[str, Any]:
    return {"templates": list_templates(project=project, pack_refs=pack_refs)}


def describe_template_tool(
    *,
    template: str,
    project: str | Path | None = None,
    pack_refs: list[str | Path] | None = None,
) -> dict[str, Any]:
    return describe_template(template, project=project, pack_refs=pack_refs)


def resolve_template_tool(
    *,
    template: str,
    params: dict[str, Any] | None = None,
    project: str | Path | None = None,
    pack_refs: list[str | Path] | None = None,
    binding_ref: str | Path | None = None,
) -> dict[str, Any]:
    return preview_resolution(
        {
            "template": template,
            "params": params or {},
            "project": str(project) if isinstance(project, Path) else project,
            "pack_refs": [str(ref) for ref in pack_refs] if pack_refs else None,
            "binding_ref": str(binding_ref) if isinstance(binding_ref, Path) else binding_ref,
        }
    )


def run_template_tool(
    *,
    template: str,
    params: dict[str, Any] | None = None,
    project: str | Path | None = None,
    outdir: str | Path | None = None,
    pack_refs: list[str | Path] | None = None,
    binding_ref: str | Path | None = None,
) -> dict[str, Any]:
    return run_template(
        template,
        params=params,
        project=project,
        outdir=outdir,
        pack_refs=pack_refs,
        binding_ref=binding_ref,
    )


def render_template_tool(
    *,
    template: str,
    params: dict[str, Any] | None = None,
    project: str | Path | None = None,
    outdir: str | Path | None = None,
    pack_refs: list[str | Path] | None = None,
    binding_ref: str | Path | None = None,
) -> dict[str, Any]:
    return render_template(
        template,
        params=params,
        project=project,
        outdir=outdir,
        pack_refs=pack_refs,
        binding_ref=binding_ref,
    )


def collect_run_outputs_tool(
    *,
    run_ref: str | Path,
    project: str | Path | None = None,
) -> dict[str, Any]:
    return collect_run_outputs(run_ref, project=project)


def test_template_tool(
    *,
    template: str,
    project: str | Path | None = None,
    outdir: str | Path | None = None,
    pack_refs: list[str | Path] | None = None,
) -> dict[str, Any]:
    return test_template(
        template,
        project=project,
        outdir=outdir,
        pack_refs=pack_refs,
    )


def list_project_runs_tool(*, project: str | Path | None = None) -> dict[str, Any]:
    return {"runs": list_project_runs(project=project)}


def latest_project_run_tool(*, run_ref: str | Path, project: str | Path | None = None) -> dict[str, Any]:
    return {"run": latest_project_run(run_ref, project=project)}


def list_project_assets_tool(*, project: str | Path | None = None) -> dict[str, Any]:
    return {"assets": resolve_project_assets(project=project)}


def inspect_run_tool(*, run_ref: str | Path, project: str | Path | None = None) -> dict[str, Any]:
    return inspect_run(run_ref, project=project)


def get_run_outputs_tool(*, run_ref: str | Path, project: str | Path | None = None) -> dict[str, Any]:
    metadata = inspect_run(run_ref, project=project)
    return {"outputs": metadata.get("outputs", {})}


def get_run_runtime_tool(*, run_ref: str | Path, project: str | Path | None = None) -> dict[str, Any]:
    return inspect_runtime(run_ref, project=project)
