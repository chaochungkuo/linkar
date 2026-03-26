from __future__ import annotations

import argparse
from pathlib import Path

from linkar.core import LinkarError, init_project, run_template


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

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("template")
    run_parser.add_argument("--pack", action="append", default=[])
    run_parser.add_argument("--project")
    run_parser.add_argument("--outdir")
    run_parser.add_argument(
        "--param",
        action="append",
        default=[],
        type=parse_key_value,
        help="Template parameter in KEY=VALUE form",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "project" and args.project_command == "init":
            project_path = init_project(args.path, project_id=args.project_id)
            print(project_path)
            return 0

        if args.command == "run":
            params = dict(args.param)
            result = run_template(
                args.template,
                params=params,
                project=args.project,
                outdir=args.outdir,
                pack_refs=args.pack,
            )
            print(result["outdir"])
            return 0

        parser.error("Unknown command")
        return 2
    except LinkarError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
