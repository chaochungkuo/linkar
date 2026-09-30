from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from linkar.assets import (
    asset_cache_dir,
    asset_cache_root,
    github_clone_url,
    is_remote_asset_ref,
    parse_remote_ref,
    resolve_asset_ref,
    resolve_asset_ref_at_revision,
    resolve_asset_refs,
    run_git,
    update_remote_asset,
)
from linkar.errors import AssetResolutionError


def commit_file(repo: Path, name: str, content: str) -> str:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.org"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / name).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", f"add {name}"], cwd=repo, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def append_commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", f"update {name}"], cwd=repo, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def test_parse_remote_ref_keeps_scp_style_git_user_host_intact() -> None:
    assert parse_remote_ref("git+git@github.com:ORG/pack.git") == (
        "git+git@github.com:ORG/pack.git",
        None,
    )


def test_parse_remote_ref_supports_revision_on_scp_style_git_ref() -> None:
    assert parse_remote_ref("git+git@github.com:ORG/pack.git@main") == (
        "git+git@github.com:ORG/pack.git",
        "main",
    )


def test_parse_remote_ref_supports_revision_on_github_ref() -> None:
    assert parse_remote_ref("github:ORG/pack@v1.0.0") == ("github:ORG/pack", "v1.0.0")


def test_asset_helpers_distinguish_remote_refs_and_use_linkar_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINKAR_HOME", str(tmp_path / "linkar-home"))

    assert asset_cache_root() == (tmp_path / "linkar-home" / "assets").resolve()
    assert asset_cache_dir("github:ORG/pack") == asset_cache_dir("github:ORG/pack")
    assert asset_cache_dir("github:ORG/pack") != asset_cache_dir("github:ORG/other")
    assert is_remote_asset_ref("github:ORG/pack") is True
    assert is_remote_asset_ref("git+https://example.org/pack.git") is True
    assert is_remote_asset_ref("./pack") is False
    assert github_clone_url("github:ORG/pack") == "https://github.com/ORG/pack.git"


def test_resolve_local_assets_and_missing_paths(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()

    resolved = resolve_asset_ref(pack)
    assert resolved.root == pack.resolve()
    assert resolved.ref == str(pack.resolve())
    assert resolve_asset_refs(None) == []
    assert [asset.root for asset in resolve_asset_refs(str(pack))] == [pack.resolve()]
    assert [asset.root for asset in resolve_asset_refs([pack, str(pack)])] == [
        pack.resolve(),
        pack.resolve(),
    ]

    with pytest.raises(AssetResolutionError, match="Asset not found"):
        resolve_asset_ref(tmp_path / "missing")


def test_update_local_asset_reports_external_management(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()

    result = update_remote_asset(str(pack))

    assert result.remote is False
    assert result.action == "local"
    assert result.updated is False
    assert result.as_dict()["root"] == str(pack.resolve())


def test_run_git_wraps_command_failures(tmp_path: Path) -> None:
    with pytest.raises(AssetResolutionError):
        run_git(["rev-parse", "HEAD"], cwd=tmp_path)


def test_remote_asset_clone_update_and_locked_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINKAR_HOME", str(tmp_path / "linkar-home"))
    origin = tmp_path / "origin"
    origin.mkdir()
    first_revision = commit_file(origin, "linkar_pack.yaml", "templates: {}\n")
    ref = f"git+{origin.as_uri()}"

    cloned = update_remote_asset(ref)
    assert cloned.action == "cloned"
    assert cloned.before is None
    assert cloned.after == first_revision

    second_revision = append_commit(origin, "linkar_pack.yaml", "templates: {}\nupdated: true\n")
    updated = update_remote_asset(ref)
    assert updated.action == "updated"
    assert updated.before == first_revision
    assert updated.after == second_revision

    unchanged = update_remote_asset(ref)
    assert unchanged.action == "unchanged"
    assert unchanged.updated is False

    locked = resolve_asset_ref_at_revision(ref, first_revision)
    assert locked.ref == ref
    assert locked.revision == first_revision
