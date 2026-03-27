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

from linkar.assets import ResolvedAsset, resolve_asset_ref, resolve_asset_refs
from linkar import __version__
from linkar.errors import (
    AssetResolutionError,
    ExecutionError,
    LinkarError,
    ParameterResolutionError,
    ProjectValidationError,
    TemplateValidationError,
)


@dataclass
class TemplateSpec:
    id: str
    version: str | None
    root: Path
    params: dict[str, dict[str, Any]]
    run_entry: str
    run_mode: str
    pack_root: Path | None = None
    pack_ref: str | None = None
    pack_revision: str | None = None


@dataclass
class Project:
    root: Path
    data: dict[str, Any]


@dataclass
class PackEntry:
    id: str
    asset: ResolvedAsset
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


def derive_pack_id(ref: str) -> str:
    raw = ref.rstrip("/").rsplit("/", 1)[-1]
    if raw.endswith(".git"):
        raw = raw[:-4]
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
    return slug or "pack"


def pack_entry_to_data(entry: PackEntry) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": entry.id,
        "ref": entry.asset.ref,
    }
    if entry.binding is not None:
        data["binding"] = entry.binding
    return data


def unique_assets(assets: list[ResolvedAsset]) -> list[ResolvedAsset]:
    seen: set[str] = set()
    ordered: list[ResolvedAsset] = []
    for asset in assets:
        if asset.ref in seen:
            continue
        seen.add(asset.ref)
        ordered.append(asset)
    return ordered


def preferred_pack_ref_for_assets(
    explicit_assets: list[ResolvedAsset],
    active_entry: PackEntry | None,
) -> str | None:
    if len(explicit_assets) == 1:
        return explicit_assets[0].ref
    if active_entry is not None and not explicit_assets:
        return active_entry.asset.ref
    return None


def load_project(path: str | Path) -> Project:
    root_path = Path(path).resolve()
    file_path = project_file(root_path)
    if not file_path.exists():
        raise ProjectValidationError(f"Project file not found: {file_path}")
    data = load_yaml(file_path)
    project_id = data.get("id")
    if not project_id:
        raise ProjectValidationError("project.yaml field 'id' is required")
    templates = data.setdefault("templates", [])
    if not isinstance(templates, list):
        raise ProjectValidationError("project.yaml field 'templates' must be a list")
    packs = data.setdefault("packs", [])
    if not isinstance(packs, list):
        raise ProjectValidationError("project.yaml field 'packs' must be a list")
    active_pack = data.get("active_pack")
    if active_pack is not None and not isinstance(active_pack, str):
        raise ProjectValidationError("project.yaml field 'active_pack' must be a string")
    return Project(root=file_path.parent, data=data)


def init_project(path: str | Path, project_id: str | None = None) -> Path:
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / "project.yaml"
    if file_path.exists():
        raise ProjectValidationError(f"Project already exists: {file_path}")
    data = {
        "id": project_id or root.name,
        "active_pack": None,
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
        return str(binding_ref.expanduser().resolve())
    return binding_ref


def project_pack_entries(project: Project | None) -> list[PackEntry]:
    if project is None:
        return []
    entries: list[PackEntry] = []
    for item in project.data.get("packs", []):
        if isinstance(item, str):
            asset = resolve_asset_ref(item)
            entries.append(PackEntry(id=derive_pack_id(asset.ref), asset=asset))
            continue
        if not isinstance(item, dict):
            raise ProjectValidationError("project.yaml pack entries must be strings or mappings")
        ref = item.get("ref")
        if not ref or not isinstance(ref, str):
            raise ProjectValidationError("project.yaml pack entry field 'ref' is required")
        pack_id = item.get("id")
        if pack_id is not None and not isinstance(pack_id, str):
            raise ProjectValidationError("project.yaml pack entry field 'id' must be a string")
        binding = item.get("binding")
        if binding is not None and not isinstance(binding, str):
            raise ProjectValidationError("project.yaml pack entry field 'binding' must be a string")
        asset = resolve_asset_ref(ref)
        entries.append(
            PackEntry(
                id=pack_id or derive_pack_id(asset.ref),
                asset=asset,
                binding=binding,
            )
        )
    return entries


def get_active_pack_entry(project: Project | None) -> PackEntry | None:
    entries = project_pack_entries(project)
    if not entries:
        return None
    active_pack = project.data.get("active_pack") if project is not None else None
    if active_pack:
        for entry in entries:
            if entry.id == active_pack or entry.asset.ref == active_pack:
                return entry
    if len(entries) == 1:
        return entries[0]
    return None


def find_project_pack_entry(project: Project, identifier: str) -> PackEntry | None:
    for entry in project_pack_entries(project):
        if entry.id == identifier or entry.asset.ref == identifier:
            return entry
    return None


def list_configured_packs(project: str | Path | Project | None = None) -> list[dict[str, Any]]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError("No active project found")
    active = project_obj.data.get("active_pack")
    return [
        {
            "id": entry.id,
            "ref": entry.asset.ref,
            "binding": entry.binding,
            "revision": entry.asset.revision,
            "active": active == entry.id or (active is None and len(project_obj.data.get("packs", [])) == 1),
        }
        for entry in project_pack_entries(project_obj)
    ]


def add_project_pack(
    ref: str,
    *,
    project: str | Path | Project | None = None,
    pack_id: str | None = None,
    binding: str | None = None,
    activate: bool = False,
) -> dict[str, Any]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    if project_obj is None:
        raise ProjectValidationError("No active project found")
    asset = resolve_asset_ref(ref)
    resolved_id = pack_id or derive_pack_id(asset.ref)
    for entry in project_pack_entries(project_obj):
        if entry.id == resolved_id:
            raise ProjectValidationError(f"Pack id already exists in project: {resolved_id}")
        if entry.asset.ref == asset.ref:
            raise ProjectValidationError(f"Pack already exists in project: {asset.ref}")
    entry = PackEntry(id=resolved_id, asset=asset, binding=binding)
    project_obj.data.setdefault("packs", []).append(pack_entry_to_data(entry))
    if activate or len(project_obj.data["packs"]) == 1:
        project_obj.data["active_pack"] = resolved_id
    save_yaml(project_obj.root / "project.yaml", project_obj.data)
    return {
        "id": resolved_id,
        "ref": asset.ref,
        "binding": binding,
        "active": project_obj.data.get("active_pack") == resolved_id,
    }


def set_active_pack(
    identifier: str,
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
        raise ProjectValidationError("No active project found")
    entry = find_project_pack_entry(project_obj, identifier)
    if entry is None:
        raise ProjectValidationError(f"Pack not found in project: {identifier}")
    project_obj.data["active_pack"] = entry.id
    save_yaml(project_obj.root / "project.yaml", project_obj.data)
    return {
        "id": entry.id,
        "ref": entry.asset.ref,
        "binding": entry.binding,
        "active": True,
    }


def remove_project_pack(
    identifier: str,
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
        raise ProjectValidationError("No active project found")
    entry = find_project_pack_entry(project_obj, identifier)
    if entry is None:
        raise ProjectValidationError(f"Pack not found in project: {identifier}")
    kept: list[dict[str, Any] | str] = []
    for item in project_obj.data.get("packs", []):
        if isinstance(item, str):
            if resolve_asset_ref(item).ref == entry.asset.ref:
                continue
            kept.append(item)
            continue
        if item.get("id") == entry.id or item.get("ref") == entry.asset.ref:
            continue
        kept.append(item)
    project_obj.data["packs"] = kept
    if project_obj.data.get("active_pack") == entry.id:
        remaining_entries = project_pack_entries(project_obj)
        project_obj.data["active_pack"] = remaining_entries[0].id if remaining_entries else None
    save_yaml(project_obj.root / "project.yaml", project_obj.data)
    return {
        "id": entry.id,
        "ref": entry.asset.ref,
        "binding": entry.binding,
    }


def load_template(
    template_ref: str | Path,
    pack_assets: list[ResolvedAsset] | None = None,
    preferred_pack_ref: str | None = None,
) -> TemplateSpec:
    ref_path = Path(template_ref)
    if ref_path.exists():
        root = ref_path.resolve()
        pack_asset: ResolvedAsset | None = None
    else:
        candidates: list[Path] = []
        candidate_assets: list[ResolvedAsset] = []
        for pack_asset in pack_assets or []:
            candidate = pack_asset.root / "templates" / str(template_ref)
            if (candidate / "template.yaml").exists():
                candidates.append(candidate)
                candidate_assets.append(pack_asset)
        if not candidates:
            raise AssetResolutionError(
                f"Template not found: {template_ref}. Pass a template path or use --pack."
            )
        if len(candidates) > 1:
            if preferred_pack_ref is not None:
                preferred = [
                    (candidate, asset)
                    for candidate, asset in zip(candidates, candidate_assets)
                    if asset.ref == preferred_pack_ref
                ]
                if len(preferred) == 1:
                    root = preferred[0][0]
                    pack_asset = preferred[0][1]
                    candidates = []
                else:
                    joined = ", ".join(asset.ref for asset in candidate_assets)
                    raise AssetResolutionError(
                        f"Template '{template_ref}' is ambiguous across packs: {joined}"
                    )
            else:
                joined = ", ".join(asset.ref for asset in candidate_assets)
                raise AssetResolutionError(
                    f"Template '{template_ref}' is ambiguous across packs: {joined}"
                )
        if candidates:
            root = candidates[0]
            pack_asset = candidate_assets[0]

    spec_path = root / "template.yaml"
    if not spec_path.exists():
        raise TemplateValidationError(f"template.yaml not found in {root}")

    data = load_yaml(spec_path)
    template_id = data.get("id")
    if not template_id:
        raise TemplateValidationError(f"Template id missing in {spec_path}")
    template_version = data.get("version")
    if template_version is not None and not isinstance(template_version, str):
        raise TemplateValidationError(f"Template version must be a string in {spec_path}")

    run = data.get("run") or {}
    entry = run.get("entry")
    if not entry:
        raise TemplateValidationError(f"Template run.entry missing in {spec_path}")
    entry_path = root / entry
    if not entry_path.exists():
        raise TemplateValidationError(f"Template entrypoint not found: {entry_path}")

    params = data.get("params") or {}
    if not isinstance(params, dict):
        raise TemplateValidationError(f"Template params must be a mapping in {spec_path}")
    for key, raw_spec in params.items():
        if not isinstance(key, str) or not key:
            raise TemplateValidationError(
                f"Template param names must be non-empty strings in {spec_path}"
            )
        spec = raw_spec or {}
        if not isinstance(spec, dict):
            raise TemplateValidationError(
                f"Template param spec must be a mapping for '{key}' in {spec_path}"
            )
        param_type = spec.get("type", "str")
        if param_type not in {"str", "int", "float", "bool", "path"}:
            raise TemplateValidationError(
                f"Unsupported param type '{param_type}' for '{key}' in {spec_path}"
            )

    return TemplateSpec(
        id=template_id,
        version=template_version,
        root=root,
        params=params,
        run_entry=entry,
        run_mode=run.get("mode", "direct"),
        pack_root=root.parent.parent if root.parent.name == "templates" else None,
        pack_ref=pack_asset.ref if pack_asset is not None else None,
        pack_revision=pack_asset.revision if pack_asset is not None else None,
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
        raise ParameterResolutionError(f"Invalid bool value: {value}")
    if param_type == "path":
        return str(Path(value).expanduser().resolve())
    raise ParameterResolutionError(f"Unsupported param type: {param_type}")


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
            raise AssetResolutionError("Binding 'default' requires a selected pack")
        if not (pack_root / "binding.yaml").exists():
            raise AssetResolutionError(f"Pack does not provide a default binding: {pack_root}")
        return pack_root
    binding_asset = resolve_asset_ref(binding_ref)
    if not (binding_asset.root / "binding.yaml").exists():
        raise AssetResolutionError(f"binding.yaml not found in {binding_asset.root}")
    return binding_asset.root


def load_binding_config(binding_ref: str | Path | None, pack_root: Path | None) -> tuple[Path | None, dict[str, Any]]:
    root = binding_asset_root(binding_ref, pack_root)
    if root is None:
        return None, {}
    data = load_yaml(root / "binding.yaml")
    templates = data.get("templates") or {}
    if not isinstance(templates, dict):
        raise AssetResolutionError("binding.yaml field 'templates' must be a mapping")
    return root, data


def resolve_binding_function(name: str, search_roots: list[Path]) -> Any:
    for root in search_roots:
        candidate = root / "functions" / f"{name}.py"
        if not candidate.exists():
            continue
        module_name = f"linkar_binding_{candidate.stem}_{abs(hash(str(candidate)))}"
        spec = importlib.util.spec_from_file_location(module_name, candidate)
        if spec is None or spec.loader is None:
            raise AssetResolutionError(f"Unable to load binding function: {candidate}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        resolve = getattr(module, "resolve", None)
        if not callable(resolve):
            raise AssetResolutionError(f"Binding function file must define resolve(ctx): {candidate}")
        return resolve
    raise AssetResolutionError(f"Binding function not found: {name}")


def resolve_bound_value(
    template: TemplateSpec,
    key: str,
    binding_root: Path | None,
    binding_data: dict[str, Any],
    project: Project | None,
    resolved_params: dict[str, Any],
) -> tuple[bool, Any, dict[str, Any] | None]:
    templates = binding_data.get("templates") or {}
    template_binding = templates.get(template.id) or {}
    if not isinstance(template_binding, dict):
        raise AssetResolutionError(
            f"binding.yaml template entry must be a mapping for '{template.id}'"
        )
    params = template_binding.get("params") or {}
    if not isinstance(params, dict):
        raise AssetResolutionError(
            f"binding.yaml params entry must be a mapping for '{template.id}'"
        )
    if key not in params:
        return False, None, None

    rule = params[key] or {}
    if not isinstance(rule, dict):
        raise AssetResolutionError(
            f"binding.yaml param rule must be a mapping for '{template.id}.{key}'"
        )
    source = rule.get("from")
    ctx = BindingContext(template=template, project=project, resolved_params=dict(resolved_params))

    if source == "output":
        output_key = rule.get("key", key)
        value = ctx.latest_output(str(output_key))
        if value is None:
            raise ParameterResolutionError(
                f"Binding could not resolve output '{output_key}' for '{template.id}.{key}'"
            )
        return True, value, {
            "source": "binding",
            "binding_source": "output",
            "key": str(output_key),
        }
    if source == "function":
        function_name = rule.get("name")
        if not function_name or not isinstance(function_name, str):
            raise AssetResolutionError(
                f"Binding function name is required for '{template.id}.{key}'"
            )
        search_roots = []
        if binding_root is not None:
            search_roots.append(binding_root)
        if template.pack_root is not None and template.pack_root not in search_roots:
            search_roots.append(template.pack_root)
        value = resolve_binding_function(function_name, search_roots)(ctx)
        if value is None:
            raise ParameterResolutionError(
                f"Binding function returned no value for '{template.id}.{key}'"
            )
        return True, value, {
            "source": "binding",
            "binding_source": "function",
            "name": function_name,
        }
    if source == "value":
        if "value" not in rule:
            raise AssetResolutionError(
                f"Binding literal value is required for '{template.id}.{key}'"
            )
        return True, rule["value"], {
            "source": "binding",
            "binding_source": "value",
        }

    raise AssetResolutionError(
        f"Unsupported binding source '{source}' for '{template.id}.{key}'"
    )


def resolve_params_detailed(
    template: TemplateSpec,
    cli_params: dict[str, Any] | None = None,
    project: Project | None = None,
    binding_ref: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    cli_params = cli_params or {}
    binding_root, binding_data = load_binding_config(binding_ref, template.pack_root)
    resolved: dict[str, Any] = {}
    provenance: dict[str, dict[str, Any]] = {}

    for key, raw_spec in template.params.items():
        spec = raw_spec or {}
        param_type = spec.get("type", "str")
        if key in cli_params:
            raw_value = cli_params[key]
            raw_provenance = {"source": "explicit"}
        else:
            has_bound_value, bound_value, bound_provenance = resolve_bound_value(
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
                raw_provenance = bound_provenance or {"source": "binding"}
            elif project_value is not None:
                raw_value = project_value
                raw_provenance = {"source": "project", "key": key}
            elif "default" in spec:
                raw_value = spec["default"]
                raw_provenance = {"source": "default"}
            elif spec.get("required"):
                raise ParameterResolutionError(f"Missing required param: {key}")
            else:
                continue

        resolved[key] = parse_param_value(raw_value, param_type)
        provenance[key] = raw_provenance

    return resolved, provenance


def resolve_params(
    template: TemplateSpec,
    cli_params: dict[str, Any] | None = None,
    project: Project | None = None,
    binding_ref: str | Path | None = None,
) -> dict[str, Any]:
    resolved, _ = resolve_params_detailed(
        template,
        cli_params=cli_params,
        project=project,
        binding_ref=binding_ref,
    )
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


def list_templates(
    pack_refs: str | Path | list[str | Path] | None = None,
    project: str | Path | Project | None = None,
) -> list[dict[str, Any]]:
    if isinstance(project, (str, Path)):
        project_obj = load_project(project)
    elif project is None:
        project_obj = discover_project()
    else:
        project_obj = project
    project_entries = project_pack_entries(project_obj)
    active_entry = get_active_pack_entry(project_obj)
    ordered_project_entries = sorted(
        project_entries,
        key=lambda entry: 0 if active_entry is not None and entry.id == active_entry.id else 1,
    )
    pack_assets = unique_assets(resolve_asset_refs(pack_refs) + [entry.asset for entry in ordered_project_entries])
    seen: set[tuple[str, str]] = set()
    templates: list[dict[str, Any]] = []
    for asset in pack_assets:
        templates_dir = asset.root / "templates"
        if not templates_dir.exists():
            continue
        for child in sorted(templates_dir.iterdir()):
            spec_path = child / "template.yaml"
            if not child.is_dir() or not spec_path.exists():
                continue
            spec = load_yaml(spec_path)
            template_id = spec.get("id") or child.name
            key = (template_id, asset.ref)
            if key in seen:
                continue
            seen.add(key)
            templates.append(
                {
                    "id": template_id,
                    "version": spec.get("version"),
                    "pack_ref": asset.ref,
                    "pack_revision": asset.revision,
                    "path": str(child.resolve()),
                }
            )
    return templates


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
