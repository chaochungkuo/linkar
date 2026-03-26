from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from typing import Any

import yaml

from linkar import __version__


class LinkarError(Exception):
    """Base error for linkar."""


@dataclass
class TemplateSpec:
    id: str
    root: Path
    params: dict[str, dict[str, Any]]
    run_entry: str
    run_mode: str
    pack_root: Path | None = None


@dataclass
class Project:
    root: Path
    data: dict[str, Any]


@dataclass
class PackEntry:
    ref: Path
    binding: str | None = None


@dataclass
class BindingContext:
    template: TemplateSpec
    project: Project | None
    resolved_params: dict[str, Any]

    def latest_output(self, key: str) -> Any | None:
        return latest_project_output(self.project, key)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise LinkarError(f"Expected mapping in {path}")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def project_file(path: Path) -> Path:
    if path.is_dir():
        return path / "project.yaml"
    return path


def load_project(path: str | Path) -> Project:
    root_path = Path(path).resolve()
    file_path = project_file(root_path)
    if not file_path.exists():
        raise LinkarError(f"Project file not found: {file_path}")
    data = load_yaml(file_path)
    project_id = data.get("id")
    if not project_id:
        raise LinkarError("project.yaml field 'id' is required")
    templates = data.setdefault("templates", [])
    if not isinstance(templates, list):
        raise LinkarError("project.yaml field 'templates' must be a list")
    packs = data.setdefault("packs", [])
    if not isinstance(packs, list):
        raise LinkarError("project.yaml field 'packs' must be a list")
    return Project(root=file_path.parent, data=data)


def init_project(path: str | Path, project_id: str | None = None) -> Path:
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / "project.yaml"
    if file_path.exists():
        raise LinkarError(f"Project already exists: {file_path}")
    data = {
        "id": project_id or root.name,
        "packs": [],
        "templates": [],
    }
    save_yaml(file_path, data)
    return file_path


def discover_project(start: str | Path | None = None) -> Project | None:
    root = Path.cwd() if start is None else Path(start).resolve()
    candidate = root / "project.yaml"
    if candidate.exists():
        return load_project(root)
    return None


def normalize_binding_ref(binding_ref: str | Path | None) -> str | Path | None:
    if binding_ref is None:
        return None
    if isinstance(binding_ref, Path):
        return binding_ref.expanduser().resolve()
    return binding_ref


def normalize_pack_refs(pack_refs: str | Path | list[str | Path] | None) -> list[Path]:
    if pack_refs is None:
        return []
    if isinstance(pack_refs, (str, Path)):
        raw_refs: list[str | Path] = [pack_refs]
    else:
        raw_refs = list(pack_refs)
    normalized: list[Path] = []
    for ref in raw_refs:
        normalized.append(Path(ref).expanduser().resolve())
    return normalized


def project_pack_entries(project: Project | None) -> list[PackEntry]:
    if project is None:
        return []
    entries: list[PackEntry] = []
    for item in project.data.get("packs", []):
        if isinstance(item, str):
            entries.append(PackEntry(ref=Path(item).expanduser().resolve()))
            continue
        if not isinstance(item, dict):
            raise LinkarError("project.yaml pack entries must be strings or mappings")
        ref = item.get("ref")
        if not ref or not isinstance(ref, str):
            raise LinkarError("project.yaml pack entry field 'ref' is required")
        binding = item.get("binding")
        if binding is not None and not isinstance(binding, str):
            raise LinkarError("project.yaml pack entry field 'binding' must be a string")
        entries.append(PackEntry(ref=Path(ref).expanduser().resolve(), binding=binding))
    return entries


def load_template(
    template_ref: str | Path,
    pack_refs: str | Path | list[str | Path] | None = None,
) -> TemplateSpec:
    ref_path = Path(template_ref)
    if ref_path.exists():
        root = ref_path.resolve()
    else:
        candidates: list[Path] = []
        for pack_root in normalize_pack_refs(pack_refs):
            candidate = pack_root / "templates" / str(template_ref)
            if (candidate / "template.yaml").exists():
                candidates.append(candidate)
        if not candidates:
            raise LinkarError(
                f"Template not found: {template_ref}. Pass a template path or use --pack."
            )
        if len(candidates) > 1:
            joined = ", ".join(str(path.parent.parent) for path in candidates)
            raise LinkarError(
                f"Template '{template_ref}' is ambiguous across packs: {joined}"
            )
        root = candidates[0]

    spec_path = root / "template.yaml"
    if not spec_path.exists():
        raise LinkarError(f"template.yaml not found in {root}")

    data = load_yaml(spec_path)
    template_id = data.get("id")
    if not template_id:
        raise LinkarError(f"Template id missing in {spec_path}")

    run = data.get("run") or {}
    entry = run.get("entry")
    if not entry:
        raise LinkarError(f"Template run.entry missing in {spec_path}")
    entry_path = root / entry
    if not entry_path.exists():
        raise LinkarError(f"Template entrypoint not found: {entry_path}")

    params = data.get("params") or {}
    if not isinstance(params, dict):
        raise LinkarError(f"Template params must be a mapping in {spec_path}")
    for key, raw_spec in params.items():
        if not isinstance(key, str) or not key:
            raise LinkarError(f"Template param names must be non-empty strings in {spec_path}")
        spec = raw_spec or {}
        if not isinstance(spec, dict):
            raise LinkarError(f"Template param spec must be a mapping for '{key}' in {spec_path}")
        param_type = spec.get("type", "str")
        if param_type not in {"str", "int", "float", "bool", "path"}:
            raise LinkarError(f"Unsupported param type '{param_type}' for '{key}' in {spec_path}")

    return TemplateSpec(
        id=template_id,
        root=root,
        params=params,
        run_entry=entry,
        run_mode=run.get("mode", "direct"),
        pack_root=root.parent.parent if root.parent.name == "templates" else None,
    )


def env_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def parse_param_value(value: Any, param_type: str) -> Any:
    if param_type == "str":
        return str(value)
    if param_type == "int":
        return int(value)
    if param_type == "float":
        return float(value)
    if param_type == "bool":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise LinkarError(f"Invalid bool value: {value}")
    if param_type == "path":
        return str(Path(value).expanduser().resolve())
    raise LinkarError(f"Unsupported param type: {param_type}")


def format_env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def latest_project_output(project: Project | None, key: str) -> Any | None:
    if project is None:
        return None
    templates = project.data.get("templates", [])
    for item in reversed(templates):
        outputs = item.get("outputs") or {}
        if key in outputs:
            return outputs[key]
    return None


def binding_asset_root(binding_ref: str | Path | None, pack_root: Path | None) -> Path | None:
    if binding_ref is None:
        return None
    if binding_ref == "default":
        if pack_root is None:
            raise LinkarError("Binding 'default' requires a selected pack")
        if not (pack_root / "binding.yaml").exists():
            raise LinkarError(f"Pack does not provide a default binding: {pack_root}")
        return pack_root
    binding_path = Path(binding_ref).expanduser().resolve()
    if not (binding_path / "binding.yaml").exists():
        raise LinkarError(f"binding.yaml not found in {binding_path}")
    return binding_path


def load_binding_config(binding_ref: str | Path | None, pack_root: Path | None) -> tuple[Path | None, dict[str, Any]]:
    root = binding_asset_root(binding_ref, pack_root)
    if root is None:
        return None, {}
    data = load_yaml(root / "binding.yaml")
    templates = data.get("templates") or {}
    if not isinstance(templates, dict):
        raise LinkarError("binding.yaml field 'templates' must be a mapping")
    return root, data


def resolve_binding_function(name: str, search_roots: list[Path]) -> Any:
    for root in search_roots:
        candidate = root / "functions" / f"{name}.py"
        if not candidate.exists():
            continue
        module_name = f"linkar_binding_{candidate.stem}_{abs(hash(str(candidate)))}"
        spec = importlib.util.spec_from_file_location(module_name, candidate)
        if spec is None or spec.loader is None:
            raise LinkarError(f"Unable to load binding function: {candidate}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        resolve = getattr(module, "resolve", None)
        if not callable(resolve):
            raise LinkarError(f"Binding function file must define resolve(ctx): {candidate}")
        return resolve
    raise LinkarError(f"Binding function not found: {name}")


def resolve_bound_value(
    template: TemplateSpec,
    key: str,
    binding_root: Path | None,
    binding_data: dict[str, Any],
    project: Project | None,
    resolved_params: dict[str, Any],
) -> tuple[bool, Any]:
    templates = binding_data.get("templates") or {}
    template_binding = templates.get(template.id) or {}
    if not isinstance(template_binding, dict):
        raise LinkarError(f"binding.yaml template entry must be a mapping for '{template.id}'")
    params = template_binding.get("params") or {}
    if not isinstance(params, dict):
        raise LinkarError(f"binding.yaml params entry must be a mapping for '{template.id}'")
    if key not in params:
        return False, None

    rule = params[key] or {}
    if not isinstance(rule, dict):
        raise LinkarError(f"binding.yaml param rule must be a mapping for '{template.id}.{key}'")
    source = rule.get("from")
    ctx = BindingContext(template=template, project=project, resolved_params=dict(resolved_params))

    if source == "output":
        output_key = rule.get("key", key)
        value = ctx.latest_output(str(output_key))
        if value is None:
            raise LinkarError(
                f"Binding could not resolve output '{output_key}' for '{template.id}.{key}'"
            )
        return True, value
    if source == "function":
        function_name = rule.get("name")
        if not function_name or not isinstance(function_name, str):
            raise LinkarError(f"Binding function name is required for '{template.id}.{key}'")
        search_roots = []
        if binding_root is not None:
            search_roots.append(binding_root)
        if template.pack_root is not None and template.pack_root not in search_roots:
            search_roots.append(template.pack_root)
        value = resolve_binding_function(function_name, search_roots)(ctx)
        if value is None:
            raise LinkarError(
                f"Binding function returned no value for '{template.id}.{key}'"
            )
        return True, value
    if source == "value":
        if "value" not in rule:
            raise LinkarError(f"Binding literal value is required for '{template.id}.{key}'")
        return True, rule["value"]

    raise LinkarError(f"Unsupported binding source '{source}' for '{template.id}.{key}'")


def resolve_params(
    template: TemplateSpec,
    cli_params: dict[str, Any] | None = None,
    project: Project | None = None,
    binding_ref: str | Path | None = None,
) -> dict[str, Any]:
    cli_params = cli_params or {}
    binding_root, binding_data = load_binding_config(binding_ref, template.pack_root)
    resolved: dict[str, Any] = {}

    for key, raw_spec in template.params.items():
        spec = raw_spec or {}
        param_type = spec.get("type", "str")
        if key in cli_params:
            raw_value = cli_params[key]
        else:
            has_bound_value, bound_value = resolve_bound_value(
                template=template,
                key=key,
                binding_root=binding_root,
                binding_data=binding_data,
                project=project,
                resolved_params=resolved,
            )
            project_value = latest_project_output(project, key)
            if has_bound_value:
                raw_value = bound_value
            elif project_value is not None:
                raw_value = project_value
            elif "default" in spec:
                raw_value = spec["default"]
            elif spec.get("required"):
                raise LinkarError(f"Missing required param: {key}")
            else:
                continue

        resolved[key] = parse_param_value(raw_value, param_type)

    return resolved


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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def collect_outputs(outdir: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    results_dir = outdir / "results"
    if results_dir.exists():
        outputs["results_dir"] = str(results_dir)
    return outputs


def update_project(project: Project, template: TemplateSpec, instance_id: str, outdir: Path, params: dict[str, Any], outputs: dict[str, Any], meta_path: Path) -> None:
    relative_path = os.path.relpath(outdir, project.root)
    relative_meta = os.path.relpath(meta_path, project.root)
    entry = {
        "id": template.id,
        "instance_id": instance_id,
        "path": relative_path,
        "params": params,
        "outputs": outputs,
        "meta": relative_meta,
    }
    project.data.setdefault("templates", []).append(entry)
    save_yaml(project.root / "project.yaml", project.data)


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
    combined_pack_refs = normalize_pack_refs(pack_refs) + [entry.ref for entry in project_entries]
    template = load_template(template_ref, pack_refs=combined_pack_refs)
    selected_binding_ref = normalize_binding_ref(binding_ref)
    if selected_binding_ref is None and template.pack_root is not None:
        for entry in project_entries:
            if entry.ref == template.pack_root:
                selected_binding_ref = normalize_binding_ref(entry.binding)
                break
    resolved_params = resolve_params(
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
        raise LinkarError(f"Unsupported run mode: {template.run_mode}")

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
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )

    if completed.returncode != 0:
        raise LinkarError(
            f"Template execution failed with exit code {completed.returncode}. "
            f"See {runtime_path}"
        )

    outputs = collect_outputs(output_dir)
    meta_path = linkar_dir / "meta.json"
    write_json(
        meta_path,
        {
            "template": template.id,
            "instance_id": instance_id,
            "params": resolved_params,
            "outputs": outputs,
            "software": [{"name": "linkar", "version": __version__}],
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
