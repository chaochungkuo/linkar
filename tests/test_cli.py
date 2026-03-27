from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from linkar.core import load_project, load_template, resolve_project_assets, run_template
from linkar.errors import (
    AssetResolutionError,
    ProjectValidationError,
    TemplateValidationError,
)


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "linkar.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_git(*args: str, cwd: Path) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def create_git_repo(path: Path) -> str:
    run_git("init", cwd=path)
    run_git("config", "user.email", "test@example.com", cwd=path)
    run_git("config", "user.name", "Test User", cwd=path)
    run_git("add", ".", cwd=path)
    run_git("commit", "-m", "initial", cwd=path)
    return path.resolve().as_uri()


def make_template(
    root: Path,
    template_id: str,
    params: str,
    body: str,
    *,
    version: str | None = None,
) -> Path:
    template_dir = root / template_id
    template_dir.mkdir(parents=True)
    header = [f"id: {template_id}"]
    if version is not None:
        header.append(f"version: {version}")
    (template_dir / "template.yaml").write_text(
        "\n".join(
            header
            + [
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


def make_binding(root: Path, template_id: str, rules: str, function_name: str | None = None, function_body: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "binding.yaml").write_text(
        "\n".join(
            [
                "templates:",
                f"  {template_id}:",
                "    params:",
                rules,
                "",
            ]
        )
    )
    if function_name is not None and function_body is not None:
        functions_dir = root / "functions"
        functions_dir.mkdir(exist_ok=True)
        (functions_dir / f"{function_name}.py").write_text(function_body)
    return root


def test_project_init(tmp_path: Path) -> None:
    target = tmp_path / "demo"
    completed = run_cli("project", "init", str(target), "--id", "project_001", cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr

    data = yaml.safe_load((target / "project.yaml").read_text())
    assert data["id"] == "project_001"
    assert data["active_pack"] is None
    assert data["packs"] == []
    assert data["templates"] == []


def test_project_init_with_name_creates_directory(tmp_path: Path) -> None:
    completed = run_cli("project", "init", "--name", "PROJECT1", cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr

    project_dir = tmp_path / "PROJECT1"
    assert project_dir.is_dir()
    data = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert data["id"] == "PROJECT1"
    assert data["active_pack"] is None
    assert data["packs"] == []
    assert data["templates"] == []


def test_pack_commands_manage_project_configuration(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    pack_one = tmp_path / "pack_one"
    pack_two = tmp_path / "pack_two"
    pack_one.mkdir()
    pack_two.mkdir()

    added = run_cli("pack", "add", str(pack_one), "--id", "pack_one", cwd=project_dir)
    assert added.returncode == 0, added.stderr
    assert "pack_one" in added.stdout

    added_two = run_cli(
        "pack",
        "add",
        str(pack_two),
        "--id",
        "pack_two",
        "--activate",
        cwd=project_dir,
    )
    assert added_two.returncode == 0, added_two.stderr

    listed = run_cli("pack", "list", cwd=project_dir)
    assert listed.returncode == 0, listed.stderr
    assert "*\tpack_two\t" in listed.stdout
    assert "-\tpack_one\t" in listed.stdout

    shown = run_cli("pack", "show", cwd=project_dir)
    assert shown.returncode == 0, shown.stderr
    assert "pack_two" in shown.stdout

    used = run_cli("pack", "use", "pack_one", cwd=project_dir)
    assert used.returncode == 0, used.stderr
    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert project["active_pack"] == "pack_one"

    removed = run_cli("pack", "remove", "pack_two", cwd=project_dir)
    assert removed.returncode == 0, removed.stderr
    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert len(project["packs"]) == 1
    assert project["packs"][0]["id"] == "pack_one"


def test_pack_add_without_project_shows_actionable_error(tmp_path: Path) -> None:
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()

    completed = run_cli("pack", "add", str(pack_dir), cwd=tmp_path)
    assert completed.returncode == 1
    assert "Adding a pack requires an active project." in completed.stderr
    assert "pass --project PATH" in completed.stderr
    assert "linkar project init --name demo" in completed.stderr


def test_global_pack_commands_manage_user_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    pack_one = tmp_path / "pack_one"
    pack_two = tmp_path / "pack_two"
    pack_one.mkdir()
    pack_two.mkdir()
    env = {"LINKAR_HOME": str(home)}

    added = run_cli("config", "pack", "add", str(pack_one), "--id", "pack_one", cwd=tmp_path, env_extra=env)
    assert added.returncode == 0, added.stderr
    assert "pack_one" in added.stdout

    added_two = run_cli("config", "pack", "add", str(pack_two), "--id", "pack_two", "--activate", cwd=tmp_path, env_extra=env)
    assert added_two.returncode == 0, added_two.stderr

    listed = run_cli("config", "pack", "list", cwd=tmp_path, env_extra=env)
    assert listed.returncode == 0, listed.stderr
    assert "*\tpack_two\t" in listed.stdout
    assert "-\tpack_one\t" in listed.stdout

    shown = run_cli("config", "pack", "show", cwd=tmp_path, env_extra=env)
    assert shown.returncode == 0, shown.stderr
    assert "pack_two" in shown.stdout

    used = run_cli("config", "pack", "use", "pack_one", cwd=tmp_path, env_extra=env)
    assert used.returncode == 0, used.stderr

    config = yaml.safe_load((home / "config.yaml").read_text())
    assert config["active_pack"] == "pack_one"

    removed = run_cli("config", "pack", "remove", "pack_two", cwd=tmp_path, env_extra=env)
    assert removed.returncode == 0, removed.stderr

    config = yaml.safe_load((home / "config.yaml").read_text())
    assert len(config["packs"]) == 1
    assert config["packs"][0]["id"] == "pack_one"


def test_project_init_rejects_path_and_name_together(tmp_path: Path) -> None:
    completed = run_cli("project", "init", "demo", "--name", "PROJECT1", cwd=tmp_path)
    assert completed.returncode == 1
    assert "Use either PATH or --name, not both" in completed.stderr


def test_help_output_is_clean_and_descriptive(tmp_path: Path) -> None:
    root_help = run_cli("--help", cwd=tmp_path)
    assert root_help.returncode == 0, root_help.stderr
    assert "Run reusable computational templates" in root_help.stdout
    assert "Commands" in root_help.stdout
    assert "linkar run raw hello --pack" in root_help.stdout

    run_help = run_cli("run", "--help", cwd=tmp_path)
    assert run_help.returncode == 0, run_help.stderr
    assert "Run configured templates with template-aware options" in run_help.stdout
    assert "raw" in run_help.stdout

    project_init_help = run_cli("project", "init", "--help", cwd=tmp_path)
    assert project_init_help.returncode == 0, project_init_help.stderr
    assert "use --name to create a new" in project_init_help.stdout.lower()
    assert "directory automatically." in project_init_help.stdout.lower()
    assert "--name" in project_init_help.stdout
    assert "PROJECT_NAME" in project_init_help.stdout

    raw_help = run_cli("run", "raw", "--help", cwd=tmp_path)
    assert raw_help.returncode == 0, raw_help.stderr
    assert "Run any template by id or path" in raw_help.stdout
    assert "TEMPLATE" in raw_help.stdout
    assert "Options" in raw_help.stdout


def test_bare_cli_shows_helpful_guidance(tmp_path: Path) -> None:
    completed = run_cli(cwd=tmp_path)
    assert completed.returncode == 0
    assert "Run reusable computational templates" in completed.stdout
    assert "Commands" in completed.stdout
    assert "Error" not in completed.stdout


def test_parser_errors_show_contextual_help(tmp_path: Path) -> None:
    completed = run_cli("run", "raw", cwd=tmp_path)
    assert completed.returncode == 2
    assert "Missing argument 'TEMPLATE'" in completed.stderr
    assert "Usage: linkar run raw" in completed.stderr
    assert "Use -h or --help for more details." in completed.stderr


def test_run_template_updates_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "raw",
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
    assert meta["template_version"] == "0.1.0"
    assert meta["params"]["name"] == "Linkar"
    assert meta["param_provenance"]["name"]["source"] == "explicit"
    assert instance["template_version"] == "0.1.0"


def test_template_version_is_recorded_for_custom_templates(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    template = make_template(
        tmp_path / "templates",
        "versioned_template",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/name.txt"
""",
        version="1.2.3",
    )

    completed = run_cli(
        "run",
        "raw",
        str(template),
        "--param",
        "name=Versioned",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    entry = project["templates"][0]
    assert entry["template_version"] == "1.2.3"

    meta = json.loads((project_dir / entry["meta"]).read_text())
    assert meta["template_version"] == "1.2.3"


def test_run_discovers_project_from_current_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "raw",
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
        "raw",
        str(producer),
        "--param",
        "sample_name=S1",
        cwd=project_dir,
    )
    assert produce.returncode == 0, produce.stderr

    consume = run_cli("run", "raw", str(consumer), cwd=project_dir)
    assert consume.returncode == 0, consume.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert [entry["id"] for entry in project["templates"]] == ["produce_fastq", "consume_fastq"]
    consumed = project_dir / project["templates"][1]["path"] / "results" / "consumed.txt"
    assert consumed.read_text().strip() == "S1"

    consume_meta = json.loads((project_dir / project["templates"][1]["meta"]).read_text())
    assert consume_meta["param_provenance"]["results_dir"]["source"] == "project"


def test_ephemeral_run_uses_linkar_runs(tmp_path: Path) -> None:
    completed = run_cli(
        "run",
        "raw",
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
        "--name",
        "ConfiguredPack",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    indexed = yaml.safe_load(project_file.read_text())
    assert indexed["templates"][0]["id"] == "hello"
    assert indexed["templates"][0]["pack"]["id"] == "pack"


def test_global_pack_configuration_is_used_for_template_lookup(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = {"LINKAR_HOME": str(home)}
    pack_root = tmp_path / "pack"
    hello_template = ROOT / "examples" / "packs" / "basic" / "templates" / "hello"
    target_template = pack_root / "templates" / "hello"
    target_template.mkdir(parents=True)
    (target_template / "template.yaml").write_text((hello_template / "template.yaml").read_text())
    run_script = target_template / "run.sh"
    run_script.write_text((hello_template / "run.sh").read_text())
    run_script.chmod(0o755)

    added = run_cli("config", "pack", "add", str(pack_root), "--id", "global_pack", cwd=tmp_path, env_extra=env)
    assert added.returncode == 0, added.stderr

    completed = run_cli("run", "hello", "--name", "GlobalPack", cwd=tmp_path, env_extra=env)
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, GlobalPack"


def test_project_pack_takes_precedence_over_global_pack(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = {"LINKAR_HOME": str(home)}
    global_pack = tmp_path / "global_pack"
    project_pack = tmp_path / "project_pack"
    make_template(
        global_pack / "templates",
        "dup",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'global %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/out.txt"
""",
    )
    make_template(
        project_pack / "templates",
        "dup",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'project %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/out.txt"
""",
    )

    added = run_cli("config", "pack", "add", str(global_pack), "--id", "global_pack", cwd=tmp_path, env_extra=env)
    assert added.returncode == 0, added.stderr

    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path, env_extra=env)
    assert init.returncode == 0, init.stderr
    assert run_cli("pack", "add", str(project_pack), "--id", "project_pack", cwd=project_dir, env_extra=env).returncode == 0

    completed = run_cli("run", "dup", "--name", "Chosen", cwd=project_dir, env_extra=env)
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    outdir = project_dir / project["templates"][0]["path"]
    assert (outdir / "results" / "out.txt").read_text().strip() == "project Chosen"
    assert project["templates"][0]["pack"]["id"] == "project_pack"


def test_active_pack_resolves_duplicate_template_ids(tmp_path: Path) -> None:
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

    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr
    assert run_cli("pack", "add", str(pack_one), "--id", "pack_one", cwd=project_dir).returncode == 0
    assert run_cli("pack", "add", str(pack_two), "--id", "pack_two", "--activate", cwd=project_dir).returncode == 0

    completed = run_cli("run", "dup", "--name", "Linkar", cwd=project_dir)
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    outdir = project_dir / project["templates"][0]["path"]
    assert (outdir / "results" / "out.txt").read_text().strip() == "two Linkar"
    assert project["templates"][0]["pack"]["id"] == "pack_two"


def test_dynamic_template_help_exposes_template_specific_options(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "fastqc",
        "  input:\n    type: path\n    required: true\n  threads:\n    type: int\n    default: 4",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${INPUT}" > "${LINKAR_RESULTS_DIR}/input.txt"
printf '%s\n' "${THREADS}" > "${LINKAR_RESULTS_DIR}/threads.txt"
""",
    )
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root)}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    completed = run_cli("run", "fastqc", "--help", cwd=project_dir)
    assert completed.returncode == 0, completed.stderr
    assert "--input PATH" in completed.stdout
    assert "--threads INT" in completed.stdout


def test_template_test_command_runs_template_local_test_script(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "self_tested",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/name.txt"
""",
    )
    testdata = template / "testdata"
    testdata.mkdir()
    (testdata / "fixture.txt").write_text("fixture")
    test_script = template / "test.sh"
    test_script.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
test -d "${LINKAR_TEST_DIR}"
test -d "${LINKAR_RESULTS_DIR}"
test -d "${LINKAR_TESTDATA_DIR}"
cp "${LINKAR_TESTDATA_DIR}/fixture.txt" "${LINKAR_RESULTS_DIR}/copied.txt"
"""
    )
    test_script.chmod(0o755)

    completed = run_cli("test", str(template), cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert "PASS self_tested" in completed.stdout

    workspace = Path(completed.stdout.strip().split("\t", 1)[1])
    assert (workspace / "results" / "copied.txt").read_text().strip() == "fixture"
    runtime = json.loads((workspace / ".linkar" / "runtime.json").read_text())
    assert runtime["success"] is True


def test_template_test_command_can_resolve_template_from_pack(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    template = make_template(
        pack_root / "templates",
        "pack_tested",
        "  value:\n    type: str\n    default: ok",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${VALUE}" > "${LINKAR_RESULTS_DIR}/value.txt"
""",
    )
    test_script = template / "test.sh"
    test_script.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'pack test\n' > "${LINKAR_RESULTS_DIR}/result.txt"
"""
    )
    test_script.chmod(0o755)

    completed = run_cli("test", "pack_tested", "--pack", str(pack_root), cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert "PASS pack_tested" in completed.stdout


def test_template_test_command_fails_cleanly_without_test_script(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "missing_test",
        "  value:\n    type: str\n    default: ok",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${VALUE}" > "${LINKAR_RESULTS_DIR}/value.txt"
""",
    )

    completed = run_cli("test", str(template), cwd=tmp_path)
    assert completed.returncode == 1
    assert "test.sh not found" in completed.stderr


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
        "raw",
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
        "raw",
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

    completed = run_cli("run", "raw", str(template), "--param", "name=x", cwd=tmp_path)
    assert completed.returncode == 1
    assert "runtime.json" in completed.stderr

    runs_root = tmp_path / ".linkar" / "runs"
    run_dirs = list(runs_root.iterdir())
    assert len(run_dirs) == 1
    runtime = json.loads((run_dirs[0] / ".linkar" / "runtime.json").read_text())
    assert runtime["returncode"] == 7
    assert runtime["success"] is False
    assert "boom" in runtime["stderr"]


def test_pack_default_binding_can_resolve_param_from_named_output(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "produce_data",
        "  sample_name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${LINKAR_RESULTS_DIR}/dataset"
printf '%s\n' "${SAMPLE_NAME}" > "${LINKAR_RESULTS_DIR}/dataset/sample.txt"
""",
    )
    make_template(
        pack_root / "templates",
        "consume_data",
        "  source_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
cp "${SOURCE_DIR}/dataset/sample.txt" "${LINKAR_RESULTS_DIR}/consumed.txt"
""",
    )
    make_binding(
        pack_root,
        "consume_data",
        "      source_dir:\n        from: output\n        key: results_dir",
    )

    project_dir = tmp_path / "study"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root), "binding": "default"}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    produce = run_cli(
        "run",
        "produce_data",
        "--sample-name",
        "S1",
        cwd=project_dir,
    )
    assert produce.returncode == 0, produce.stderr

    consume = run_cli("run", "consume_data", cwd=project_dir)
    assert consume.returncode == 0, consume.stderr
    outdir = Path(consume.stdout.strip())
    assert (outdir / "results" / "consumed.txt").read_text().strip() == "S1"
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["param_provenance"]["source_dir"]["source"] == "binding"
    assert meta["param_provenance"]["source_dir"]["binding_source"] == "output"
    assert meta["pack"]["ref"] == str(pack_root.resolve())
    assert meta["binding"]["ref"] == "default"


def test_ad_hoc_binding_override_can_use_external_function(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "consume_literal",
        "  source_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
cp "${SOURCE_DIR}/sample.txt" "${LINKAR_RESULTS_DIR}/copied.txt"
""",
    )
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sample.txt").write_text("BOUND")
    binding_root = make_binding(
        tmp_path / "binding",
        "consume_literal",
        "      source_dir:\n        from: function\n        name: pick_source",
        function_name="pick_source",
        function_body=f"""from pathlib import Path

def resolve(ctx):
    return str(Path({str(source_dir)!r}).resolve())
""",
    )

    completed = run_cli(
        "run",
        "raw",
        "consume_literal",
        "--pack",
        str(pack_root),
        "--binding",
        str(binding_root),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    outdir = Path(completed.stdout.strip())
    assert (outdir / "results" / "copied.txt").read_text().strip() == "BOUND"
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["param_provenance"]["source_dir"]["binding_source"] == "function"
    assert meta["binding"]["ref"] == str(binding_root.resolve())


def test_project_binding_choice_overrides_pack_default(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "consume_override",
        "  source_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
cp "${SOURCE_DIR}/sample.txt" "${LINKAR_RESULTS_DIR}/override.txt"
""",
    )
    make_binding(
        pack_root,
        "consume_override",
        "      source_dir:\n        from: value\n        value: /definitely/missing",
    )
    source_dir = tmp_path / "real_source"
    source_dir.mkdir()
    (source_dir / "sample.txt").write_text("OVERRIDE")
    override_binding = make_binding(
        tmp_path / "override_binding",
        "consume_override",
        f"      source_dir:\n        from: value\n        value: {str(source_dir)!r}",
    )

    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root), "binding": str(override_binding)}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    completed = run_cli("run", "consume_override", cwd=project_dir)
    assert completed.returncode == 0, completed.stderr
    outdir = Path(completed.stdout.strip())
    assert (outdir / "results" / "override.txt").read_text().strip() == "OVERRIDE"
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["param_provenance"]["source_dir"]["binding_source"] == "value"
    assert meta["binding"]["ref"] == str(override_binding.resolve())


def test_default_parameter_provenance_is_recorded(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "with_default",
        "  greeting:\n    type: str\n    default: hi",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${GREETING}" > "${LINKAR_RESULTS_DIR}/greeting.txt"
""",
    )

    completed = run_cli("run", "raw", str(template), cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    outdir = Path(completed.stdout.strip())
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["params"]["greeting"] == "hi"
    assert meta["param_provenance"]["greeting"]["source"] == "default"


def test_git_pack_reference_is_cached_and_revision_is_recorded(tmp_path: Path) -> None:
    pack_root = tmp_path / "remote_pack"
    make_template(
        pack_root / "templates",
        "git_wave",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'Git wave, %s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/wave.txt"
""",
    )
    git_url = f"git+{create_git_repo(pack_root)}"
    linkar_home = tmp_path / "linkar_home"
    linkar_home.mkdir()

    completed = run_cli(
        "run",
        "raw",
        "git_wave",
        "--pack",
        git_url,
        "--param",
        "name=Linkar",
        cwd=tmp_path,
        env_extra={"LINKAR_HOME": str(linkar_home)},
    )
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["pack"]["ref"] == git_url
    assert meta["pack"]["revision"]
    cache_root = linkar_home / "assets"
    assert cache_root.exists()


def test_git_binding_reference_can_be_loaded_from_cache(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "git_bound",
        "  source_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
cp "${SOURCE_DIR}/sample.txt" "${LINKAR_RESULTS_DIR}/copied.txt"
""",
    )
    source_dir = tmp_path / "git_source"
    source_dir.mkdir()
    (source_dir / "sample.txt").write_text("REMOTE")
    binding_root = make_binding(
        tmp_path / "remote_binding",
        "git_bound",
        "      source_dir:\n        from: function\n        name: locate_source",
        function_name="locate_source",
        function_body=f"""from pathlib import Path

def resolve(ctx):
    return str(Path({str(source_dir)!r}).resolve())
""",
    )
    git_url = f"git+{create_git_repo(binding_root)}"
    linkar_home = tmp_path / "linkar_home_binding"
    linkar_home.mkdir()

    completed = run_cli(
        "run",
        "raw",
        "git_bound",
        "--pack",
        str(pack_root),
        "--binding",
        git_url,
        cwd=tmp_path,
        env_extra={"LINKAR_HOME": str(linkar_home)},
    )
    assert completed.returncode == 0, completed.stderr
    outdir = Path(completed.stdout.strip())
    assert (outdir / "results" / "copied.txt").read_text().strip() == "REMOTE"
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["binding"]["ref"] == git_url


def test_project_runs_command_lists_indexed_runs(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "raw",
        "hello",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=ListRuns",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    runs = run_cli("project", "runs", cwd=project_dir)
    assert runs.returncode == 0, runs.stderr
    assert "hello_001\thello\t" in runs.stdout


def test_templates_command_lists_templates_from_configured_project_packs(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "listed_template",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/name.txt"
""",
    )
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root)}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    completed = run_cli("templates", cwd=project_dir)
    assert completed.returncode == 0, completed.stderr
    assert f"listed_template\t{pack_root.resolve()}" in completed.stdout


def test_inspect_run_command_returns_metadata_json(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "raw",
        "hello",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Inspect",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    inspected = run_cli("inspect", "run", "hello_001", cwd=project_dir)
    assert inspected.returncode == 0, inspected.stderr
    metadata = json.loads(inspected.stdout)
    assert metadata["template"] == "hello"
    assert metadata["params"]["name"] == "Inspect"


def test_methods_command_aggregates_runs_in_project_order(tmp_path: Path) -> None:
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

    produce = run_cli("run", "raw", str(producer), "--param", "sample_name=S1", cwd=project_dir)
    assert produce.returncode == 0, produce.stderr
    consume = run_cli("run", "raw", str(consumer), cwd=project_dir)
    assert consume.returncode == 0, consume.stderr

    methods = run_cli("methods", cwd=project_dir)
    assert methods.returncode == 0, methods.stderr
    assert "Step 1: template 'produce_fastq'" in methods.stdout
    assert "Step 2: template 'consume_fastq'" in methods.stdout
    assert methods.stdout.index("produce_fastq") < methods.stdout.index("consume_fastq")
    assert "sample_name=S1" in methods.stdout


def test_core_raises_typed_project_and_template_errors(tmp_path: Path) -> None:
    broken_project = tmp_path / "broken_project"
    broken_project.mkdir()
    (broken_project / "project.yaml").write_text("templates: []\n")
    try:
        load_project(broken_project)
    except ProjectValidationError as exc:
        assert exc.code == "invalid_project"
    else:
        raise AssertionError("Expected ProjectValidationError")

    broken_template = tmp_path / "broken_template"
    broken_template.mkdir()
    (broken_template / "template.yaml").write_text("id: broken\nrun: {}\n")
    try:
        load_template(broken_template)
    except TemplateValidationError as exc:
        assert exc.code == "invalid_template"
    else:
        raise AssertionError("Expected TemplateValidationError")


def test_resolve_project_assets_returns_structured_pack_info(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "asset_template",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/name.txt"
""",
    )
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root), "binding": "default"}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    assets = resolve_project_assets(project_dir)
    assert assets == [
        {
            "pack_id": "pack",
            "pack_ref": str(pack_root.resolve()),
            "pack_root": str(pack_root.resolve()),
            "pack_revision": None,
            "binding": "default",
            "active": True,
        }
    ]


def test_missing_binding_asset_raises_typed_error(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "binding_error",
        "  source_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
cp "${SOURCE_DIR}/sample.txt" "${LINKAR_RESULTS_DIR}/copied.txt"
""",
    )
    try:
        run_template(
            "binding_error",
            pack_refs=[str(pack_root)],
            binding_ref=str(tmp_path / "missing_binding"),
        )
    except AssetResolutionError as exc:
        assert exc.code == "asset_resolution_error"
        assert "Asset not found" in str(exc)
    else:
        raise AssertionError("Expected AssetResolutionError")
