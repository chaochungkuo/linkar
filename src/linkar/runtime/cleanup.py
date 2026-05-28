from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkar.assets import resolve_asset_ref
from linkar.errors import ProjectValidationError
from linkar.runtime.models import Project
from linkar.runtime.projects import load_project


@dataclass(frozen=True)
class CleanupTarget:
    template_id: str
    root: Path
    meta_path: Path
    rules: list[dict[str, Any]]
    rules_source: str


def clean_project_artifacts(
    target: str | Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    target_path = Path(target).resolve()
    targets = resolve_cleanup_targets(target_path)
    items = planned_cleanup_items(targets)
    for item in items:
        item["display_path"] = display_cleanup_path(Path(item["path"]), target_path)
    removed_items: list[dict[str, Any]] = []
    for item in items:
        if not dry_run:
            remove_cleanup_path(Path(item["path"]))
        removed_items.append(item)
    return {
        "kind": "project_clean",
        "target": str(target_path),
        "dry_run": dry_run,
        "templates": [
            {
                "template": target.template_id,
                "root": str(target.root),
                "meta": str(target.meta_path),
                "rules": target.rules,
                "rules_source": target.rules_source,
            }
            for target in targets
        ],
        "items": removed_items,
        "count": len(removed_items),
        "bytes": sum(int(item.get("bytes", 0)) for item in removed_items),
    }


def resolve_cleanup_targets(target: Path) -> list[CleanupTarget]:
    if not target.exists():
        raise ProjectValidationError(f"Cleanup target not found: {target}")
    project_file = target / "project.yaml" if target.is_dir() else target
    if project_file.name == "project.yaml" and project_file.exists():
        project = load_project(project_file)
        return resolve_project_cleanup_targets(project)

    meta_path = target / ".linkar" / "meta.json" if target.is_dir() else target
    if meta_path.name == "meta.json" and meta_path.exists():
        cleanup_target = cleanup_target_from_meta(meta_path, project=discover_parent_project(meta_path))
        return [cleanup_target] if cleanup_target.rules else []

    raise ProjectValidationError(
        "Cleanup requires a Linkar project directory, project.yaml, rendered template directory, or .linkar/meta.json."
    )


def resolve_project_cleanup_targets(project: Project) -> list[CleanupTarget]:
    targets: list[CleanupTarget] = []
    seen: set[Path] = set()
    for entry in project.data.get("templates", []):
        meta_value = entry.get("meta")
        if not isinstance(meta_value, str) or not meta_value.strip():
            continue
        meta_path = (project.root / meta_value).resolve()
        if meta_path in seen or not meta_path.exists():
            continue
        seen.add(meta_path)
        cleanup_target = cleanup_target_from_meta(meta_path, project=project)
        if cleanup_target.rules:
            targets.append(cleanup_target)
    return targets


def discover_parent_project(path: Path) -> Project | None:
    start = path if path.is_dir() else path.parent
    for parent in [start, *start.parents]:
        project_path = parent / "project.yaml"
        if project_path.exists():
            return load_project(project_path)
    return None


def cleanup_target_from_meta(meta_path: Path, *, project: Project | None = None) -> CleanupTarget:
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    template_id = metadata.get("template")
    if not isinstance(template_id, str) or not template_id:
        raise ProjectValidationError(f"Run metadata template field is missing in {meta_path}")
    rules = None
    rules_source = "none"
    latest = cleanup_rules_from_latest_configured_template(metadata, project=project, source=meta_path)
    if latest is not None:
        rules, rules_source = latest
    if rules is None:
        rules = metadata.get("cleanup")
        rules_source = "run metadata"
    if rules is None:
        recorded = cleanup_rules_from_recorded_template(metadata, source=meta_path)
        if recorded is not None:
            rules, rules_source = recorded
    if rules is None:
        rules = []
    if not isinstance(rules, list):
        raise ProjectValidationError(f"Run metadata cleanup field must be a list in {meta_path}")
    return CleanupTarget(
        template_id=template_id,
        root=meta_path.parent.parent.resolve(),
        meta_path=meta_path.resolve(),
        rules=[validate_cleanup_rule(rule, source=meta_path) for rule in rules],
        rules_source=rules_source,
    )


def cleanup_rules_from_latest_configured_template(
    metadata: dict[str, Any],
    *,
    project: Project | None,
    source: Path,
) -> tuple[list[dict[str, Any]], str] | None:
    template_id = metadata.get("template")
    if not isinstance(template_id, str):
        return None
    try:
        from linkar.runtime.templates import combined_configured_pack_entries, load_template

        entries, _ = combined_configured_pack_entries(project)
        for entry in entries:
            try:
                template = load_template(
                    template_id,
                    pack_assets=[entry.asset],
                    preferred_pack_ref=entry.asset.ref,
                )
            except Exception:
                continue
            return template.cleanup, f"latest configured template ({entry.id})"
    except Exception as exc:
        raise ProjectValidationError(
            f"Could not load latest configured cleanup rules for template '{template_id}' in {source}: {exc}"
        ) from exc
    return None


def cleanup_rules_from_recorded_template(metadata: dict[str, Any], *, source: Path) -> tuple[list[dict[str, Any]], str] | None:
    template_id = metadata.get("template")
    pack = metadata.get("pack")
    if not isinstance(template_id, str) or not isinstance(pack, dict):
        return None
    pack_ref = pack.get("ref")
    if not isinstance(pack_ref, str) or not pack_ref.strip():
        return None
    try:
        asset = resolve_asset_ref(pack_ref)
        from linkar.runtime.templates import load_template

        template = load_template(template_id, pack_assets=[asset], preferred_pack_ref=asset.ref)
    except Exception as exc:
        raise ProjectValidationError(
            f"Could not load cleanup rules for template '{template_id}' from recorded pack {pack_ref!r} in {source}: {exc}"
        ) from exc
    return template.cleanup, "recorded template"


def validate_cleanup_rule(rule: Any, *, source: Path) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise ProjectValidationError(f"Cleanup rules must be mappings in {source}")
    has_path = "path" in rule
    has_glob = "glob" in rule
    if has_path == has_glob:
        raise ProjectValidationError(f"Cleanup rules must declare exactly one of path or glob in {source}")
    key = "path" if has_path else "glob"
    value = rule.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"Cleanup rule {key} must be a non-empty string in {source}")
    assert_safe_relative_pattern(value, source=source)
    cleanup_type = rule.get("type", "any")
    if cleanup_type not in {"any", "dir", "file"}:
        raise ProjectValidationError(f"Cleanup rule type must be one of any, dir, or file in {source}")
    return {key: value.strip(), "type": cleanup_type}


def assert_safe_relative_pattern(value: str, *, source: Path) -> None:
    path = Path(value)
    if path.is_absolute():
        raise ProjectValidationError(f"Cleanup rule cannot use an absolute path in {source}: {value}")
    if ".." in path.parts:
        raise ProjectValidationError(f"Cleanup rule cannot contain '..' in {source}: {value}")


def planned_cleanup_items(targets: list[CleanupTarget]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for target in targets:
        for rule in target.rules:
            for path in matched_cleanup_paths(target.root, rule):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                items.append(
                    {
                        "template": target.template_id,
                        "root": str(target.root),
                        "path": str(resolved),
                        "rule": {key: value for key, value in rule.items() if key in {"path", "glob", "type"}},
                        "bytes": path_size(resolved),
                    }
                )
    return items


def display_cleanup_path(path: Path, target: Path) -> str:
    try:
        return str(path.resolve().relative_to(target.resolve()))
    except ValueError:
        return path.name or str(path)


def matched_cleanup_paths(root: Path, rule: dict[str, Any]) -> list[Path]:
    if "path" in rule:
        candidates = [root / rule["path"]]
    else:
        candidates = list(root.glob(rule["glob"]))
    matches: list[Path] = []
    for candidate in candidates:
        if not candidate.exists() and not candidate.is_symlink():
            continue
        resolved = candidate.resolve()
        if resolved == root.resolve():
            raise ProjectValidationError(f"Cleanup candidate cannot target the template root: {candidate}")
        try:
            resolved.relative_to(root.resolve())
        except ValueError as exc:
            raise ProjectValidationError(f"Cleanup candidate escapes template root: {candidate}") from exc
        if rule["type"] == "dir" and not candidate.is_dir():
            continue
        if rule["type"] == "file" and not candidate.is_file():
            continue
        matches.append(candidate)
    return sorted(matches)


def path_size(path: Path) -> int:
    try:
        if path.is_symlink() or path.is_file():
            return path.lstat().st_size
        total = 0
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
            current = Path(dirpath)
            total += current.lstat().st_size
            for dirname in list(dirnames):
                child = current / dirname
                if child.is_symlink():
                    total += child.lstat().st_size
                    dirnames.remove(dirname)
            for filename in filenames:
                child = current / filename
                total += child.lstat().st_size
        return total
    except OSError:
        return 0


def remove_cleanup_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
