from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkar.assets import ResolvedAsset


@dataclass
class TemplateSpec:
    id: str
    version: str | None
    description: str | None
    root: Path
    params: dict[str, dict[str, Any]]
    outputs: dict[str, dict[str, Any]]
    tools_required: list[str]
    tools_required_any: list[list[str]]
    run_entry: str | None
    run_command: str | None
    run_mode: str
    pack_root: Path | None = None
    pack_ref: str | None = None
    pack_revision: str | None = None


@dataclass
class Project:
    root: Path
    data: dict[str, Any]


@dataclass
class PackEntry:
    id: str
    asset: ResolvedAsset
    binding: str | None = None


@dataclass
class BindingContext:
    template: TemplateSpec
    project: Project | None
    resolved_params: dict[str, Any]

    def latest_output(self, key: str, template_id: str | None = None) -> Any | None:
        from linkar.runtime.projects import latest_project_output

        return latest_project_output(self.project, key, template_id=template_id)
