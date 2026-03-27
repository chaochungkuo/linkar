from __future__ import annotations

import argparse
import sys
from pathlib import Path

from linkar import __version__
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


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    pass


class ParserUsageError(Exception):
    def __init__(self, parser: argparse.ArgumentParser, message: str):
        super().__init__(message)
        self.parser = parser
        self.message = message


class LinkarArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ParserUsageError(self, message)


def parse_key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected KEY=VALUE")
    key, raw = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("Parameter key must not be empty")
    return key, raw


def resolve_project_init_target(
    *,
    path: str | None,
    name: str | None,
) -> tuple[str, str | None]:
    if path and name:
        raise ProjectValidationError("Use either PATH or --name, not both")
    if name:
        return name, name
    if path:
        return path, None
    return ".", None


def build_parser() -> argparse.ArgumentParser:
    parser = LinkarArgumentParser(
        prog="linkar",
        description="Run reusable computational templates with transparent project state and provenance.",
        epilog=(
            "Examples:\n"
            "  linkar project init .\n"
            "  linkar run hello --pack ./examples/packs/basic --param name=Linkar\n"
            "  linkar project runs\n"
            "  linkar inspect run hello_001\n"
        ),
        formatter_class=HelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed Linkar version and exit.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="commands",
        metavar="COMMAND",
    )

    project_parser = subparsers.add_parser(
        "project",
        help="Initialize a project or inspect indexed runs.",
        description="Create a Linkar project or inspect run records stored in project.yaml.",
        formatter_class=HelpFormatter,
    )
    project_subparsers = project_parser.add_subparsers(
        dest="project_command",
        required=True,
        title="project commands",
        metavar="PROJECT_COMMAND",
    )
    project_init = project_subparsers.add_parser(
        "init",
        help="Create a new project in a directory.",
        description="Create project.yaml in the target directory. Use --name to create a new directory automatically.",
        formatter_class=HelpFormatter,
    )
    project_init.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PATH",
        help="Directory to initialize as a Linkar project.",
    )
    project_init.add_argument(
        "--name",
        metavar="PROJECT_NAME",
        help="Create a new directory with this name and use it as the project id unless --id is set.",
    )
    project_init.add_argument(
        "--id",
        dest="project_id",
        metavar="PROJECT_ID",
        help="Project identifier to write into project.yaml. Defaults to the directory name.",
    )
    project_runs = project_subparsers.add_parser(
        "runs",
        help="List runs recorded in a project.",
        description="Show template instances recorded in project.yaml.",
        formatter_class=HelpFormatter,
    )
    project_runs.add_argument(
        "--project",
        metavar="PATH",
        help="Project directory or project.yaml path. Defaults to the current directory.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run a template once.",
        description="Resolve parameters, execute a template, and record run metadata.",
        formatter_class=HelpFormatter,
        epilog=(
            "Examples:\n"
            "  linkar run hello --pack ./examples/packs/basic --param name=Linkar\n"
            "  linkar run rnaseq --project ./study\n"
        ),
    )
    run_parser.add_argument("template", metavar="TEMPLATE", help="Template id or path to a template directory.")
    run_parser.add_argument(
        "--pack",
        action="append",
        default=[],
        metavar="REF",
        help="Pack path or asset reference to search for the template. Repeat to add more than one.",
    )
    run_parser.add_argument(
        "--binding",
        metavar="REF",
        help="Binding path or asset reference used to resolve parameters.",
    )
    run_parser.add_argument(
        "--project",
        metavar="PATH",
        help="Project directory or project.yaml path. Defaults to the current directory.",
    )
    run_parser.add_argument(
        "--outdir",
        metavar="PATH",
        help="Write run artifacts to a specific directory instead of the default location.",
    )
    run_parser.add_argument(
        "--param",
        action="append",
        default=[],
        type=parse_key_value,
        metavar="KEY=VALUE",
        help="Template parameter in KEY=VALUE form",
    )

    templates_parser = subparsers.add_parser(
        "templates",
        help="List available templates.",
        description="List templates visible from explicit packs and the active project configuration.",
        formatter_class=HelpFormatter,
    )
    templates_parser.add_argument(
        "--pack",
        action="append",
        default=[],
        metavar="REF",
        help="Pack path or asset reference to include in the search. Repeat to add more than one.",
    )
    templates_parser.add_argument(
        "--project",
        metavar="PATH",
        help="Project directory or project.yaml path. Defaults to the current directory.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect recorded metadata.",
        description="Inspect metadata for recorded Linkar runs.",
        formatter_class=HelpFormatter,
    )
    inspect_subparsers = inspect_parser.add_subparsers(
        dest="inspect_command",
        required=True,
        title="inspect commands",
        metavar="INSPECT_COMMAND",
    )
    inspect_run_parser = inspect_subparsers.add_parser(
        "run",
        help="Show metadata for one run.",
        description="Inspect run metadata by instance id or run directory path.",
        formatter_class=HelpFormatter,
    )
    inspect_run_parser.add_argument("run_ref", metavar="RUN_REF", help="Run instance id or path to a run directory.")
    inspect_run_parser.add_argument(
        "--project",
        metavar="PATH",
        help="Project directory or project.yaml path. Defaults to the current directory.",
    )

    methods_parser = subparsers.add_parser(
        "methods",
        help="Generate a methods draft from run metadata.",
        description="Generate an editable methods summary from the runs recorded in a project.",
        formatter_class=HelpFormatter,
    )
    methods_parser.add_argument(
        "--project",
        metavar="PATH",
        help="Project directory or project.yaml path. Defaults to the current directory.",
    )

    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the local Linkar API server.",
        description="Expose the local project/runtime API over HTTP for automation and agents.",
        formatter_class=HelpFormatter,
    )
    serve_parser.add_argument("--host", default="127.0.0.1", metavar="HOST", help="Host interface to bind.")
    serve_parser.add_argument("--port", default=8000, type=int, metavar="PORT", help="Port to listen on.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ui = CliUI()
    raw_args = sys.argv[1:] if argv is None else argv

    if not raw_args:
        ui.print_text(parser.format_help().rstrip())
        ui.print_text("Try 'linkar run --help' for a focused command example.")
        return 1

    try:
        args = parser.parse_args(raw_args)
    except ParserUsageError as exc:
        ui.print_usage_error(
            exc.message,
            exc.parser.format_help(),
            "Use '--help' on the command you are trying to run for examples and options.",
        )
        return 2

    try:
        if args.command == "project" and args.project_command == "init":
            target_path, implied_id = resolve_project_init_target(path=args.path, name=args.name)
            project_path = init_project(target_path, project_id=args.project_id or implied_id)
            project_id = args.project_id or implied_id or Path(target_path).resolve().name
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

        raise ParserUsageError(parser, "unknown command")
    except LinkarError as exc:
        ui.print_error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
