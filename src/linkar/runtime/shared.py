from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from linkar.assets import ResolvedAsset
from linkar.errors import LinkarError, ParameterResolutionError
from linkar.runtime.models import PackEntry

TEMPLATE_SPEC_FILENAMES = ("linkar_template.yaml", "template.yaml")
PACK_SPEC_FILENAMES = ("linkar_pack.yaml", "binding.yaml")


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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def project_file(path: Path) -> Path:
    if path.is_dir():
        return path / "project.yaml"
    return path


def find_template_spec_path(root: Path) -> Path | None:
    for filename in TEMPLATE_SPEC_FILENAMES:
        candidate = root / filename
        if candidate.exists():
            return candidate
    return None


def find_pack_spec_path(root: Path) -> Path | None:
    for filename in PACK_SPEC_FILENAMES:
        candidate = root / filename
        if candidate.exists():
            return candidate
    return None


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


def normalize_binding_ref(binding_ref: str | Path | None) -> str | Path | None:
    if binding_ref is None:
        return None
    if isinstance(binding_ref, Path):
        return str(binding_ref.expanduser().resolve())
    return binding_ref


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
    if param_type == "list[path]":
        if isinstance(value, (list, tuple)):
            raw_items = list(value)
        else:
            raw_items = [item for item in str(value).split(os.pathsep) if item]
        return [str(Path(item).expanduser().resolve()) for item in raw_items]
    raise ParameterResolutionError(f"Unsupported param type: {param_type}")


def format_env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return os.pathsep.join(str(item) for item in value)
    return str(value)
