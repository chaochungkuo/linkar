from __future__ import annotations

from pathlib import Path

from linkar.runtime.projects import init_project, load_project
from linkar.runtime.runs import (
    determine_outdir,
    determine_test_dir,
    next_instance_id,
    should_exclude_runtime_path,
    should_render_shell_wrapper,
    stage_runtime_bundle,
)
from linkar.runtime.templates import load_template


def make_template(root: Path, template_id: str, body: str, *, entry_name: str = "run.sh") -> Path:
    template_dir = root / template_id
    template_dir.mkdir(parents=True)
    (template_dir / "template.yaml").write_text(
        "\n".join(
            [
                f"id: {template_id}",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "outputs:",
                "  results_dir: {}",
                "run:",
                f"  entry: {entry_name}",
                "  mode: direct",
                "",
            ]
        )
    )
    entry = template_dir / entry_name
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(body)
    entry.chmod(0o755)
    return template_dir


def test_next_instance_id_uses_project_history_count(tmp_path: Path) -> None:
    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)
    project.data["templates"] = [
        {"id": "demo", "instance_id": "demo_001"},
        {"id": "other", "instance_id": "other_001"},
        {"id": "demo", "instance_id": "demo_002"},
    ]

    assert next_instance_id("demo", project) == "demo_003"
    assert next_instance_id("other", project) == "other_002"


def test_determine_outdir_and_testdir_follow_project_and_ephemeral_rules(tmp_path: Path) -> None:
    template_dir = make_template(tmp_path / "templates", "demo", "#!/usr/bin/env bash\n")
    template = load_template(template_dir)
    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)

    outdir = determine_outdir(template, project, None, "demo_001")
    assert outdir == (project.root / "demo_001").resolve()

    testdir = determine_test_dir(template, project, None)
    assert testdir.parent.parent == (project.root / ".linkar").resolve()
    assert testdir.parent.name == "tests"

    ephemeral_outdir = determine_outdir(template, None, None, "demo_999")
    assert ephemeral_outdir.parent.parent.name == ".linkar"
    assert ephemeral_outdir.parent.name == "runs"


def test_stage_runtime_bundle_copies_support_files_but_excludes_test_only_files(tmp_path: Path) -> None:
    template_dir = make_template(
        tmp_path / "pack" / "templates",
        "pixi_demo",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    (template_dir / "pixi.toml").write_text("[workspace]\nname='demo'\n")
    (template_dir / "helper.py").write_text("print('helper')\n")
    (template_dir / "test.sh").write_text("#!/usr/bin/env bash\n")
    (template_dir / "test.py").write_text("print('test')\n")
    (template_dir / "testdata").mkdir()
    (template_dir / "testdata" / "fixture.txt").write_text("fixture\n")
    (template_dir / ".pixi").mkdir()
    (template_dir / ".pixi" / "cache").write_text("ignored\n")

    template = load_template(template_dir)
    output_dir = tmp_path / "run"
    output_dir.mkdir()

    stage_runtime_bundle(template, output_dir)

    assert (output_dir / "run.sh").is_file()
    assert (output_dir / "pixi.toml").is_file()
    assert (output_dir / "helper.py").is_file()
    assert not (output_dir / "test.sh").exists()
    assert not (output_dir / "test.py").exists()
    assert not (output_dir / "testdata").exists()
    assert not (output_dir / ".pixi").exists()


def test_render_shell_wrapper_detection_only_applies_to_script_sh_entries(tmp_path: Path) -> None:
    direct_template = load_template(make_template(tmp_path / "templates", "direct_demo", "#!/usr/bin/env bash\n"))
    scripted_template = load_template(
        make_template(tmp_path / "templates", "script_demo", "#!/usr/bin/env bash\n", entry_name="script.sh")
    )

    assert should_render_shell_wrapper(direct_template) is False
    assert should_render_shell_wrapper(scripted_template) is True


def test_runtime_bundle_exclusion_helper_matches_current_policy() -> None:
    assert should_exclude_runtime_path(Path("test.sh")) is True
    assert should_exclude_runtime_path(Path("test.py")) is True
    assert should_exclude_runtime_path(Path("testdata")) is True
    assert should_exclude_runtime_path(Path(".pixi")) is True
    assert should_exclude_runtime_path(Path("run.sh")) is False
    assert should_exclude_runtime_path(Path("pixi.toml")) is False
