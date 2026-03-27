from __future__ import annotations

import sys
from collections import defaultdict
from functools import update_wrapper
from pathlib import Path
from typing import Any

try:
    import rich_click as click
except ImportError:
    import click

from linkar import __version__
from linkar.assets import resolve_asset_refs
from linkar.core import (
    discover_project,
    generate_methods,
    init_project,
    inspect_run,
    list_project_runs,
    list_templates,
    load_project,
    load_template,
    project_pack_entries,
    run_template,
)
from linkar.errors import LinkarError, ParameterResolutionError, ProjectValidationError
from linkar.server import serve
from linkar.ui import CliUI

if hasattr(click, "rich_click"):
    click.rich_click.STYLE_OPTION = "bold cyan"
    click.rich_click.STYLE_SWITCH = "bold bright_cyan"
    click.rich_click.STYLE_COMMAND = "bold green"
    click.rich_click.STYLE_ARGUMENT = "bold yellow"
    click.rich_click.STYLE_METAVAR = "bold magenta"
    click.rich_click.STYLE_USAGE = "bold white"
    click.rich_click.STYLE_USAGE_COMMAND = "bold cyan"
    click.rich_click.STYLE_HELPTEXT = ""
    click.rich_click.STYLE_OPTION_HELP = ""
    click.rich_click.STYLE_OPTION_DEFAULT = "dim"
    click.rich_click.STYLE_REQUIRED_SHORT = "bold red"
    click.rich_click.ERRORS_SUGGESTION = "Use [bold cyan]-h[/bold cyan] or [bold cyan]--help[/bold cyan] for more details."
    click.rich_click.FOOTER_TEXT = (
        "Examples:\n"
        "  linkar project init --name study\n"
        "  linkar run raw hello --pack ./examples/packs/basic --param name=Linkar\n"
        "  linkar run hello --name Linkar\n\n"
        "Linkar keeps the CLI thin over the core runtime semantics."
    )


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
    pack_assets = resolve_asset_refs(pack_refs) + [
        entry.asset for entry in project_pack_entries(project_obj)
    ]
    template = load_template(template_ref, pack_assets=pack_assets)
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
    return f"{name} ({'; '.join(pieces)})"


def prompt_for_param(name: str, spec: dict[str, Any]) -> Any:
    param_type = spec.get("type", "str")
    label = name.replace("_", " ")
    return click.prompt(label, type=click_type_for_param(param_type))


def can_prompt() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_with_optional_prompts(
    template_ref: str,
    *,
    params: dict[str, Any],
    project: str | None,
    outdir: str | None,
    pack_refs: list[str] | None,
    binding_ref: str | None,
    prompt_missing: bool,
):
    template, _ = load_template_for_cli(template_ref, project=project, pack_refs=pack_refs)
    pending_params = dict(params)
    prompted: set[str] = set()

    while True:
        try:
            return run_template(
                template_ref,
                params=pending_params,
                project=project,
                outdir=outdir,
                pack_refs=pack_refs,
                binding_ref=binding_ref,
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


def shell_complete_template_ref(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
) -> list[click.shell_completion.CompletionItem]:
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


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(__version__, prog_name="linkar")
@click.pass_context
def app(ctx: click.Context) -> None:
    """Run reusable computational templates with transparent project state and provenance."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


@app.group("project")
def project_group() -> None:
    """Create a Linkar project or inspect run records stored in project.yaml."""


@project_group.command("init")
@click.argument("path", required=False)
@click.option(
    "--name",
    metavar="PROJECT_NAME",
    help="Create a new directory with this name and use it as the project id unless --id is set.",
)
@click.option(
    "--id",
    "project_id",
    metavar="PROJECT_ID",
    help="Project identifier to write into project.yaml. Defaults to the directory name.",
)
@handle_linkar_errors
def project_init(path: str | None, name: str | None, project_id: str | None, ui: CliUI) -> None:
    """Create project.yaml in the target directory. Use --name to create a new directory automatically."""
    target_path, implied_id = resolve_project_init_target(path, name)
    project_path = init_project(target_path, project_id=project_id or implied_id)
    resolved_id = project_id or implied_id or Path(target_path).resolve().name
    ui.print_project_created(project_path, resolved_id)


@project_group.command("runs")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
)
@handle_linkar_errors
def project_runs(project: str | None, ui: CliUI) -> None:
    """Show template instances recorded in project.yaml."""
    ui.print_runs(list_project_runs(project=project))


def template_command_callback(template_id: str, template_path: str):
    template_spec = load_template(template_path)

    @handle_linkar_errors
    def callback(
        project: str | None,
        binding: str | None,
        outdir: str | None,
        prompt_missing: bool,
        param: tuple[tuple[str, str], ...],
        ui: CliUI,
        **template_values: Any,
    ) -> None:
        params = {key: value for key, value in template_values.items() if value is not None}
        params.update(params_from_pairs(param))
        with ui.status("Running template"):
            result = run_with_optional_prompts(
                template_id,
                params=params,
                project=project,
                outdir=outdir,
                pack_refs=None,
                binding_ref=binding,
                prompt_missing=prompt_missing,
            )
        ui.print_run_completed(result)

    params: list[click.Parameter] = []
    for key, spec in template_spec.params.items():
        params.append(
            click.Option(
                [f"--{key.replace('_', '-')}"],
                type=click_type_for_param(spec.get("type", "str")),
                metavar=spec.get("type", "str").upper(),
                required=False,
                help=help_for_param(key, spec),
                show_default=False,
            )
        )

    params.extend(
        [
            click.Option(
                ["--project"],
                type=click.Path(path_type=str, dir_okay=True, file_okay=True),
                help="Project directory or project.yaml path. Defaults to the current directory.",
                show_default=False,
            ),
            click.Option(
                ["--binding"],
                type=str,
                shell_complete=shell_complete_filesystem_ref,
                help="Binding path or asset reference used to resolve parameters.",
                show_default=False,
            ),
            click.Option(
                ["--outdir"],
                type=click.Path(path_type=str, dir_okay=True, file_okay=True),
                help="Write run artifacts to a specific directory instead of the default location.",
                show_default=False,
            ),
            click.Option(
                ["--prompt/--no-prompt", "prompt_missing"],
                default=True,
                help="Prompt interactively for unresolved required parameters when running in a TTY.",
                show_default=True,
            ),
            click.Option(
                ["--param"],
                multiple=True,
                callback=lambda _ctx, _param, value: tuple(parse_key_value(item) for item in value),
                metavar="KEY=VALUE",
                help="Additional parameter override in KEY=VALUE form.",
                show_default=False,
            ),
        ]
    )

    return click.Command(
        name=template_id,
        callback=callback,
        params=params,
        help=f"Run template '{template_id}'.",
        short_help=f"Run template '{template_id}'.",
    )


@handle_linkar_errors
def run_raw_command(
    template: str,
    pack: tuple[str, ...],
    binding: str | None,
    project: str | None,
    outdir: str | None,
    prompt_missing: bool,
    param: tuple[tuple[str, str], ...],
    ui: CliUI,
) -> None:
    """Run any template by id or path using the generic execution interface."""
    with ui.status("Running template"):
        result = run_with_optional_prompts(
            template,
            params=params_from_pairs(param),
            project=project,
            outdir=outdir,
            pack_refs=list(pack),
            binding_ref=binding,
            prompt_missing=prompt_missing,
        )
    ui.print_run_completed(result)


class DynamicRunGroup(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        command_names = {"raw"}
        duplicates: dict[str, int] = defaultdict(int)
        try:
            for template in list_templates(project=None):
                duplicates[template["id"]] += 1
            for template_id, count in duplicates.items():
                if count == 1:
                    command_names.add(template_id)
        except LinkarError:
            pass
        return sorted(command_names)

    def get_command(self, ctx: click.Context, cmd_name: str):
        if cmd_name == "raw":
            return raw_run_command

        try:
            visible = [template for template in list_templates(project=None) if template["id"] == cmd_name]
        except LinkarError:
            visible = []

        if len(visible) == 1:
            return template_command_callback(cmd_name, visible[0]["path"])
        if len(visible) > 1:
            def ambiguous() -> None:
                raise ProjectValidationError(
                    f"Template '{cmd_name}' is ambiguous across configured packs. Use 'linkar run raw {cmd_name} --pack ...' instead."
                )

            return click.Command(cmd_name, callback=handle_linkar_errors(ambiguous))
        return None


@app.group(
    "run",
    cls=DynamicRunGroup,
    invoke_without_command=True,
    no_args_is_help=True,
)
@click.pass_context
def run_group(ctx: click.Context) -> None:
    """Run configured templates with template-aware options or use 'raw' for ad hoc execution."""


raw_run_command = click.Command(
    name="raw",
    callback=run_raw_command,
    params=[
        click.Argument(
            ["template"],
            required=True,
            shell_complete=shell_complete_template_ref,
        ),
        click.Option(
            ["--pack"],
            multiple=True,
            type=str,
            shell_complete=shell_complete_filesystem_ref,
            help="Pack path or asset reference to search for the template. Repeat to add more than one.",
            show_default=False,
        ),
        click.Option(
            ["--binding"],
            type=str,
            shell_complete=shell_complete_filesystem_ref,
            help="Binding path or asset reference used to resolve parameters.",
            show_default=False,
        ),
        click.Option(
            ["--project"],
            type=click.Path(path_type=str, dir_okay=True, file_okay=True),
            help="Project directory or project.yaml path. Defaults to the current directory.",
            show_default=False,
        ),
        click.Option(
            ["--outdir"],
            type=click.Path(path_type=str, dir_okay=True, file_okay=True),
            help="Write run artifacts to a specific directory instead of the default location.",
            show_default=False,
        ),
        click.Option(
            ["--prompt/--no-prompt", "prompt_missing"],
            default=True,
            help="Prompt interactively for unresolved required parameters when running in a TTY.",
            show_default=True,
        ),
        click.Option(
            ["--param"],
            multiple=True,
            callback=lambda _ctx, _param, value: tuple(parse_key_value(item) for item in value),
            metavar="KEY=VALUE",
            help="Template parameter in KEY=VALUE form.",
            show_default=False,
        ),
    ],
    help="Run any template by id or path using the generic execution interface.",
    short_help="Run a template with the generic interface.",
)


@app.command("templates")
@click.option(
    "--pack",
    multiple=True,
    type=str,
    shell_complete=shell_complete_filesystem_ref,
    help="Pack path or asset reference to include in the search. Repeat to add more than one.",
    show_default=False,
)
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def templates_command(pack: tuple[str, ...], project: str | None, ui: CliUI) -> None:
    """List templates visible from explicit packs and the active project configuration."""
    ui.print_templates(list_templates(pack_refs=list(pack), project=project))


@app.group("inspect")
def inspect_group() -> None:
    """Inspect metadata for recorded Linkar runs."""


@inspect_group.command("run")
@click.argument("run_ref")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def inspect_run_command(run_ref: str, project: str | None, ui: CliUI) -> None:
    """Inspect run metadata by instance id or run directory path."""
    ui.print_metadata(inspect_run(run_ref, project=project))


@app.command("methods")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def methods_command(project: str | None, ui: CliUI) -> None:
    """Generate an editable methods summary from the runs recorded in a project."""
    ui.print_methods(generate_methods(project=project))


@app.command("serve")
@click.option("--host", default="127.0.0.1", metavar="HOST", show_default=True, help="Host interface to bind.")
@click.option("--port", default=8000, type=int, metavar="PORT", show_default=True, help="Port to listen on.")
def serve_command(host: str, port: int) -> None:
    """Expose the local project/runtime API over HTTP for automation and agents."""
    ui = CliUI()
    ui.print_server_banner(host, port)
    serve(host=host, port=port)


def main() -> int:
    app.main(prog_name="linkar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
