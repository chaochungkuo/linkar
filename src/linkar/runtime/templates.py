from __future__ import annotations

from pathlib import Path
from typing import Any

from linkar.assets import ResolvedAsset, resolve_asset_refs
from linkar.errors import AssetResolutionError, TemplateValidationError
from linkar.runtime.config import get_active_global_pack_entry, global_pack_entries
from linkar.runtime.models import PackEntry, Project, TemplateSpec
from linkar.runtime.projects import get_active_pack_entry, load_project, project_pack_entries, discover_project
from linkar.runtime.shared import load_yaml, preferred_pack_ref_for_assets, unique_assets


def combined_configured_pack_entries(project_obj: Project | None) -> tuple[list[PackEntry], PackEntry | None]:
    project_entries = project_pack_entries(project_obj)
    global_entries = global_pack_entries()
    active_project_entry = get_active_pack_entry(project_obj)
    active_global_entry = get_active_global_pack_entry()
    ordered_project_entries = sorted(
        project_entries,
        key=lambda entry: 0 if active_project_entry is not None and entry.id == active_project_entry.id else 1,
    )
    project_refs = {entry.asset.ref for entry in ordered_project_entries}
    ordered_global_entries = sorted(
        [entry for entry in global_entries if entry.asset.ref not in project_refs],
        key=lambda entry: 0 if active_global_entry is not None and entry.id == active_global_entry.id else 1,
    )
    return ordered_project_entries + ordered_global_entries, active_project_entry or active_global_entry


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
    description = data.get("description")
    if description is not None and not isinstance(description, str):
        raise TemplateValidationError(f"Template description must be a string in {spec_path}")

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
        if param_type not in {"str", "int", "float", "bool", "path", "list[path]"}:
            raise TemplateValidationError(
                f"Unsupported param type '{param_type}' for '{key}' in {spec_path}"
            )

    outputs = data.get("outputs") or {}
    if not isinstance(outputs, dict):
        raise TemplateValidationError(f"Template outputs must be a mapping in {spec_path}")
    for key, raw_spec in outputs.items():
        if not isinstance(key, str) or not key:
            raise TemplateValidationError(
                f"Template output names must be non-empty strings in {spec_path}"
            )
        spec = raw_spec or {}
        if not isinstance(spec, dict):
            raise TemplateValidationError(
                f"Template output spec must be a mapping for '{key}' in {spec_path}"
            )
        if "path" in spec and "glob" in spec:
            raise TemplateValidationError(
                f"Template output '{key}' cannot declare both 'path' and 'glob' in {spec_path}"
            )
        if "path" in spec and (not isinstance(spec["path"], str) or not spec["path"].strip()):
            raise TemplateValidationError(
                f"Template output '{key}' path must be a non-empty string in {spec_path}"
            )
        if "glob" in spec and (not isinstance(spec["glob"], str) or not spec["glob"].strip()):
            raise TemplateValidationError(
                f"Template output '{key}' glob must be a non-empty string in {spec_path}"
            )

    return TemplateSpec(
        id=template_id,
        version=template_version,
        description=description,
        root=root,
        params=params,
        outputs=outputs,
        run_entry=entry,
        run_mode=run.get("mode", "direct"),
        pack_root=root.parent.parent if root.parent.name == "templates" else None,
        pack_ref=pack_asset.ref if pack_asset is not None else None,
        pack_revision=pack_asset.revision if pack_asset is not None else None,
    )


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
    configured_entries, active_entry = combined_configured_pack_entries(project_obj)
    explicit_pack_assets = resolve_asset_refs(pack_refs)
    pack_assets = unique_assets(explicit_pack_assets + [entry.asset for entry in configured_entries])
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
                    "description": spec.get("description"),
                    "version": spec.get("version"),
                    "pack_ref": asset.ref,
                    "pack_revision": asset.revision,
                    "required_inputs": [
                        name
                        for name, raw_spec in (spec.get("params") or {}).items()
                        if isinstance(raw_spec, dict) and raw_spec.get("required")
                    ],
                    "expected_outputs": list((spec.get("outputs") or {}).keys()) or ["results_dir"],
                    "path": str(child.resolve()),
                }
            )
    return templates
