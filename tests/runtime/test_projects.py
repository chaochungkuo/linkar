from __future__ import annotations

from pathlib import Path

import pytest

from linkar.errors import ProjectValidationError
from linkar.runtime.projects import (
    get_active_pack_entry,
    init_project,
    latest_project_output,
    load_project,
)
from linkar.runtime.shared import save_yaml


def test_latest_project_output_can_filter_by_template_id(tmp_path: Path) -> None:
    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)
    project.data["templates"] = [
        {"id": "produce_alpha", "outputs": {"results_dir": "/tmp/alpha"}},
        {"id": "produce_beta", "outputs": {"results_dir": "/tmp/beta"}},
    ]
    save_yaml(project.root / "project.yaml", project.data)

    assert latest_project_output(project, "results_dir") == "/tmp/beta"
    assert latest_project_output(project, "results_dir", template_id="produce_alpha") == "/tmp/alpha"
    assert latest_project_output(project, "results_dir", template_id="missing") is None


def test_load_project_rejects_non_list_pack_field(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text(
        "id: demo\nactive_pack: null\npacks: {}\ntemplates: []\n"
    )

    with pytest.raises(ProjectValidationError, match="project.yaml field 'packs' must be a list"):
        load_project(project_dir)


def test_get_active_pack_entry_uses_active_pack_or_single_pack(tmp_path: Path) -> None:
    pack_one = tmp_path / "pack_one"
    pack_two = tmp_path / "pack_two"
    pack_one.mkdir()
    pack_two.mkdir()

    project_path = init_project(tmp_path / "project")
    project = load_project(project_path.parent)

    project.data["packs"] = [{"id": "one", "ref": str(pack_one)}]
    save_yaml(project.root / "project.yaml", project.data)
    project = load_project(project.root)
    assert get_active_pack_entry(project).id == "one"

    project.data["packs"] = [
        {"id": "one", "ref": str(pack_one)},
        {"id": "two", "ref": str(pack_two)},
    ]
    project.data["active_pack"] = "two"
    save_yaml(project.root / "project.yaml", project.data)
    project = load_project(project.root)
    assert get_active_pack_entry(project).id == "two"
