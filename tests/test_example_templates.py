from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "linkar.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_all_basic_pack_templates_have_passing_template_tests(tmp_path: Path) -> None:
    pack_root = ROOT / "examples" / "packs" / "basic"
    template_ids = [
        "simple_echo",
        "simple_file_input",
        "simple_boolean_flag",
        "download_test_data",
        "fastq_stats",
        "glob_reports",
        "pixi_echo",
        "pixi_pytest",
        "portable_python",
    ]

    for template_id in template_ids:
        completed = run_cli("test", template_id, "--pack", str(pack_root), cwd=tmp_path)
        assert completed.returncode == 0, f"{template_id}: {completed.stderr}"


def test_all_chaining_pack_templates_have_passing_template_tests(tmp_path: Path) -> None:
    pack_root = ROOT / "examples" / "packs" / "chaining"
    template_ids = ["produce_message", "consume_message"]

    for template_id in template_ids:
        completed = run_cli("test", template_id, "--pack", str(pack_root), cwd=tmp_path)
        assert completed.returncode == 0, f"{template_id}: {completed.stderr}"


def test_all_pack_management_templates_have_passing_template_tests(tmp_path: Path) -> None:
    pack_roots = [
        ROOT / "examples" / "packs" / "pack_management" / "pack_one",
        ROOT / "examples" / "packs" / "pack_management" / "pack_two",
    ]

    for pack_root in pack_roots:
        completed = run_cli("test", "dup", "--pack", str(pack_root), cwd=tmp_path)
        assert completed.returncode == 0, f"{pack_root.name}: {completed.stderr}"


def test_all_remote_pack_templates_have_passing_template_tests(tmp_path: Path) -> None:
    pack_root = ROOT / "examples" / "packs" / "remote"
    completed = run_cli("test", "remote_wave", "--pack", str(pack_root), cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr


def test_all_binding_override_pack_templates_have_passing_template_tests(tmp_path: Path) -> None:
    pack_root = ROOT / "examples" / "packs" / "binding_overrides"
    for template_id in ["produce_data", "consume_data"]:
        completed = run_cli("test", template_id, "--pack", str(pack_root), cwd=tmp_path)
        assert completed.returncode == 0, f"{template_id}: {completed.stderr}"
