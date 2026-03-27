from __future__ import annotations

from pathlib import Path
from typing import Any

from linkar.assets import resolve_asset_ref
from linkar.errors import ProjectValidationError
from linkar.runtime.models import PackEntry, Project
from linkar.runtime.shared import derive_pack_id, load_yaml, pack_entry_to_data, project_file, save_yaml


def missing_project_error(action: str = "This command") -> ProjectValidationError:
    return ProjectValidationError(
        f"{action} requires an active project. Run it inside a directory containing project.yaml, "
        "pass --project PATH, or create one with 'linkar project init --name demo'."
    )


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
        raise missing_project_error("Listing configured packs")
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
        raise missing_project_error("Adding a pack")
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
        raise missing_project_error("Selecting an active pack")
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
        raise missing_project_error("Removing a pack")
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


def latest_project_output(project: Project | None, key: str) -> Any | None:
    if project is None:
        return None
    templates = project.data.get("templates", [])
    for item in reversed(templates):
        outputs = item.get("outputs") or {}
        if key in outputs:
            return outputs[key]
    return None
