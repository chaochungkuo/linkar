from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from linkar.errors import AssetResolutionError, ParameterResolutionError
from linkar.runtime.bindings import (
    load_binding_config,
    resolve_params_detailed,
    resolve_params_detailed_with_warnings,
)
from linkar.runtime.projects import init_project, load_project
from linkar.runtime.shared import format_env_value, save_yaml
from linkar.runtime.templates import load_template


def make_template(root: Path, template_id: str, params: str, body: str) -> Path:
    template_dir = root / "templates" / template_id
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                f"id: {template_id}",
                "params:",
                params,
                "outputs:",
                "  results_dir: {}",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )
    run_script = template_dir / "run.sh"
    run_script.write_text(body)
    run_script.chmod(0o755)
    return template_dir


def make_binding(root: Path, content: dict) -> None:
    save_yaml(root / "linkar_pack.yaml", content)


def test_load_binding_config_accepts_legacy_binding_yaml_filename(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir(parents=True)
    save_yaml(pack_root / "binding.yaml", {"templates": {"demo": {"params": {"x": {"value": "y"}}}}})

    root, data = load_binding_config(binding_ref="default", pack_root=pack_root)

    assert root == pack_root
    assert data["templates"]["demo"]["params"]["x"]["value"] == "y"


def test_binding_output_rule_targets_specific_template_id(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root,
        "consume",
        "  results_dir:\n    type: path\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    make_binding(
        pack_root,
        {
            "templates": {
                "consume": {
                    "params": {
                        "results_dir": {
                            "template": "produce_alpha",
                            "output": "results_dir",
                        }
                    }
                }
            }
        },
    )

    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)
    project.data["templates"] = [
        {"id": "produce_alpha", "outputs": {"results_dir": "/tmp/alpha"}},
        {"id": "produce_beta", "outputs": {"results_dir": "/tmp/beta"}},
    ]
    save_yaml(project.root / "project.yaml", project.data)

    template = load_template(pack_root / "templates" / "consume")
    resolved, provenance = resolve_params_detailed(template, project=project, binding_ref="default")

    assert resolved["results_dir"] == str(Path("/tmp/alpha").resolve())
    assert provenance["results_dir"]["binding_source"] == "output"
    assert provenance["results_dir"]["template"] == "produce_alpha"
    assert provenance["results_dir"]["output"] == "results_dir"


def test_binding_function_rule_uses_shape_based_syntax(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root,
        "consume",
        "  source_dir:\n    type: path\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir(parents=True)
    (functions_dir / "locate_source.py").write_text(
        "def resolve(ctx):\n    return '/tmp/from_function'\n"
    )
    make_binding(
        pack_root,
        {"templates": {"consume": {"params": {"source_dir": {"function": "locate_source"}}}}},
    )

    template = load_template(pack_root / "templates" / "consume")
    resolved, provenance = resolve_params_detailed(template, binding_ref="default")

    assert resolved["source_dir"] == str(Path("/tmp/from_function").resolve())
    assert provenance["source_dir"]["binding_source"] == "function"
    assert provenance["source_dir"]["name"] == "locate_source"


def test_binding_rule_requires_template_when_output_is_declared(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root,
        "consume",
        "  results_dir:\n    type: path\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    make_binding(
        pack_root,
        {"templates": {"consume": {"params": {"results_dir": {"output": "results_dir"}}}}},
    )

    template = load_template(pack_root / "templates" / "consume")
    with pytest.raises(AssetResolutionError, match="Binding template id is required"):
        resolve_params_detailed(template, binding_ref="default")


def test_binding_still_accepts_legacy_from_syntax(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root,
        "consume",
        "  source_dir:\n    type: path\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    make_binding(
        pack_root,
        {"templates": {"consume": {"params": {"source_dir": {"from": "value", "value": "/tmp/legacy"}}}}},
    )

    template = load_template(pack_root / "templates" / "consume")
    resolved, provenance = resolve_params_detailed(template, binding_ref="default")

    assert resolved["source_dir"] == str(Path("/tmp/legacy").resolve())
    assert provenance["source_dir"]["binding_source"] == "value"


def test_binding_output_rule_can_resolve_list_path_values(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root,
        "consume",
        "  report_files:\n    type: list[path]\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    make_binding(
        pack_root,
        {
            "templates": {
                "consume": {
                    "params": {
                        "report_files": {
                            "template": "produce_reports",
                            "output": "fastqc_reports",
                        }
                    }
                }
            }
        },
    )

    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)
    project.data["templates"] = [
        {
            "id": "produce_reports",
            "outputs": {
                "fastqc_reports": ["/tmp/a_fastqc.html", "/tmp/b_fastqc.html"],
            },
        }
    ]
    save_yaml(project.root / "project.yaml", project.data)

    template = load_template(pack_root / "templates" / "consume")
    resolved, provenance = resolve_params_detailed(template, project=project, binding_ref="default")

    assert resolved["report_files"] == [
        str(Path("/tmp/a_fastqc.html").resolve()),
        str(Path("/tmp/b_fastqc.html").resolve()),
    ]
    assert provenance["report_files"]["template"] == "produce_reports"
    assert format_env_value(resolved["report_files"]) == (
        f"{resolved['report_files'][0]}:{resolved['report_files'][1]}"
    )


def test_binding_function_can_emit_structured_warnings(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root,
        "consume",
        "  genome:\n    type: str\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir(parents=True, exist_ok=True)
    (functions_dir / "derive_genome.py").write_text(
        "def resolve(ctx):\n"
        "    ctx.warn(\n"
        "        \"Could not derive genome from metadata.\",\n"
        "        action=\"Edit run.sh before execution.\",\n"
        "        fallback=\"__EDIT_ME_GENOME__\",\n"
        "    )\n"
        "    return '__EDIT_ME_GENOME__'\n"
    )
    make_binding(
        pack_root,
        {"templates": {"consume": {"params": {"genome": {"function": "derive_genome"}}}}},
    )

    template = load_template(pack_root / "templates" / "consume")
    resolved, provenance, warnings = resolve_params_detailed_with_warnings(
        template,
        binding_ref="default",
    )

    assert resolved["genome"] == "__EDIT_ME_GENOME__"
    assert provenance["genome"]["binding_source"] == "function"
    assert warnings == [
        {
            "template": "consume",
            "param": "genome",
            "message": "Could not derive genome from metadata.",
            "action": "Edit run.sh before execution.",
            "fallback": "__EDIT_ME_GENOME__",
        }
    ]
