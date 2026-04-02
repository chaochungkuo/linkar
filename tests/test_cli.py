from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from rich.console import Console

from linkar import __version__
from linkar.core import load_project, load_template, resolve_project_assets, run_template
from linkar.errors import (
    AssetResolutionError,
    ProjectValidationError,
    TemplateValidationError,
)
from linkar.ui import CliUI, THEME


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


def skip_if_known_pixi_runtime_panic(completed: subprocess.CompletedProcess[str]) -> None:
    if completed.returncode == 0:
        return
    match = re.search(r"See (.+/\.linkar/runtime\.json)", completed.stderr)
    if not match:
        return
    runtime_path = Path(match.group(1))
    if not runtime_path.exists():
        return
    runtime = json.loads(runtime_path.read_text())
    stderr = runtime.get("stderr", "")
    if "Attempted to create a NULL object" in stderr or "the operation was cancelled" in stderr:
        pytest.skip("pixi runtime panicked in this macOS sandbox environment")


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
    description: str | None = None,
    outputs: str | None = None,
    entry_name: str = "run.sh",
) -> Path:
    template_dir = root / template_id
    template_dir.mkdir(parents=True)
    header = [f"id: {template_id}"]
    if version is not None:
        header.append(f"version: {version}")
    if description is not None:
        header.append(f"description: {description}")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            header
            + [
                "params:",
                params,
                "outputs:",
                outputs or "  results_dir: {}",
                "run:",
                f"  entry: {entry_name}",
                "  mode: direct",
                "",
            ]
        )
    )
    run_script = template_dir / entry_name
    run_script.parent.mkdir(parents=True, exist_ok=True)
    run_script.write_text(body)
    run_script.chmod(0o755)
    return template_dir


def make_binding(root: Path, template_id: str, rules: str, function_name: str | None = None, function_body: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "linkar_pack.yaml").write_text(
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


def test_completion_bash_prints_completion_script(tmp_path: Path) -> None:
    completed = run_cli("completion", "bash", cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert "_LINKAR_COMPLETE" in completed.stdout
    assert "complete -o nosort -F" in completed.stdout
    assert "linkar" in completed.stdout


def test_completion_zsh_prints_completion_script(tmp_path: Path) -> None:
    completed = run_cli("completion", "zsh", cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert "_LINKAR_COMPLETE" in completed.stdout
    assert "#compdef linkar" in completed.stdout
    assert "compdef" in completed.stdout


def test_completion_install_bash_writes_user_completion_file(tmp_path: Path) -> None:
    env = {"HOME": str(tmp_path / "home")}
    completed = run_cli("completion", "install", "bash", "--yes", cwd=tmp_path, env_extra=env)
    assert completed.returncode == 0, completed.stderr
    target = Path(completed.stdout.strip())
    assert target == (tmp_path / "home" / ".local" / "share" / "bash-completion" / "completions" / "linkar")
    assert target.read_text() == "$(linkar completion bash)\n"


def test_completion_install_zsh_writes_user_completion_file(tmp_path: Path) -> None:
    env = {"HOME": str(tmp_path / "home")}
    completed = run_cli("completion", "install", "zsh", "--yes", cwd=tmp_path, env_extra=env)
    assert completed.returncode == 0, completed.stderr
    target = Path(completed.stdout.strip())
    assert target == (tmp_path / "home" / ".zsh" / "completions" / "_linkar")
    assert target.read_text() == "$(linkar completion zsh)\n"


def test_completion_install_bash_rc_file_appends_eval_line(tmp_path: Path) -> None:
    rc_file = tmp_path / ".bashrc"
    rc_file.write_text("# existing\n", encoding="utf-8")
    completed = run_cli(
        "completion",
        "install",
        "bash",
        "--yes",
        "--rc-file",
        str(rc_file),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(rc_file)
    assert rc_file.read_text(encoding="utf-8") == '# existing\neval "$(linkar completion bash)"\n'


def test_completion_install_bash_rc_file_is_idempotent(tmp_path: Path) -> None:
    rc_file = tmp_path / ".bashrc"
    rc_file.write_text('eval "$(linkar completion bash)"\n', encoding="utf-8")
    completed = run_cli(
        "completion",
        "install",
        "bash",
        "--yes",
        "--rc-file",
        str(rc_file),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    assert rc_file.read_text(encoding="utf-8") == 'eval "$(linkar completion bash)"\n'


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


def test_project_init_uses_global_author_defaults(tmp_path: Path) -> None:
    env = {"LINKAR_HOME": str(tmp_path / "home")}
    configured = run_cli(
        "config",
        "author",
        "set",
        "--name",
        "Casey Kuo",
        "--email",
        "casey@example.org",
        "--organization",
        "IZKF",
        cwd=tmp_path,
        env_extra=env,
    )
    assert configured.returncode == 0, configured.stderr

    completed = run_cli("project", "init", "--name", "study", cwd=tmp_path, env_extra=env)
    assert completed.returncode == 0, completed.stderr

    data = yaml.safe_load((tmp_path / "study" / "project.yaml").read_text())
    assert data["author"] == {
        "name": "Casey Kuo",
        "email": "casey@example.org",
        "organization": "IZKF",
    }


def test_project_init_author_options_override_global_defaults(tmp_path: Path) -> None:
    env = {"LINKAR_HOME": str(tmp_path / "home")}
    configured = run_cli(
        "config",
        "author",
        "set",
        "--name",
        "Casey Kuo",
        "--email",
        "casey@example.org",
        "--organization",
        "IZKF",
        cwd=tmp_path,
        env_extra=env,
    )
    assert configured.returncode == 0, configured.stderr

    completed = run_cli(
        "project",
        "init",
        "--name",
        "study",
        "--author-name",
        "Alex Example",
        "--author-email",
        "alex@example.org",
        cwd=tmp_path,
        env_extra=env,
    )
    assert completed.returncode == 0, completed.stderr

    data = yaml.safe_load((tmp_path / "study" / "project.yaml").read_text())
    assert data["author"] == {
        "name": "Alex Example",
        "email": "alex@example.org",
        "organization": "IZKF",
    }


def test_project_init_can_adopt_existing_run(tmp_path: Path) -> None:
    ad_hoc = run_cli(
        "run",
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Adopted",
        cwd=tmp_path,
    )
    assert ad_hoc.returncode == 0, ad_hoc.stderr
    run_dir = Path(ad_hoc.stdout.strip())

    completed = run_cli("project", "init", "--name", "study", "--adopt", str(run_dir), cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr

    data = yaml.safe_load((tmp_path / "study" / "project.yaml").read_text())
    assert len(data["templates"]) == 1
    entry = data["templates"][0]
    assert entry["id"] == "simple_echo"
    assert entry["instance_id"].startswith("simple_echo_")
    assert entry["adopted"] is True
    assert entry["params"]["name"] == "Adopted"
    assert entry["outputs"]["greeting_file"].endswith("results/greeting.txt")
    assert entry["path"] == str(run_dir)
    assert entry["history_path"] == str(run_dir)


def test_project_adopt_run_imports_existing_linkar_run(tmp_path: Path) -> None:
    ad_hoc = run_cli(
        "run",
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Later",
        cwd=tmp_path,
    )
    assert ad_hoc.returncode == 0, ad_hoc.stderr
    run_dir = Path(ad_hoc.stdout.strip())

    init = run_cli("project", "init", "--name", "study", cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    adopted = run_cli("project", "adopt-run", str(run_dir), cwd=tmp_path / "study")
    assert adopted.returncode == 0, adopted.stderr

    data = yaml.safe_load((tmp_path / "study" / "project.yaml").read_text())
    assert len(data["templates"]) == 1
    entry = data["templates"][0]
    assert entry["adopted"] is True
    assert entry["params"]["name"] == "Later"
    assert entry["meta"].endswith(".linkar/meta.json")


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
    assert "human-friendly CLI" in root_help.stdout
    assert "machine-readable" in root_help.stdout
    assert "Commands" in root_help.stdout
    assert "linkar run simple_echo --pack" in root_help.stdout
    assert "linkar render demultiplex --outdir" in root_help.stdout
    assert "linkar serve --port 8000" in root_help.stdout
    assert "linkar mcp serve" in root_help.stdout
    assert "╭─ Options" in root_help.stdout

    run_help = run_cli("run", "--help", cwd=tmp_path)
    assert run_help.returncode == 0, run_help.stderr
    assert "Run templates with template-aware options or the generic TEMPLATE" in run_help.stdout
    assert "raw" not in run_help.stdout
    assert "╭─ Options" in run_help.stdout
    assert "╭─ Commands" in run_help.stdout

    render_help = run_cli("render", "--help", cwd=tmp_path)
    assert render_help.returncode == 0, render_help.stderr
    assert "Render template bundles with template-aware options" in render_help.stdout
    assert "raw" not in render_help.stdout
    assert "╭─ Options" in render_help.stdout
    assert "╭─ Commands" in render_help.stdout

    mcp_help = run_cli("mcp", "--help", cwd=tmp_path)
    assert mcp_help.returncode == 0, mcp_help.stderr
    assert "local MCP server" in mcp_help.stdout

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
    assert "╭─ Options" in raw_help.stdout


def test_bare_cli_shows_helpful_guidance(tmp_path: Path) -> None:
    completed = run_cli(cwd=tmp_path)
    assert completed.returncode == 0
    assert "Run reusable computational templates" in completed.stdout
    assert "Commands" in completed.stdout
    assert "Error" not in completed.stdout


def test_parser_errors_show_contextual_help(tmp_path: Path) -> None:
    completed = run_cli("run", cwd=tmp_path)
    assert completed.returncode == 0
    assert "Usage: linkar run" in completed.stdout
    assert "Commands" in completed.stdout

    rendered = run_cli("render", cwd=tmp_path)
    assert rendered.returncode == 0
    assert "Usage: linkar render" in rendered.stdout
    assert "Commands" in rendered.stdout


def test_run_template_updates_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "simple_echo",
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
    assert instance["id"] == "simple_echo"
    results_file = project_dir / instance["path"] / "results" / "greeting.txt"
    assert results_file.read_text().strip() == "Hello, Linkar"

    meta = json.loads((project_dir / instance["meta"]).read_text())
    assert meta["template"] == "simple_echo"
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


def test_script_entry_renders_self_contained_run_launcher(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    template = make_template(
        tmp_path / "templates",
        "scripted_template",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/name.txt"
""",
        entry_name="script.sh",
    )

    completed = run_cli(
        "run",
        str(template),
        "--param",
        "name=Rendered",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    outdir = project_dir / project["templates"][0]["path"]
    assert (outdir / "run.sh").is_file()
    assert (outdir / "script.sh").is_file()
    assert (outdir / "results" / "name.txt").read_text().strip() == "Rendered"

    rerun = subprocess.run(
        [str(outdir / "run.sh")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert rerun.returncode == 0, rerun.stderr
    assert (outdir / "results" / "name.txt").read_text().strip() == "Rendered"


def test_render_command_only_stages_launcher_without_running(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "render_only_cli",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/name.txt"
""",
    )

    completed = run_cli(
        "render",
        str(template),
        "--param",
        "name=Rendered",
        "--outdir",
        str(tmp_path / "rendered"),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr

    rendered_dir = tmp_path / "rendered"
    assert (rendered_dir / "run.sh").is_file()
    assert not (rendered_dir / "linkar-run.sh").exists()
    assert not (rendered_dir / "linkar_template.yaml").exists()
    assert not (rendered_dir / "results" / "name.txt").exists()


def test_collect_command_updates_outputs_after_manual_run(tmp_path: Path) -> None:
    completed = run_cli(
        "render",
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Collected",
        "--outdir",
        str(tmp_path / "rendered"),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr

    rendered_dir = tmp_path / "rendered"
    manual = subprocess.run(
        [str(rendered_dir / "run.sh")],
        cwd=rendered_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert manual.returncode == 0, manual.stderr

    collect = run_cli("collect", str(rendered_dir), cwd=tmp_path)
    assert collect.returncode == 0, collect.stderr

    meta = json.loads((rendered_dir / ".linkar" / "meta.json").read_text())
    assert meta["outputs"]["greeting_file"] == str((rendered_dir / "results" / "greeting.txt").resolve())


def test_run_command_executes_even_for_legacy_render_mode_template(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "legacy_render_cli",
        "",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'executed\n' > "${LINKAR_RESULTS_DIR}/name.txt"
""",
    )
    spec_path = template / "linkar_template.yaml"
    spec_path.write_text(spec_path.read_text().replace("mode: direct", "mode: render"))

    completed = run_cli(
        "run",
        str(template),
        "--outdir",
        str(tmp_path / "executed"),
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "executed" / "results" / "name.txt").read_text().strip() == "executed"


def test_run_discovers_project_from_current_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Autodiscovery",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    assert len(project["templates"]) == 1
    assert project["templates"][0]["id"] == "simple_echo"


def test_project_run_uses_stable_project_path_and_history_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=StablePath",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    assert outdir == (project_dir / "simple_echo")
    assert outdir.is_symlink()
    assert outdir.resolve().parent.name == "runs"
    assert (outdir / "results" / "greeting.txt").read_text().strip() == "Hello, StablePath"

    project = yaml.safe_load((project_dir / "project.yaml").read_text())
    entry = project["templates"][0]
    assert entry["path"] == "simple_echo"
    assert entry["history_path"] == ".linkar/runs/simple_echo_001"
    assert entry["meta"] == ".linkar/runs/simple_echo_001/.linkar/meta.json"


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

    consume_meta = json.loads((project_dir / project["templates"][1]["meta"]).read_text())
    assert consume_meta["param_provenance"]["results_dir"]["source"] == "project"


def test_ephemeral_run_uses_linkar_runs(tmp_path: Path) -> None:
    completed = run_cli(
        "run",
        "simple_echo",
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


def test_pixi_echo_can_run_as_real_template(tmp_path: Path) -> None:
    completed = run_cli(
        "run",
        "pixi_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=PixiRuntime",
        cwd=tmp_path,
    )
    skip_if_known_pixi_runtime_panic(completed)
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    assert (outdir / "pixi.toml").is_file()
    assert (outdir / "write_greeting.py").is_file()
    assert (outdir / "greeting.txt").read_text().strip() == "Hello from pixi, PixiRuntime"


def test_pixi_pytest_can_run_as_real_template(tmp_path: Path) -> None:
    completed = run_cli(
        "run",
        "pixi_pytest",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=PytestRuntime",
        cwd=tmp_path,
    )
    skip_if_known_pixi_runtime_panic(completed)
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    assert (outdir / "pixi.toml").is_file()
    assert (outdir / "test_greeting.py").is_file()
    report_text = (outdir / "pytest-report.xml").read_text()
    assert 'tests="1"' in report_text
    assert 'failures="0"' in report_text


def test_basic_example_templates_are_valid(tmp_path: Path) -> None:
    pack_root = ROOT / "examples" / "packs" / "basic"

    for template_id in [
        "simple_echo",
        "simple_file_input",
        "simple_boolean_flag",
        "download_test_data",
        "fastq_stats",
        "pixi_echo",
        "pixi_pytest",
    ]:
        completed = run_cli("test", template_id, "--pack", str(pack_root), cwd=tmp_path)
        assert completed.returncode == 0, completed.stderr


def test_chaining_example_pack_can_resolve_default_binding(tmp_path: Path) -> None:
    pack_root = ROOT / "examples" / "packs" / "chaining"
    project_dir = tmp_path / "project"

    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    added = run_cli("pack", "add", str(pack_root), "--id", "chaining", "--binding", "default", cwd=project_dir)
    assert added.returncode == 0, added.stderr

    produce = run_cli("run", "produce_message", "--message", "hello chain", cwd=project_dir)
    assert produce.returncode == 0, produce.stderr

    consume = run_cli("run", "consume_message", cwd=project_dir)
    assert consume.returncode == 0, consume.stderr

    outdir = Path(consume.stdout.strip())
    assert (outdir / "results" / "consumed.txt").read_text().strip() == "consumed: hello chain"


def test_pack_management_examples_follow_active_pack_selection(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    pack_one = ROOT / "examples" / "packs" / "pack_management" / "pack_one"
    pack_two = ROOT / "examples" / "packs" / "pack_management" / "pack_two"

    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr
    assert run_cli("pack", "add", str(pack_one), "--id", "pack_one", cwd=project_dir).returncode == 0
    assert run_cli("pack", "add", str(pack_two), "--id", "pack_two", "--activate", cwd=project_dir).returncode == 0

    completed = run_cli("run", "dup", "--name", "Example", cwd=project_dir)
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    assert (outdir / "results" / "out.txt").read_text().strip() == "pack two: Example"


def test_project_pack_configuration_is_used_for_template_lookup(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    hello_template = ROOT / "examples" / "packs" / "basic" / "templates" / "simple_echo"
    target_template = pack_root / "templates" / "simple_echo"
    shutil.copytree(hello_template, target_template)

    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root)}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    completed = run_cli(
        "run",
        "simple_echo",
        "--name",
        "ConfiguredPack",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    indexed = yaml.safe_load(project_file.read_text())
    assert indexed["templates"][0]["id"] == "simple_echo"
    assert indexed["templates"][0]["pack"]["id"] == "pack"


def test_global_pack_configuration_is_used_for_template_lookup(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = {"LINKAR_HOME": str(home)}
    pack_root = tmp_path / "pack"
    hello_template = ROOT / "examples" / "packs" / "basic" / "templates" / "simple_echo"
    target_template = pack_root / "templates" / "simple_echo"
    shutil.copytree(hello_template, target_template)

    added = run_cli("config", "pack", "add", str(pack_root), "--id", "global_pack", cwd=tmp_path, env_extra=env)
    assert added.returncode == 0, added.stderr

    completed = run_cli("run", "simple_echo", "--name", "GlobalPack", cwd=tmp_path, env_extra=env)
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
    assert "--input" in completed.stdout
    assert "PATH" in completed.stdout
    assert "--threads" in completed.stdout
    assert "INT" in completed.stdout
    assert "╭─ Options" in completed.stdout


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
    assert "test.sh or test.py not found" in completed.stderr


def test_template_test_command_supports_python_entrypoint(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "python_tested",
        "  value:\n    type: str\n    default: ok",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${VALUE}" > "${LINKAR_RESULTS_DIR}/value.txt"
""",
    )
    test_python = template / "test.py"
    test_python.write_text(
        """from __future__ import annotations

import os
import subprocess
from pathlib import Path

os.environ.setdefault("VALUE", "ok")
os.environ.setdefault("LINKAR_RESULTS_DIR", "./.tmp-test/results")
Path(os.environ["LINKAR_RESULTS_DIR"]).mkdir(parents=True, exist_ok=True)
subprocess.run(["./run.sh"], check=True)
results_dir = Path(os.environ["LINKAR_RESULTS_DIR"])
assert (results_dir / "value.txt").read_text().strip() == "ok"
"""
    )

    completed = run_cli("test", str(template), cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert "PASS python_tested" in completed.stdout


def test_template_test_command_rejects_multiple_test_entrypoints(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "confused_test",
        "  value:\n    type: str\n    default: ok",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${VALUE}" > "${LINKAR_RESULTS_DIR}/value.txt"
""",
    )
    test_shell = template / "test.sh"
    test_shell.write_text("#!/usr/bin/env bash\nset -euo pipefail\n")
    test_shell.chmod(0o755)
    (template / "test.py").write_text("print('noop')\n")

    completed = run_cli("test", str(template), cwd=tmp_path)
    assert completed.returncode == 1
    assert "Both test.sh and test.py exist" in completed.stderr


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
    assert "Use --pack REF" in completed.stderr


def test_missing_template_suggests_pack_or_path_resolution(tmp_path: Path) -> None:
    completed = run_cli("run", "missing_template", cwd=tmp_path)

    assert completed.returncode == 1
    assert "Template not found: missing_template" in completed.stderr
    assert "explicit template path" in completed.stderr
    assert "linkar pack add REF" in completed.stderr


def test_missing_required_param_suggests_cli_binding_or_default(tmp_path: Path) -> None:
    template = make_template(
        tmp_path / "templates",
        "needs_name",
        "  sample_name:\n    type: str\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )

    completed = run_cli("run", str(template), cwd=tmp_path)

    assert completed.returncode == 1
    assert "Missing required param: sample_name" in completed.stderr
    assert "--sample-name VALUE" in completed.stderr
    assert "--param sample_name=VALUE" in completed.stderr
    assert "define a default in linkar_template.yaml" in completed.stderr


def test_binding_function_failures_surface_as_linkar_errors(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "needs_binding",
        "  samplesheet:\n    type: path\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    make_binding(
        pack_root,
        "needs_binding",
        "      samplesheet:\n        function: fail_samplesheet",
        function_name="fail_samplesheet",
        function_body="""def resolve(ctx):\n    raise RuntimeError('samplesheet could not be generated because no demultiplex demux_fastq_files output was found in the current project')\n""",
    )

    completed = run_cli(
        "run",
        "needs_binding",
        "--pack",
        str(pack_root),
        "--binding",
        "default",
        cwd=tmp_path,
    )

    assert completed.returncode == 1
    assert "Binding function failed for 'needs_binding.samplesheet'" in completed.stderr
    assert "no demultiplex demux_fastq_files output was found in the current project" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_render_shows_structured_binding_warnings(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    template = make_template(
        pack_root / "templates",
        "warns_on_render",
        "  genome:\n    type: str\n    required: true",
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf '%s\\n' \"${GENOME}\" > \"${LINKAR_RESULTS_DIR}/genome.txt\"\n",
    )
    template_yaml = template / "linkar_template.yaml"
    template_yaml.write_text(
        template_yaml.read_text().replace("  entry: run.sh\n  mode: direct", "  command: >-\n    printf '%s\\n' \"${GENOME}\" > \"${LINKAR_RESULTS_DIR}/genome.txt\"\n  mode: render")
    )
    make_binding(
        pack_root,
        "warns_on_render",
        "      genome:\n        function: derive_genome",
        function_name="derive_genome",
        function_body=(
            "def resolve(ctx):\n"
            "    ctx.warn(\n"
            "        \"Could not derive genome from metadata.\",\n"
            "        action=\"Edit run.sh before execution.\",\n"
            "        fallback=\"__EDIT_ME_GENOME__\",\n"
            "    )\n"
            "    return '__EDIT_ME_GENOME__'\n"
        ),
    )

    completed = run_cli(
        "render",
        "warns_on_render",
        "--pack",
        str(pack_root),
        "--binding",
        "default",
        "--outdir",
        str(tmp_path / "rendered"),
        cwd=tmp_path,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Could not derive genome from metadata." in completed.stderr
    assert "__EDIT_ME_GENOME__" in completed.stderr
    assert "Edit run.sh before execution." in completed.stderr
    meta = json.loads((tmp_path / "rendered" / ".linkar" / "meta.json").read_text())
    assert meta["warnings"] == [
        {
            "template": "warns_on_render",
            "param": "genome",
            "message": "Could not derive genome from metadata.",
            "action": "Edit run.sh before execution.",
            "fallback": "__EDIT_ME_GENOME__",
        }
    ]


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
        "      source_dir:\n        template: produce_data\n        output: results_dir",
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
    assert meta["param_provenance"]["source_dir"]["template"] == "produce_data"
    assert meta["param_provenance"]["source_dir"]["output"] == "results_dir"
    assert meta["pack"]["ref"] == str(pack_root.resolve())
    assert meta["binding"]["ref"] == "default"


def test_binding_output_rule_can_target_specific_template_id(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "produce_alpha",
        "  message:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${MESSAGE}" > "${LINKAR_RESULTS_DIR}/message.txt"
""",
    )
    make_template(
        pack_root / "templates",
        "produce_beta",
        "  message:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${MESSAGE}" > "${LINKAR_RESULTS_DIR}/message.txt"
""",
    )
    make_template(
        pack_root / "templates",
        "consume_selected",
        "  results_dir:\n    type: path\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
cp "${RESULTS_DIR}/message.txt" "${LINKAR_RESULTS_DIR}/selected.txt"
""",
    )
    make_binding(
        pack_root,
        "consume_selected",
        "      results_dir:\n        template: produce_alpha\n        output: results_dir",
    )

    project_dir = tmp_path / "study"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    project_file = project_dir / "project.yaml"
    project = yaml.safe_load(project_file.read_text())
    project["packs"] = [{"ref": str(pack_root), "binding": "default"}]
    project_file.write_text(yaml.safe_dump(project, sort_keys=False))

    alpha = run_cli("run", "produce_alpha", "--message", "ALPHA", cwd=project_dir)
    assert alpha.returncode == 0, alpha.stderr
    beta = run_cli("run", "produce_beta", "--message", "BETA", cwd=project_dir)
    assert beta.returncode == 0, beta.stderr

    consume = run_cli("run", "consume_selected", cwd=project_dir)
    assert consume.returncode == 0, consume.stderr
    outdir = Path(consume.stdout.strip())
    assert (outdir / "results" / "selected.txt").read_text().strip() == "ALPHA"


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
        "      source_dir:\n        function: pick_source",
        function_name="pick_source",
        function_body=f"""from pathlib import Path

def resolve(ctx):
    return str(Path({str(source_dir)!r}).resolve())
""",
    )

    completed = run_cli(
        "run",
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
        "      source_dir:\n        value: /definitely/missing",
    )
    source_dir = tmp_path / "real_source"
    source_dir.mkdir()
    (source_dir / "sample.txt").write_text("OVERRIDE")
    override_binding = make_binding(
        tmp_path / "override_binding",
        "consume_override",
        f"      source_dir:\n        value: {str(source_dir)!r}",
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

    completed = run_cli("run", str(template), cwd=tmp_path)
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
        "      source_dir:\n        function: locate_source",
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
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=ListRuns",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    runs = run_cli("project", "runs", cwd=project_dir)
    assert runs.returncode == 0, runs.stderr
    assert "simple_echo_001\tsimple_echo\t" in runs.stdout


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
        version="1.2.3",
        description="Template used for listing tests",
        outputs="  results_dir: {}\n  name_file: {}",
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
    assert f"PACK\t{pack_root.resolve()}" in completed.stdout
    assert "listed_template\tTemplate used for listing tests\tname\tresults_dir,name_file\t1.2.3" in completed.stdout


def test_run_metadata_collects_declared_outputs_from_default_results_subpaths(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "declared_outputs",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${LINKAR_RESULTS_DIR}/output" "${LINKAR_RESULTS_DIR}/reports"
printf '%s\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/output/name.txt"
printf '<html>%s</html>\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/reports/report.html"
""",
        outputs="  results_dir: {}\n  output_dir: {}\n  report_html:\n    path: reports/report.html",
    )

    completed = run_cli(
        "run",
        "declared_outputs",
        "--pack",
        str(pack_root),
        "--param",
        "name=Linkar",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["outputs"] == {
        "results_dir": str((outdir / "results").resolve()),
        "output_dir": str((outdir / "results" / "output").resolve()),
        "report_html": str((outdir / "results" / "reports" / "report.html").resolve()),
    }


def test_run_metadata_collects_declared_glob_outputs(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    make_template(
        pack_root / "templates",
        "glob_outputs",
        "  name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${LINKAR_RESULTS_DIR}/fastqc"
printf '<html>%s-1</html>\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/fastqc/a_fastqc.html"
printf '<html>%s-2</html>\n' "${NAME}" > "${LINKAR_RESULTS_DIR}/fastqc/b_fastqc.html"
""",
        outputs="  fastqc_reports:\n    glob: fastqc/*_fastqc.html",
    )

    completed = run_cli(
        "run",
        "glob_outputs",
        "--pack",
        str(pack_root),
        "--param",
        "name=Linkar",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr

    outdir = Path(completed.stdout.strip())
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text())
    assert meta["outputs"] == {
        "fastqc_reports": [
            str((outdir / "results" / "fastqc" / "a_fastqc.html").resolve()),
            str((outdir / "results" / "fastqc" / "b_fastqc.html").resolve()),
        ]
    }


def test_project_binding_can_pass_glob_output_into_list_path_param(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    producer = make_template(
        tmp_path / "templates",
        "produce_reports",
        "  sample_name:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "${LINKAR_RESULTS_DIR}/fastqc"
printf '<html>%s-A</html>\n' "${SAMPLE_NAME}" > "${LINKAR_RESULTS_DIR}/fastqc/a_fastqc.html"
printf '<html>%s-B</html>\n' "${SAMPLE_NAME}" > "${LINKAR_RESULTS_DIR}/fastqc/b_fastqc.html"
""",
        outputs="  fastqc_reports:\n    glob: fastqc/*_fastqc.html",
    )
    consumer = make_template(
        tmp_path / "templates",
        "consume_reports",
        "  report_files:\n    type: list[path]\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
IFS=':' read -r -a files <<< "${REPORT_FILES}"
printf '%s\n' "${#files[@]}" > "${LINKAR_RESULTS_DIR}/count.txt"
printf '%s\n' "${files[0]}" > "${LINKAR_RESULTS_DIR}/first.txt"
""",
    )
    binding_root = make_binding(
        tmp_path / "binding",
        "consume_reports",
        "      report_files:\n        template: produce_reports\n        output: fastqc_reports",
    )

    producer_run = run_template(
        producer,
        params={"sample_name": "demo"},
        project=project_dir,
    )
    producer_outdir = Path(producer_run["outdir"])
    assert (producer_outdir / "results" / "fastqc" / "a_fastqc.html").exists()

    consumer_run = run_template(
        consumer,
        project=project_dir,
        binding_ref=str(binding_root),
    )

    consumer_outdir = Path(consumer_run["outdir"])
    assert (consumer_outdir / "results" / "count.txt").read_text().strip() == "2"
    assert (consumer_outdir / "results" / "first.txt").read_text().strip().endswith("a_fastqc.html")
    meta = json.loads((consumer_outdir / ".linkar" / "meta.json").read_text())
    assert meta["param_provenance"]["report_files"]["binding_source"] == "output"
    assert meta["param_provenance"]["report_files"]["output"] == "fastqc_reports"


def test_binding_override_example_pack_can_switch_between_default_and_override_bindings(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    pack_root = ROOT / "examples" / "packs" / "binding_overrides"
    override_binding = pack_root / "override_binding"

    add = run_cli("pack", "add", str(pack_root), "--id", "binding_overrides", "--binding", "default", cwd=project_dir)
    assert add.returncode == 0, add.stderr

    produce = run_cli("run", "produce_data", "--value", "project", cwd=project_dir)
    assert produce.returncode == 0, produce.stderr

    consume_default = run_cli("run", "consume_data", cwd=project_dir)
    assert consume_default.returncode == 0, consume_default.stderr
    default_outdir = Path(consume_default.stdout.strip())
    assert (default_outdir / "results" / "copied.txt").read_text().strip() == "project"

    consume_override = run_cli("run", "consume_data", "--binding", str(override_binding), cwd=project_dir)
    assert consume_override.returncode == 0, consume_override.stderr
    override_outdir = Path(consume_override.stdout.strip())
    assert (override_outdir / "results" / "copied.txt").read_text().strip() == "override"


def test_inspect_run_command_returns_metadata_json(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    init = run_cli("project", "init", str(project_dir), cwd=tmp_path)
    assert init.returncode == 0, init.stderr

    completed = run_cli(
        "run",
        "simple_echo",
        "--pack",
        str(ROOT / "examples" / "packs" / "basic"),
        "--param",
        "name=Inspect",
        cwd=project_dir,
    )
    assert completed.returncode == 0, completed.stderr

    inspected = run_cli("inspect", "run", "simple_echo_001", cwd=project_dir)
    assert inspected.returncode == 0, inspected.stderr
    metadata = json.loads(inspected.stdout)
    assert metadata["template"] == "simple_echo"
    assert metadata["params"]["name"] == "Inspect"


def test_run_verbose_streams_template_stdout_and_stderr(tmp_path: Path) -> None:
    template_root = tmp_path / "templates"
    make_template(
        template_root,
        "verbose_demo",
        "  message:\n    type: str\n    required: true",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'stdout:%s\\n' "${MESSAGE}"
printf 'stderr:%s\\n' "${MESSAGE}" >&2
printf '%s\\n' "${MESSAGE}" > "${LINKAR_RESULTS_DIR}/message.txt"
""",
    )

    completed = run_cli(
        "run",
        str(template_root / "verbose_demo"),
        "--param",
        "message=hello",
        "--verbose",
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    assert "stdout:hello" in completed.stdout
    assert "stderr:hello" in completed.stderr

    outdir = Path(completed.stdout.strip().splitlines()[-1])
    assert (outdir / "results" / "message.txt").read_text().strip() == "hello"


def test_print_metadata_renders_rich_run_inspection_view(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    ui = CliUI()
    ui.console = Console(record=True, force_terminal=True, width=120, theme=THEME)
    metadata = {
        "template": "demultiplex",
        "template_version": "1.2.3",
        "instance_id": "demultiplex_001",
        "params": {
            "bcl_dir": "/data/run",
            "samplesheet": "./samplesheet.csv",
            "threads": 4,
        },
        "param_provenance": {
            "bcl_dir": {"source": "explicit"},
            "samplesheet": {
                "source": "binding",
                "binding_source": "function",
                "name": "get_api_samplesheet",
            },
            "threads": {"source": "default"},
        },
        "outputs": {
            "results_dir": "/tmp/demux/results",
            "report_files": ["/tmp/demux/results/a.txt", "/tmp/demux/results/b.txt"],
        },
        "software": [{"name": "linkar", "version": __version__}],
        "pack": {"ref": "/packs/izkf", "revision": "abc123"},
        "binding": {"ref": "default"},
        "command": ["/tmp/demux/run.sh"],
        "timestamp": "2026-04-02T12:00:00+00:00",
        "run_mode": "run",
        "template_run_mode": "direct",
    }

    ui.print_metadata(metadata)

    rendered = ui.console.export_text()
    assert "Run Inspection" in rendered
    assert "demultiplex_001" in rendered
    assert "binding:function:get_api_samplesheet" in rendered
    assert "No outputs collected yet" not in rendered
    assert "/tmp/demux/run.sh" in rendered


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

    produce = run_cli("run", str(producer), "--param", "sample_name=S1", cwd=project_dir)
    assert produce.returncode == 0, produce.stderr
    consume = run_cli("run", str(consumer), cwd=project_dir)
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
    (broken_template / "linkar_template.yaml").write_text("id: broken\nrun: {}\n")
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
