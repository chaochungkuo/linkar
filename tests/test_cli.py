from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "linkar.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def make_template(root: Path, template_id: str, params: str, body: str) -> Path:
    template_dir = root / template_id
    template_dir.mkdir(parents=True)
    (template_dir / "template.yaml").write_text(
        "\n".join(
            [
                f"id: {template_id}",
                "params:",
                params,
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


def test_project_init(tmp_path: Path) -> None:
    target = tmp_path / "demo"
    completed = run_cli("project", "init", str(target), "--id", "project_001", cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr

    data = yaml.safe_load((target / "project.yaml").read_text())
    assert data["id"] == "project_001"
    assert data["packs"] == []
    assert data["templates"] == []


def test_run_template_updates_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "hello",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--project",
        str(project_dir),
        "--param",
        "name=Linkar",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert len(project["templates"]) == 1
    instance = project["templates"][0]
    assert instance["id"] == "hello"
    results_file = project_dir / instance["path"] / "results" / "greeting.txt"
    assert results_file.read_text().strip() == "Hello, Linkar"

    meta = json.loads((project_dir / instance["meta"]).read_text())
    assert meta["template"] == "hello"
    assert meta["params"]["name"] == "Linkar"


def test_run_discovers_project_from_current_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "hello",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Autodiscovery",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert len(project["templates"]) == 1
    assert project["templates"][0]["id"] == "hello"


def test_local_templates_can_chain_without_pack(tmp_path: Path) -> None:
    project_dir = tmp_path / "study"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    producer = make_template(
        tmp_path / "templates",
        "produce_fastq",
        "  sample_name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${LINKAR_RESULTS_DIR}/fastq"
printf '%s\n' "${SAMPLE_NAME}" > "${LINKAR_RESULTS_DIR}/fastq/sample.txt"
""",
    )
    consumer = make_template(
        tmp_path / "templates",
        "consume_fastq",
        "  results_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
test -f "${RESULTS_DIR}/fastq/sample.txt"
cp "${RESULTS_DIR}/fastq/sample.txt" "${LINKAR_RESULTS_DIR}/consumed.txt"
""",
    )

    produce = run_cli(
        "run",
        str(producer),
        "--param",
        "sample_name=S1",
        cwd=project_dir,
    )
    assert produce.returncode == 0, produce.stderr

    consume = run_cli("run", str(consumer), cwd=project_dir)
    assert consume.returncode == 0, consume.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert [entry["id"] for entry in project["templates"]] == ["produce_fastq", "consume_fastq"]
    consumed = project_dir / project["templates"][1]["path"] / "results" / "consumed.txt"
    assert consumed.read_text().strip() == "S1"


def test_ephemeral_run_uses_linkar_runs(tmp_path: Path) -> None:
    completed = run_cli(
        "run",
        "hello",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Ephemeral",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    assert outdir.parent.name == "runs"
    assert outdir.parent.parent.name == ".linkar"
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, Ephemeral"


def test_project_pack_configuration_is_used_for_template_lookup(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    hello_template = ROOT / "examples" / "packs" / "basic" / "templates" / "hello"
    target_template = pack_root / "templates" / "hello"
    target_template.mkdir(parents=True)
    (target_template / "template.yaml").write_text((hello_template / "template.yaml").read_text())
    run_script = target_template / "run.sh"
    run_script.write_text((hello_template / "run.sh").read_text())
    run_script.chmod(0o755)

    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root)}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    completed = run_cli(
        "run",
        "hello",
        "--param",
        "name=ConfiguredPack",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    indexed = yaml.safe_load(project_file.read_text())
    assert indexed["templates"][0]["id"] == "hello"


def test_multiple_pack_flags_are_searched_in_order(tmp_path: Path) -> None:
    pack_one = tmp_path / "pack_one"
    pack_two = tmp_path / "pack_two"
    make_template(
        pack_two / "templates",
        "wave",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'Wave, %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/wave.txt"
""",
    )
    pack_one.mkdir(parents=True)

    completed = run_cli(
        "run",
        "wave",
        "--pack",
        str(pack_one),
        "--pack",
        str(pack_two),
        "--param",
        "name=Linkar",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    outdir = Path(completed.stdout.strip())
    assert (outdir / "results" / "wave.txt").read_text().strip() == "Wave, Linkar"


def test_ambiguous_template_ids_across_packs_fail_clearly(tmp_path: Path) -> None:
    pack_one = tmp_path / "pack_one"
    pack_two = tmp_path / "pack_two"
    make_template(
        pack_one / "templates",
        "dup",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'one %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/out.txt"
""",
    )
    make_template(
        pack_two / "templates",
        "dup",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'two %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/out.txt"
""",
    )

    completed = run_cli(
        "run",
        "dup",
        "--pack",
        str(pack_one),
        "--pack",
        str(pack_two),
        "--param",
        "name=Linkar",
        cwd=tmp_path,
    )
    assert completed.returncode == 1
    assert "ambiguous across packs" in completed.stderr


def test_failed_run_writes_runtime_diagnostics(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "always_fails",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
echo "boom" >&2
exit 7
""",
    )

    completed = run_cli("run", str(template), "--param", "name=x", cwd=tmp_path)
    assert completed.returncode == 1
    assert "runtime.json" in completed.stderr

    runs_root = tmp_path / ".linkar" / "runs"
    run_dirs = list(runs_root.iterdir())
    assert len(run_dirs) == 1
    runtime = json.loads((run_dirs[0] / ".linkar" / "runtime.json").read_text())
    assert runtime["returncode"] == 7
    assert "boom" in runtime["stderr"]
