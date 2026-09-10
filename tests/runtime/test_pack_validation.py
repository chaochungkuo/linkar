from __future__ import annotations

from pathlib import Path

import yaml

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
    (root / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "linkar_template.yaml").write_text(
        yaml.safe_dump(
            {
                "id": template_id,
                "params": params or {},
                "outputs": outputs or {},
                "run": {"entry": "run.sh", "mode": "direct"},
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
