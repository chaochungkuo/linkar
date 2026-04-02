from __future__ import annotations

from pathlib import Path

import pytest

from linkar.errors import ExecutionError, TemplateValidationError
from linkar.runtime.projects import init_project, load_project
from linkar.runtime.runs import (
    collect_declared_glob_output,
    collect_outputs,
    default_output_relative_path,
    determine_project_alias_dir,
    determine_outdir,
    determine_test_dir,
    next_instance_id,
    render_mode_launcher_path,
    render_template,
    resolve_declared_output_path,
    ensure_required_tools_available,
    sync_project_alias,
    should_exclude_runtime_path,
    should_render_shell_wrapper,
    stage_runtime_bundle,
    run_template,
)
from linkar.runtime.templates import load_template


def make_template(root: Path, template_id: str, body: str, *, entry_name: str = "run.sh") -> Path:
    template_dir = root / template_id
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
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


def test_load_template_accepts_legacy_template_yaml_filename(tmp_path: Path) -> None:
    template_dir = tmp_path / "legacy_template"
    template_dir.mkdir(parents=True)
    (template_dir / "template.yaml").write_text(
        "\n".join(
            [
                "id: legacy_template",
                "outputs:",
                "  results_dir: {}",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )
    (template_dir / "run.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n")
    (template_dir / "run.sh").chmod(0o755)

    template = load_template(template_dir)

    assert template.id == "legacy_template"


def test_load_template_accepts_run_command_without_entry(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_template"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_template",
                "run:",
                "  mode: direct",
                "  command: echo hello",
                "",
            ]
        )
    )

    template = load_template(template_dir)

    assert template.run_entry is None
    assert template.run_command == "echo hello"


def test_load_template_rejects_both_run_entry_and_run_command(tmp_path: Path) -> None:
    template_dir = tmp_path / "bad_command_template"
    template_dir.mkdir(parents=True)
    (template_dir / "run.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\n")
    (template_dir / "run.sh").chmod(0o755)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: bad_command_template",
                "run:",
                "  entry: run.sh",
                "  command: echo hello",
                "  mode: direct",
                "",
            ]
        )
    )

    with pytest.raises(TemplateValidationError, match="both run.entry and run.command"):
        load_template(template_dir)


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
    assert outdir == (project.root / ".linkar" / "runs" / "demo_001").resolve()
    assert determine_project_alias_dir(template, project) == (project.root / "demo").resolve()

    testdir = determine_test_dir(template, project, None)
    assert testdir.parent.parent == (project.root / ".linkar").resolve()
    assert testdir.parent.name == "tests"

    ephemeral_outdir = determine_outdir(template, None, None, "demo_999")
    assert ephemeral_outdir.parent.parent.name == ".linkar"
    assert ephemeral_outdir.parent.name == "runs"


def test_sync_project_alias_points_stable_project_path_to_history_dir(tmp_path: Path) -> None:
    history_dir = tmp_path / ".linkar" / "runs" / "demo_001"
    history_dir.mkdir(parents=True)
    alias_dir = tmp_path / "demo"

    sync_project_alias(history_dir, alias_dir)

    assert alias_dir.is_symlink()
    assert alias_dir.resolve() == history_dir.resolve()


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
    assert should_exclude_runtime_path(Path(".rattler-cache")) is True
    assert should_exclude_runtime_path(Path("run.sh")) is False
    assert should_exclude_runtime_path(Path("pixi.toml")) is False


def test_default_output_relative_path_uses_results_dir_conventions() -> None:
    assert default_output_relative_path("results_dir") == Path(".")
    assert default_output_relative_path("fastqc_dir") == Path("fastqc")
    assert default_output_relative_path("output_dir") == Path("output")
    assert default_output_relative_path("report_html") == Path("report_html")


def test_resolve_declared_output_path_supports_default_and_explicit_paths(tmp_path: Path) -> None:
    outdir = tmp_path / "demo_001"
    outdir.mkdir()

    assert resolve_declared_output_path("fastqc_dir", {}, outdir) == (outdir / "results" / "fastqc").resolve()
    assert resolve_declared_output_path(
        "report_html",
        {"path": "reports/report.html"},
        outdir,
    ) == (outdir / "results" / "reports" / "report.html").resolve()


def test_collect_declared_glob_output_returns_sorted_matches(tmp_path: Path) -> None:
    outdir = tmp_path / "run"
    (outdir / "results" / "fastqc").mkdir(parents=True)
    (outdir / "results" / "fastqc" / "b_fastqc.html").write_text("<html>b</html>\n")
    (outdir / "results" / "fastqc" / "a_fastqc.html").write_text("<html>a</html>\n")

    matches = collect_declared_glob_output({"glob": "fastqc/*_fastqc.html"}, outdir)

    assert matches == [
        str((outdir / "results" / "fastqc" / "a_fastqc.html").resolve()),
        str((outdir / "results" / "fastqc" / "b_fastqc.html").resolve()),
    ]


def test_collect_outputs_uses_declared_relative_paths_when_present(tmp_path: Path) -> None:
    template_dir = make_template(tmp_path / "templates", "outputs_demo", "#!/usr/bin/env bash\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: outputs_demo",
                "outputs:",
                "  results_dir: {}",
                "  output_dir: {}",
                "  report_html:",
                "    path: reports/report.html",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )
    template = load_template(template_dir)
    outdir = tmp_path / "run"
    (outdir / "results" / "output").mkdir(parents=True)
    (outdir / "results" / "reports").mkdir(parents=True)
    (outdir / "results" / "reports" / "report.html").write_text("<html></html>\n")

    outputs = collect_outputs(template, outdir)

    assert outputs == {
        "results_dir": str((outdir / "results").resolve()),
        "output_dir": str((outdir / "results" / "output").resolve()),
        "report_html": str((outdir / "results" / "reports" / "report.html").resolve()),
    }


def test_collect_outputs_records_declared_glob_outputs_as_lists(tmp_path: Path) -> None:
    template_dir = make_template(tmp_path / "templates", "glob_demo", "#!/usr/bin/env bash\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: glob_demo",
                "outputs:",
                "  fastqc_reports:",
                "    glob: fastqc/*_fastqc.html",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )
    template = load_template(template_dir)
    outdir = tmp_path / "run"
    (outdir / "results" / "fastqc").mkdir(parents=True)
    (outdir / "results" / "fastqc" / "a_fastqc.html").write_text("<html>a</html>\n")
    (outdir / "results" / "fastqc" / "b_fastqc.html").write_text("<html>b</html>\n")

    outputs = collect_outputs(template, outdir)

    assert outputs == {
        "fastqc_reports": [
            str((outdir / "results" / "fastqc" / "a_fastqc.html").resolve()),
            str((outdir / "results" / "fastqc" / "b_fastqc.html").resolve()),
        ]
    }


def test_collect_outputs_falls_back_to_results_dir_for_legacy_templates(tmp_path: Path) -> None:
    template_dir = make_template(tmp_path / "templates", "legacy_demo", "#!/usr/bin/env bash\n")
    template = load_template(template_dir)
    outdir = tmp_path / "run"
    (outdir / "results").mkdir(parents=True)

    assert collect_outputs(template, outdir) == {"results_dir": str((outdir / "results").resolve())}


def test_render_template_stages_bundle_and_writes_launcher_without_executing(tmp_path: Path) -> None:
    template_dir = make_template(
        tmp_path / "templates",
        "render_demo",
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'executed\\n' > \"${LINKAR_RESULTS_DIR}/executed.txt\"\n",
    )
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: render_demo",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "run:",
                "  entry: run.sh",
                "  mode: render",
                "",
            ]
        )
    )

    result = render_template(template_dir, params={"name": "demo"}, outdir=tmp_path / "rendered")
    rendered_dir = Path(result["history_outdir"])
    launcher = render_mode_launcher_path(rendered_dir)

    assert result["run_mode"] == "render"
    assert rendered_dir.is_dir()
    assert (rendered_dir / "run.sh").is_file()
    assert launcher.is_file()
    assert not (rendered_dir / "linkar_template.yaml").exists()
    assert not (rendered_dir / "results" / "executed.txt").exists()
    assert 'export NAME=demo' in launcher.read_text(encoding="utf-8")
    assert 'template-entry-run.sh' in launcher.read_text(encoding="utf-8")


def test_render_template_does_not_update_project_history_or_alias(tmp_path: Path) -> None:
    template_dir = make_template(
        tmp_path / "templates",
        "render_project_demo",
        "#!/usr/bin/env bash\nset -euo pipefail\n",
    )
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: render_project_demo",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "run:",
                "  entry: run.sh",
                "  mode: render",
                "",
            ]
        )
    )
    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)

    result = render_template(template_dir, params={"name": "demo"}, project=project)

    project_after = load_project(project.root)
    assert project_after.data["templates"] == []
    assert not (project.root / "render_project_demo").exists()
    assert Path(result["history_outdir"]).is_dir()


def test_direct_run_command_executes_without_template_wrapper_script(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_direct"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_direct",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "run:",
                "  mode: direct",
                "  command: >-",
                "    printf '%s\\n' \"${NAME}\" > \"${LINKAR_RESULTS_DIR}/name.txt\"",
                "",
            ]
        )
    )

    result = run_template(template_dir, params={"name": "demo"}, outdir=tmp_path / "out")
    outdir = Path(result["history_outdir"])

    assert (outdir / "results" / "name.txt").read_text() == "demo\n"
    assert (outdir / "run.sh").is_file()
    assert not (outdir / "linkar-run.sh").exists()


def test_render_template_with_run_command_writes_single_launcher(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_render"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_render",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "run:",
                "  mode: render",
                "  command: >-",
                "    printf '%s\\n' \"${NAME}\" > \"${LINKAR_RESULTS_DIR}/name.txt\"",
                "",
            ]
        )
    )

    result = render_template(template_dir, params={"name": "demo"}, outdir=tmp_path / "rendered")
    outdir = Path(result["history_outdir"])
    launcher = render_mode_launcher_path(outdir)

    assert launcher.is_file()
    assert not (outdir / "linkar_template.yaml").exists()
    assert "bash -lc" not in launcher.read_text(encoding="utf-8")
    text = launcher.read_text(encoding="utf-8")
    assert "NAME=demo" in text
    assert '${script_dir}/results' in text
    assert not (outdir / "results" / "name.txt").exists()


def test_run_template_executes_even_when_template_declares_legacy_render_mode(tmp_path: Path) -> None:
    template_dir = make_template(
        tmp_path / "templates",
        "legacy_render_mode",
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'executed\\n' > \"${LINKAR_RESULTS_DIR}/executed.txt\"\n",
    )
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: legacy_render_mode",
                "run:",
                "  entry: run.sh",
                "  mode: render",
                "",
            ]
        )
    )

    result = run_template(template_dir, outdir=tmp_path / "executed")
    outdir = Path(result["history_outdir"])

    assert result["run_mode"] == "run"
    assert (outdir / "results" / "executed.txt").read_text() == "executed\n"


def test_load_template_parses_tool_requirements(tmp_path: Path) -> None:
    template_dir = make_template(tmp_path / "templates", "tool_demo", "#!/usr/bin/env bash\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: tool_demo",
                "tools:",
                "  required:",
                "    - pixi",
                "  required_any:",
                "    - [bcl-convert, bcl_convert]",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )

    template = load_template(template_dir)

    assert template.tools_required == ["pixi"]
    assert template.tools_required_any == [["bcl-convert", "bcl_convert"]]


def test_load_template_rejects_invalid_tool_requirements(tmp_path: Path) -> None:
    template_dir = make_template(tmp_path / "templates", "broken_tools", "#!/usr/bin/env bash\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: broken_tools",
                "tools:",
                "  required_any:",
                "    - pixi",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )

    with pytest.raises(TemplateValidationError, match="tools.required_any entries must be non-empty lists"):
        load_template(template_dir)


def test_ensure_required_tools_available_reports_missing_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template_dir = make_template(tmp_path / "templates", "missing_tools", "#!/usr/bin/env bash\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: missing_tools",
                "tools:",
                "  required:",
                "    - missingcmd",
                "  required_any:",
                "    - [tool_a, tool_b]",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )
    template = load_template(template_dir)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    with pytest.raises(ExecutionError, match="missing required commands: missingcmd; missing any of: tool_a, tool_b"):
        ensure_required_tools_available(template)


def test_run_template_checks_required_tools_before_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template_dir = make_template(
        tmp_path / "templates",
        "tool_checked",
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'ran\\n' > \"${LINKAR_RESULTS_DIR}/done.txt\"\n",
    )
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: tool_checked",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "tools:",
                "  required:",
                "    - missingcmd",
                "run:",
                "  entry: run.sh",
                "  mode: direct",
                "",
            ]
        )
    )
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    with pytest.raises(ExecutionError, match="Template 'tool_checked' cannot run because required tools are unavailable"):
        run_template(template_dir, params={"name": "demo"})
