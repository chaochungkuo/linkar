from __future__ import annotations

from typing import Any

from linkar.mcp_tools import (
    describe_template_tool,
    generate_methods_tool,
    get_run_outputs_tool,
    get_run_runtime_tool,
    inspect_run_tool,
    list_project_assets_tool,
    list_project_runs_tool,
    list_templates_tool,
    resolve_template_tool,
    run_template_tool,
    test_template_tool,
)


def _require_mcp() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised through CLI/runtime use
        raise RuntimeError(
            "MCP support requires the optional dependency 'mcp'. Install it with "
            "`pip install 'linkar[mcp]'`, `pipx install 'linkar[mcp]'`, or add the extra in your environment."
        ) from exc
    return FastMCP


def build_server() -> Any:
    FastMCP = _require_mcp()
    mcp = FastMCP("Linkar")

    @mcp.tool(description="List templates available from explicit pack refs, the current project, and global config.")
    def linkar_list_templates(
        project: str | None = None,
        pack_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        return list_templates_tool(project=project, pack_refs=pack_refs)

    @mcp.tool(description="Describe one template contract, including params, outputs, and runtime entrypoint.")
    def linkar_describe_template(
        template: str,
        project: str | None = None,
        pack_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        return describe_template_tool(template=template, project=project, pack_refs=pack_refs)

    @mcp.tool(description="Resolve a template's params through explicit values, bindings, project outputs, and defaults without executing it.")
    def linkar_resolve(
        template: str,
        params: dict[str, Any] | None = None,
        project: str | None = None,
        pack_refs: list[str] | None = None,
        binding_ref: str | None = None,
    ) -> dict[str, Any]:
        return resolve_template_tool(
            template=template,
            params=params,
            project=project,
            pack_refs=pack_refs,
            binding_ref=binding_ref,
        )

    @mcp.tool(description="Run a template and return the recorded run artifact paths and metadata.")
    def linkar_run(
        template: str,
        params: dict[str, Any] | None = None,
        project: str | None = None,
        outdir: str | None = None,
        pack_refs: list[str] | None = None,
        binding_ref: str | None = None,
    ) -> dict[str, Any]:
        return run_template_tool(
            template=template,
            params=params,
            project=project,
            outdir=outdir,
            pack_refs=pack_refs,
            binding_ref=binding_ref,
        )

    @mcp.tool(description="Run a template's local test entrypoint through Linkar.")
    def linkar_test(
        template: str,
        project: str | None = None,
        outdir: str | None = None,
        pack_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        return test_template_tool(
            template=template,
            project=project,
            outdir=outdir,
            pack_refs=pack_refs,
        )

    @mcp.tool(description="List recorded runs from the current or selected project.")
    def linkar_list_project_runs(project: str | None = None) -> dict[str, Any]:
        return list_project_runs_tool(project=project)

    @mcp.tool(description="List packs configured on the current or selected project.")
    def linkar_list_project_assets(project: str | None = None) -> dict[str, Any]:
        return list_project_assets_tool(project=project)

    @mcp.tool(description="Inspect the full metadata for one recorded run by instance id or path.")
    def linkar_inspect_run(run_ref: str, project: str | None = None) -> dict[str, Any]:
        return inspect_run_tool(run_ref=run_ref, project=project)

    @mcp.tool(description="Read only the outputs for one recorded run.")
    def linkar_get_run_outputs(run_ref: str, project: str | None = None) -> dict[str, Any]:
        return get_run_outputs_tool(run_ref=run_ref, project=project)

    @mcp.tool(description="Read only the runtime diagnostics for one recorded run.")
    def linkar_get_run_runtime(run_ref: str, project: str | None = None) -> dict[str, Any]:
        return get_run_runtime_tool(run_ref=run_ref, project=project)

    @mcp.tool(description="Generate short methods text from recorded runs in the current or selected project.")
    def linkar_generate_methods(project: str | None = None) -> dict[str, Any]:
        return generate_methods_tool(project=project)

    return mcp


def main() -> None:
    server = build_server()
    server.run()
