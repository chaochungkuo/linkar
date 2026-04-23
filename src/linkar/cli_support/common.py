from __future__ import annotations

import sys
from functools import update_wrapper
from pathlib import Path
from typing import Any

try:
    import rich_click as click
except ImportError:
    import click

from linkar.assets import resolve_asset_refs
from linkar.core import (
    discover_project,
    load_project,
    load_template,
    preferred_pack_ref_for_assets,
    render_template,
    run_template,
    unique_assets,
)
from linkar.errors import LinkarError, ParameterResolutionError, ProjectValidationError
from linkar.runtime.templates import combined_configured_pack_entries
from linkar.ui import CliUI


def parse_key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise click.BadParameter("Expected KEY=VALUE")
    key, raw = value.split("=", 1)
    if not key:
        raise click.BadParameter("Parameter key must not be empty")
    return key, raw


def params_from_pairs(pairs: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {key: value for key, value in pairs}


def load_project_or_discover(project: str | None):
    if project:
        return load_project(project)
    return discover_project()


def load_template_for_cli(
    template_ref: str,
    *,
    project: str | None = None,
    pack_refs: list[str] | None = None,
):
    project_obj = load_project_or_discover(project)
    configured_entries, active_entry = combined_configured_pack_entries(project_obj)
    explicit_pack_assets = resolve_asset_refs(pack_refs)
    pack_assets = unique_assets(explicit_pack_assets + [entry.asset for entry in configured_entries])
    preferred_pack_ref = preferred_pack_ref_for_assets(explicit_pack_assets, active_entry)
    template = load_template(
        template_ref,
        pack_assets=pack_assets,
        preferred_pack_ref=preferred_pack_ref,
    )
    return template, project_obj


def click_type_for_param(param_type: str) -> click.ParamType:
    if param_type == "int":
        return click.INT
    if param_type == "float":
        return click.FLOAT
    if param_type == "bool":
        return click.BOOL
    if param_type == "path":
        return click.Path(path_type=str, dir_okay=True, file_okay=True)
    return click.STRING


def help_for_param(name: str, spec: dict[str, Any]) -> str:
    pieces = [f"type: {spec.get('type', 'str')}"]
    if spec.get("required"):
        pieces.append("required when not resolved elsewhere")
    if "default" in spec:
        pieces.append(f"default: {spec['default']}")
    summary = f"{name} ({'; '.join(pieces)})"
    description = str(spec.get("description") or "").strip()
    if not description:
        return summary
    return f"{summary}\n{description}"


def prompt_for_param(name: str, spec: dict[str, Any]) -> Any:
    param_type = spec.get("type", "str")
    label = name.replace("_", " ")
    return click.prompt(label, type=click_type_for_param(param_type))


def can_prompt() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def execute_with_optional_prompts(
    template_ref: str,
    *,
    params: dict[str, Any],
    project: str | None,
    outdir: str | None,
    pack_refs: list[str] | None,
    binding_ref: str | None,
    prompt_missing: bool,
    action: str = "run",
    verbose: bool = False,
    refresh: bool = False,
):
    template, _ = load_template_for_cli(template_ref, project=project, pack_refs=pack_refs)
    effective_verbose = verbose or template.run_verbose_by_default
    pending_params = dict(params)
    prompted: set[str] = set()
    execute = render_template if action == "render" else run_template

    while True:
        try:
            execute_kwargs = {
                "params": pending_params,
                "project": project,
                "outdir": outdir,
                "pack_refs": pack_refs,
                "binding_ref": binding_ref,
            }
            if action == "run":
                execute_kwargs["verbose"] = effective_verbose
                execute_kwargs["refresh"] = refresh
            return execute(
                template_ref,
                **execute_kwargs,
            )
        except ParameterResolutionError as exc:
            prefix = "Missing required param: "
            if not prompt_missing or not can_prompt() or not str(exc).startswith(prefix):
                raise
            missing_key = str(exc)[len(prefix) :]
            if missing_key in prompted or missing_key not in template.params:
                raise
            pending_params[missing_key] = prompt_for_param(missing_key, template.params[missing_key])
            prompted.add(missing_key)


def run_with_optional_prompts(
    template_ref: str,
    *,
    params: dict[str, Any],
    project: str | None,
    outdir: str | None,
    pack_refs: list[str] | None,
    binding_ref: str | None,
    prompt_missing: bool,
    verbose: bool = False,
    refresh: bool = False,
):
    return execute_with_optional_prompts(
        template_ref,
        params=params,
        project=project,
        outdir=outdir,
        pack_refs=pack_refs,
        binding_ref=binding_ref,
        prompt_missing=prompt_missing,
        action="run",
        verbose=verbose,
        refresh=refresh,
    )


def should_stream_output_by_default(
    template_ref: str,
    *,
    project: str | None,
    pack_refs: list[str] | None,
) -> bool:
    template, _ = load_template_for_cli(template_ref, project=project, pack_refs=pack_refs)
    return template.run_verbose_by_default


def shell_complete_template_ref(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[click.shell_completion.CompletionItem]:
    from linkar.core import list_templates

    project = ctx.params.get("project")
    pack_refs = ctx.params.get("pack") or []
    items: list[click.shell_completion.CompletionItem] = []
    try:
        for template in list_templates(pack_refs=pack_refs, project=project):
            template_id = template["id"]
            if template_id.startswith(incomplete):
                items.append(click.shell_completion.CompletionItem(template_id))
    except LinkarError:
        pass

    search_root = Path(incomplete or ".")
    parent = search_root.parent if incomplete else Path(".")
    prefix = search_root.name
    try:
        for child in parent.iterdir():
            if not child.name.startswith(prefix):
                continue
            if child.is_dir():
                items.append(click.shell_completion.CompletionItem(str(child)))
    except OSError:
        pass
    return items


def shell_complete_filesystem_ref(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[click.shell_completion.CompletionItem]:
    search_root = Path(incomplete or ".")
    parent = search_root.parent if incomplete else Path(".")
    prefix = search_root.name
    items: list[click.shell_completion.CompletionItem] = []
    try:
        for child in parent.iterdir():
            if child.name.startswith(prefix):
                items.append(click.shell_completion.CompletionItem(str(child)))
    except OSError:
        pass
    return items


def handle_linkar_errors(fn):
    def wrapper(*args, **kwargs):
        ui = CliUI()
        try:
            return fn(*args, ui=ui, **kwargs)
        except LinkarError as exc:
            ui.print_error(str(exc))
            raise click.exceptions.Exit(1) from exc

    return update_wrapper(wrapper, fn)


def resolve_project_init_target(path: str | None, name: str | None) -> tuple[str, str | None]:
    if path and name:
        raise ProjectValidationError("Use either PATH or --name, not both")
    if name:
        return name, name
    if path:
        return path, None
    return ".", None
