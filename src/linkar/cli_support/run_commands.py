from __future__ import annotations

from collections import defaultdict
from typing import Any

try:
    import rich_click as click
except ImportError:
    import click

from linkar.core import discover_project, get_active_global_pack_entry, get_active_pack_entry, list_templates, load_template
from linkar.errors import LinkarError, ProjectValidationError
from linkar.ui import CliUI
from linkar.cli_support.common import (
    click_type_for_param,
    execute_with_optional_prompts,
    handle_linkar_errors,
    help_for_param,
    parse_key_value,
    params_from_pairs,
    shell_complete_filesystem_ref,
    shell_complete_template_ref,
    should_stream_output_by_default,
)

CommandClass = getattr(click, "RichCommand", click.Command)
GroupClass = getattr(click, "RichGroup", click.Group)


def template_command_callback(
    template_id: str,
    template_path: str,
    pack_ref: str | None = None,
    *,
    action: str = "run",
):
    template_spec = load_template(template_path)
    status_message = "Rendering template" if action == "render" else "Running template"

    @handle_linkar_errors
    def callback(
        project: str | None,
        binding: str | None,
        outdir: str | None,
        prompt_missing: bool,
        *,
        param: tuple[tuple[str, str], ...],
        verbose: bool = False,
        refresh: bool = False,
        ui: CliUI,
        **template_values: Any,
    ) -> None:
        params = {key: value for key, value in template_values.items() if value is not None}
        params.update(params_from_pairs(param))
        run_template_ref = template_id if pack_ref is not None else template_path
        run_pack_refs = [pack_ref] if pack_ref is not None else None
        effective_verbose = verbose or (action == "run" and template_spec.run_verbose_by_default)
        if effective_verbose and action == "run":
            result = execute_with_optional_prompts(
                run_template_ref,
                params=params,
                project=project,
                outdir=outdir,
                pack_refs=run_pack_refs,
                binding_ref=binding,
                prompt_missing=prompt_missing,
                action=action,
                verbose=True,
                refresh=refresh,
            )
        else:
            with ui.status(status_message):
                result = execute_with_optional_prompts(
                    run_template_ref,
                    params=params,
                    project=project,
                    outdir=outdir,
                    pack_refs=run_pack_refs,
                    binding_ref=binding,
                    prompt_missing=prompt_missing,
                    action=action,
                    refresh=refresh,
                )
        if action == "render":
            ui.print_render_completed(result)
        else:
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
        ]
    )
    if action == "run":
        params.append(
            click.Option(
                ["--verbose"],
                is_flag=True,
                help="Stream the template command stdout and stderr while it runs.",
                show_default=False,
            )
        )
        params.append(
            click.Option(
                ["--refresh"],
                is_flag=True,
                help="For render-mode templates in projects, rerender the visible bundle before execution.",
                show_default=False,
            )
        )
    params.append(
        click.Option(
            ["--param"],
            multiple=True,
            callback=lambda _ctx, _param, value: tuple(parse_key_value(item) for item in value),
            metavar="KEY=VALUE",
            help="Additional parameter override in KEY=VALUE form.",
            show_default=False,
        )
    )

    return CommandClass(
        name=template_id,
        callback=callback,
        params=params,
        help=(
            f"{'Render' if action == 'render' else 'Run'} template '{template_id}'. "
            + (
                "This template uses run.mode=render, so project runs reuse the visible bundle unless --refresh is passed."
                if action == "run" and template_spec.run_mode == "render"
                else ""
            )
        ).strip(),
        short_help=f"{'Render' if action == 'render' else 'Run'} template '{template_id}'.",
    )


def generic_run_callback(bound_template: str | None = None, *, action: str = "run"):
    status_message = "Rendering template" if action == "render" else "Running template"

    @handle_linkar_errors
    def callback(
        pack: tuple[str, ...],
        binding: str | None,
        project: str | None,
        outdir: str | None,
        prompt_missing: bool,
        *,
        param: tuple[tuple[str, str], ...],
        verbose: bool = False,
        refresh: bool = False,
        ui: CliUI,
        template: str | None = None,
    ) -> None:
        template_ref = bound_template or template
        if template_ref is None:
            raise ProjectValidationError("Missing template reference.")
        effective_verbose = verbose or (
            action == "run"
            and should_stream_output_by_default(
                template_ref,
                project=project,
                pack_refs=list(pack),
            )
        )
        if effective_verbose and action == "run":
            result = execute_with_optional_prompts(
                template_ref,
                params=params_from_pairs(param),
                project=project,
                outdir=outdir,
                pack_refs=list(pack),
                binding_ref=binding,
                prompt_missing=prompt_missing,
                action=action,
                verbose=True,
                refresh=refresh,
            )
        else:
            with ui.status(status_message):
                result = execute_with_optional_prompts(
                    template_ref,
                    params=params_from_pairs(param),
                    project=project,
                    outdir=outdir,
                    pack_refs=list(pack),
                    binding_ref=binding,
                    prompt_missing=prompt_missing,
                    action=action,
                    refresh=refresh,
                )
        if action == "render":
            ui.print_render_completed(result)
        else:
            ui.print_run_completed(result)

    return callback


def make_generic_run_command(
    name: str,
    *,
    bound_template: str | None = None,
    hidden: bool = False,
    action: str = "run",
):
    params: list[click.Parameter] = []
    if bound_template is None:
        params.append(
            click.Argument(
                ["template"],
                required=True,
                shell_complete=shell_complete_template_ref,
            )
        )

    params.extend(
        [
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
        ]
    )
    if action == "run":
        params.append(
            click.Option(
                ["--verbose"],
                is_flag=True,
                help="Stream the template command stdout and stderr while it runs.",
                show_default=False,
            )
        )
        params.append(
            click.Option(
                ["--refresh"],
                is_flag=True,
                help="For render-mode templates in projects, rerender the visible bundle before execution.",
                show_default=False,
            )
        )
    params.append(
        click.Option(
            ["--param"],
            multiple=True,
            callback=lambda _ctx, _param, value: tuple(parse_key_value(item) for item in value),
            metavar="KEY=VALUE",
            help="Template parameter in KEY=VALUE form.",
            show_default=False,
        )
    )

    return CommandClass(
        name=name,
        callback=generic_run_callback(bound_template, action=action),
        params=params,
        help=(
            "Render any template by id or path using the generic staging interface."
            if action == "render"
            else "Run any template by id or path using the generic execution interface."
        ),
        short_help=(
            "Render a template with the generic interface."
            if action == "render"
            else "Run a template with the generic interface."
        ),
        hidden=hidden,
    )


class DynamicTemplateGroup(GroupClass):
    action = "run"

    def list_commands(self, ctx: click.Context) -> list[str]:
        command_names: set[str] = set()
        by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        try:
            templates = list_templates(project=None)
            project_obj = discover_project()
            active_entry = get_active_pack_entry(project_obj) or get_active_global_pack_entry()
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
            return render_raw_command if self.action == "render" else raw_run_command

        try:
            project_obj = discover_project()
            active_entry = get_active_pack_entry(project_obj) or get_active_global_pack_entry()
            visible = [template for template in list_templates(project=None) if template["id"] == cmd_name]
        except LinkarError:
            visible = []

        if len(visible) == 1:
            return template_command_callback(
                cmd_name,
                visible[0]["path"],
                visible[0]["pack_ref"],
                action=self.action,
            )
        if len(visible) > 1:
            if active_entry is not None:
                active_matches = [template for template in visible if template["pack_ref"] == active_entry.asset.ref]
                if len(active_matches) == 1:
                    return template_command_callback(
                        cmd_name,
                        active_matches[0]["path"],
                        active_matches[0]["pack_ref"],
                        action=self.action,
                    )

        return make_generic_run_command(cmd_name, bound_template=cmd_name, action=self.action)

class DynamicRunGroup(DynamicTemplateGroup):
    action = "run"


class DynamicRenderGroup(DynamicTemplateGroup):
    action = "render"


raw_run_command = make_generic_run_command("raw", hidden=True, action="run")
render_raw_command = make_generic_run_command("raw", hidden=True, action="render")
