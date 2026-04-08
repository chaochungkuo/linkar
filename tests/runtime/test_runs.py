from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from linkar.errors import ExecutionError, TemplateValidationError
from linkar.runtime.config import save_global_config
from linkar.runtime.config import load_global_config
from linkar.runtime.projects import init_project, load_project
from linkar.runtime.shared import save_yaml
from linkar.runtime.runs import (
    collect_run_outputs,
    collect_declared_glob_output,
    collect_outputs,
    default_output_relative_path,
    determine_project_alias_dir,
    determine_outdir,
    determine_render_outdir,
    determine_test_dir,
    next_instance_id,
    render_mode_launcher_path,
    render_template,
    resolve_declared_output_path,
    ensure_required_tools_available,
    sync_project_alias,
    should_exclude_runtime_path,
    should_render_shell_wrapper,
    should_use_pty_for_verbose_output,
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
    assert determine_render_outdir(template, project, None, "demo_001") == (project.root / "demo").resolve()

    testdir = determine_test_dir(template, project, None)
    assert testdir.parent.parent == (project.root / ".linkar").resolve()
    assert testdir.parent.name == "tests"

    ephemeral_outdir = determine_outdir(template, None, None, "demo_999")
    assert ephemeral_outdir.parent.parent.name == ".linkar"
    assert ephemeral_outdir.parent.name == "runs"
    assert determine_render_outdir(template, None, None, "demo_999") == ephemeral_outdir


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


def test_should_use_pty_for_verbose_output_requires_real_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStream:
        def __init__(self, is_tty: bool) -> None:
            self._is_tty = is_tty

        def isatty(self) -> bool:
            return self._is_tty

    monkeypatch.setattr("linkar.runtime.runs.sys.stdin", FakeStream(True))
    monkeypatch.setattr("linkar.runtime.runs.sys.stdout", FakeStream(True))
    monkeypatch.setattr("linkar.runtime.runs.sys.stderr", FakeStream(True))
    monkeypatch.setattr("linkar.runtime.runs.os.name", "posix")
    assert should_use_pty_for_verbose_output() is True

    monkeypatch.setattr("linkar.runtime.runs.sys.stderr", FakeStream(False))
    assert should_use_pty_for_verbose_output() is False
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
    text = launcher.read_text(encoding="utf-8")
    assert 'Run ./run.sh from inside ${expected_dir}' in text
    assert 'cd "${script_dir}"' not in text
    assert 'export NAME=demo' in text
    assert 'template-entry-run.sh' in text


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
    assert (project.root / "render_project_demo").is_dir()
    assert Path(result["history_outdir"]) == (project.root / "render_project_demo").resolve()


def test_render_template_uses_default_binding_for_active_global_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    linkar_home = tmp_path / "linkar-home"
    monkeypatch.setenv("LINKAR_HOME", str(linkar_home))

    pack_root = tmp_path / "pack"
    template_dir = pack_root / "templates" / "global_default_binding_demo"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: global_default_binding_demo",
                "params:",
                "  source_dir:",
                "    type: path",
                "    required: true",
                "run:",
                "  mode: render",
                "  command: >-",
                "    printf '%s\\n' \"${source_dir}\" > \"${LINKAR_RESULTS_DIR}/source.txt\"",
                "",
            ]
        )
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir()
    (functions_dir / "derive_render_outdir.py").write_text(
        "from pathlib import Path\n"
        "\n"
        "def resolve(ctx):\n"
        "    source = Path(ctx.resolved_params['source_dir'])\n"
        f"    return str(Path({str((tmp_path / 'global-render-root')).__repr__()}) / source.name)\n"
    )
    save_yaml(
        pack_root / "linkar_pack.yaml",
        {
            "templates": {
                "global_default_binding_demo": {
                    "outdir": {
                        "function": "derive_render_outdir",
                    }
                }
            }
        },
    )

    config = load_global_config()
    config.data["packs"] = [{"id": "demo_pack", "ref": str(pack_root)}]
    config.data["active_pack"] = "demo_pack"
    save_global_config(config)

    source_dir = tmp_path / "inputs" / "run_global"
    source_dir.mkdir(parents=True)

    result = render_template(
        "global_default_binding_demo",
        params={"source_dir": str(source_dir)},
    )

    outdir = Path(result["history_outdir"])
    assert outdir == (tmp_path / "global-render-root" / "run_global").resolve()
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text(encoding="utf-8"))
    assert meta["binding"]["ref"] == "default"
    assert meta["outdir_provenance"]["binding_source"] == "function"


def test_render_template_uses_bound_outdir_function(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    template_dir = pack_root / "templates" / "render_bound_outdir"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: render_bound_outdir",
                "params:",
                "  source_dir:",
                "    type: path",
                "    required: true",
                "run:",
                "  mode: render",
                "  command: >-",
                "    printf '%s\\n' \"${source_dir}\" > \"${LINKAR_RESULTS_DIR}/source.txt\"",
                "",
            ]
        )
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir()
    (functions_dir / "derive_render_outdir.py").write_text(
        "from pathlib import Path\n"
        "\n"
        "def resolve(ctx):\n"
        "    source = Path(ctx.resolved_params['source_dir'])\n"
        f"    return str(Path({str((tmp_path / 'rendered-root')).__repr__()}) / source.name)\n"
    )
    save_yaml(
        pack_root / "linkar_pack.yaml",
        {
            "templates": {
                "render_bound_outdir": {
                    "outdir": {
                        "function": "derive_render_outdir",
                    }
                }
            }
        },
    )

    source_dir = tmp_path / "inputs" / "run_a"
    source_dir.mkdir(parents=True)

    result = render_template(
        template_dir,
        params={"source_dir": str(source_dir)},
        binding_ref="default",
    )

    outdir = Path(result["history_outdir"])
    assert outdir == (tmp_path / "rendered-root" / "run_a").resolve()
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text(encoding="utf-8"))
    assert meta["outdir_provenance"]["binding_source"] == "function"
    assert meta["outdir_provenance"]["name"] == "derive_render_outdir"


def test_render_template_explicit_outdir_overrides_bound_outdir(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    template_dir = pack_root / "templates" / "render_outdir_precedence"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: render_outdir_precedence",
                "params:",
                "  source_dir:",
                "    type: path",
                "    required: true",
                "run:",
                "  mode: render",
                "  command: >-",
                "    printf '%s\\n' \"${source_dir}\" > \"${LINKAR_RESULTS_DIR}/source.txt\"",
                "",
            ]
        )
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir()
    (functions_dir / "derive_render_outdir.py").write_text(
        "def resolve(ctx):\n"
        f"    return {str((tmp_path / 'should-not-be-used')).__repr__()}\n"
    )
    save_yaml(
        pack_root / "linkar_pack.yaml",
        {
            "templates": {
                "render_outdir_precedence": {
                    "outdir": {
                        "function": "derive_render_outdir",
                    }
                }
            }
        },
    )

    explicit_outdir = tmp_path / "explicit-render"
    source_dir = tmp_path / "inputs" / "run_b"
    source_dir.mkdir(parents=True)

    result = render_template(
        template_dir,
        params={"source_dir": str(source_dir)},
        binding_ref="default",
        outdir=explicit_outdir,
    )

    outdir = Path(result["history_outdir"])
    assert outdir == explicit_outdir.resolve()
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text(encoding="utf-8"))
    assert meta["outdir_provenance"]["source"] == "cli"


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
    assert 'Run ./run.sh from inside ${expected_dir}' in text
    assert 'cd "${script_dir}"' not in text
    assert "name=demo" in text
    assert "NAME=demo" not in text
    assert "./results" in text
    assert not (outdir / "results" / "name.txt").exists()


def test_render_template_supports_explicit_param_placeholders(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_render_param_placeholder"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_render_param_placeholder",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "run:",
                "  mode: render",
                "  command: >-",
                "    printf '%s\\n' \"${param:name}\" > \"${LINKAR_RESULTS_DIR}/name.txt\"",
                "",
            ]
        )
    )

    result = render_template(template_dir, params={"name": "demo"}, outdir=tmp_path / "rendered")
    launcher = render_mode_launcher_path(Path(result["history_outdir"]))
    text = launcher.read_text(encoding="utf-8")

    assert "${param:name}" not in text
    assert "name=demo" in text
    assert 'printf \'%s\\n\' "${name}"' in text
    assert "${param:name:+x}" not in text


def test_run_template_supports_explicit_param_placeholders(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_direct_param_placeholder"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_direct_param_placeholder",
                "params:",
                "  name:",
                "    type: str",
                "    required: true",
                "run:",
                "  mode: direct",
                "  command: >-",
                "    printf '%s\\n' \"${param:name}\" > \"${LINKAR_RESULTS_DIR}/name.txt\"",
                "",
            ]
        )
    )

    result = run_template(template_dir, params={"name": "demo"}, outdir=tmp_path / "out")
    outdir = Path(result["history_outdir"])

    assert (outdir / "results" / "name.txt").read_text() == "demo\n"
    launcher_text = (outdir / "run.sh").read_text(encoding="utf-8")
    assert "${param:name}" not in launcher_text
    assert 'export NAME=demo' in launcher_text
    assert '"${NAME}"' in launcher_text


def test_render_template_supports_param_placeholder_expansions(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_render_param_expansion"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_render_param_expansion",
                "params:",
                "  name:",
                "    type: str",
                '    default: ""',
                "run:",
                "  mode: render",
                "  command: >-",
                '    printf \'%s\\n\' ${param:name:+--name "${param:name}"} > "${LINKAR_RESULTS_DIR}/cmd.txt"',
                "",
            ]
        )
    )

    result = render_template(template_dir, params={"name": "demo"}, outdir=tmp_path / "rendered")
    text = render_mode_launcher_path(Path(result["history_outdir"])).read_text(encoding="utf-8")

    assert "${param:name:+--name" not in text
    assert '${name:+--name "${name}"}' in text


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


def test_render_template_localizes_bound_file_params_into_render_dir(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    template_dir = pack_root / "templates" / "bound_file_render"
    template_dir.mkdir(parents=True)
    cached_dir = tmp_path / "cache"
    cached_dir.mkdir()
    cached_file = cached_dir / "samplesheet.csv"
    cached_file.write_text("sample_id\nS1\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: bound_file_render",
                "params:",
                "  samplesheet:",
                "    type: path",
                "    required: true",
                "run:",
                "  command: >-",
                '    printf "%s\\n" "${samplesheet}" > "./results/path.txt"',
                "",
            ]
        )
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir()
    (functions_dir / "provide_samplesheet.py").write_text(
        "def resolve(ctx):\n"
        f"    return {cached_file.as_posix()!r}\n"
    )
    save_yaml(
        pack_root / "linkar_pack.yaml",
        {
            "templates": {
                "bound_file_render": {
                    "params": {
                        "samplesheet": {
                            "function": "provide_samplesheet"
                        }
                    }
                }
            }
        },
    )

    result = render_template(template_dir, binding_ref="default", outdir=tmp_path / "rendered")
    outdir = Path(result["history_outdir"])

    assert (outdir / "samplesheet.csv").read_text() == "sample_id\nS1\n"
    text = (outdir / "run.sh").read_text(encoding="utf-8")
    assert "samplesheet=./samplesheet.csv" in text
    assert str(cached_file) not in text


def test_render_template_overwrites_staged_file_when_bound_file_uses_same_name(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    template_dir = pack_root / "templates" / "samplesheet_collision"
    template_dir.mkdir(parents=True)
    cached_dir = tmp_path / "cache"
    cached_dir.mkdir()
    cached_file = cached_dir / "samplesheet.csv"
    cached_file.write_text("from_api\n")
    (template_dir / "samplesheet.csv").write_text("from_template\n")
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: samplesheet_collision",
                "params:",
                "  samplesheet:",
                "    type: path",
                "    required: true",
                "run:",
                "  command: >-",
                '    printf "%s\\n" "${samplesheet}" > "./results/path.txt"',
                "",
            ]
        )
    )
    functions_dir = pack_root / "functions"
    functions_dir.mkdir()
    (functions_dir / "provide_samplesheet.py").write_text(
        "def resolve(ctx):\n"
        f"    return {cached_file.as_posix()!r}\n"
    )
    save_yaml(
        pack_root / "linkar_pack.yaml",
        {
            "templates": {
                "samplesheet_collision": {
                    "params": {
                        "samplesheet": {
                            "function": "provide_samplesheet"
                        }
                    }
                }
            }
        },
    )

    result = render_template(template_dir, binding_ref="default", outdir=tmp_path / "rendered")
    outdir = Path(result["history_outdir"])

    assert (outdir / "samplesheet.csv").read_text() == "from_api\n"
    assert not (outdir / "samplesheet_samplesheet.csv").exists()


def test_collect_run_outputs_updates_rendered_meta_after_manual_execution(tmp_path: Path) -> None:
    template_dir = tmp_path / "command_render_collect"
    template_dir.mkdir(parents=True)
    (template_dir / "linkar_template.yaml").write_text(
        "\n".join(
            [
                "id: command_render_collect",
                "outputs:",
                "  report_file:",
                "    path: report.txt",
                "run:",
                "  command: >-",
                '    printf "done\\n" > "./results/report.txt"',
                "",
            ]
        )
    )

    rendered = render_template(template_dir, outdir=tmp_path / "rendered")
    outdir = Path(rendered["history_outdir"])
    subprocess.run([str(outdir / "run.sh")], cwd=outdir, check=True)

    result = collect_run_outputs(outdir)
    meta = json.loads((outdir / ".linkar" / "meta.json").read_text(encoding="utf-8"))

    assert result["outputs"]["report_file"] == str((outdir / "results" / "report.txt").resolve())
    assert meta["outputs"]["report_file"] == str((outdir / "results" / "report.txt").resolve())
    assert "collected_at" in meta


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
