from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = REPO_ROOT / "schemas"
EXAMPLE_PACKS = REPO_ROOT / "examples" / "packs"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.mark.parametrize(
    "schema_name",
    [
        "linkar-binding.schema.json",
        "linkar-pack.schema.json",
        "linkar-project.schema.json",
        "linkar-template.schema.json",
    ],
)
def test_schema_is_valid_draft_2020_12(schema_name: str) -> None:
    jsonschema.Draft202012Validator.check_schema(load_schema(schema_name))


def test_example_templates_match_template_schema() -> None:
    validator = jsonschema.Draft202012Validator(load_schema("linkar-template.schema.json"))
    specs = sorted(EXAMPLE_PACKS.glob("*/templates/*/linkar_template.yaml"))
    assert specs
    for spec in specs:
        validator.validate(load_yaml(spec))


def test_example_packs_match_pack_schema() -> None:
    validator = jsonschema.Draft202012Validator(load_schema("linkar-pack.schema.json"))
    specs = sorted(EXAMPLE_PACKS.glob("*/linkar_pack.yaml"))
    assert specs
    for spec in specs:
        validator.validate(load_yaml(spec))


def test_project_schema_accepts_linkar_generated_fields() -> None:
    validator = jsonschema.Draft202012Validator(load_schema("linkar-project.schema.json"))
    validator.validate(
        {
            "id": "study",
            "linkar": {"schema_version": 1, "created_with": "0.7.2"},
            "author": {
                "name": "Casey Kuo",
                "email": "casey@example.org",
                "organization": "Genomics Facility",
            },
            "active_pack": "facility",
            "packs": [
                {
                    "id": "facility",
                    "ref": "github:example/facility-pack",
                    "binding": "default",
                    "revision": "abc123",
                }
            ],
            "templates": [
                {
                    "id": "analysis",
                    "template_version": "1.0.0",
                    "instance_id": "analysis_001",
                    "path": "analysis",
                    "history_path": ".linkar/runs/analysis_001",
                    "params": {"input": "reads.fastq.gz"},
                    "outputs": {"results_dir": "analysis/results"},
                    "meta": ".linkar/meta/analysis_001.json",
                    "state": "completed",
                    "adopted": True,
                    "binding": {"ref": "default"},
                    "pack": {
                        "id": "facility",
                        "ref": "github:example/facility-pack",
                        "revision": "abc123",
                    },
                }
            ],
        }
    )


def test_schemas_reject_conflicting_contracts() -> None:
    template_validator = jsonschema.Draft202012Validator(load_schema("linkar-template.schema.json"))
    pack_validator = jsonschema.Draft202012Validator(load_schema("linkar-pack.schema.json"))

    with pytest.raises(jsonschema.ValidationError):
        template_validator.validate(
            {"id": "bad", "run": {"entry": "run.sh", "command": "bash run.sh"}}
        )
    with pytest.raises(jsonschema.ValidationError):
        pack_validator.validate(
            {"templates": {"bad": {"params": {"input": {"function": "f", "value": 1}}}}}
        )
