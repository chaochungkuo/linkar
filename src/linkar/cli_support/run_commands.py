from __future__ import annotations

from collections import defaultdict
from typing import Any

try:
    import rich_click as click
except ImportError:
    import click

from linkar.core import discover_project, get_active_pack_entry, list_templates, load_template
from linkar.errors import LinkarError, ProjectValidationError
from linkar.ui import CliUI
from linkar.cli_support.common import (
    click_type_for_param,
    handle_linkar_errors,
    help_for_param,
    parse_key_value,
    params_from_pairs,
    run_with_optional_prompts,
    shell_complete_filesystem_ref,
    shell_complete_template_ref,
)


def template_command_callback(template_id: str, template_path: str, pack_ref: str | None = None):
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
        run_template_ref = template_id if pack_ref is not None else template_path
        run_pack_refs = [pack_ref] if pack_ref is not None else None
        with ui.status("Running template"):
            result = run_with_optional_prompts(
                run_template_ref,
                params=params,
                project=project,
                outdir=outdir,
                pack_refs=run_pack_refs,
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
        by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        try:
            templates = list_templates(project=None)
            project_obj = discover_project()
            active_entry = get_active_pack_entry(project_obj)
            for template in templates:
                by_id[template["id"]].append(template)
            for template_id, matches in by_id.items():
                if len(matches) == 1:
                    command_names.add(template_id)
                    continue
                if active_entry is not None and any(match["pack_ref"] == active_entry.asset.ref for match in matches):
                    command_names.add(template_id)
        except LinkarError:
            pass
        return sorted(command_names)

    def get_command(self, ctx: click.Context, cmd_name: str):
        if cmd_name == "raw":
            return raw_run_command

        try:
            project_obj = discover_project()
            active_entry = get_active_pack_entry(project_obj)
            visible = [template for template in list_templates(project=None) if template["id"] == cmd_name]
        except LinkarError:
            visible = []

        if len(visible) == 1:
            return template_command_callback(cmd_name, visible[0]["path"], visible[0]["pack_ref"])
        if len(visible) > 1:
            if active_entry is not None:
                active_matches = [template for template in visible if template["pack_ref"] == active_entry.asset.ref]
                if len(active_matches) == 1:
                    return template_command_callback(
                        cmd_name,
                        active_matches[0]["path"],
                        active_matches[0]["pack_ref"],
                    )

            def ambiguous() -> None:
                raise ProjectValidationError(
                    f"Template '{cmd_name}' is ambiguous across configured packs. Use 'linkar run raw {cmd_name} --pack ...' instead."
                )

            return click.Command(cmd_name, callback=handle_linkar_errors(ambiguous))
        return None


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
