from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from linkar.assets import resolve_asset_ref
from linkar.errors import AssetResolutionError, ParameterResolutionError
from linkar.runtime.models import BindingContext, Project, TemplateSpec
from linkar.runtime.shared import find_pack_spec_path, load_yaml, parse_param_value


def binding_asset_root(binding_ref: str | Path | None, pack_root: Path | None) -> Path | None:
    if binding_ref is None:
        return None
    if binding_ref == "default":
        if pack_root is None:
            raise AssetResolutionError("Binding 'default' requires a selected pack")
        if find_pack_spec_path(pack_root) is None:
            raise AssetResolutionError(
                f"Pack does not provide a default binding: {pack_root}. Expected linkar_pack.yaml (or legacy binding.yaml) at the pack root."
            )
        return pack_root
    binding_asset = resolve_asset_ref(binding_ref)
    if find_pack_spec_path(binding_asset.root) is None:
        raise AssetResolutionError(f"linkar_pack.yaml not found in {binding_asset.root}")
    return binding_asset.root


def load_binding_config(binding_ref: str | Path | None, pack_root: Path | None) -> tuple[Path | None, dict[str, Any]]:
    root = binding_asset_root(binding_ref, pack_root)
    if root is None:
        return None, {}
    spec_path = find_pack_spec_path(root)
    if spec_path is None:
        raise AssetResolutionError(f"linkar_pack.yaml not found in {root}")
    data = load_yaml(spec_path)
    templates = data.get("templates") or {}
    if not isinstance(templates, dict):
        raise AssetResolutionError(f"{spec_path.name} field 'templates' must be a mapping")
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
            f"linkar_pack.yaml template entry must be a mapping for '{template.id}'"
        )
    params = template_binding.get("params") or {}
    if not isinstance(params, dict):
        raise AssetResolutionError(
            f"linkar_pack.yaml params entry must be a mapping for '{template.id}'"
        )
    if key not in params:
        return False, None, None

    rule = params[key] or {}
    if not isinstance(rule, dict):
        raise AssetResolutionError(
            f"linkar_pack.yaml param rule must be a mapping for '{template.id}.{key}'"
        )
    ctx = BindingContext(template=template, project=project, resolved_params=dict(resolved_params))

    if "template" in rule or "output" in rule:
        template_name = rule.get("template")
        output_key = rule.get("output", key)
        if not template_name or not isinstance(template_name, str):
            raise AssetResolutionError(
                f"Binding template id is required for '{template.id}.{key}'"
            )
        value = ctx.latest_output(str(output_key), template_id=template_name)
        if value is None:
            raise ParameterResolutionError(
                f"Binding could not resolve output '{template_name}.{output_key}' for '{template.id}.{key}'"
            )
        return True, value, {
            "source": "binding",
            "binding_source": "output",
            "template": template_name,
            "output": str(output_key),
        }
    if "function" in rule:
        function_name = rule.get("function")
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
    if "value" in rule:
        return True, rule["value"], {
            "source": "binding",
            "binding_source": "value",
        }

    source = rule.get("from")
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
            "output": str(output_key),
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
        f"Unsupported binding rule for '{template.id}.{key}'"
    )


def resolve_params_detailed(
    template: TemplateSpec,
    cli_params: dict[str, Any] | None = None,
    project: Project | None = None,
    binding_ref: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    from linkar.runtime.projects import latest_project_output

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
                raise ParameterResolutionError(
                    f"Missing required param: {key}. Pass --{key.replace('_', '-')} VALUE, --param {key}=VALUE, add a binding, or define a default in linkar_template.yaml."
                )
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
