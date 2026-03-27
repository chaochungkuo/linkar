from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from linkar import __version__
from linkar.assets import resolve_asset_refs
from linkar.errors import ExecutionError, LinkarError, ProjectValidationError, TemplateValidationError
from linkar.runtime.bindings import resolve_params_detailed
from linkar.runtime.models import Project, TemplateSpec
from linkar.runtime.projects import (
    discover_project,
    find_project_pack_entry,
    get_active_pack_entry,
    load_project,
    project_pack_entries,
)
from linkar.runtime.shared import (
    derive_pack_id,
    env_key,
    format_env_value,
    normalize_binding_ref,
    preferred_pack_ref_for_assets,
    unique_assets,
    utc_now,
    write_json,
)
from linkar.runtime.templates import load_template


def next_instance_id(template_id: str, project: Project | None = None) -> str:
    if project is None:
        stamp = utc_now().strftime("%Y%m%d_%H%M%S")
        return f"{template_id}_{stamp}"

    matches = 0
    for item in project.data.get("templates", []):
        if item.get("id") == template_id:
            matches += 1
    return f"{template_id}_{matches + 1:03d}"


def determine_outdir(
    template: TemplateSpec,
    project: Project | None,
    outdir: str | Path | None,
    instance_id: str,
) -> Path:
    if outdir is not None:
        return Path(outdir).resolve()
    if project is not None:
        return (project.root / instance_id).resolve()
    return (Path.cwd() / ".linkar" / "runs" / instance_id).resolve()


def determine_test_dir(
    template: TemplateSpec,
    project: Project | None,
    outdir: str | Path | None,
) -> Path:
    if outdir is not None:
        return Path(outdir).resolve()
    stamp = utc_now().strftime("%Y%m%d_%H%M%S")
    if project is not None:
        return (project.root / ".linkar" / "tests" / f"{template.id}_{stamp}").resolve()
    return (Path.cwd() / ".linkar" / "tests" / f"{template.id}_{stamp}").resolve()


def collect_outputs(outdir: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    results_dir = outdir / "results"
    if results_dir.exists():
        outputs["results_dir"] = str(results_dir)
    return outputs


def update_project(
    project: Project,
    template: TemplateSpec,
    instance_id: str,
    outdir: Path,
    params: dict[str, Any],
    outputs: dict[str, Any],
    meta_path: Path,
) -> None:
    from linkar.runtime.shared import save_yaml

    relative_path = os.path.relpath(outdir, project.root)
    relative_meta = os.path.relpath(meta_path, project.root)
    entry = {
        "id": template.id,
        "template_version": template.version,
        "instance_id": instance_id,
        "path": relative_path,
        "params": params,
        "outputs": outputs,
        "meta": relative_meta,
    }
    if template.pack_ref is not None:
        pack_entry = find_project_pack_entry(project, template.pack_ref)
        entry["pack"] = {
            "id": pack_entry.id if pack_entry is not None else derive_pack_id(template.pack_ref),
            "ref": template.pack_ref,
            "revision": template.pack_revision,
        }
    project.data.setdefault("templates", []).append(entry)
    save_yaml(project.root / "project.yaml", project.data)


def list_project_runs(project: str | Path | Project | None = None) -> list[dict[str, Any]]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError("No active project found")
    return list(project_obj.data.get("templates", []))


def resolve_project_assets(project: str | Path | Project | None = None) -> list[dict[str, Any]]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError("No active project found")
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

    runs = list_project_runs(project=project)
    for entry in runs:
        if entry.get("instance_id") != str(run_ref):
            continue
        if isinstance(project, Project):
            project_root = project.root
        elif isinstance(project, (str, Path)):
            project_root = load_project(project).root
        else:
            project_obj = discover_project()
            if project_obj is None:
                break
            project_root = project_obj.root
        meta_path = (project_root / entry["meta"]).resolve()
        with meta_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    raise ProjectValidationError(f"Run not found: {run_ref}")


def generate_methods(project: str | Path | Project | None = None) -> str:
    runs = list_project_runs(project=project)
    if not runs:
        raise LinkarError("No recorded runs found for methods generation")

    fragments: list[str] = []
    for index, run in enumerate(runs, start=1):
        metadata = inspect_run(run["instance_id"], project=project)
        template = metadata["template"]
        software = metadata.get("software") or []
        software_text = ", ".join(
            f"{item['name']} {item.get('version', 'unknown')}"
            for item in software
            if isinstance(item, dict) and item.get("name")
        )
        params = metadata.get("params") or {}
        params_text = ", ".join(f"{key}={value}" for key, value in sorted(params.items()))

        sentence = f"Step {index}: template '{template}' was run"
        if software_text:
            sentence += f" using {software_text}"
        if params_text:
            sentence += f" with parameters {params_text}"
        sentence += "."
        fragments.append(sentence)
    return " ".join(fragments)


def test_template(
    template_ref: str | Path,
    project: str | Path | Project | None = None,
    outdir: str | Path | None = None,
    pack_refs: str | Path | list[str | Path] | None = None,
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project

    project_entries = project_pack_entries(project_obj)
    active_entry = get_active_pack_entry(project_obj)
    explicit_pack_assets = resolve_asset_refs(pack_refs)
    ordered_project_entries = sorted(
        project_entries,
        key=lambda entry: 0 if active_entry is not None and entry.id == active_entry.id else 1,
    )
    combined_pack_assets = unique_assets(
        explicit_pack_assets + [entry.asset for entry in ordered_project_entries]
    )
    preferred_pack_ref = preferred_pack_ref_for_assets(explicit_pack_assets, active_entry)
    template = load_template(
        template_ref,
        pack_assets=combined_pack_assets,
        preferred_pack_ref=preferred_pack_ref,
    )

    test_script = template.root / "test.sh"
    if not test_script.exists():
        raise TemplateValidationError(f"test.sh not found in {template.root}")

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

    command = [str(test_script.resolve())]
    started_at = utc_now()
    completed = subprocess.run(
        command,
        cwd=template.root,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    finished_at = utc_now()

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
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    project_entries = project_pack_entries(project_obj)
    active_entry = get_active_pack_entry(project_obj)
    explicit_pack_assets = resolve_asset_refs(pack_refs)
    ordered_project_entries = sorted(
        project_entries,
        key=lambda entry: 0 if active_entry is not None and entry.id == active_entry.id else 1,
    )
    combined_pack_assets = unique_assets(
        explicit_pack_assets + [entry.asset for entry in ordered_project_entries]
    )
    preferred_pack_ref = preferred_pack_ref_for_assets(explicit_pack_assets, active_entry)
    template = load_template(
        template_ref,
        pack_assets=combined_pack_assets,
        preferred_pack_ref=preferred_pack_ref,
    )
    selected_binding_ref = normalize_binding_ref(binding_ref)
    if selected_binding_ref is None and template.pack_root is not None:
        for entry in ordered_project_entries:
            if entry.asset.root == template.pack_root:
                selected_binding_ref = normalize_binding_ref(entry.binding)
                break
    resolved_params, param_provenance = resolve_params_detailed(
        template,
        cli_params=params,
        project=project_obj,
        binding_ref=selected_binding_ref,
    )
    instance_id = next_instance_id(template.id, project_obj)
    output_dir = determine_outdir(template, project_obj, outdir, instance_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results").mkdir(exist_ok=True)
    linkar_dir = output_dir / ".linkar"
    linkar_dir.mkdir(exist_ok=True)

    if template.run_mode != "direct":
        raise ExecutionError(f"Unsupported run mode: {template.run_mode}")

    env = os.environ.copy()
    for key, value in resolved_params.items():
        env[env_key(key)] = format_env_value(value)
    env["LINKAR_OUTPUT_DIR"] = str(output_dir)
    env["LINKAR_RESULTS_DIR"] = str(output_dir / "results")
    env["LINKAR_INSTANCE_ID"] = instance_id
    if project_obj is not None:
        env["LINKAR_PROJECT_DIR"] = str(project_obj.root)

    command = [str((template.root / template.run_entry).resolve())]
    started_at = utc_now()
    completed = subprocess.run(
        command,
        cwd=output_dir,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    finished_at = utc_now()

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
        },
    )

    if completed.returncode != 0:
        raise ExecutionError(
            f"Template execution failed with exit code {completed.returncode}. "
            f"See {runtime_path}"
        )

    outputs = collect_outputs(output_dir)
    meta_path = linkar_dir / "meta.json"
    write_json(
        meta_path,
        {
            "template": template.id,
            "template_version": template.version,
            "instance_id": instance_id,
            "params": resolved_params,
            "param_provenance": param_provenance,
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
            "command": command,
            "timestamp": finished_at.isoformat(),
        },
    )

    if project_obj is not None:
        update_project(
            project_obj,
            template=template,
            instance_id=instance_id,
            outdir=output_dir,
            params=resolved_params,
            outputs=outputs,
            meta_path=meta_path,
        )

    return {
        "template": template.id,
        "instance_id": instance_id,
        "outdir": str(output_dir),
        "meta": str(meta_path),
        "runtime": str(runtime_path),
    }
