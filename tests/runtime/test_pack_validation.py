from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from linkar.errors import TemplateValidationError
from linkar.runtime.pack_validation import validate_pack


ROOT = Path(__file__).resolve().parents[2]


def write_template(
    pack_root: Path,
    directory: str,
    template_id: str,
    *,
    params: dict | None = None,
    outputs: dict | None = None,
) -> None:
    root = pack_root / "templates" / directory
    root.mkdir(parents=True)
    (root / "script.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "linkar_template.yaml").write_text(
        yaml.safe_dump(
            {
                "id": template_id,
                "params": params or {},
                "outputs": outputs or {},
                "run": {"entry": "script.sh", "mode": "direct"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_validate_pack_accepts_valid_chaining_example() -> None:
    report = validate_pack(ROOT / "examples" / "packs" / "chaining")

    assert report["valid"] is True
    assert report["template_count"] == 2
    assert report["binding_count"] == 1
    assert report["errors"] == []


def test_validate_pack_reports_broken_cross_references(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    write_template(pack_root, "producer", "producer", outputs={"results_dir": {}})
    write_template(pack_root, "consumer", "consumer", params={"input": {"type": "path"}})
    (pack_root / "functions").mkdir()
    (pack_root / "functions" / "bad_resolver.py").write_text("def other():\n    pass\n", encoding="utf-8")
    (pack_root / "linkar_pack.yaml").write_text(
        yaml.safe_dump(
            {
                "templates": {
                    "consumer": {
                        "params": {
                            "unknown": {"function": "missing_resolver"},
                            "input": {"template": "producer", "output": "missing_output"},
                        },
                        "outdir": {"function": "bad_resolver"},
                    },
                    "ghost": {},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = validate_pack(pack_root)

    assert report["valid"] is False
    assert {error["code"] for error in report["errors"]} == {
        "invalid_function",
        "missing_function",
        "missing_output",
        "missing_param",
        "missing_template",
    }


def test_validate_pack_requires_pack_contract(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir()

    with pytest.raises(TemplateValidationError, match="Pack contract not found"):
        validate_pack(pack_root)


def test_validate_pack_reports_missing_templates_and_invalid_bindings(tmp_path: Path) -> None:
    missing_templates = tmp_path / "missing-templates"
    missing_templates.mkdir()
    (missing_templates / "linkar_pack.yaml").write_text("templates: {}\n", encoding="utf-8")

    missing_report = validate_pack(missing_templates)
    assert [error["code"] for error in missing_report["errors"]] == ["missing_templates_dir"]

    invalid_bindings = tmp_path / "invalid-bindings"
    (invalid_bindings / "templates").mkdir(parents=True)
    (invalid_bindings / "linkar_pack.yaml").write_text("templates: bad\n", encoding="utf-8")

    invalid_report = validate_pack(invalid_bindings)
    assert [error["code"] for error in invalid_report["errors"]] == ["invalid_bindings"]


def test_validate_pack_reports_rule_shape_and_unknown_field_errors(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    write_template(pack_root, "producer", "producer", outputs={"result": {}})
    params = {f"value_{index}": {"type": "str"} for index in range(8)}
    write_template(pack_root, "consumer", "consumer", params=params)
    (pack_root / "linkar_pack.yaml").write_text(
        yaml.safe_dump(
            {
                "templates": {
                    "consumer": {
                        "params": {
                            "value_0": "not-a-mapping",
                            "value_1": {},
                            "value_2": {"template": ""},
                            "value_3": {"template": "ghost", "output": "result"},
                            "value_4": {"template": "producer", "output": ""},
                            "value_5": {"from": "value"},
                            "value_6": {"from": "unsupported"},
                            "value_7": {"value": "x", "function": "also_x"},
                        },
                        "unexpected": True,
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = validate_pack(pack_root)
    codes = [error["code"] for error in report["errors"]]

    assert report["valid"] is False
    assert report["binding_count"] == 8
    assert codes.count("invalid_rule") == 7
    assert "missing_template" in codes
    assert "unknown_binding_field" in codes


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("def broken(:\n", "invalid_function"),
        ("def other():\n    return None\n", "invalid_function"),
        ("async def resolve(ctx):\n    return 'ok'\n", None),
    ],
)
def test_validate_pack_checks_binding_function_source(
    tmp_path: Path,
    source: str,
    expected_code: str | None,
) -> None:
    pack_root = tmp_path / "pack"
    write_template(pack_root, "consumer", "consumer", params={"value": {"type": "str"}})
    functions = pack_root / "functions"
    functions.mkdir()
    (functions / "resolver.py").write_text(source, encoding="utf-8")
    (pack_root / "linkar_pack.yaml").write_text(
        yaml.safe_dump(
            {"templates": {"consumer": {"params": {"value": {"function": "resolver"}}}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = validate_pack(pack_root)

    if expected_code is None:
        assert report["valid"] is True
    else:
        assert expected_code in {error["code"] for error in report["errors"]}
