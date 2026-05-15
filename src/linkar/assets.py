from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkar.errors import AssetResolutionError


@dataclass(frozen=True)
class ResolvedAsset:
    ref: str
    root: Path
    revision: str | None = None


@dataclass(frozen=True)
class AssetUpdateResult:
    ref: str
    root: Path | None
    remote: bool
    before: str | None = None
    after: str | None = None
    updated: bool = False
    action: str = "unchanged"
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "root": str(self.root) if self.root is not None else None,
            "remote": self.remote,
            "before": self.before,
            "after": self.after,
            "updated": self.updated,
            "action": self.action,
            "message": self.message,
        }


def asset_cache_root() -> Path:
    linkar_home = os.environ.get("LINKAR_HOME")
    if linkar_home:
        return Path(linkar_home).expanduser().resolve() / "assets"
    return Path.home() / ".linkar" / "assets"


def is_remote_asset_ref(ref: str) -> bool:
    return ref.startswith("github:") or ref.startswith("git+")


def parse_remote_ref(ref: str) -> tuple[str, str | None]:
    if ref.startswith("git+"):
        raw = ref.split("git+", 1)[1]
        if raw.startswith(("http://", "https://", "ssh://", "file://")):
            base, sep, revision = ref.rpartition("@")
            if sep and base:
                return base, revision
            return ref, None
        marker = ".git@"
        if marker in ref:
            base, revision = ref.rsplit(marker, 1)
            return f"{base}.git", revision
        return ref, None

    base, sep, revision = ref.rpartition("@")
    if sep and base:
        return base, revision
    return ref, None


def github_clone_url(ref: str) -> str:
    _, repo = ref.split("github:", 1)
    return f"https://github.com/{repo}.git"


def git_clone_url(ref: str) -> str:
    return ref.split("git+", 1)[1]


def asset_cache_dir(ref: str) -> Path:
    digest = hashlib.sha256(ref.encode("utf-8")).hexdigest()[:16]
    return asset_cache_root() / digest


def run_git(args: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise AssetResolutionError(message)
    return completed.stdout.strip()


def try_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )


def current_revision(root: Path) -> str | None:
    return run_git(["rev-parse", "HEAD"], cwd=root)


def current_branch(root: Path) -> str | None:
    completed = try_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=root)
    if completed.returncode != 0:
        return None
    branch = completed.stdout.strip()
    return branch or None


def remote_default_branch(root: Path) -> str | None:
    completed = try_git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], cwd=root)
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    if value.startswith("origin/"):
        return value.split("/", 1)[1]
    return value or None


def ref_exists(root: Path, ref: str) -> bool:
    completed = try_git(["rev-parse", "--verify", "--quiet", ref], cwd=root)
    return completed.returncode == 0


def checkout_update_target(root: Path, requested_revision: str | None) -> str | None:
    if requested_revision:
        remote_branch = f"origin/{requested_revision}"
        if ref_exists(root, remote_branch):
            if not ref_exists(root, f"refs/heads/{requested_revision}"):
                run_git(["checkout", "-B", requested_revision, "--track", remote_branch], cwd=root)
            else:
                run_git(["checkout", requested_revision], cwd=root)
            return requested_revision
        run_git(["checkout", requested_revision], cwd=root)
        return current_branch(root)

    branch = current_branch(root)
    if branch:
        return branch
    default_branch = remote_default_branch(root)
    if default_branch:
        run_git(["checkout", default_branch], cwd=root)
        return default_branch
    return None


def ensure_remote_asset(ref: str) -> ResolvedAsset:
    base_ref, requested_revision = parse_remote_ref(ref)
    clone_url = github_clone_url(base_ref) if base_ref.startswith("github:") else git_clone_url(base_ref)
    cache_dir = asset_cache_dir(ref)
    if not cache_dir.exists():
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        run_git(["clone", clone_url, str(cache_dir)])
        if requested_revision:
            run_git(["checkout", requested_revision], cwd=cache_dir)
    revision = current_revision(cache_dir)
    return ResolvedAsset(ref=ref, root=cache_dir, revision=revision)


def resolve_asset_ref_at_revision(ref: str, revision: str | None) -> ResolvedAsset:
    if revision is None or not is_remote_asset_ref(ref):
        return resolve_asset_ref(ref)
    base_ref, _ = parse_remote_ref(ref)
    locked_ref = f"{base_ref}@{revision}"
    asset = resolve_asset_ref(locked_ref)
    return ResolvedAsset(ref=ref, root=asset.root, revision=asset.revision)


def update_remote_asset(ref: str) -> AssetUpdateResult:
    if not is_remote_asset_ref(ref):
        asset = resolve_asset_ref(ref)
        return AssetUpdateResult(
            ref=asset.ref,
            root=asset.root,
            remote=False,
            before=asset.revision,
            after=asset.revision,
            action="local",
            message="Local packs are updated outside Linkar.",
        )

    _, requested_revision = parse_remote_ref(ref)
    cache_dir = asset_cache_dir(ref)
    if not cache_dir.exists():
        asset = ensure_remote_asset(ref)
        return AssetUpdateResult(
            ref=asset.ref,
            root=asset.root,
            remote=True,
            before=None,
            after=asset.revision,
            updated=True,
            action="cloned",
            message="Remote pack was cloned into the Linkar asset cache.",
        )

    before = current_revision(cache_dir)
    run_git(["fetch", "--tags", "origin"], cwd=cache_dir)
    branch = checkout_update_target(cache_dir, requested_revision)
    if branch:
        run_git(["pull", "--ff-only", "origin", branch], cwd=cache_dir)
    after = current_revision(cache_dir)
    updated = before != after
    return AssetUpdateResult(
        ref=ref,
        root=cache_dir,
        remote=True,
        before=before,
        after=after,
        updated=updated,
        action="updated" if updated else "unchanged",
        message=None if updated else "Remote pack cache was already current.",
    )


def resolve_asset_ref(ref: str | Path) -> ResolvedAsset:
    if isinstance(ref, Path):
        root = ref.expanduser().resolve()
        if not root.exists():
            raise AssetResolutionError(f"Asset not found: {root}")
        return ResolvedAsset(ref=str(root), root=root)

    if is_remote_asset_ref(ref):
        return ensure_remote_asset(ref)

    path = Path(ref).expanduser()
    if path.exists():
        root = path.resolve()
        return ResolvedAsset(ref=str(root), root=root)

    raise AssetResolutionError(f"Asset not found: {path.resolve()}")


def resolve_asset_refs(refs: str | Path | list[str | Path] | None) -> list[ResolvedAsset]:
    if refs is None:
        return []
    if isinstance(refs, (str, Path)):
        raw_refs: list[str | Path] = [refs]
    else:
        raw_refs = list(refs)
    return [resolve_asset_ref(ref) for ref in raw_refs]
