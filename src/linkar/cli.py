from __future__ import annotations

try:
    import rich_click as click
except ImportError:
    import click

from pathlib import Path

from linkar import __version__
from linkar.cli_support.common import (
    load_project_or_discover,
    handle_linkar_errors,
    resolve_project_init_target,
    shell_complete_filesystem_ref,
    shell_complete_template_ref,
)
from linkar.cli_support.run_commands import DynamicRunGroup, raw_run_command
from linkar.core import (
    add_global_pack,
    add_project_pack,
    discover_project,
    generate_methods,
    get_active_global_pack_entry,
    get_active_pack_entry,
    global_config_path,
    init_project,
    inspect_run,
    list_configured_packs,
    list_global_packs,
    list_project_runs,
    list_templates,
    load_project,
    remove_global_pack,
    remove_project_pack,
    set_active_global_pack,
    set_active_pack,
    test_template,
)
from linkar.errors import ProjectValidationError
from linkar.runtime.projects import missing_project_error
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
        "  linkar run hello --name Linkar\n"
        "  linkar test fastqc --pack /path/to/pack\n\n"
        "Linkar keeps the CLI thin over the core runtime semantics."
    )


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


@app.group("pack")
def pack_group() -> None:
    """Manage packs saved in the active project configuration."""


@app.group("config")
def config_group() -> None:
    """Manage user-level Linkar configuration."""


@config_group.group("pack")
def config_pack_group() -> None:
    """Manage global packs saved in user config."""


@config_pack_group.command("add")
@click.argument("ref")
@click.option("--id", "pack_id", metavar="PACK_ID", help="Stable pack id stored in the global config.")
@click.option("--activate/--no-activate", default=True, show_default=True, help="Make this the active global pack after adding it.")
@handle_linkar_errors
def config_pack_add_command(ref: str, pack_id: str | None, activate: bool, ui: CliUI) -> None:
    result = add_global_pack(ref, pack_id=pack_id, activate=activate)
    ui.print_text(f"{result['id']}\t{result['ref']}")


@config_pack_group.command("list")
@handle_linkar_errors
def config_pack_list_command(ui: CliUI) -> None:
    """List global packs saved in user config."""
    ui.print_packs(list_global_packs())


@config_pack_group.command("use")
@click.argument("identifier")
@handle_linkar_errors
def config_pack_use_command(identifier: str, ui: CliUI) -> None:
    """Select the active global pack."""
    result = set_active_global_pack(identifier)
    ui.print_text(f"{result['id']}\t{result['ref']}")


@config_pack_group.command("remove")
@click.argument("identifier")
@handle_linkar_errors
def config_pack_remove_command(identifier: str, ui: CliUI) -> None:
    """Remove a configured global pack."""
    result = remove_global_pack(identifier)
    ui.print_text(f"{result['id']}\t{result['ref']}")


@config_pack_group.command("show")
@handle_linkar_errors
def config_pack_show_command(ui: CliUI) -> None:
    """Show the active global pack."""
    active_entry = get_active_global_pack_entry()
    if active_entry is None:
        raise ProjectValidationError(
            f"No active global pack configured. Add one with 'linkar config pack add REF'. Config file: {global_config_path()}"
        )
    ui.print_text(f"{active_entry.id}\t{active_entry.asset.ref}")


@pack_group.command("add")
@click.argument("ref")
@click.option("--id", "pack_id", metavar="PACK_ID", help="Stable pack id stored in project.yaml.")
@click.option("--binding", metavar="REF", help="Binding ref for this pack. Use 'default' for the pack default binding.")
@click.option("--activate/--no-activate", default=True, show_default=True, help="Make this pack the active pack after adding it.")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def pack_add_command(
    ref: str,
    pack_id: str | None,
    binding: str | None,
    activate: bool,
    project: str | None,
    ui: CliUI,
) -> None:
    result = add_project_pack(ref, project=project, pack_id=pack_id, binding=binding, activate=activate)
    ui.print_text(f"{result['id']}\t{result['ref']}")


@pack_group.command("list")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def pack_list_command(project: str | None, ui: CliUI) -> None:
    """List packs saved in the project configuration."""
    ui.print_packs(list_configured_packs(project=project))


@pack_group.command("use")
@click.argument("identifier")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def pack_use_command(identifier: str, project: str | None, ui: CliUI) -> None:
    """Select the active/default pack for the project."""
    result = set_active_pack(identifier, project=project)
    ui.print_text(f"{result['id']}\t{result['ref']}")


@pack_group.command("remove")
@click.argument("identifier")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def pack_remove_command(identifier: str, project: str | None, ui: CliUI) -> None:
    """Remove a configured pack from the project."""
    result = remove_project_pack(identifier, project=project)
    ui.print_text(f"{result['id']}\t{result['ref']}")


@pack_group.command("show")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def pack_show_command(project: str | None, ui: CliUI) -> None:
    """Show the active/default pack for the project."""
    project_obj = load_project_or_discover(project)
    if project_obj is None:
        raise missing_project_error("Showing the active pack")
    active_entry = get_active_pack_entry(project_obj)
    if active_entry is None:
        raise ProjectValidationError("No active pack configured")
    ui.print_text(f"{active_entry.id}\t{active_entry.asset.ref}")


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


@app.group(
    "run",
    cls=DynamicRunGroup,
    invoke_without_command=True,
    no_args_is_help=True,
)
@click.pass_context
def run_group(ctx: click.Context) -> None:
    """Run configured templates with template-aware options or use 'raw' for ad hoc execution."""


run_group.add_command(raw_run_command)


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


@app.command("test")
@click.argument("template", shell_complete=shell_complete_template_ref)
@click.option(
    "--pack",
    multiple=True,
    type=str,
    shell_complete=shell_complete_filesystem_ref,
    help="Pack path or asset reference to search for the template. Repeat to add more than one.",
    show_default=False,
)
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@click.option(
    "--outdir",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Write test artifacts to a specific directory instead of the default test workspace.",
    show_default=False,
)
@handle_linkar_errors
def test_command(
    template: str,
    pack: tuple[str, ...],
    project: str | None,
    outdir: str | None,
    ui: CliUI,
) -> None:
    """Run a template-local test.sh if the template provides one."""
    with ui.status("Testing template"):
        result = test_template(
            template,
            project=project,
            outdir=outdir,
            pack_refs=list(pack),
        )
    ui.print_test_completed(result)


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
