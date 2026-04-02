from __future__ import annotations

import json
import os
import shlex
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any

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

    def status(self, message: str):
        if not self.rich_enabled:
            return nullcontext()
        return self.console.status(f"[accent]{message}[/accent]", spinner="dots")

    def print_project_created(self, path: Path, project_id: str) -> None:
        if not self.rich_enabled:
            self.plain_print(str(path))
            return
        body = Text()
        body.append("Project", style="label")
        body.append(": ", style="muted")
        body.append(project_id, style="accent")
        body.append("\n")
        body.append("Path", style="label")
        body.append(": ", style="muted")
        body.append(str(path), style="value")
        self.console.print(Panel(body, title="[accent]Linkar[/accent]", border_style="accent"))

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
        if not self.rich_enabled:
            self.plain_print(str(outdir))
            return
        body = Text()
        body.append("Run Dir", style="label")
        body.append(": ", style="muted")
        body.append(str(outdir), style="value")
        body.append("\n")
        body.append("Outputs", style="label")
        body.append(": ", style="muted")
        body.append(str(len(result.get("outputs", {}))), style="accent")
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
        if not self.rich_enabled:
            for run in runs:
                self.plain_print(f"{run['instance_id']}\t{run['id']}\t{run['path']}")
            return
        table = Table(box=box.SIMPLE_HEAVY, header_style="accent")
        table.add_column("Instance")
        table.add_column("Template")
        table.add_column("Path", style="value")
        for run in runs:
            table.add_row(run["instance_id"], run["id"], run["path"])
        self.console.print(table)

    def print_templates(self, templates: list[dict[str, Any]]) -> None:
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
            self.console.print(f"[label]Pack:[/label] [value]{pack_ref}[/value]")
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
            self.console.print(table)

    def print_packs(self, packs: list[dict[str, Any]]) -> None:
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
            table.add_row("yes" if pack.get("active") else "", pack["id"], pack["ref"], pack.get("binding") or "")
        self.console.print(table)

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
        return str(value)

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
        self.console.print(
            Panel(
                summary,
                title="[accent]Run Inspection[/accent]",
                border_style="accent",
                box=box.ROUNDED,
            )
        )

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
            self.console.print(table)

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
            self.console.print(table)

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

    def print_metadata(self, metadata: dict[str, Any]) -> None:
        if not self.rich_enabled:
            self.plain_print(json.dumps(metadata, indent=2, sort_keys=True))
            return
        if self._looks_like_run_metadata(metadata):
            self._print_run_metadata(metadata)
            return
        self.console.print(JSON.from_data(metadata))

    def print_methods(self, text: str) -> None:
        if not self.rich_enabled:
            self.plain_print(text)
            return
        self.console.print(
            Panel(
                text,
                title="[accent]Methods Draft[/accent]",
                border_style="accent",
                box=box.ROUNDED,
            )
        )

    def print_server_banner(self, host: str, port: int) -> None:
        if not self.rich_enabled:
            self.plain_print(f"Serving Linkar API on http://{host}:{port}")
            return
        body = Text()
        body.append("Endpoint", style="label")
        body.append(": ", style="muted")
        body.append(f"http://{host}:{port}", style="accent")
        body.append("\n")
        body.append("Mode", style="label")
        body.append(": ", style="muted")
        body.append("local API server", style="value")
        self.console.print(
            Panel(
                body,
                title="[accent]Linkar Serve[/accent]",
                border_style="accent",
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
