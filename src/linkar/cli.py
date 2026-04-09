from __future__ import annotations

try:
    import rich_click as click
except ImportError:
    import click

from pathlib import Path
from click.shell_completion import get_completion_class

from linkar import __version__
from linkar.cli_support.common import (
    load_project_or_discover,
    handle_linkar_errors,
    resolve_project_init_target,
    shell_complete_filesystem_ref,
    shell_complete_template_ref,
)
from linkar.cli_support.run_commands import (
    DynamicRenderGroup,
    DynamicRunGroup,
    raw_run_command,
    render_raw_command,
)
from linkar.core import (
    add_global_pack,
    add_project_pack,
    adopt_run_into_project,
    clear_global_author,
    collect_run_outputs,
    discover_project,
    generate_methods,
    get_active_global_pack_entry,
    get_active_pack_entry,
    get_global_author,
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
    remove_project_run,
    set_global_author,
    set_active_global_pack,
    set_active_pack,
    test_template,
)
from linkar.errors import ProjectValidationError
from linkar.mcp_server import main as serve_mcp
from linkar.runtime.projects import missing_project_error
from linkar.server import parse_api_token_specs, serve
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
        "  linkar config pack add ~/github/izkf_genomics_pack\n"
        "  linkar pack add /path/to/project-pack\n"
        "  linkar project init --name study --adopt /path/to/run\n"
        "  linkar run fastqc --input sample.fastq.gz\n"
        "  linkar render demultiplex --outdir ./demux_bundle\n"
        "  linkar run simple_echo --pack ./examples/packs/basic --param name=Linkar\n"
        "  linkar collect ./demux_bundle\n"
        "  linkar test fastqc\n"
        "  linkar serve --port 8000 --api-token local-dev:read,resolve,execute\n\n"
        "  linkar mcp serve\n\n"
        "Linkar keeps the CLI thin over the same core semantics used by the local API."
    )


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(__version__, prog_name="linkar")
@click.pass_context
def app(ctx: click.Context) -> None:
    """Run reusable computational templates with a human-friendly CLI and machine-readable local state."""
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
    """Add a global pack to the user config."""
    result = add_global_pack(ref, pack_id=pack_id, activate=activate)
    ui.print_pack_summary(
        "[accent]Global Pack Added[/accent]",
        pack_id=result["id"],
        ref=result["ref"],
        active=result.get("active"),
        plain_text=f"{result['id']}\t{result['ref']}",
    )


@config_pack_group.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json", "yaml"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@handle_linkar_errors
def config_pack_list_command(output_format: str, ui: CliUI) -> None:
    """List global packs saved in user config."""
    packs = list_global_packs()
    if output_format == "rich":
        ui.print_packs(packs)
        return
    ui.print_data(packs, format=output_format)


@config_pack_group.command("use")
@click.argument("identifier")
@handle_linkar_errors
def config_pack_use_command(identifier: str, ui: CliUI) -> None:
    """Select the active global pack."""
    result = set_active_global_pack(identifier)
    ui.print_pack_summary(
        "[accent]Global Pack Selected[/accent]",
        pack_id=result["id"],
        ref=result["ref"],
        active=result.get("active"),
        plain_text=f"{result['id']}\t{result['ref']}",
    )


@config_pack_group.command("remove")
@click.argument("identifier")
@handle_linkar_errors
def config_pack_remove_command(identifier: str, ui: CliUI) -> None:
    """Remove a configured global pack."""
    result = remove_global_pack(identifier)
    ui.print_pack_summary(
        "[accent]Global Pack Removed[/accent]",
        pack_id=result["id"],
        ref=result["ref"],
        plain_text=f"{result['id']}\t{result['ref']}",
    )


@config_pack_group.command("show")
@handle_linkar_errors
def config_pack_show_command(ui: CliUI) -> None:
    """Show the active global pack."""
    active_entry = get_active_global_pack_entry()
    if active_entry is None:
        raise ProjectValidationError(
            f"No active global pack configured. Add one with 'linkar config pack add REF'. Config file: {global_config_path()}"
        )
    ui.print_pack_summary(
        "[accent]Active Global Pack[/accent]",
        pack_id=active_entry.id,
        ref=active_entry.asset.ref,
        plain_text=f"{active_entry.id}\t{active_entry.asset.ref}",
        active=True,
    )


@config_group.group("author")
def config_author_group() -> None:
    """Manage default author metadata reused when creating new projects."""


@config_author_group.command("set")
@click.option("--name", "author_name", metavar="NAME", help="Default author name.")
@click.option("--email", "author_email", metavar="EMAIL", help="Default author email.")
@click.option("--organization", metavar="ORG", help="Default author organization.")
@handle_linkar_errors
def config_author_set_command(
    author_name: str | None,
    author_email: str | None,
    organization: str | None,
    ui: CliUI,
) -> None:
    """Set default author metadata in the global Linkar config."""
    ui.print_metadata(
        {
            "author": set_global_author(
                name=author_name,
                email=author_email,
                organization=organization,
            )
        }
    )


@config_author_group.command("show")
@handle_linkar_errors
def config_author_show_command(ui: CliUI) -> None:
    """Show default author metadata from the global Linkar config."""
    ui.print_metadata({"author": get_global_author()})


@config_author_group.command("clear")
@handle_linkar_errors
def config_author_clear_command(ui: CliUI) -> None:
    """Remove default author metadata from the global Linkar config."""
    clear_global_author()
    ui.print_summary_panel(
        "[accent]Author Defaults Cleared[/accent]",
        [("Status", "author defaults cleared")],
        plain_text="author defaults cleared",
    )


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
    """Add a pack to the active project."""
    result = add_project_pack(ref, project=project, pack_id=pack_id, binding=binding, activate=activate)
    ui.print_pack_summary(
        "[accent]Project Pack Added[/accent]",
        pack_id=result["id"],
        ref=result["ref"],
        binding=result.get("binding"),
        active=result.get("active"),
        plain_text=f"{result['id']}\t{result['ref']}",
    )


@pack_group.command("list")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json", "yaml"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@handle_linkar_errors
def pack_list_command(project: str | None, output_format: str, ui: CliUI) -> None:
    """List packs saved in the project configuration."""
    packs = list_configured_packs(project=project)
    if output_format == "rich":
        ui.print_packs(packs)
        return
    ui.print_data(packs, format=output_format)


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
    ui.print_pack_summary(
        "[accent]Project Pack Selected[/accent]",
        pack_id=result["id"],
        ref=result["ref"],
        binding=result.get("binding"),
        active=result.get("active"),
        plain_text=f"{result['id']}\t{result['ref']}",
    )


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
    ui.print_pack_summary(
        "[accent]Project Pack Removed[/accent]",
        pack_id=result["id"],
        ref=result["ref"],
        binding=result.get("binding"),
        plain_text=f"{result['id']}\t{result['ref']}",
    )


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
    ui.print_pack_summary(
        "[accent]Active Project Pack[/accent]",
        pack_id=active_entry.id,
        ref=active_entry.asset.ref,
        binding=active_entry.binding,
        active=True,
        plain_text=f"{active_entry.id}\t{active_entry.asset.ref}",
    )


@app.group("project")
def project_group() -> None:
    """Create a Linkar project or inspect run records stored in project.yaml."""


@app.group("mcp")
def mcp_group() -> None:
    """Expose Linkar as a local MCP server for agent clients."""


@mcp_group.command("serve")
def mcp_serve_command() -> None:
    """Start the stdio MCP server."""
    try:
        serve_mcp()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


@app.group("completion")
def completion_group() -> None:
    """Print shell completion scripts for supported shells."""


def _print_completion_script(shell: str) -> None:
    cls = get_completion_class(shell)
    if cls is None:
        raise click.ClickException(f"Unsupported shell for completion: {shell}")
    click.echo(cls(app, {}, "linkar", "_LINKAR_COMPLETE").source())


def _default_completion_install_target(shell: str, rc_file: str | None = None) -> tuple[Path, str]:
    home = Path.home()
    if shell == "bash":
        if rc_file is not None:
            target = Path(rc_file).expanduser().resolve()
            line = 'eval "$(linkar completion bash)"'
            return target, line
        completion_dir = home / ".local" / "share" / "bash-completion" / "completions"
        return completion_dir / "linkar", "$(linkar completion bash)"
    if shell == "zsh":
        if rc_file is not None:
            target = Path(rc_file).expanduser().resolve()
            line = 'eval "$(linkar completion zsh)"'
            return target, line
        completion_dir = home / ".zsh" / "completions"
        return completion_dir / "_linkar", "$(linkar completion zsh)"
    raise click.ClickException(f"Unsupported shell for completion install: {shell}")


def _install_completion(shell: str, *, rc_file: str | None = None, assume_yes: bool = False) -> None:
    target, content = _default_completion_install_target(shell, rc_file=rc_file)
    target.parent.mkdir(parents=True, exist_ok=True)

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if content in existing:
        click.echo(str(target))
        return

    if rc_file is not None:
        new_text = existing
        if new_text and not new_text.endswith("\n"):
            new_text += "\n"
        new_text += f'{content}\n'
        prompt = f"Append Linkar {shell} completion setup to {target}?"
    else:
        new_text = content
        if not new_text.endswith("\n"):
            new_text += "\n"
        prompt = f"Write Linkar {shell} completion script to {target}?"

    if not assume_yes and not click.confirm(prompt, default=True):
        raise click.exceptions.Exit(1)

    target.write_text(new_text, encoding="utf-8")
    click.echo(str(target))


@completion_group.command("bash")
def completion_bash_command() -> None:
    """Print the bash completion script."""
    _print_completion_script("bash")


@completion_group.command("zsh")
def completion_zsh_command() -> None:
    """Print the zsh completion script."""
    _print_completion_script("zsh")


@completion_group.group("install")
def completion_install_group() -> None:
    """Install shell completion for supported shells."""


@completion_install_group.command("bash")
@click.option("--yes", is_flag=True, help="Install without interactive confirmation.")
@click.option(
    "--rc-file",
    type=click.Path(path_type=str, dir_okay=False),
    help="Append eval-based setup to this shell rc file instead of writing a user completion file.",
    show_default=False,
)
def completion_install_bash_command(yes: bool, rc_file: str | None) -> None:
    """Install bash completion in a user-level location."""
    _install_completion("bash", rc_file=rc_file, assume_yes=yes)


@completion_install_group.command("zsh")
@click.option("--yes", is_flag=True, help="Install without interactive confirmation.")
@click.option(
    "--rc-file",
    type=click.Path(path_type=str, dir_okay=False),
    help="Append eval-based setup to this shell rc file instead of writing a user completion file.",
    show_default=False,
)
def completion_install_zsh_command(yes: bool, rc_file: str | None) -> None:
    """Install zsh completion in a user-level location."""
    _install_completion("zsh", rc_file=rc_file, assume_yes=yes)


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
@click.option("--author-name", metavar="NAME", help="Project author name. Defaults to the configured global author.")
@click.option("--author-email", metavar="EMAIL", help="Project author email. Defaults to the configured global author.")
@click.option(
    "--author-organization",
    metavar="ORG",
    help="Project author organization. Defaults to the configured global author.",
)
@click.option(
    "--adopt",
    "adopt_runs",
    multiple=True,
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Existing Linkar run directory or .linkar/meta.json to import into the new project. Repeat to adopt more than one run.",
    show_default=False,
)
@handle_linkar_errors
def project_init(
    path: str | None,
    name: str | None,
    project_id: str | None,
    author_name: str | None,
    author_email: str | None,
    author_organization: str | None,
    adopt_runs: tuple[str, ...],
    ui: CliUI,
) -> None:
    """Create project.yaml in the target directory. Use --name to create a new directory automatically."""
    target_path, implied_id = resolve_project_init_target(path, name)
    author = dict(get_global_author() or {})
    if author_name is not None:
        author["name"] = author_name
    if author_email is not None:
        author["email"] = author_email
    if author_organization is not None:
        author["organization"] = author_organization
    project_path = init_project(
        target_path,
        project_id=project_id or implied_id,
        author=author or None,
    )
    for run_ref in adopt_runs:
        adopt_run_into_project(run_ref, project=project_path.parent)
    resolved_id = project_id or implied_id or Path(target_path).resolve().name
    ui.print_project_created(project_path, resolved_id)


@project_group.command("adopt-run")
@click.argument("run_ref", nargs=-1)
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def project_adopt_run_command(run_ref: tuple[str, ...], project: str | None, ui: CliUI) -> None:
    """Import existing Linkar run directories into the active project index."""
    if not run_ref:
        raise ProjectValidationError("Provide at least one run reference to adopt.")
    adopted: list[dict[str, str]] = []
    with ui.status("Adopting runs"):
        for item in run_ref:
            entry = adopt_run_into_project(item, project=project)
            adopted.append({"instance_id": entry["instance_id"], "path": entry["path"]})
    ui.print_runs(
        [
            {"instance_id": item["instance_id"], "id": "adopted", "path": item["path"]}
            for item in adopted
        ]
    )


@project_group.command("remove-run")
@click.argument("run_ref")
@click.option(
    "--delete-files/--keep-files",
    default=False,
    show_default=True,
    help="Also delete the recorded run directory from disk.",
)
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def project_remove_run_command(
    run_ref: str,
    delete_files: bool,
    project: str | None,
    ui: CliUI,
) -> None:
    """Remove a run record from the active project, optionally deleting its files."""
    result = remove_project_run(run_ref, project=project, delete_files=delete_files)
    suffix = " deleted" if delete_files else " detached"
    ui.print_run_removal(
        instance_id=result["instance_id"],
        template_id=result["id"],
        path=result["path"],
        deleted=delete_files,
        plain_text=f"{result['instance_id']}\t{result['id']}\t{result['path']}{suffix}",
    )


@project_group.command("runs")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json", "yaml"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@handle_linkar_errors
def project_runs(project: str | None, output_format: str, ui: CliUI) -> None:
    """Show template instances recorded in project.yaml."""
    runs = list_project_runs(project=project)
    if output_format == "rich":
        ui.print_runs(runs)
        return
    ui.print_data(runs, format=output_format)


def _select_project_runs(runs: list[dict[str, object]], run_ref: str | None) -> list[dict[str, object]]:
    if not run_ref:
        return runs

    exact_instance_matches = [run for run in runs if str(run.get("instance_id") or "") == run_ref]
    if exact_instance_matches:
        return exact_instance_matches

    template_matches = [run for run in runs if str(run.get("id") or "") == run_ref]
    if template_matches:
        return template_matches

    path_matches = [run for run in runs if str(run.get("path") or "") == run_ref]
    if path_matches:
        return path_matches

    raise ProjectValidationError(f"Run not found in project: {run_ref}")


@project_group.command("view")
@click.argument("run_ref", required=False)
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json", "yaml"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@handle_linkar_errors
def project_view_command(run_ref: str | None, project: str | None, output_format: str, ui: CliUI) -> None:
    """Show project metadata and recorded runs in a human-friendly view."""
    project_obj = load_project_or_discover(project)
    if project_obj is None:
        raise missing_project_error("Viewing project metadata")
    runs = _select_project_runs(list_project_runs(project=project_obj), run_ref)
    if output_format == "rich":
        ui.print_project_view(project_obj.data, project_path=project_obj.root, runs=runs)
        return
    payload = dict(project_obj.data)
    payload["project_path"] = str(project_obj.root)
    payload["templates"] = runs
    ui.print_data(payload, format=output_format)


@app.group(
    "run",
    cls=DynamicRunGroup,
    invoke_without_command=True,
    no_args_is_help=False,
)
@click.pass_context
def run_group(ctx: click.Context) -> None:
    """Run templates with template-aware options or the generic TEMPLATE interface."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


run_group.add_command(raw_run_command)


@app.group(
    "render",
    cls=DynamicRenderGroup,
    invoke_without_command=True,
    no_args_is_help=False,
)
@click.pass_context
def render_group(ctx: click.Context) -> None:
    """Render template bundles with template-aware options or the generic TEMPLATE interface."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


render_group.add_command(render_raw_command)


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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json", "yaml"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@handle_linkar_errors
def templates_command(pack: tuple[str, ...], project: str | None, output_format: str, ui: CliUI) -> None:
    """List templates visible from explicit packs and the active project configuration."""
    templates = list_templates(pack_refs=list(pack), project=project)
    if output_format == "rich":
        ui.print_templates(templates)
        return
    ui.print_data(templates, format=output_format)


@app.command("collect")
@click.argument("run_ref")
@click.option(
    "--project",
    type=click.Path(path_type=str, dir_okay=True, file_okay=True),
    help="Project directory or project.yaml path. Defaults to the current directory.",
    show_default=False,
)
@handle_linkar_errors
def collect_command(run_ref: str, project: str | None, ui: CliUI) -> None:
    """Collect declared outputs for a previously rendered or manually executed run directory."""
    with ui.status("Collecting outputs"):
        result = collect_run_outputs(run_ref, project=project)
    ui.print_collect_completed(result)


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
@click.option(
    "--verbose",
    is_flag=True,
    help="Stream the template test stdout and stderr while it runs.",
    show_default=False,
)
@handle_linkar_errors
def test_command(
    template: str,
    pack: tuple[str, ...],
    project: str | None,
    outdir: str | None,
    verbose: bool,
    ui: CliUI,
) -> None:
    """Run a template-local test.sh or test.py if the template provides one."""
    if verbose:
        result = test_template(
            template,
            project=project,
            outdir=outdir,
            pack_refs=list(pack),
            verbose=True,
        )
    else:
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["rich", "json", "yaml"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
@handle_linkar_errors
def inspect_run_command(run_ref: str, project: str | None, output_format: str, ui: CliUI) -> None:
    """Inspect run metadata by instance id or run directory path."""
    metadata = inspect_run(run_ref, project=project)
    if output_format == "rich":
        ui.print_metadata(metadata)
        return
    ui.print_data(metadata, format=output_format)


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
@click.option(
    "--api-token",
    "api_tokens",
    multiple=True,
    metavar="TOKEN[:ROLES]",
    help="Bearer token spec for the local API. Repeat as needed. Roles default to read,resolve,execute.",
)
def serve_command(host: str, port: int, api_tokens: tuple[str, ...]) -> None:
    """Expose the local project/runtime API over HTTP for automation and agents."""
    ui = CliUI()
    parsed_api_tokens = parse_api_token_specs(list(api_tokens)) or None
    ui.print_server_banner(host, port, auth_enabled=parsed_api_tokens is not None)
    serve(host=host, port=port, api_tokens=parsed_api_tokens)


def main() -> int:
    app.main(prog_name="linkar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
