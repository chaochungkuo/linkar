from __future__ import annotations

import json
import os
import shlex
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any
import yaml

try:
    from rich import box
    from rich.console import Console
    from rich.json import JSON
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme
except ImportError:
    Console = None
    JSON = None
    Panel = None
    Table = None
    Text = None
    Theme = None
    box = None
    RICH_AVAILABLE = False
else:
    RICH_AVAILABLE = True


THEME = (
    Theme(
        {
            "accent": "bold cyan",
            "info": "bold bright_blue",
            "muted": "dim white",
            "ok": "bold green",
            "warn": "bold yellow",
            "error": "bold red",
            "label": "bold bright_white",
            "value": "white",
        }
    )
    if RICH_AVAILABLE
    else None
)


class CliUI:
    def __init__(self) -> None:
        if RICH_AVAILABLE:
            self.console = Console(theme=THEME)
            self.error_console = Console(stderr=True, theme=THEME)
        else:
            self.console = None
            self.error_console = None

    @property
    def rich_enabled(self) -> bool:
        return (
            RICH_AVAILABLE
            and self.console is not None
            and self.console.is_terminal
            and not os.environ.get("NO_COLOR")
        )

    def plain_print(self, value: str) -> None:
        print(value)

    def plain_error(self, value: str) -> None:
        print(value, file=sys.stderr)

    def print_text(self, value: str) -> None:
        self.plain_print(value)

    def print_data(self, data: Any, *, format: str = "rich") -> None:
        if format == "json":
            self.plain_print(json.dumps(data, indent=2, sort_keys=True))
            return
        if format == "yaml":
            self.plain_print(yaml.safe_dump(data, sort_keys=False, allow_unicode=False).rstrip())
            return
        if isinstance(data, dict):
            self.print_metadata(data)
            return
        if isinstance(data, list):
            self.plain_print(json.dumps(data, indent=2, sort_keys=True))
            return
        self.plain_print(str(data))

    def print_summary_panel(
        self,
        title: str,
        fields: list[tuple[str, Any]],
        *,
        plain_text: str | None = None,
        border_style: str = "info",
    ) -> None:
        if not self.rich_enabled:
            self.plain_print(plain_text if plain_text is not None else "\n".join(f"{key}: {value}" for key, value in fields))
            return
        body = Text()
        first = True
        for label, value in fields:
            if not first:
                body.append("\n")
            first = False
            body.append(str(label), style="label")
            body.append(": ", style="muted")
            body.append(str(value), style="value")
        self.console.print(
            Panel(
                body,
                title=title,
                border_style=border_style,
                box=box.ROUNDED,
            )
        )

    def _print_tabled_panel(
        self,
        table: Any,
        *,
        title: str,
        border_style: str = "info",
    ) -> None:
        self.console.print(
            Panel(
                table,
                title=title,
                border_style=border_style,
                box=box.ROUNDED,
            )
        )

    def _print_empty_state(self, title: str, message: str, *, border_style: str = "warn") -> None:
        if not self.rich_enabled:
            self.plain_print(message)
            return
        self.console.print(
            Panel(
                Text(message, style="muted"),
                title=title,
                border_style=border_style,
                box=box.ROUNDED,
            )
        )

    def status(self, message: str):
        if not self.rich_enabled:
            return nullcontext()
        return self.console.status(f"[info]{message}[/info]", spinner="dots")

    def print_project_created(self, path: Path, project_id: str) -> None:
        self.print_summary_panel(
            "[ok]Project Created[/ok]",
            [("Project", project_id), ("Path", path)],
            plain_text=str(path),
            border_style="ok",
        )

    def print_run_completed(self, result: dict[str, Any]) -> None:
        outdir = Path(result["outdir"])
        history_outdir = Path(result.get("history_outdir", result["outdir"]))
        if not self.rich_enabled:
            self.plain_print(str(outdir))
            self.print_warnings(result.get("warnings") or [])
            return
        body = Text()
        body.append("Run", style="label")
        body.append(": ", style="muted")
        body.append(str(result["instance_id"]), style="accent")
        body.append("\n")
        body.append("Results", style="label")
        body.append(": ", style="muted")
        body.append(str(outdir / "results"), style="value")
        body.append("\n")
        body.append("Project Dir", style="label")
        body.append(": ", style="muted")
        body.append(str(outdir), style="value")
        if history_outdir != outdir:
            body.append("\n")
            body.append("History Dir", style="label")
            body.append(": ", style="muted")
            body.append(str(history_outdir), style="value")
        self.console.print(
            Panel(
                body,
                title="[ok]Run Completed[/ok]",
                border_style="ok",
                box=box.ROUNDED,
            )
        )
        self.print_warnings(result.get("warnings") or [])

    def print_render_completed(self, result: dict[str, Any]) -> None:
        outdir = Path(result["outdir"])
        history_outdir = Path(result.get("history_outdir", result["outdir"]))
        launcher = history_outdir / "run.sh"
        if not self.rich_enabled:
            self.plain_print(str(outdir))
            self.print_warnings(result.get("warnings") or [])
            return
        body = Text()
        body.append("Template", style="label")
        body.append(": ", style="muted")
        body.append(str(result["template"]), style="accent")
        body.append("\n")
        body.append("Rendered Dir", style="label")
        body.append(": ", style="muted")
        body.append(str(outdir), style="value")
        body.append("\n")
        body.append("Launcher", style="label")
        body.append(": ", style="muted")
        body.append(str(launcher), style="value")
        self.console.print(
            Panel(
                body,
                title="[ok]Render Completed[/ok]",
                border_style="ok",
                box=box.ROUNDED,
            )
        )
        self.print_warnings(result.get("warnings") or [])

    def print_warnings(self, warnings: list[dict[str, Any]]) -> None:
        if not warnings:
            return
        if not self.rich_enabled:
            for warning in warnings:
                scope = warning.get("template") or "template"
                param = warning.get("param")
                if param:
                    scope = f"{scope}.{param}"
                line = f"Warning: {scope}: {warning.get('message', '')}"
                fallback = warning.get("fallback")
                if fallback is not None:
                    line += f" Fallback: {fallback}."
                action = warning.get("action")
                if action:
                    line += f" Action: {action}"
                self.plain_error(line)
            return

        table = Table(box=box.SIMPLE_HEAVY, header_style="warn")
        table.add_column("Scope", style="warn", no_wrap=True)
        table.add_column("Message", style="value")
        table.add_column("Fallback", style="value")
        table.add_column("Action", style="value")
        for warning in warnings:
            scope = warning.get("template") or "template"
            param = warning.get("param")
            if param:
                scope = f"{scope}.{param}"
            table.add_row(
                scope,
                str(warning.get("message", "")),
                str(warning.get("fallback", "")),
                str(warning.get("action", "")),
            )
        self.error_console.print(
            Panel(
                table,
                title="[warn]Warnings[/warn]",
                border_style="warn",
                box=box.ROUNDED,
            )
        )

    def print_collect_completed(self, result: dict[str, Any]) -> None:
        outdir = Path(result["outdir"])
        project_updated = bool(result.get("project_updated"))
        project_path = str(result.get("project_path") or "")
        if not self.rich_enabled:
            self.plain_print(str(outdir))
            if project_path:
                if project_updated:
                    self.plain_print(f"project updated\t{project_path}")
                else:
                    self.plain_print(f"project unchanged\t{project_path}")
            else:
                self.plain_print("project unchanged\t(no active project)")
            return
        body = Text()
        body.append("Run Dir", style="label")
        body.append(": ", style="muted")
        body.append(str(outdir), style="value")
        body.append("\n")
        body.append("Outputs", style="label")
        body.append(": ", style="muted")
        body.append(str(len(result.get("outputs", {}))), style="accent")
        body.append("\n")
        body.append("Project", style="label")
        body.append(": ", style="muted")
        if project_path:
            body.append("updated" if project_updated else "unchanged", style="accent" if project_updated else "warn")
            body.append(" ", style="muted")
            body.append(project_path, style="value")
        else:
            body.append("unchanged", style="warn")
            body.append(" ", style="muted")
            body.append("(no active project)", style="value")
        self.console.print(
            Panel(
                body,
                title="[ok]Outputs Collected[/ok]",
                border_style="ok",
                box=box.ROUNDED,
            )
        )

    def print_test_completed(self, result: dict[str, Any]) -> None:
        outdir = Path(result["outdir"])
        if not self.rich_enabled:
            self.plain_print(f"PASS {result['template']}\t{outdir}")
            return
        body = Text()
        body.append("Template", style="label")
        body.append(": ", style="muted")
        body.append(str(result["template"]), style="accent")
        body.append("\n")
        body.append("Workspace", style="label")
        body.append(": ", style="muted")
        body.append(str(outdir), style="value")
        self.console.print(
            Panel(
                body,
                title="[ok]Test Passed[/ok]",
                border_style="ok",
                box=box.ROUNDED,
            )
        )

    def print_runs(self, runs: list[dict[str, Any]]) -> None:
        if not runs:
            self._print_empty_state("[warn]Recorded Runs[/warn]", "No runs recorded.")
            return
        if not self.rich_enabled:
            for run in runs:
                state = run.get("state")
                suffix = f"\t{state}" if state else ""
                self.plain_print(f"{run['instance_id']}\t{run['id']}\t{run['path']}{suffix}")
            return

        has_state = any(run.get("state") not in (None, "") or "adopted" in run for run in runs)
        has_binding = any(isinstance(run.get("binding"), dict) and run["binding"].get("ref") for run in runs)
        has_version = any(run.get("template_version") not in (None, "") for run in runs)

        table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        table.add_column("Instance")
        table.add_column("Template")
        table.add_column("Path", style="value")
        if has_state:
            table.add_column("State", style="value", no_wrap=True)
        if has_binding:
            table.add_column("Binding", style="value", no_wrap=True)
        if has_version:
            table.add_column("Version", style="value", no_wrap=True)
        for run in runs:
            row = [
                str(run["instance_id"]),
                str(run["id"]),
                self._project_value_text(run["path"]),
            ]
            if has_state:
                row.append(self._run_state_text(run))
            if has_binding:
                binding = run.get("binding")
                row.append(str(binding.get("ref")) if isinstance(binding, dict) and binding.get("ref") else "-")
            if has_version:
                row.append(str(run.get("template_version") or "-"))
            table.add_row(*row)
        self._print_tabled_panel(table, title="[info]Recorded Runs[/info]")

    def _project_author_text(self, author: dict[str, Any] | None) -> str:
        if not author:
            return "-"
        fields = [str(author.get(key) or "").strip() for key in ("name", "email", "organization")]
        values = [value for value in fields if value]
        return ", ".join(values) if values else "-"

    def _project_pack_fields(
        self,
        pack: Any,
        *,
        active_pack: str | None,
        total_packs: int,
    ) -> tuple[str, str, str, bool]:
        if isinstance(pack, str):
            return ("", pack, "", active_pack == pack or (active_pack is None and total_packs == 1))
        if isinstance(pack, dict):
            pack_id = str(pack.get("id") or "")
            pack_ref = str(pack.get("ref") or "")
            binding = str(pack.get("binding") or "")
            is_active = active_pack == pack_id or active_pack == pack_ref or (active_pack is None and total_packs == 1)
            return (pack_id, pack_ref, binding, is_active)
        return ("", str(pack), "", False)

    def _run_state_text(self, run: dict[str, Any]) -> str:
        state = str(run.get("state") or "").strip()
        if state:
            if run.get("adopted"):
                return f"{state} (adopted)"
            return state
        if "adopted" in run:
            return "adopted" if run.get("adopted") else "managed"
        return "-"

    def _looks_like_path_text(self, value: str) -> bool:
        return "/" in value or "\\" in value

    def _shorten_project_path(self, value: str, *, max_length: int = 72) -> str:
        text = value.strip()
        if len(text) <= max_length:
            return text

        separator = "/" if "/" in text else "\\"
        parts = [part for part in text.split(separator) if part]
        if not parts:
            return text

        suffix_parts: list[str] = []
        current = ""
        budget = max_length - 4
        for part in reversed(parts):
            candidate = part if not current else f"{part}{separator}{current}"
            if len(candidate) > budget and suffix_parts:
                break
            current = candidate
            suffix_parts.append(part)
            if len(candidate) >= budget:
                break

        if not current:
            return "..." + text[-(max_length - 3) :]
        return f"...{separator}{current}"

    def _project_value_text(self, value: Any, *, max_list_items: int | None = None) -> str:
        if isinstance(value, list):
            if not value:
                return "-"
            items = [self._project_value_text(item) for item in value]
            if max_list_items is not None and len(items) > max_list_items:
                remaining = len(items) - max_list_items
                items = items[:max_list_items] + [f"... (+{remaining} more)"]
            return "\n".join(items)
        if isinstance(value, dict):
            if not value:
                return "-"
            return json.dumps(value, sort_keys=True)
        if value is None:
            return "-"
        text = str(value)
        if self.rich_enabled and self._looks_like_path_text(text):
            return self._shorten_project_path(text)
        return text

    def _plain_append_mapping(self, lines: list[str], title: str, mapping: dict[str, Any] | None) -> None:
        lines.append(f"{title}:")
        if not mapping:
            lines.append("  -")
            return
        for key, value in mapping.items():
            if isinstance(value, list):
                if not value:
                    lines.append(f"  {key}: []")
                    continue
                lines.append(f"  {key}:")
                for item in value:
                    item_text = self._project_value_text(item)
                    indented = item_text.replace("\n", "\n      ")
                    lines.append(f"    - {indented}")
                continue
            value_text = self._project_value_text(value).replace("\n", "\n    ")
            lines.append(f"  {key}: {value_text}")

    def print_project_view(
        self,
        project_data: dict[str, Any],
        *,
        project_path: Path,
        runs: list[dict[str, Any]],
    ) -> None:
        project_id = str(project_data.get("id") or project_path.name)
        active_pack = project_data.get("active_pack")
        active_pack_text = str(active_pack) if active_pack is not None else "-"
        author_text = self._project_author_text(project_data.get("author"))
        packs = list(project_data.get("packs") or [])

        if not self.rich_enabled:
            lines = [
                f"Project: {project_id}",
                f"Path: {project_path}",
                f"Active Pack: {active_pack_text}",
                f"Author: {author_text}",
                f"Packs: {len(packs)}",
            ]
            if packs:
                for pack in packs:
                    pack_id, pack_ref, binding, is_active = self._project_pack_fields(
                        pack,
                        active_pack=active_pack if isinstance(active_pack, str) else None,
                        total_packs=len(packs),
                    )
                    marker = "*" if is_active else "-"
                    parts = [marker]
                    if pack_id:
                        parts.append(pack_id)
                    if pack_ref:
                        parts.append(pack_ref)
                    if binding:
                        parts.append(f"binding={binding}")
                    lines.append("  " + " ".join(parts))
            lines.append(f"Runs: {len(runs)}")
            for run in runs:
                lines.append("")
                lines.append(f"Run: {run.get('instance_id', '-')}" + f" ({run.get('id', '-')})")
                for key in ("path", "history_path", "template_version", "binding", "adopted", "meta"):
                    if key in run:
                        value_text = self._project_value_text(run.get(key)).replace("\n", "\n  ")
                        lines.append(f"{key}: {value_text}")
                pack = run.get("pack")
                if pack:
                    lines.append(f"pack: {self._project_value_text(pack)}")
                self._plain_append_mapping(lines, "params", run.get("params"))
                self._plain_append_mapping(lines, "outputs", run.get("outputs"))
            self.plain_print("\n".join(lines))
            return

        summary = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        summary.add_column("Field", style="label", no_wrap=True)
        summary.add_column("Value", style="value")
        summary.add_row("Project", project_id)
        summary.add_row("Path", self._project_value_text(str(project_path)))
        summary.add_row("Active Pack", active_pack_text)
        summary.add_row("Author", author_text)
        summary.add_row("Runs", str(len(runs)))
        self.console.print(
            Panel(
                summary,
                title="[info]Project Overview[/info]",
                border_style="info",
                box=box.ROUNDED,
            )
        )

        if packs:
            pack_table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            pack_table.add_column("Active", no_wrap=True)
            pack_table.add_column("Pack")
            pack_table.add_column("Ref", style="value")
            pack_table.add_column("Binding", style="value")
            for pack in packs:
                pack_id, pack_ref, binding, is_active = self._project_pack_fields(
                    pack,
                    active_pack=active_pack if isinstance(active_pack, str) else None,
                    total_packs=len(packs),
                )
                pack_table.add_row(
                    "yes" if is_active else "",
                    pack_id or "-",
                    self._project_value_text(pack_ref or "-"),
                    binding or "-",
                )
            self.console.print(
                Panel(
                    pack_table,
                    title="[info]Configured Packs[/info]",
                    border_style="info",
                    box=box.ROUNDED,
                )
            )

        if not runs:
            self.console.print(
                Panel(
                    Text("No runs recorded in project.yaml.", style="muted"),
                    title="[warn]Recorded Runs[/warn]",
                    border_style="warn",
                    box=box.ROUNDED,
                )
            )
            return

        summary_runs = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        summary_runs.add_column("Instance", style="label", no_wrap=True)
        summary_runs.add_column("Template", style="value", no_wrap=True)
        summary_runs.add_column("Path", style="value")
        if any(run.get("state") not in (None, "") or "adopted" in run for run in runs):
            summary_runs.add_column("State", style="value", no_wrap=True)
        if any(isinstance(run.get("binding"), dict) and run["binding"].get("ref") for run in runs):
            summary_runs.add_column("Binding", style="value", no_wrap=True)
        if any(run.get("template_version") not in (None, "") for run in runs):
            summary_runs.add_column("Version", style="value", no_wrap=True)

        show_state = any(run.get("state") not in (None, "") or "adopted" in run for run in runs)
        show_binding = any(isinstance(run.get("binding"), dict) and run["binding"].get("ref") for run in runs)
        show_version = any(run.get("template_version") not in (None, "") for run in runs)

        for run in runs:
            row = [
                str(run.get("instance_id") or "-"),
                str(run.get("id") or "-"),
                self._project_value_text(run.get("path") or "-"),
            ]
            if show_state:
                row.append(self._run_state_text(run))
            if show_binding:
                binding = run.get("binding")
                row.append(str(binding.get("ref")) if isinstance(binding, dict) and binding.get("ref") else "-")
            if show_version:
                row.append(str(run.get("template_version") or "-"))
            summary_runs.add_row(*row)

        self._print_tabled_panel(summary_runs, title="[info]Run Summary[/info]")

        for run in runs:
            meta_table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            meta_table.add_column("Field", style="label", no_wrap=True)
            meta_table.add_column("Value", style="value")
            meta_table.add_row("Template", str(run.get("id") or "-"))
            meta_table.add_row("Path", self._project_value_text(run.get("path") or "-"))
            if run.get("history_path"):
                meta_table.add_row("History", self._project_value_text(run.get("history_path")))
            if "template_version" in run:
                meta_table.add_row("Version", self._project_value_text(run.get("template_version")))
            if "binding" in run:
                meta_table.add_row("Binding", self._project_value_text(run.get("binding")))
            if "adopted" in run:
                meta_table.add_row("Adopted", self._project_value_text(run.get("adopted")))
            if run.get("state") not in (None, ""):
                meta_table.add_row("State", self._project_value_text(run.get("state")))
            if run.get("pack"):
                meta_table.add_row("Pack", self._project_value_text(run.get("pack")))
            if run.get("meta"):
                meta_table.add_row("Meta", self._project_value_text(run.get("meta")))

            params_table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            params_table.add_column("Param", style="label", no_wrap=True)
            params_table.add_column("Value", style="value")
            params = run.get("params") or {}
            if isinstance(params, dict) and params:
                for key, value in params.items():
                    params_table.add_row(str(key), self._project_value_text(value, max_list_items=5))
            else:
                params_table.add_row("-", "-")

            outputs_table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            outputs_table.add_column("Output", style="label", no_wrap=True)
            outputs_table.add_column("Value", style="value")
            outputs = run.get("outputs") or {}
            if isinstance(outputs, dict) and outputs:
                for key, value in outputs.items():
                    outputs_table.add_row(str(key), self._project_value_text(value, max_list_items=5))
            else:
                outputs_table.add_row("-", "-")

            self.console.print(
                Panel(
                    meta_table,
                    title=f"[ok]{run.get('instance_id', '-') }[/ok]",
                    border_style="ok",
                    box=box.ROUNDED,
                )
            )
            self._print_tabled_panel(params_table, title="[info]Parameters[/info]")
            self._print_tabled_panel(outputs_table, title="[ok]Outputs[/ok]", border_style="ok")

    def print_templates(self, templates: list[dict[str, Any]]) -> None:
        if not templates:
            self._print_empty_state("[warn]Template Catalog[/warn]", "No templates found.")
            return
        grouped: dict[str, list[dict[str, Any]]] = {}
        for template in templates:
            grouped.setdefault(template["pack_ref"], []).append(template)
        if not self.rich_enabled:
            first_group = True
            for pack_ref, pack_templates in grouped.items():
                if not first_group:
                    self.plain_print("")
                first_group = False
                self.plain_print(f"PACK\t{pack_ref}")
                for template in pack_templates:
                    description = template.get("description") or "-"
                    required_inputs = ",".join(template.get("required_inputs") or []) or "-"
                    expected_outputs = ",".join(template.get("expected_outputs") or []) or "-"
                    version = template.get("version") or "-"
                    self.plain_print(
                        f"{template['id']}\t{description}\t{required_inputs}\t{expected_outputs}\t{version}"
                    )
            return
        first_group = True
        for pack_ref, pack_templates in grouped.items():
            if not first_group:
                self.console.print()
            first_group = False
            self.console.print(f"[label]Pack:[/label] [value]{self._project_value_text(pack_ref)}[/value]")
            table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            table.add_column("Template")
            table.add_column("Description", style="value")
            table.add_column("Required Inputs", style="value")
            table.add_column("Expected Outputs", style="value")
            table.add_column("Version", style="value")
            for template in pack_templates:
                table.add_row(
                    template["id"],
                    template.get("description") or "-",
                    ", ".join(template.get("required_inputs") or []) or "-",
                    ", ".join(template.get("expected_outputs") or []) or "-",
                    template.get("version") or "-",
                )
            self._print_tabled_panel(table, title="[info]Template Catalog[/info]")

    def print_packs(self, packs: list[dict[str, Any]]) -> None:
        if not packs:
            self._print_empty_state("[warn]Configured Packs[/warn]", "No packs configured.")
            return
        if not self.rich_enabled:
            for pack in packs:
                active = "*" if pack.get("active") else "-"
                binding = pack.get("binding") or ""
                self.plain_print(f"{active}\t{pack['id']}\t{pack['ref']}\t{binding}")
            return
        table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        table.add_column("Active")
        table.add_column("Pack")
        table.add_column("Ref", style="value")
        table.add_column("Binding", style="value")
        for pack in packs:
            table.add_row(
                "yes" if pack.get("active") else "",
                pack["id"],
                self._project_value_text(pack["ref"]),
                pack.get("binding") or "",
            )
        self._print_tabled_panel(table, title="[info]Configured Packs[/info]")

    def _looks_like_run_metadata(self, metadata: dict[str, Any]) -> bool:
        required = {"template", "instance_id", "params", "outputs"}
        return required.issubset(metadata)

    def _metadata_value_text(self, value: Any) -> str:
        if isinstance(value, list):
            return "\n".join(self._metadata_value_text(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True)
        if value is None:
            return "-"
        text = str(value)
        if self.rich_enabled and self._looks_like_path_text(text):
            return self._shorten_project_path(text)
        return text

    def _provenance_text(self, provenance: dict[str, Any] | None) -> str:
        if not provenance:
            return "-"
        source = provenance.get("source")
        if source == "explicit":
            return "cli"
        if source == "default":
            return "default"
        if source == "project":
            key = provenance.get("key")
            return f"project:{key}" if key else "project"
        if source == "binding":
            binding_source = provenance.get("binding_source")
            if binding_source == "function":
                name = provenance.get("name")
                return f"binding:function:{name}" if name else "binding:function"
            if binding_source == "output":
                template = provenance.get("template")
                output = provenance.get("output")
                if template and output:
                    return f"binding:output:{template}.{output}"
                if output:
                    return f"binding:output:{output}"
            if binding_source == "value":
                return "binding:value"
            return "binding"
        return str(source or "-")

    def _command_text(self, command: Any) -> str:
        if isinstance(command, list) and all(isinstance(item, str) for item in command):
            return shlex.join(command)
        return self._metadata_value_text(command)

    def _print_run_metadata(self, metadata: dict[str, Any]) -> None:
        summary = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        summary.add_column("Field", style="label", no_wrap=True)
        summary.add_column("Value", style="value")
        summary_rows = [
            ("Template", metadata.get("template")),
            ("Instance", metadata.get("instance_id")),
            ("Run Mode", metadata.get("run_mode")),
            ("Template Mode", metadata.get("template_run_mode")),
            ("Version", metadata.get("template_version")),
            ("Timestamp", metadata.get("timestamp")),
        ]
        pack = metadata.get("pack")
        if isinstance(pack, dict):
            summary_rows.append(("Pack", pack.get("ref")))
            if pack.get("revision"):
                summary_rows.append(("Pack Revision", pack.get("revision")))
        binding = metadata.get("binding")
        if isinstance(binding, dict) and binding.get("ref"):
            summary_rows.append(("Binding", binding.get("ref")))
        software = metadata.get("software")
        if isinstance(software, list) and software:
            first = software[0]
            if isinstance(first, dict) and first.get("name"):
                value = first["name"]
                if first.get("version"):
                    value = f"{value} {first['version']}"
                summary_rows.append(("Software", value))
        for label, value in summary_rows:
            if value in (None, "", []):
                continue
            summary.add_row(label, self._metadata_value_text(value))
        self._print_tabled_panel(summary, title="[info]Run Details[/info]")

        params = metadata.get("params") or {}
        provenance = metadata.get("param_provenance") or {}
        if isinstance(params, dict) and params:
            table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            table.add_column("Param", style="label", no_wrap=True)
            table.add_column("Value", style="value")
            table.add_column("Source", style="muted")
            for key, value in params.items():
                table.add_row(
                    key,
                    self._metadata_value_text(value),
                    self._provenance_text(provenance.get(key)),
                )
            self._print_tabled_panel(table, title="[info]Resolved Parameters[/info]")

        outputs = metadata.get("outputs") or {}
        if isinstance(outputs, dict):
            table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
            table.add_column("Output", style="label", no_wrap=True)
            table.add_column("Value", style="value")
            if outputs:
                for key, value in outputs.items():
                    table.add_row(key, self._metadata_value_text(value))
            else:
                table.add_row("outputs", "No outputs collected yet")
            self._print_tabled_panel(table, title="[ok]Collected Outputs[/ok]", border_style="ok")

        command = metadata.get("command")
        if command:
            self.console.print(
                Panel(
                    self._command_text(command),
                    title="[accent]Command[/accent]",
                    border_style="accent",
                    box=box.ROUNDED,
                )
            )

    def _print_generic_metadata(self, metadata: dict[str, Any]) -> None:
        title = "[info]Metadata[/info]"
        rows: list[tuple[str, Any]] = []

        if len(metadata) == 1:
            key, value = next(iter(metadata.items()))
            if isinstance(value, dict):
                title = f"[info]{str(key).replace('_', ' ').title()}[/info]"
                rows = [(str(inner_key).replace("_", " ").title(), inner_value) for inner_key, inner_value in value.items()]
            else:
                title = f"[info]{str(key).replace('_', ' ').title()}[/info]"
                rows = [(str(key).replace("_", " ").title(), value)]
        else:
            rows = [(str(key).replace("_", " ").title(), value) for key, value in metadata.items()]

        table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        table.add_column("Field", style="label", no_wrap=True)
        table.add_column("Value", style="value")
        if rows:
            for label, value in rows:
                table.add_row(label, self._metadata_value_text(value))
        else:
            table.add_row("-", "-")
        self._print_tabled_panel(table, title=title)

    def print_metadata(self, metadata: dict[str, Any]) -> None:
        if not self.rich_enabled:
            self.plain_print(json.dumps(metadata, indent=2, sort_keys=True))
            return
        if self._looks_like_run_metadata(metadata):
            self._print_run_metadata(metadata)
            return
        self._print_generic_metadata(metadata)

    def print_methods(self, text: str) -> None:
        if not self.rich_enabled:
            self.plain_print(text)
            return
        self.console.print(
            Panel(
                text,
                title="[info]Methods Preview[/info]",
                border_style="info",
                box=box.ROUNDED,
            )
        )

    def print_server_banner(self, host: str, port: int, *, auth_enabled: bool = False) -> None:
        if not self.rich_enabled:
            auth_text = " (auth enabled)" if auth_enabled else ""
            self.plain_print(f"Serving Linkar API on http://{host}:{port}{auth_text}")
            return
        body = Text()
        body.append("Endpoint", style="label")
        body.append(": ", style="muted")
        body.append(f"http://{host}:{port}", style="accent")
        body.append("\n")
        body.append("Mode", style="label")
        body.append(": ", style="muted")
        body.append("local API server", style="value")
        body.append("\n")
        body.append("Auth", style="label")
        body.append(": ", style="muted")
        body.append("bearer token required" if auth_enabled else "open/local only", style="value")
        body.append("\n")
        body.append("Try", style="label")
        body.append(": ", style="muted")
        body.append(f"GET http://{host}:{port}/v1", style="accent")
        self.console.print(
            Panel(
                body,
                title="[info]Local API Server[/info]",
                border_style="info",
                box=box.ROUNDED,
            )
        )

    def print_error(self, message: str) -> None:
        if not self.rich_enabled:
            self.plain_error(message)
            return
        self.error_console.print(
            Panel(
                message,
                title="[error]Error[/error]",
                border_style="error",
                box=box.ROUNDED,
            )
        )

    def print_usage_error(self, message: str, help_text: str, hint: str | None = None) -> None:
        if not self.rich_enabled:
            self.plain_error(f"Error: {message}")
            self.plain_error("")
            self.plain_error(help_text.rstrip())
            if hint:
                self.plain_error("")
                self.plain_error(hint)
            return

        body = Text()
        body.append(message, style="error")
        if hint:
            body.append("\n")
            body.append(hint, style="muted")
        self.error_console.print(
            Panel(
                body,
                title="[error]Usage Error[/error]",
                border_style="error",
                box=box.ROUNDED,
            )
        )
        self.error_console.print(help_text.rstrip())

    def print_pack_summary(
        self,
        title: str,
        *,
        pack_id: str,
        ref: str,
        binding: str | None = None,
        active: bool | None = None,
        plain_text: str | None = None,
    ) -> None:
        fields: list[tuple[str, Any]] = [("Pack", pack_id), ("Ref", ref)]
        if binding:
            fields.append(("Binding", binding))
        if active is not None:
            fields.append(("Active", "yes" if active else "no"))
        self.print_summary_panel(title, fields, plain_text=plain_text, border_style="accent")

    def print_run_removal(
        self,
        *,
        instance_id: str,
        template_id: str,
        path: str,
        deleted: bool,
        plain_text: str,
    ) -> None:
        title = "[warn]Run Deleted[/warn]" if deleted else "[accent]Run Detached[/accent]"
        border_style = "warn" if deleted else "accent"
        self.print_summary_panel(
            title,
            [("Instance", instance_id), ("Template", template_id), ("Path", path)],
            plain_text=plain_text,
            border_style=border_style,
        )
