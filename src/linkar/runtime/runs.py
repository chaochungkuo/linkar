from __future__ import annotations

import json
import os
import pty
import re
import select
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from linkar import __version__
from linkar.assets import resolve_asset_refs
from linkar.errors import ExecutionError, ProjectValidationError, TemplateValidationError
from linkar.runtime.bindings import (
    load_binding_config,
    resolve_bound_outdir,
    resolve_params_detailed_with_warnings,
)
from linkar.runtime.models import Project, TemplateSpec
from linkar.runtime.projects import (
    discover_project,
    find_project_pack_entry,
    load_project,
    project_pack_entries,
)
from linkar.runtime.config import get_active_global_pack_entry
from linkar.runtime.shared import (
    derive_pack_id,
    env_key,
    find_pack_spec_path,
    format_env_value,
    normalize_binding_ref,
    preferred_pack_ref_for_assets,
    save_yaml,
    unique_assets,
    utc_now,
    write_json,
)
from linkar.runtime.templates import combined_configured_pack_entries, load_template


def next_instance_id(template_id: str, project: Project | None = None) -> str:
    if project is None:
        stamp = utc_now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{template_id}_{stamp}"

    matches = 0
    for item in project.data.get("templates", []):
        if item.get("id") == template_id:
            matches += 1
    return f"{template_id}_{matches + 1:03d}"


def infer_default_binding_ref(
    template: TemplateSpec,
    selected_binding_ref: str | Path | None,
    project_obj: Project | None,
) -> str | Path | None:
    if selected_binding_ref is not None or template.pack_root is None:
        return selected_binding_ref
    active_global_entry = get_active_global_pack_entry()
    if active_global_entry is None:
        return selected_binding_ref
    if active_global_entry.asset.root != template.pack_root:
        return selected_binding_ref
    if find_pack_spec_path(active_global_entry.asset.root) is None:
        return selected_binding_ref
    return "default"


def determine_outdir(
    template: TemplateSpec,
    project: Project | None,
    outdir: str | Path | None,
    instance_id: str,
) -> Path:
    if outdir is not None:
        return Path(outdir).resolve()
    if project is not None:
        return (project.root / ".linkar" / "runs" / instance_id).resolve()
    return (Path.cwd() / ".linkar" / "runs" / instance_id).resolve()


def determine_project_alias_dir(template: TemplateSpec, project: Project | None) -> Path | None:
    if project is None:
        return None
    return project.root / template.id


def determine_render_outdir(
    template: TemplateSpec,
    project: Project | None,
    outdir: str | Path | None,
    instance_id: str,
) -> Path:
    if outdir is not None:
        return Path(outdir).resolve()
    alias_dir = determine_project_alias_dir(template, project)
    if alias_dir is not None:
        return alias_dir.resolve()
    return determine_outdir(template, project, outdir, instance_id)


def determine_test_dir(
    template: TemplateSpec,
    project: Project | None,
    outdir: str | Path | None,
) -> Path:
    if outdir is not None:
        return Path(outdir).resolve()
    stamp = utc_now().strftime("%Y%m%d_%H%M%S_%f")
    if project is not None:
        return (project.root / ".linkar" / "tests" / f"{template.id}_{stamp}").resolve()
    return (Path.cwd() / ".linkar" / "tests" / f"{template.id}_{stamp}").resolve()


def default_output_relative_path(output_name: str) -> Path:
    if output_name == "results_dir":
        return Path(".")
    if output_name.endswith("_dir"):
        return Path(output_name.removesuffix("_dir"))
    return Path(output_name)


def resolve_declared_output_path(output_name: str, spec: dict[str, Any], outdir: Path) -> Path:
    results_dir = outdir / "results"
    relative_path = spec.get("path")
    if relative_path is None:
        relative = default_output_relative_path(output_name)
    elif isinstance(relative_path, str) and relative_path.strip():
        relative = Path(relative_path)
    else:
        raise TemplateValidationError(
            f"Output '{output_name}' path must be a non-empty string when provided"
        )
    return (results_dir / relative).resolve()


def collect_declared_glob_output(spec: dict[str, Any], outdir: Path) -> list[str]:
    results_dir = (outdir / "results").resolve()
    pattern = spec.get("glob")
    if not isinstance(pattern, str) or not pattern.strip():
        raise TemplateValidationError("Declared glob output requires a non-empty string pattern")
    matches = sorted(path.resolve() for path in results_dir.glob(pattern))
    return [str(path) for path in matches]


def collect_outputs(template: TemplateSpec, outdir: Path) -> dict[str, Any]:
    return collect_outputs_from_declared(template.outputs, outdir)


def declared_outputs_or_default(declared_outputs: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return declared_outputs or {"results_dir": {}}


def collect_outputs_from_declared(
    declared_outputs: dict[str, dict[str, Any]] | None,
    outdir: Path,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    results_dir = (outdir / "results").resolve()
    declared_outputs = declared_outputs_or_default(declared_outputs)
    if declared_outputs:
        for output_name, spec in declared_outputs.items():
            if "glob" in spec:
                matched_paths = collect_declared_glob_output(spec, outdir)
                if matched_paths:
                    outputs[output_name] = matched_paths
                continue
            output_path = resolve_declared_output_path(output_name, spec, outdir)
            if output_path.exists():
                outputs[output_name] = str(output_path)
        return outputs

    if results_dir.exists():
        outputs["results_dir"] = str(results_dir)
    return outputs


RUNTIME_BUNDLE_EXCLUDES = {
    ".git",
    ".pixi",
    ".rattler-cache",
    ".pytest_cache",
    "__pycache__",
    "test.sh",
    "test.py",
    "testdata",
}


def should_exclude_runtime_path(path: Path) -> bool:
    return path.name in RUNTIME_BUNDLE_EXCLUDES


def stage_runtime_bundle(
    template: TemplateSpec,
    output_dir: Path,
    *,
    include_template_spec: bool = True,
) -> None:
    for child in template.root.iterdir():
        if should_exclude_runtime_path(child):
            continue
        if not include_template_spec and child.name in {"linkar_template.yaml", "template.yaml"}:
            continue
        destination = output_dir / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*RUNTIME_BUNDLE_EXCLUDES),
            )
        else:
            shutil.copy2(child, destination)


def render_mode_launcher_path(output_dir: Path) -> Path:
    return output_dir / "run.sh"


def ensure_required_tools_available(template: TemplateSpec) -> None:
    missing_required = [tool for tool in template.tools_required if shutil.which(tool) is None]
    missing_required_any = [
        group for group in template.tools_required_any if not any(shutil.which(tool) is not None for tool in group)
    ]
    if not missing_required and not missing_required_any:
        return

    parts: list[str] = []
    if missing_required:
        parts.append(f"missing required commands: {', '.join(missing_required)}")
    if missing_required_any:
        parts.extend(
            f"missing any of: {', '.join(group)}"
            for group in missing_required_any
        )
    raise ExecutionError(
        f"Template '{template.id}' cannot run because required tools are unavailable: {'; '.join(parts)}"
    )


def should_render_shell_wrapper(template: TemplateSpec) -> bool:
    return template.run_entry is not None and Path(template.run_entry).name == "script.sh"


def resolve_param_placeholders(
    command: str,
    resolved_params: dict[str, Any],
    *,
    for_render: bool,
) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        suffix = match.group(2) or ""
        name = key if for_render else env_key(key)
        return f"${{{name}{suffix}}}"

    pattern = re.compile(r"\$\{param:([A-Za-z0-9_]+)([^}]*)\}")
    rendered = command
    while True:
        updated = pattern.sub(replace, rendered)
        if updated == rendered:
            return updated
        rendered = updated


def render_launcher(
    launcher_path: Path,
    template: TemplateSpec,
    output_dir: Path,
    resolved_params: dict[str, Any],
    instance_id: str,
    project_obj: Project | None,
    target_entry: str | None = None,
) -> Path:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        '',
        'script_dir="$(cd "$(dirname "$0")" && pwd)"',
        'export LINKAR_OUTPUT_DIR="${script_dir}"',
        'export LINKAR_RESULTS_DIR="${script_dir}/results"',
        f"export LINKAR_INSTANCE_ID={shlex.quote(instance_id)}",
    ]
    if template.pack_root is not None:
        lines.append(f"export LINKAR_PACK_ROOT={shlex.quote(str(template.pack_root))}")
    if project_obj is not None:
        lines.append(f"export LINKAR_PROJECT_DIR={shlex.quote(str(project_obj.root))}")
    for key, value in sorted(resolved_params.items()):
        lines.append(f"export {env_key(key)}={shlex.quote(format_env_value(value))}")
    if template.run_command is not None:
        command = resolve_param_placeholders(template.run_command, resolved_params, for_render=False)
        lines.append(f"exec bash -lc {shlex.quote(command)}")
    else:
        entry_name = target_entry or template.run_entry
        if entry_name is None:
            raise ExecutionError(f"Template '{template.id}' is missing a runnable entrypoint")
        lines.append(f'exec "${{script_dir}}/{entry_name}"')
    launcher_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    launcher_path.chmod(0o755)
    return launcher_path


def render_entry_script(
    script_path: Path,
    template: TemplateSpec,
    resolved_params: dict[str, Any],
    instance_id: str,
    project_obj: Project | None,
) -> Path:
    original_text = script_path.read_text(encoding="utf-8")
    original_lines = original_text.splitlines()
    shebang = "#!/usr/bin/env bash"
    body_start = 0
    if original_lines and original_lines[0].startswith("#!"):
        shebang = original_lines[0]
        body_start = 1

    lines = [
        shebang,
        'expected_dir="$(cd "$(dirname "$0")" && pwd)"',
        'if [[ "$PWD" != "$expected_dir" ]]; then',
        '  echo "Run ./run.sh from inside ${expected_dir}" >&2',
        "  exit 1",
        "fi",
        'export LINKAR_OUTPUT_DIR="${expected_dir}"',
        'export LINKAR_RESULTS_DIR="${expected_dir}/results"',
        f"export LINKAR_INSTANCE_ID={shlex.quote(instance_id)}",
    ]
    if template.pack_root is not None:
        lines.append(f"export LINKAR_PACK_ROOT={shlex.quote(str(template.pack_root))}")
    if project_obj is not None:
        lines.append(f"export LINKAR_PROJECT_DIR={shlex.quote(str(project_obj.root))}")
    for key, value in sorted(resolved_params.items()):
        lines.append(f"export {env_key(key)}={shlex.quote(format_env_value(value))}")
    lines.append("")
    lines.extend(original_lines[body_start:])
    script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def resolve_render_command(
    command: str,
    resolved_params: dict[str, Any],
    instance_id: str,
    project_obj: Project | None,
) -> str:
    substitutions = {
        "LINKAR_OUTPUT_DIR": ".",
        "LINKAR_RESULTS_DIR": "./results",
        "LINKAR_INSTANCE_ID": shlex.quote(instance_id),
        "LINKAR_PROJECT_DIR": shlex.quote(str(project_obj.root)) if project_obj is not None else '""',
    }

    rendered = resolve_param_placeholders(command, resolved_params, for_render=True)
    for key, value in substitutions.items():
        rendered = rendered.replace(f"${{{key}}}", value)
        rendered = re.sub(rf"\${key}(?![A-Za-z0-9_])", value, rendered)
    for key in sorted(resolved_params):
        rendered = re.sub(
            rf"\$\{{{env_key(key)}(?=[:}}])",
            f"${{{key}",
            rendered,
        )
        rendered = re.sub(
            rf"\${env_key(key)}(?![A-Za-z0-9_])",
            f"${key}",
            rendered,
        )
    return rendered


def render_command_param_keys(command: str, resolved_params: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in resolved_params:
        if re.search(rf"\$\{{param:{re.escape(key)}(?:[^}}]*)\}}", command) or re.search(rf"\$\{{{re.escape(key)}(?=[:}}])", command) or re.search(
            rf"\${re.escape(key)}(?![A-Za-z0-9_])",
            command,
        ):
            keys.append(key)
    return keys


def execute_optional_render_command(
    template: TemplateSpec,
    resolved_params: dict[str, Any],
    instance_id: str,
    project_obj: Project | None,
    output_dir: Path,
    *,
    verbose: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Any, Any] | None:
    if template.render_command is None:
        return None
    env = os.environ.copy()
    env["LINKAR_OUTPUT_DIR"] = "."
    env["LINKAR_RESULTS_DIR"] = "./results"
    env["LINKAR_INSTANCE_ID"] = instance_id
    env["LINKAR_TEMPLATE_DIR"] = str(output_dir)
    env["LINKAR_TEMPLATE_ID"] = template.id
    if template.pack_root is not None:
        env["LINKAR_PACK_ROOT"] = str(template.pack_root)
    if project_obj is not None:
        env["LINKAR_PROJECT_DIR"] = str(project_obj.root)
    for key, value in sorted(resolved_params.items()):
        formatted = format_env_value(value)
        env[env_key(key)] = formatted
        env[key] = formatted

    command = resolve_render_command(
        template.render_command,
        resolved_params,
        instance_id,
        project_obj,
    )
    return execute_subprocess(["bash", "-lc", command], cwd=output_dir, env=env, verbose=verbose)


def write_render_script(
    script_path: Path,
    template: TemplateSpec,
    resolved_params: dict[str, Any],
    instance_id: str,
    project_obj: Project | None,
    output_dir: Path,
) -> Path:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        '',
        'expected_dir="$(cd "$(dirname "$0")" && pwd)"',
        'if [[ "$PWD" != "$expected_dir" ]]; then',
        '  echo "Run ./run.sh from inside ${expected_dir}" >&2',
        "  exit 1",
        "fi",
        'mkdir -p "./results"',
    ]
    if template.run_command is not None:
        rendered_command = resolve_render_command(template.run_command, resolved_params, instance_id, project_obj)
        used_keys = render_command_param_keys(rendered_command, resolved_params)
        if used_keys:
            lines.extend(
                [
                    "",
                    "# Editable values",
                ]
            )
        for key in used_keys:
            value = resolved_params[key]
            lines.append(f"{key}={shlex.quote(format_env_value(value))}")
        if used_keys:
            lines.extend(
                [
                    "",
                    "# Execution",
                ]
            )
        lines.append(rendered_command)
    else:
        entry_name = template.run_entry or "run.sh"
        if entry_name == "run.sh":
            staged_entry = output_dir / "run.sh"
            return render_entry_script(
                staged_entry,
                template,
                resolved_params,
                instance_id,
                project_obj,
            )
        lines.extend(
            [
                'export LINKAR_OUTPUT_DIR="."',
                'export LINKAR_RESULTS_DIR="./results"',
                f"export LINKAR_INSTANCE_ID={shlex.quote(instance_id)}",
            ]
        )
        if template.pack_root is not None:
            lines.append(f"export LINKAR_PACK_ROOT={shlex.quote(str(template.pack_root))}")
        if project_obj is not None:
            lines.append(f"export LINKAR_PROJECT_DIR={shlex.quote(str(project_obj.root))}")
        for key, value in sorted(resolved_params.items()):
            lines.append(f"export {env_key(key)}={shlex.quote(format_env_value(value))}")
        lines.append(f'exec "./{entry_name}"')
    script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def localized_render_path(
    output_dir: Path,
    param_name: str,
    source_path: Path,
    *,
    index: int | None = None,
) -> Path:
    candidate_name = source_path.name
    candidate = output_dir / candidate_name
    if index is None:
        return candidate
    if candidate.exists():
        prefix = f"{param_name}_{index}" if index is not None else param_name
        candidate = output_dir / f"{prefix}_{candidate_name}"
    return candidate


def localize_render_params(
    template: TemplateSpec,
    resolved_params: dict[str, Any],
    param_provenance: dict[str, dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    localized = dict(resolved_params)
    for key, spec in template.params.items():
        provenance = param_provenance.get(key) or {}
        if provenance.get("source") != "binding":
            continue
        param_type = (spec or {}).get("type", "str")
        value = localized.get(key)
        if param_type == "path" and isinstance(value, str):
            source_path = Path(value)
            if source_path.is_file():
                target = localized_render_path(output_dir, key, source_path)
                shutil.copy2(source_path, target)
                localized[key] = f"./{target.name}"
        elif param_type == "list[path]" and isinstance(value, list):
            localized_items: list[str] = []
            changed = False
            for idx, item in enumerate(value, start=1):
                source_path = Path(item)
                if source_path.is_file():
                    target = localized_render_path(output_dir, key, source_path, index=idx)
                    shutil.copy2(source_path, target)
                    localized_items.append(f"./{target.name}")
                    changed = True
                else:
                    localized_items.append(item)
            if changed:
                localized[key] = localized_items
    return localized


def can_reuse_render_bundle(output_dir: Path) -> bool:
    return (output_dir / "run.sh").exists() and (output_dir / ".linkar" / "meta.json").exists()


def load_existing_render_bundle_context(output_dir: Path) -> tuple[str, dict[str, Any], dict[str, Any], list[dict[str, Any]], str | Path | None]:
    meta_path = output_dir / ".linkar" / "meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    instance_id = metadata.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id:
        raise ProjectValidationError(f"Run metadata missing required field 'instance_id': {meta_path}")
    params = metadata.get("params") if isinstance(metadata.get("params"), dict) else {}
    provenance = metadata.get("param_provenance") if isinstance(metadata.get("param_provenance"), dict) else {}
    warnings = metadata.get("warnings") if isinstance(metadata.get("warnings"), list) else []
    binding = metadata.get("binding")
    binding_ref = binding.get("ref") if isinstance(binding, dict) else None
    return instance_id, params, provenance, warnings, binding_ref


def prepare_template_execution(
    template_ref: str | Path,
    params: dict[str, Any] | None,
    project: str | Path | Project | None,
    outdir: str | Path | None,
    pack_refs: str | Path | list[str | Path] | None,
    binding_ref: str | Path | None,
    *,
    include_template_spec: bool = True,
    action: str = "run",
    refresh: bool = False,
) -> tuple[
    Project | None,
    TemplateSpec,
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    str | Path | None,
    str,
    Path,
    Path,
    Path,
    dict[str, Any] | None,
    dict[str, str],
]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    configured_entries, active_entry = combined_configured_pack_entries(project_obj)
    explicit_pack_assets = resolve_asset_refs(pack_refs)
    combined_pack_assets = unique_assets(
        explicit_pack_assets + [entry.asset for entry in configured_entries]
    )
    preferred_pack_ref = preferred_pack_ref_for_assets(explicit_pack_assets, active_entry)
    template = load_template(
        template_ref,
        pack_assets=combined_pack_assets,
        preferred_pack_ref=preferred_pack_ref,
    )
    selected_binding_ref = normalize_binding_ref(binding_ref)
    if selected_binding_ref is None and template.pack_root is not None:
        for entry in configured_entries:
            if entry.asset.root == template.pack_root:
                selected_binding_ref = normalize_binding_ref(entry.binding)
                break
    selected_binding_ref = infer_default_binding_ref(template, selected_binding_ref, project_obj)
    reuse_existing_render_bundle = False
    existing_output_dir: Path | None = None
    if (
        action == "run"
        and project_obj is not None
        and template.run_mode == "render"
        and outdir is None
    ):
        candidate_output_dir = determine_render_outdir(template, project_obj, None, "preview")
        if (
            can_reuse_render_bundle(candidate_output_dir)
            and not refresh
            and not params
            and binding_ref is None
        ):
            reuse_existing_render_bundle = True
            existing_output_dir = candidate_output_dir

    if reuse_existing_render_bundle and existing_output_dir is not None:
        resolved_params: dict[str, Any]
        param_provenance: dict[str, Any]
        warnings: list[dict[str, Any]]
        instance_id: str
        (
            instance_id,
            resolved_params,
            param_provenance,
            warnings,
            existing_binding_ref,
        ) = load_existing_render_bundle_context(existing_output_dir)
        if selected_binding_ref is None and existing_binding_ref is not None:
            selected_binding_ref = existing_binding_ref
        outdir_provenance: dict[str, Any] | None = None
        output_dir = existing_output_dir
        display_dir = output_dir
        linkar_dir = output_dir / ".linkar"

        ensure_required_tools_available(template)

        env = os.environ.copy()
        for key, value in resolved_params.items():
            env[env_key(key)] = format_env_value(value)
        env["LINKAR_OUTPUT_DIR"] = str(output_dir)
        env["LINKAR_RESULTS_DIR"] = str(output_dir / "results")
        env["LINKAR_INSTANCE_ID"] = instance_id
        if template.pack_root is not None:
            env["LINKAR_PACK_ROOT"] = str(template.pack_root)
        if project_obj is not None:
            env["LINKAR_PROJECT_DIR"] = str(project_obj.root)

        return (
            project_obj,
            template,
            resolved_params,
            param_provenance,
            warnings,
            selected_binding_ref,
            instance_id,
            output_dir,
            display_dir,
            linkar_dir,
            outdir_provenance,
            env,
        )

    resolved_params, param_provenance, warnings = resolve_params_detailed_with_warnings(
        template,
        cli_params=params,
        project=project_obj,
        binding_ref=selected_binding_ref,
    )
    outdir_provenance: dict[str, Any] | None = {"source": "cli"} if outdir is not None else None
    selected_outdir = outdir
    if outdir is None:
        binding_root, binding_data = load_binding_config(selected_binding_ref, template.pack_root)
        has_bound_outdir, bound_outdir, bound_outdir_provenance = resolve_bound_outdir(
            template,
            binding_root,
            binding_data,
            project_obj,
            resolved_params,
            warnings,
        )
        if has_bound_outdir:
            selected_outdir = bound_outdir
            outdir_provenance = bound_outdir_provenance
    instance_id = next_instance_id(template.id, project_obj)
    run_uses_visible_project_dir = (
        action == "run"
        and project_obj is not None
        and template.run_mode == "render"
        and selected_outdir is None
    )
    if action == "render" or run_uses_visible_project_dir:
        output_dir = determine_render_outdir(template, project_obj, selected_outdir, instance_id)
    else:
        output_dir = determine_outdir(template, project_obj, selected_outdir, instance_id)
    display_dir = (
        determine_project_alias_dir(template, project_obj)
        if action != "render" and not run_uses_visible_project_dir and selected_outdir is None
        else output_dir
    )
    if display_dir is None:
        display_dir = output_dir

    ensure_required_tools_available(template)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results").mkdir(exist_ok=True)
    linkar_dir = output_dir / ".linkar"
    linkar_dir.mkdir(exist_ok=True)

    env = os.environ.copy()
    for key, value in resolved_params.items():
        env[env_key(key)] = format_env_value(value)
    env["LINKAR_OUTPUT_DIR"] = str(output_dir)
    env["LINKAR_RESULTS_DIR"] = str(output_dir / "results")
    env["LINKAR_INSTANCE_ID"] = instance_id
    if template.pack_root is not None:
        env["LINKAR_PACK_ROOT"] = str(template.pack_root)
    if project_obj is not None:
        env["LINKAR_PROJECT_DIR"] = str(project_obj.root)

    stage_runtime_bundle(template, output_dir, include_template_spec=include_template_spec)

    return (
        project_obj,
        template,
        resolved_params,
        param_provenance,
        warnings,
        selected_binding_ref,
        instance_id,
        output_dir,
        display_dir,
        linkar_dir,
        outdir_provenance,
        env,
    )


def build_run_command(
    template: TemplateSpec,
    output_dir: Path,
    resolved_params: dict[str, Any],
    instance_id: str,
    project_obj: Project | None,
) -> list[str]:
    if template.run_command is not None:
        return [
            str(
                render_launcher(
                    output_dir / "run.sh",
                    template,
                    output_dir,
                    resolved_params,
                    instance_id,
                    project_obj,
                ).resolve()
            )
        ]
    if should_render_shell_wrapper(template):
        return [
            str(
                render_launcher(
                    output_dir / "run.sh",
                    template,
                    output_dir,
                    resolved_params,
                    instance_id,
                    project_obj,
                    target_entry="script.sh",
                ).resolve()
            )
        ]
    if template.run_entry is None:
        raise ExecutionError(f"Template '{template.id}' is missing a runnable entrypoint")
    return [str((output_dir / template.run_entry).resolve())]


def execute_subprocess(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    verbose: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Any, Any]:
    started_at = utc_now()
    if not verbose:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        finished_at = utc_now()
        return completed, started_at, finished_at

    if should_use_pty_for_verbose_output():
        master_fd, slave_fd = pty.openpty()
        os.set_blocking(master_fd, False)
        stdout_chunks: list[str] = []
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                close_fds=True,
            )
        finally:
            os.close(slave_fd)

        while True:
            process_exited = process.poll() is not None
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            had_output = False
            if ready:
                while True:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except BlockingIOError:
                        break
                    except OSError:
                        chunk = b""
                    if not chunk:
                        break
                    had_output = True
                    text = chunk.decode(errors="replace")
                    stdout_chunks.append(text)
                    sys.stdout.write(text)
                    sys.stdout.flush()
            if process_exited and not had_output:
                break

        os.close(master_fd)

        finished_at = utc_now()
        completed = subprocess.CompletedProcess(
            args=command,
            returncode=process.wait(),
            stdout="".join(stdout_chunks),
            stderr="",
        )
        return completed, started_at, finished_at

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def pump(stream: Any, sink: Any, chunks: list[str]) -> None:
        if stream is None:
            return
        try:
            for line in stream:
                chunks.append(line)
                sink.write(line)
                sink.flush()
        finally:
            stream.close()

    stdout_thread = threading.Thread(target=pump, args=(process.stdout, sys.stdout, stdout_chunks))
    stderr_thread = threading.Thread(target=pump, args=(process.stderr, sys.stderr, stderr_chunks))
    stdout_thread.start()
    stderr_thread.start()
    returncode = process.wait()
    stdout_thread.join()
    stderr_thread.join()

    finished_at = utc_now()
    completed = subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
    )
    return completed, started_at, finished_at


def should_use_pty_for_verbose_output() -> bool:
    return (
        os.name == "posix"
        and sys.stdin.isatty()
        and sys.stdout.isatty()
        and sys.stderr.isatty()
    )


def update_project(
    project: Project,
    template: TemplateSpec,
    instance_id: str,
    outdir: Path,
    display_outdir: Path,
    params: dict[str, Any],
    outputs: dict[str, Any],
    meta_path: Path,
    *,
    state: str,
    adopted: bool = False,
    replace_existing: bool = False,
) -> None:
    from linkar.runtime.shared import save_yaml

    relative_path = os.path.relpath(display_outdir, project.root)
    relative_history_path = os.path.relpath(outdir, project.root)
    relative_meta = os.path.relpath(meta_path, project.root)
    entry = {
        "id": template.id,
        "template_version": template.version,
        "instance_id": instance_id,
        "path": relative_path,
        "history_path": relative_history_path,
        "params": params,
        "outputs": outputs,
        "meta": relative_meta,
        "state": state,
    }
    if adopted:
        entry["adopted"] = True
    if template.pack_ref is not None:
        pack_entry = find_project_pack_entry(project, template.pack_ref)
        entry["pack"] = {
            "id": pack_entry.id if pack_entry is not None else derive_pack_id(template.pack_ref),
            "ref": template.pack_ref,
            "revision": template.pack_revision,
        }
    templates = project.data.setdefault("templates", [])
    if replace_existing:
        for index, existing in enumerate(templates):
            if existing.get("meta") == relative_meta:
                templates[index] = entry
                save_yaml(project.root / "project.yaml", project.data)
                return
    templates.append(entry)
    save_yaml(project.root / "project.yaml", project.data)


def project_path_reference(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return str(resolved)
    return os.path.relpath(resolved, project_root)


def build_adopted_project_entry(
    project: Project,
    metadata: dict[str, Any],
    *,
    outdir: Path,
    meta_path: Path,
) -> dict[str, Any]:
    instance_id = metadata.get("instance_id")
    template_id = metadata.get("template")
    if not isinstance(instance_id, str) or not instance_id:
        raise ProjectValidationError(f"Run metadata missing required field 'instance_id': {meta_path}")
    if not isinstance(template_id, str) or not template_id:
        raise ProjectValidationError(f"Run metadata missing required field 'template': {meta_path}")
    params = metadata.get("params")
    outputs = metadata.get("outputs")
    if params is None or not isinstance(params, dict):
        raise ProjectValidationError(f"Run metadata field 'params' must be a mapping: {meta_path}")
    if outputs is None or not isinstance(outputs, dict):
        raise ProjectValidationError(f"Run metadata field 'outputs' must be a mapping: {meta_path}")

    entry = {
        "id": template_id,
        "template_version": metadata.get("template_version"),
        "instance_id": instance_id,
        "path": str(outdir.resolve()),
        "history_path": str(outdir.resolve()),
        "params": params,
        "outputs": outputs,
        "meta": project_path_reference(meta_path, project.root),
        "state": infer_metadata_state(metadata, meta_path),
        "adopted": True,
    }
    pack = metadata.get("pack")
    if isinstance(pack, dict) and pack.get("ref"):
        entry["pack"] = {
            "id": derive_pack_id(pack["ref"]),
            "ref": pack["ref"],
            "revision": pack.get("revision"),
        }
    binding = metadata.get("binding")
    if isinstance(binding, dict) and binding.get("ref"):
        entry["binding"] = {"ref": binding["ref"]}
    return entry


def infer_metadata_state(metadata: dict[str, Any], meta_path: Path) -> str:
    runtime_path = meta_path.with_name("runtime.json")
    if runtime_path.exists():
        try:
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            runtime = {}
        success = runtime.get("success")
        if success is True:
            run_mode = metadata.get("run_mode")
            if run_mode == "render":
                return "rendered"
            return "completed"
        if success is False:
            return "failed"
    if metadata.get("run_mode") == "render":
        return "rendered"
    return "completed"


def adopt_run_into_project(
    run_ref: str | Path,
    *,
    project: str | Path | Project | None = None,
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError(
            "Adopting a run requires an active project. Run it inside a directory containing project.yaml or pass --project PATH."
        )

    refreshed = collect_run_outputs(run_ref)
    meta_path = Path(refreshed["meta"]).resolve()
    outdir = Path(refreshed["outdir"]).resolve()
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    entry = build_adopted_project_entry(project_obj, metadata, outdir=outdir, meta_path=meta_path)

    templates = project_obj.data.setdefault("templates", [])
    for existing in templates:
        if existing.get("instance_id") == entry["instance_id"]:
            raise ProjectValidationError(f"Run instance already exists in project: {entry['instance_id']}")
        if existing.get("meta") == entry["meta"]:
            raise ProjectValidationError(f"Run metadata already exists in project: {entry['meta']}")

    templates.append(entry)
    save_yaml(project_obj.root / "project.yaml", project_obj.data)
    return entry


def sync_project_alias(output_dir: Path, alias_dir: Path) -> None:
    if alias_dir.exists() or alias_dir.is_symlink():
        if alias_dir.is_symlink() or alias_dir.is_file():
            alias_dir.unlink()
        else:
            raise ProjectValidationError(
                f"Cannot create project alias at {alias_dir}: path already exists and is not a symlink"
            )
    alias_dir.symlink_to(output_dir, target_is_directory=True)


def list_project_runs(project: str | Path | Project | None = None) -> list[dict[str, Any]]:
    project_obj = _load_project_for_runs(project, action="Listing project runs")
    return list(project_obj.data.get("templates", []))


def _resolve_project_entry_path(project_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _entry_history_path(project_root: Path, entry: dict[str, Any]) -> Path | None:
    return _resolve_project_entry_path(project_root, entry.get("history_path") or entry.get("path"))


def _entry_visible_path(project_root: Path, entry: dict[str, Any]) -> Path | None:
    return _resolve_project_entry_path(project_root, entry.get("path"))


def _entry_meta_path(project_root: Path, entry: dict[str, Any]) -> Path | None:
    return _resolve_project_entry_path(project_root, entry.get("meta"))


def _load_project_for_runs(project: str | Path | Project | None, *, action: str) -> Project:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError(
            f"{action} requires an active project. Run it inside a directory containing project.yaml or pass --project PATH."
        )
    return project_obj


def _describe_project_run_match(entry: dict[str, Any]) -> str:
    instance_id = str(entry.get("instance_id") or "-")
    state = str(entry.get("state") or "-")
    path = str(entry.get("path") or "-")
    history_path = str(entry.get("history_path") or "-")
    return (
        f"{instance_id} [state={state}, path={path}, history_path={history_path}]"
    )


def _raise_ambiguous_project_run(run_ref: str | Path, entries: list[dict[str, Any]]) -> None:
    matching_instances = "; ".join(_describe_project_run_match(entry) for entry in entries)
    raise ProjectValidationError(
        f"Run reference '{run_ref}' is ambiguous in this project. Matching runs: {matching_instances}. "
        "Use an instance id, a run path, or a .linkar/meta.json path."
    )


def select_project_runs(
    run_ref: str | Path,
    *,
    project: str | Path | Project | None = None,
) -> list[dict[str, Any]]:
    project_obj = _load_project_for_runs(project, action="Resolving a run")
    templates = project_obj.data.setdefault("templates", [])
    run_ref_str = str(run_ref)

    exact_instance_matches = [entry for entry in templates if entry.get("instance_id") == run_ref_str]
    if exact_instance_matches:
        return exact_instance_matches

    template_matches = [entry for entry in templates if entry.get("id") == run_ref_str]
    is_bare_name = isinstance(run_ref, str) and not Path(run_ref).is_absolute() and os.sep not in run_ref
    ref_path = Path(run_ref).expanduser()
    resolved_ref = None if is_bare_name and template_matches else (ref_path.resolve() if ref_path.exists() else None)
    if template_matches:
        if len(template_matches) > 1:
            _raise_ambiguous_project_run(run_ref, template_matches)
        return template_matches

    if resolved_ref is not None:
        path_matches: list[dict[str, Any]] = []
        for entry in templates:
            candidates = {
                candidate
                for candidate in (
                    _entry_meta_path(project_obj.root, entry),
                    _entry_history_path(project_obj.root, entry),
                    _entry_visible_path(project_obj.root, entry),
                )
                if candidate is not None
            }
            history_path = _entry_history_path(project_obj.root, entry)
            if history_path is not None:
                candidates.add((history_path / ".linkar" / "meta.json").resolve())
            if resolved_ref in candidates:
                path_matches.append(entry)
        if path_matches:
            if len(path_matches) > 1:
                _raise_ambiguous_project_run(run_ref, path_matches)
            return path_matches

    raise ProjectValidationError(f"Run not found in project: {run_ref}")


def resolve_project_run(run_ref: str | Path, *, project: str | Path | Project | None = None) -> dict[str, Any]:
    matches = select_project_runs(run_ref, project=project)
    return matches[0]


def latest_project_run(run_ref: str | Path, *, project: str | Path | Project | None = None) -> dict[str, Any]:
    project_obj = _load_project_for_runs(project, action="Resolving the latest run")
    templates = project_obj.data.setdefault("templates", [])
    run_ref_str = str(run_ref)

    exact_instance_matches = [entry for entry in templates if entry.get("instance_id") == run_ref_str]
    if exact_instance_matches:
        return exact_instance_matches[-1]

    template_matches = [entry for entry in templates if entry.get("id") == run_ref_str]
    if template_matches:
        return template_matches[-1]

    resolved_ref = Path(run_ref).expanduser().resolve() if Path(run_ref).expanduser().exists() else None
    if resolved_ref is not None:
        path_matches: list[dict[str, Any]] = []
        for entry in templates:
            candidates = {
                candidate
                for candidate in (
                    _entry_meta_path(project_obj.root, entry),
                    _entry_history_path(project_obj.root, entry),
                    _entry_visible_path(project_obj.root, entry),
                )
                if candidate is not None
            }
            history_path = _entry_history_path(project_obj.root, entry)
            if history_path is not None:
                candidates.add((history_path / ".linkar" / "meta.json").resolve())
            if resolved_ref in candidates:
                path_matches.append(entry)
        if path_matches:
            return path_matches[-1]

    raise ProjectValidationError(f"Run not found in project: {run_ref}")


def _stale_duplicate_path_runs(
    project: Project,
    *,
    display_outdir: Path,
    current_meta_path: Path,
) -> list[dict[str, Any]]:
    relative_path = os.path.relpath(display_outdir, project.root)
    relative_meta = os.path.relpath(current_meta_path, project.root)
    duplicates: list[dict[str, Any]] = []
    for entry in project.data.get("templates", []):
        if entry.get("path") != relative_path:
            continue
        if entry.get("meta") == relative_meta:
            continue
        duplicates.append(entry)
    return duplicates


def prune_project_runs(
    *,
    project: str | Path | Project | None = None,
    delete_files: bool = True,
    dry_run: bool = False,
    template_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError(
            "Pruning runs requires an active project. Run it inside a directory containing project.yaml or pass --project PATH."
        )

    templates = list(project_obj.data.setdefault("templates", []))
    visible_key_last_index: dict[str, int] = {}
    visible_key_counts: dict[str, int] = {}

    for index, entry in enumerate(templates):
        if template_id and str(entry.get("id") or "") != template_id:
            continue
        visible_path = _entry_visible_path(project_obj.root, entry)
        if visible_path is None:
            continue
        key = str(visible_path)
        visible_key_last_index[key] = index
        visible_key_counts[key] = visible_key_counts.get(key, 0) + 1

    prune_indices: set[int] = set()
    for index, entry in enumerate(templates):
        if template_id and str(entry.get("id") or "") != template_id:
            continue
        visible_path = _entry_visible_path(project_obj.root, entry)
        if visible_path is None:
            continue
        key = str(visible_path)
        if visible_key_counts.get(key, 0) > 1 and visible_key_last_index.get(key) != index:
            prune_indices.add(index)

    if not prune_indices:
        return {
            "removed_runs": [],
            "deleted_paths": [],
            "skipped_paths": [],
            "missing_paths": [],
            "delete_files": delete_files,
            "dry_run": dry_run,
            "template_id": template_id or "",
        }

    kept_templates = [entry for index, entry in enumerate(templates) if index not in prune_indices]
    removed_entries = [dict(templates[index]) for index in sorted(prune_indices)]

    protected_paths: set[str] = set()
    for entry in kept_templates:
        for resolved in (
            _entry_history_path(project_obj.root, entry),
            _entry_visible_path(project_obj.root, entry),
        ):
            if resolved is not None:
                protected_paths.add(str(resolved))

    deleted_paths: list[str] = []
    skipped_paths: list[str] = []
    missing_paths: list[str] = []
    seen_history_paths: set[str] = set()

    for entry in removed_entries:
        history_path = _entry_history_path(project_obj.root, entry)
        if history_path is None:
            continue
        history_path_str = str(history_path)
        if history_path_str in seen_history_paths:
            continue
        seen_history_paths.add(history_path_str)
        if history_path_str in protected_paths:
            skipped_paths.append(history_path_str)
            continue
        if not delete_files:
            continue
        if dry_run:
            deleted_paths.append(history_path_str)
            continue
        if history_path.exists():
            if history_path.is_symlink() or history_path.is_file():
                history_path.unlink()
            else:
                shutil.rmtree(history_path)
            deleted_paths.append(history_path_str)
        else:
            missing_paths.append(history_path_str)

    if not dry_run:
        project_obj.data["templates"] = kept_templates
        save_yaml(project_obj.root / "project.yaml", project_obj.data)

    return {
        "removed_runs": [
            {
                "id": entry.get("id"),
                "instance_id": entry.get("instance_id"),
                "path": entry.get("path"),
                "history_path": entry.get("history_path"),
            }
            for entry in removed_entries
        ],
        "deleted_paths": deleted_paths,
        "skipped_paths": skipped_paths,
        "missing_paths": missing_paths,
        "delete_files": delete_files,
        "dry_run": dry_run,
        "template_id": template_id or "",
    }


def remove_project_run(
    run_ref: str | Path,
    *,
    project: str | Path | Project | None = None,
    delete_files: bool = False,
) -> dict[str, Any]:
    project_obj = _load_project_for_runs(project, action="Removing a run")

    templates = project_obj.data.setdefault("templates", [])
    target_entry = resolve_project_run(run_ref, project=project_obj)
    kept: list[dict[str, Any]] = []
    removed: dict[str, Any] | None = None

    for entry in templates:
        if entry is target_entry and removed is None:
            removed = dict(entry)
            entry_history_path = _entry_history_path(project_obj.root, entry)
            entry_meta_path = _entry_meta_path(project_obj.root, entry)
            removed["_history_path_resolved"] = str(entry_history_path) if entry_history_path is not None else None
            removed["_meta_path_resolved"] = str(entry_meta_path) if entry_meta_path is not None else None
            continue
        kept.append(entry)

    if removed is None:
        raise ProjectValidationError(f"Run not found in project: {run_ref}")

    project_obj.data["templates"] = kept
    save_yaml(project_obj.root / "project.yaml", project_obj.data)

    if delete_files:
        history_path_str = removed.get("_history_path_resolved")
        if not isinstance(history_path_str, str) or not history_path_str:
            raise ProjectValidationError(f"Run '{removed.get('instance_id')}' does not record a removable history path")
        history_path = Path(history_path_str)
        if history_path.exists():
            if history_path.is_symlink() or history_path.is_file():
                history_path.unlink()
            else:
                shutil.rmtree(history_path)

    return {
        "id": removed.get("id"),
        "instance_id": removed.get("instance_id"),
        "path": removed.get("path"),
        "history_path": removed.get("history_path"),
        "deleted_files": delete_files,
    }


def resolve_project_assets(project: str | Path | Project | None = None) -> list[dict[str, Any]]:
    project_obj = _load_project_for_runs(project, action="Listing project assets")
    assets: list[dict[str, Any]] = []
    for entry in project_pack_entries(project_obj):
        assets.append(
            {
                "pack_id": entry.id,
                "pack_ref": entry.asset.ref,
                "pack_root": str(entry.asset.root),
                "pack_revision": entry.asset.revision,
                "binding": entry.binding,
                "active": project_obj.data.get("active_pack") == entry.id or (
                    project_obj.data.get("active_pack") is None and len(project_obj.data.get("packs", [])) == 1
                ),
            }
        )
    return assets


def inspect_run(run_ref: str | Path, project: str | Path | Project | None = None) -> dict[str, Any]:
    ref_path = Path(run_ref)
    if ref_path.exists():
        target = ref_path.resolve()
        meta_path = target if target.is_file() else target / ".linkar" / "meta.json"
        if not meta_path.exists():
            raise ProjectValidationError(f"Run metadata not found: {meta_path}")
        with meta_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    project_obj = _load_project_for_runs(project, action="Inspecting a run")
    entry = resolve_project_run(run_ref, project=project_obj)
    meta_path = _entry_meta_path(project_obj.root, entry)
    if meta_path is None or not meta_path.exists():
        raise ProjectValidationError(f"Run metadata not found: {run_ref}")
    with meta_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def inspect_runtime(run_ref: str | Path, project: str | Path | Project | None = None) -> dict[str, Any]:
    ref_path = Path(run_ref)
    if ref_path.exists():
        target = ref_path.resolve()
        runtime_path = target if target.is_file() else target / ".linkar" / "runtime.json"
        if not runtime_path.exists():
            raise ProjectValidationError(f"Run runtime not found: {runtime_path}")
        with runtime_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    project_obj = _load_project_for_runs(project, action="Inspecting run runtime")
    entry = resolve_project_run(run_ref, project=project_obj)
    meta_path = _entry_meta_path(project_obj.root, entry)
    if meta_path is None:
        raise ProjectValidationError(f"Run runtime not found: {run_ref}")
    runtime_path = meta_path.with_name("runtime.json")
    if not runtime_path.exists():
        raise ProjectValidationError(f"Run runtime not found: {runtime_path}")
    with runtime_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_run_meta_path(run_ref: str | Path, project: str | Path | Project | None = None) -> Path:
    ref_path = Path(run_ref)
    if ref_path.exists():
        target = ref_path.resolve()
        meta_path = target if target.is_file() else target / ".linkar" / "meta.json"
        if not meta_path.exists():
            raise ProjectValidationError(f"Run metadata not found: {meta_path}")
        return meta_path

    project_obj = _load_project_for_runs(project, action="Resolving run metadata")
    entry = resolve_project_run(run_ref, project=project_obj)
    meta_path = _entry_meta_path(project_obj.root, entry)
    if meta_path is not None and meta_path.exists():
        return meta_path
    raise ProjectValidationError(f"Run not found: {run_ref}")


def maybe_update_project_outputs(meta_path: Path, outputs: dict[str, Any], project: Project | None) -> bool:
    if project is None:
        return False
    from linkar.runtime.shared import save_yaml

    relative_meta = os.path.relpath(meta_path, project.root)
    templates = project.data.get("templates", [])
    changed = False
    for entry in templates:
        if entry.get("meta") == relative_meta:
            entry["outputs"] = outputs
            changed = True
            break
    if changed:
        save_yaml(project.root / "project.yaml", project.data)
    return changed


def collect_run_outputs(
    run_ref: str | Path,
    project: str | Path | Project | None = None,
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project

    meta_path = resolve_run_meta_path(run_ref, project=project_obj)
    outdir = meta_path.parent.parent
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    declared_outputs = metadata.get("declared_outputs") or {"results_dir": {}}
    outputs = collect_outputs_from_declared(declared_outputs, outdir)
    metadata["outputs"] = outputs
    metadata["collected_at"] = utc_now().isoformat()
    write_json(meta_path, metadata)
    project_updated = maybe_update_project_outputs(meta_path, outputs, project_obj)
    return {
        "run_ref": str(run_ref),
        "outdir": str(outdir),
        "meta": str(meta_path),
        "outputs": outputs,
        "project_updated": project_updated,
        "project_path": str(project_obj.root) if project_obj is not None else "",
    }


def test_template(
    template_ref: str | Path,
    project: str | Path | Project | None = None,
    outdir: str | Path | None = None,
    pack_refs: str | Path | list[str | Path] | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project

    configured_entries, active_entry = combined_configured_pack_entries(project_obj)
    explicit_pack_assets = resolve_asset_refs(pack_refs)
    combined_pack_assets = unique_assets(
        explicit_pack_assets + [entry.asset for entry in configured_entries]
    )
    preferred_pack_ref = preferred_pack_ref_for_assets(explicit_pack_assets, active_entry)
    template = load_template(
        template_ref,
        pack_assets=combined_pack_assets,
        preferred_pack_ref=preferred_pack_ref,
    )

    test_shell = template.root / "test.sh"
    test_python = template.root / "test.py"
    if test_shell.exists() and test_python.exists():
        raise TemplateValidationError(
            f"Both test.sh and test.py exist in {template.root}; keep only one test entrypoint"
        )
    if test_shell.exists():
        command = [str(test_shell.resolve())]
    elif test_python.exists():
        command = [sys.executable, str(test_python.resolve())]
    else:
        raise TemplateValidationError(f"test.sh or test.py not found in {template.root}")

    test_dir = determine_test_dir(template, project_obj, outdir)
    test_dir.mkdir(parents=True, exist_ok=True)
    results_dir = test_dir / "results"
    results_dir.mkdir(exist_ok=True)
    linkar_dir = test_dir / ".linkar"
    linkar_dir.mkdir(exist_ok=True)

    env = os.environ.copy()
    env["LINKAR_TEMPLATE_DIR"] = str(template.root)
    env["LINKAR_TEMPLATE_ID"] = template.id
    env["LINKAR_TEST_DIR"] = str(test_dir)
    env["LINKAR_RESULTS_DIR"] = str(results_dir)
    env["LINKAR_TESTDATA_DIR"] = str((template.root / "testdata").resolve())
    if template.pack_root is not None:
        env["LINKAR_PACK_ROOT"] = str(template.pack_root)
    if project_obj is not None:
        env["LINKAR_PROJECT_DIR"] = str(project_obj.root)

    completed, started_at, finished_at = execute_subprocess(
        command,
        cwd=template.root,
        env=env,
        verbose=verbose,
    )

    runtime_path = linkar_dir / "runtime.json"
    write_json(
        runtime_path,
        {
            "command": command,
            "cwd": str(template.root),
            "returncode": completed.returncode,
            "success": completed.returncode == 0,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )

    if completed.returncode != 0:
        raise ExecutionError(
            f"Template test failed with exit code {completed.returncode}. See {runtime_path}"
        )

    return {
        "template": template.id,
        "outdir": str(test_dir),
        "runtime": str(runtime_path),
    }


def run_template(
    template_ref: str | Path,
    params: dict[str, Any] | None = None,
    project: str | Path | Project | None = None,
    outdir: str | Path | None = None,
    pack_refs: str | Path | list[str | Path] | None = None,
    binding_ref: str | Path | None = None,
    verbose: bool = False,
    refresh: bool = False,
) -> dict[str, Any]:
    (
        project_obj,
        template,
        resolved_params,
        param_provenance,
        warnings,
        selected_binding_ref,
        instance_id,
        output_dir,
        display_dir,
        linkar_dir,
        outdir_provenance,
        env,
    ) = prepare_template_execution(
        template_ref,
        params,
        project,
        outdir,
        pack_refs,
        binding_ref,
        refresh=refresh,
    )

    meta_path = linkar_dir / "meta.json"
    if project_obj is not None and template.run_mode == "render" and output_dir == display_dir:
        stale_runs = _stale_duplicate_path_runs(
            project_obj,
            display_outdir=display_dir,
            current_meta_path=meta_path,
        )
        if stale_runs:
            stale_instances = ", ".join(
                str(entry.get("instance_id"))
                for entry in stale_runs
                if entry.get("instance_id")
            )
            warnings.append(
                {
                    "template": template.id,
                    "message": "Older project entries still reference the same visible path.",
                    "fallback": f"Current run remains active at {display_dir}",
                    "action": (
                        f"Run 'linkar project prune --template {template.id}' to remove stale history"
                        + (f" ({stale_instances})" if stale_instances else "")
                    ),
                }
            )

    command = build_run_command(template, output_dir, resolved_params, instance_id, project_obj)
    completed, started_at, finished_at = execute_subprocess(
        command,
        cwd=output_dir,
        env=env,
        verbose=verbose,
    )

    runtime_path = linkar_dir / "runtime.json"
    write_json(
        runtime_path,
        {
            "command": command,
            "cwd": str(output_dir),
            "returncode": completed.returncode,
            "success": completed.returncode == 0,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "warnings": warnings,
        },
    )

    outputs = collect_outputs(template, output_dir)
    state = "completed" if completed.returncode == 0 else "failed"
    write_json(
        meta_path,
        {
            "template": template.id,
            "template_version": template.version,
            "instance_id": instance_id,
            "params": resolved_params,
            "param_provenance": param_provenance,
            "declared_outputs": declared_outputs_or_default(template.outputs),
            "outputs": outputs,
            "software": [{"name": "linkar", "version": __version__}],
            "pack": (
                {"ref": template.pack_ref, "revision": template.pack_revision}
                if template.pack_root is not None
                else None
            ),
            "binding": (
                {"ref": str(selected_binding_ref)}
                if selected_binding_ref is not None
                else None
            ),
            "outdir_provenance": outdir_provenance,
            "warnings": warnings,
            "command": command,
            "timestamp": finished_at.isoformat(),
            "run_mode": "run",
            "template_run_mode": template.run_mode,
            "state": state,
        },
    )

    if project_obj is not None:
        if output_dir != display_dir:
            sync_project_alias(output_dir, display_dir)
        update_project(
            project_obj,
            template=template,
            instance_id=instance_id,
            outdir=output_dir,
            display_outdir=display_dir,
            params=resolved_params,
            outputs=outputs,
            meta_path=meta_path,
            state=state,
            replace_existing=(output_dir == display_dir),
        )

    if completed.returncode != 0:
        raise ExecutionError(
            f"Template execution failed with exit code {completed.returncode}. "
            f"See {runtime_path}"
        )

    return {
        "template": template.id,
        "instance_id": instance_id,
        "outdir": str(display_dir),
        "history_outdir": str(output_dir),
        "meta": str(meta_path),
        "runtime": str(runtime_path),
        "run_mode": "run",
        "template_run_mode": template.run_mode,
        "warnings": warnings,
    }


def render_template(
    template_ref: str | Path,
    params: dict[str, Any] | None = None,
    project: str | Path | Project | None = None,
    outdir: str | Path | None = None,
    pack_refs: str | Path | list[str | Path] | None = None,
    binding_ref: str | Path | None = None,
) -> dict[str, Any]:
    (
        project_obj,
        template,
        resolved_params,
        param_provenance,
        warnings,
        selected_binding_ref,
        instance_id,
        output_dir,
        display_dir,
        linkar_dir,
        outdir_provenance,
        _env,
    ) = prepare_template_execution(
        template_ref,
        params,
        project,
        outdir,
        pack_refs,
        binding_ref,
        include_template_spec=False,
        action="render",
    )
    resolved_params = localize_render_params(template, resolved_params, param_provenance, output_dir)

    launcher_command = [
        str(
            write_render_script(
                render_mode_launcher_path(output_dir),
                template,
                resolved_params,
                instance_id,
                project_obj,
                output_dir,
            ).resolve()
        )
    ]
    render_hook_result = execute_optional_render_command(
        template,
        resolved_params,
        instance_id,
        project_obj,
        output_dir,
        verbose=template.run_verbose_by_default,
    )
    if render_hook_result is None:
        started_at = utc_now()
        finished_at = started_at
        completed = subprocess.CompletedProcess(
            args=launcher_command,
            returncode=0,
            stdout=f"Rendered template bundle to {output_dir}\n",
            stderr="",
        )
        runtime_command: list[str] = launcher_command
    else:
        completed, started_at, finished_at = render_hook_result
        runtime_command = [
            "bash",
            "-lc",
            resolve_render_command(
                template.render_command or "",
                resolved_params,
                instance_id,
                project_obj,
            ),
        ]
        if completed.returncode == 0:
            completed = subprocess.CompletedProcess(
                args=completed.args,
                returncode=completed.returncode,
                stdout=f"Rendered template bundle to {output_dir}\n{completed.stdout or ''}",
                stderr=completed.stderr,
            )

    runtime_path = linkar_dir / "runtime.json"
    write_json(
        runtime_path,
        {
            "command": runtime_command,
            "cwd": str(output_dir),
            "returncode": completed.returncode,
            "success": completed.returncode == 0,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "warnings": warnings,
        },
    )
    if completed.returncode != 0:
        raise ExecutionError(
            f"Template render preparation failed with exit code {completed.returncode}. "
            f"See {runtime_path}"
        )

    outputs = collect_outputs(template, output_dir) if template.render_command is not None else {}

    meta_path = linkar_dir / "meta.json"
    write_json(
        meta_path,
        {
            "template": template.id,
            "template_version": template.version,
            "instance_id": instance_id,
            "params": resolved_params,
            "param_provenance": param_provenance,
            "declared_outputs": declared_outputs_or_default(template.outputs),
            "outputs": outputs,
            "software": [{"name": "linkar", "version": __version__}],
            "pack": (
                {"ref": template.pack_ref, "revision": template.pack_revision}
                if template.pack_root is not None
                else None
            ),
            "binding": (
                {"ref": str(selected_binding_ref)}
                if selected_binding_ref is not None
                else None
            ),
            "outdir_provenance": outdir_provenance,
            "warnings": warnings,
            "command": runtime_command,
            "timestamp": finished_at.isoformat(),
            "run_mode": "render",
            "template_run_mode": template.run_mode,
            "state": "rendered",
        },
    )

    if project_obj is not None:
        update_project(
            project_obj,
            template=template,
            instance_id=instance_id,
            outdir=output_dir,
            display_outdir=display_dir,
            params=resolved_params,
            outputs=outputs,
            meta_path=meta_path,
            state="rendered",
            replace_existing=True,
        )

    return {
        "template": template.id,
        "instance_id": instance_id,
        "outdir": str(display_dir),
        "history_outdir": str(output_dir),
        "meta": str(meta_path),
        "runtime": str(runtime_path),
        "run_mode": "render",
        "template_run_mode": template.run_mode,
        "warnings": warnings,
    }
