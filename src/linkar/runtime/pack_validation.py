from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from linkar.assets import resolve_asset_ref
from linkar.errors import LinkarError, TemplateValidationError
from linkar.runtime.models import TemplateSpec
from linkar.runtime.shared import find_pack_spec_path, find_template_spec_path, load_yaml
from linkar.runtime.templates import load_template


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _available_outputs(template: TemplateSpec) -> set[str]:
    return set(template.outputs) or {"results_dir"}


def _validate_function(pack_root: Path, name: Any, path: str) -> list[dict[str, str]]:
    if not isinstance(name, str) or not name or not name.isidentifier():
        return [_issue("invalid_function", path, "Binding function must be a valid Python identifier")]
    function_path = pack_root / "functions" / f"{name}.py"
    if not function_path.is_file():
        return [_issue("missing_function", path, f"Binding function file not found: functions/{name}.py")]
    try:
        tree = ast.parse(function_path.read_text(encoding="utf-8"), filename=str(function_path))
    except (OSError, SyntaxError) as exc:
        return [_issue("invalid_function", path, f"Cannot parse functions/{name}.py: {exc}")]
    has_resolve = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "resolve"
        for node in tree.body
    )
    if not has_resolve:
        return [_issue("invalid_function", path, f"functions/{name}.py must define resolve(ctx)")]
    return []


def _validate_rule(
    *,
    pack_root: Path,
    rule: Any,
    rule_path: str,
    target_name: str,
    templates: dict[str, TemplateSpec],
) -> list[dict[str, str]]:
    if not isinstance(rule, dict):
        return [_issue("invalid_rule", rule_path, "Binding rule must be a mapping")]

    source_groups = [
        "output" if "template" in rule or "output" in rule else None,
        "function" if "function" in rule else None,
        "value" if "value" in rule and "from" not in rule else None,
        "legacy" if "from" in rule else None,
    ]
    selected = [group for group in source_groups if group is not None]
    if len(selected) != 1:
        return [_issue("invalid_rule", rule_path, "Binding rule must declare exactly one source")]

    source = selected[0]
    if source == "function":
        return _validate_function(pack_root, rule.get("function"), f"{rule_path}.function")
    if source == "value":
        return []
    if source == "output":
        template_id = rule.get("template")
        if not isinstance(template_id, str) or not template_id:
            return [_issue("invalid_rule", rule_path, "Output binding requires a template id")]
        upstream = templates.get(template_id)
        if upstream is None:
            return [_issue("missing_template", f"{rule_path}.template", f"Template not found in pack: {template_id}")]
        output_name = rule.get("output", target_name)
        if not isinstance(output_name, str) or not output_name:
            return [_issue("invalid_rule", f"{rule_path}.output", "Output name must be a non-empty string")]
        if output_name not in _available_outputs(upstream):
            return [
                _issue(
                    "missing_output",
                    f"{rule_path}.output",
                    f"Template '{template_id}' does not declare output '{output_name}'",
                )
            ]
        return []

    legacy_source = rule.get("from")
    if legacy_source == "function":
        return _validate_function(pack_root, rule.get("name"), f"{rule_path}.name")
    if legacy_source == "value":
        if "value" not in rule:
            return [_issue("invalid_rule", rule_path, "Literal binding requires value")]
        return []
    if legacy_source == "output":
        output_name = rule.get("key", target_name)
        if not isinstance(output_name, str) or not output_name:
            return [_issue("invalid_rule", f"{rule_path}.key", "Output key must be a non-empty string")]
        if not any(output_name in _available_outputs(template) for template in templates.values()):
            return [
                _issue(
                    "missing_output",
                    f"{rule_path}.key",
                    f"No template in the pack declares output '{output_name}'",
                )
            ]
        return []
    return [_issue("invalid_rule", rule_path, f"Unsupported binding source: {legacy_source!r}")]


def validate_pack(ref: str | Path) -> dict[str, Any]:
    asset = resolve_asset_ref(str(ref))
    pack_root = asset.root
    spec_path = find_pack_spec_path(pack_root)
    if spec_path is None:
        raise TemplateValidationError(
            f"Pack contract not found in {pack_root}. Expected linkar_pack.yaml (or legacy binding.yaml)."
        )

    issues: list[dict[str, str]] = []
    templates: dict[str, TemplateSpec] = {}
    templates_dir = pack_root / "templates"
    if not templates_dir.is_dir():
        issues.append(_issue("missing_templates_dir", "templates", "Pack templates directory not found"))
    else:
        for child in sorted(path for path in templates_dir.iterdir() if path.is_dir()):
            relative = f"templates/{child.name}"
            if find_template_spec_path(child) is None:
                # Runtime discovery treats support directories as non-templates.
                continue
            try:
                template = load_template(child)
            except LinkarError as exc:
                issues.append(_issue("invalid_template", relative, str(exc)))
                continue
            if template.id in templates:
                issues.append(
                    _issue("duplicate_template", relative, f"Duplicate template id: {template.id}")
                )
                continue
            templates[template.id] = template

    pack_data = load_yaml(spec_path)
    bindings = pack_data.get("templates") or {}
    if not isinstance(bindings, dict):
        issues.append(_issue("invalid_bindings", "templates", "Pack templates field must be a mapping"))
        bindings = {}

    binding_count = 0
    for template_id, raw_binding in bindings.items():
        binding_path = f"templates.{template_id}"
        template = templates.get(template_id)
        if template is None:
            issues.append(
                _issue("missing_template", binding_path, f"Binding targets missing template: {template_id}")
            )
            continue
        binding = raw_binding or {}
        if not isinstance(binding, dict):
            issues.append(_issue("invalid_binding", binding_path, "Template binding must be a mapping"))
            continue
        params = binding.get("params") or {}
        if not isinstance(params, dict):
            issues.append(_issue("invalid_binding", f"{binding_path}.params", "Params must be a mapping"))
            params = {}
        for param_name, rule in params.items():
            binding_count += 1
            rule_path = f"{binding_path}.params.{param_name}"
            if param_name not in template.params:
                issues.append(
                    _issue(
                        "missing_param",
                        rule_path,
                        f"Template '{template_id}' does not declare param '{param_name}'",
                    )
                )
            issues.extend(
                _validate_rule(
                    pack_root=pack_root,
                    rule=rule,
                    rule_path=rule_path,
                    target_name=str(param_name),
                    templates=templates,
                )
            )
        if "outdir" in binding:
            binding_count += 1
            issues.extend(
                _validate_rule(
                    pack_root=pack_root,
                    rule=binding.get("outdir"),
                    rule_path=f"{binding_path}.outdir",
                    target_name="outdir",
                    templates=templates,
                )
            )
        unknown = sorted(set(binding) - {"params", "outdir"})
        for key in unknown:
            issues.append(_issue("unknown_binding_field", f"{binding_path}.{key}", "Unknown binding field"))

    return {
        "kind": "pack_validation",
        "pack_ref": asset.ref,
        "pack_root": str(pack_root),
        "revision": asset.revision,
        "valid": not issues,
        "template_count": len(templates),
        "binding_count": binding_count,
        "errors": issues,
    }
