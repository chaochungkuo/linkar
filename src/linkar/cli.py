from __future__ import annotations

import argparse
from pathlib import Path

from linkar.core import (
    generate_methods,
    LinkarError,
    init_project,
    inspect_run,
    list_project_runs,
    list_templates,
    run_template,
)
from linkar.server import serve
from linkar.ui import CliUI


def parse_key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected KEY=VALUE")
    key, raw = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("Parameter key must not be empty")
    return key, raw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linkar")
    subparsers = parser.add_subparsers(dest="command", required=True)

    project_parser = subparsers.add_parser("project")
    project_subparsers = project_parser.add_subparsers(dest="project_command", required=True)
    project_init = project_subparsers.add_parser("init")
    project_init.add_argument("path", nargs="?", default=".")
    project_init.add_argument("--id", dest="project_id")
    project_runs = project_subparsers.add_parser("runs")
    project_runs.add_argument("--project")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("template")
    run_parser.add_argument("--pack", action="append", default=[])
    run_parser.add_argument("--binding")
    run_parser.add_argument("--project")
    run_parser.add_argument("--outdir")
    run_parser.add_argument(
        "--param",
        action="append",
        default=[],
        type=parse_key_value,
        help="Template parameter in KEY=VALUE form",
    )

    templates_parser = subparsers.add_parser("templates")
    templates_parser.add_argument("--pack", action="append", default=[])
    templates_parser.add_argument("--project")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_subparsers = inspect_parser.add_subparsers(dest="inspect_command", required=True)
    inspect_run_parser = inspect_subparsers.add_parser("run")
    inspect_run_parser.add_argument("run_ref")
    inspect_run_parser.add_argument("--project")

    methods_parser = subparsers.add_parser("methods")
    methods_parser.add_argument("--project")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ui = CliUI()

    try:
        if args.command == "project" and args.project_command == "init":
            project_path = init_project(args.path, project_id=args.project_id)
            project_id = args.project_id or Path(args.path).resolve().name
            ui.print_project_created(project_path, project_id)
            return 0
        if args.command == "project" and args.project_command == "runs":
            runs = list_project_runs(project=args.project)
            ui.print_runs(runs)
            return 0

        if args.command == "run":
            params = dict(args.param)
            with ui.status("Running template"):
                result = run_template(
                    args.template,
                    params=params,
                    project=args.project,
                    outdir=args.outdir,
                    pack_refs=args.pack,
                    binding_ref=args.binding,
                )
            ui.print_run_completed(result)
            return 0

        if args.command == "templates":
            templates = list_templates(pack_refs=args.pack, project=args.project)
            ui.print_templates(templates)
            return 0

        if args.command == "inspect" and args.inspect_command == "run":
            metadata = inspect_run(args.run_ref, project=args.project)
            ui.print_metadata(metadata)
            return 0

        if args.command == "methods":
            ui.print_methods(generate_methods(project=args.project))
            return 0

        if args.command == "serve":
            ui.print_server_banner(args.host, args.port)
            serve(host=args.host, port=args.port)
            return 0

        parser.error("Unknown command")
        return 2
    except LinkarError as exc:
        ui.print_error(str(exc))
        parser.exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
