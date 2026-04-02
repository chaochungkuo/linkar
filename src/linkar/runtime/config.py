from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkar.assets import resolve_asset_ref
from linkar.errors import ProjectValidationError
from linkar.runtime.models import PackEntry
from linkar.runtime.shared import derive_pack_id, load_yaml, pack_entry_to_data, save_yaml


@dataclass
class GlobalConfig:
    path: Path
    data: dict[str, Any]


def linkar_home_dir() -> Path:
    linkar_home = os.environ.get("LINKAR_HOME")
    if linkar_home:
        return Path(linkar_home).expanduser().resolve()
    return Path.home() / ".linkar"


def global_config_path() -> Path:
    return linkar_home_dir() / "config.yaml"


def load_global_config() -> GlobalConfig:
    path = global_config_path()
    if path.exists():
        data = load_yaml(path)
    else:
        data = {}
    packs = data.setdefault("packs", [])
    if not isinstance(packs, list):
        raise ProjectValidationError("config.yaml field 'packs' must be a list")
    active_pack = data.get("active_pack")
    if active_pack is not None and not isinstance(active_pack, str):
        raise ProjectValidationError("config.yaml field 'active_pack' must be a string")
    author = data.get("author")
    if author is not None:
        if not isinstance(author, dict):
            raise ProjectValidationError("config.yaml field 'author' must be a mapping")
        for key in ("name", "email", "organization"):
            value = author.get(key)
            if value is not None and not isinstance(value, str):
                raise ProjectValidationError(f"config.yaml field 'author.{key}' must be a string")
    return GlobalConfig(path=path, data=data)


def save_global_config(config: GlobalConfig) -> None:
    save_yaml(config.path, config.data)


def get_global_author(config: GlobalConfig | None = None) -> dict[str, str] | None:
    config_obj = config or load_global_config()
    author = config_obj.data.get("author")
    if not isinstance(author, dict):
        return None
    result = {
        key: value
        for key in ("name", "email", "organization")
        if isinstance((value := author.get(key)), str) and value
    }
    return result or None


def set_global_author(
    *,
    name: str | None = None,
    email: str | None = None,
    organization: str | None = None,
) -> dict[str, str]:
    if not any(value is not None for value in (name, email, organization)):
        raise ProjectValidationError("Provide at least one author field to set")
    config = load_global_config()
    author = dict(get_global_author(config) or {})
    if name is not None:
        author["name"] = name
    if email is not None:
        author["email"] = email
    if organization is not None:
        author["organization"] = organization
    config.data["author"] = author
    save_global_config(config)
    return author


def clear_global_author() -> None:
    config = load_global_config()
    config.data.pop("author", None)
    save_global_config(config)


def global_pack_entries(config: GlobalConfig | None = None) -> list[PackEntry]:
    config_obj = config or load_global_config()
    entries: list[PackEntry] = []
    for item in config_obj.data.get("packs", []):
        if isinstance(item, str):
            asset = resolve_asset_ref(item)
            entries.append(PackEntry(id=derive_pack_id(asset.ref), asset=asset))
            continue
        if not isinstance(item, dict):
            raise ProjectValidationError("config.yaml pack entries must be strings or mappings")
        ref = item.get("ref")
        if not ref or not isinstance(ref, str):
            raise ProjectValidationError("config.yaml pack entry field 'ref' is required")
        pack_id = item.get("id")
        if pack_id is not None and not isinstance(pack_id, str):
            raise ProjectValidationError("config.yaml pack entry field 'id' must be a string")
        asset = resolve_asset_ref(ref)
        entries.append(PackEntry(id=pack_id or derive_pack_id(asset.ref), asset=asset))
    return entries


def get_active_global_pack_entry(config: GlobalConfig | None = None) -> PackEntry | None:
    config_obj = config or load_global_config()
    entries = global_pack_entries(config_obj)
    if not entries:
        return None
    active_pack = config_obj.data.get("active_pack")
    if active_pack:
        for entry in entries:
            if entry.id == active_pack or entry.asset.ref == active_pack:
                return entry
    if len(entries) == 1:
        return entries[0]
    return None


def find_global_pack_entry(identifier: str, config: GlobalConfig | None = None) -> PackEntry | None:
    for entry in global_pack_entries(config):
        if entry.id == identifier or entry.asset.ref == identifier:
            return entry
    return None


def list_global_packs() -> list[dict[str, Any]]:
    config = load_global_config()
    active = config.data.get("active_pack")
    return [
        {
            "id": entry.id,
            "ref": entry.asset.ref,
            "binding": None,
            "revision": entry.asset.revision,
            "active": active == entry.id or (active is None and len(config.data.get("packs", [])) == 1),
        }
        for entry in global_pack_entries(config)
    ]


def add_global_pack(
    ref: str,
    *,
    pack_id: str | None = None,
    activate: bool = False,
) -> dict[str, Any]:
    config = load_global_config()
    asset = resolve_asset_ref(ref)
    resolved_id = pack_id or derive_pack_id(asset.ref)
    for entry in global_pack_entries(config):
        if entry.id == resolved_id:
            raise ProjectValidationError(f"Pack id already exists in global config: {resolved_id}")
        if entry.asset.ref == asset.ref:
            raise ProjectValidationError(f"Pack already exists in global config: {asset.ref}")
    entry = PackEntry(id=resolved_id, asset=asset)
    config.data.setdefault("packs", []).append(pack_entry_to_data(entry))
    if activate or len(config.data["packs"]) == 1:
        config.data["active_pack"] = resolved_id
    save_global_config(config)
    return {
        "id": resolved_id,
        "ref": asset.ref,
        "binding": None,
        "active": config.data.get("active_pack") == resolved_id,
    }


def set_active_global_pack(identifier: str) -> dict[str, Any]:
    config = load_global_config()
    entry = find_global_pack_entry(identifier, config)
    if entry is None:
        raise ProjectValidationError(f"Pack not found in global config: {identifier}")
    config.data["active_pack"] = entry.id
    save_global_config(config)
    return {
        "id": entry.id,
        "ref": entry.asset.ref,
        "binding": None,
        "active": True,
    }


def remove_global_pack(identifier: str) -> dict[str, Any]:
    config = load_global_config()
    entry = find_global_pack_entry(identifier, config)
    if entry is None:
        raise ProjectValidationError(f"Pack not found in global config: {identifier}")
    kept: list[dict[str, Any] | str] = []
    for item in config.data.get("packs", []):
        if isinstance(item, str):
            if resolve_asset_ref(item).ref == entry.asset.ref:
                continue
            kept.append(item)
            continue
        if item.get("id") == entry.id or item.get("ref") == entry.asset.ref:
            continue
        kept.append(item)
    config.data["packs"] = kept
    if config.data.get("active_pack") == entry.id:
        remaining_entries = global_pack_entries(config)
        config.data["active_pack"] = remaining_entries[0].id if remaining_entries else None
    save_global_config(config)
    return {
        "id": entry.id,
        "ref": entry.asset.ref,
        "binding": None,
    }
