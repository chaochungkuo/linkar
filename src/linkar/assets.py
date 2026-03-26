from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedAsset:
    ref: str
    root: Path
    revision: str | None = None


def asset_cache_root() -> Path:
    linkar_home = os.environ.get("LINKAR_HOME")
    if linkar_home:
        return Path(linkar_home).expanduser().resolve() / "assets"
    return Path.home() / ".linkar" / "assets"


def is_remote_asset_ref(ref: str) -> bool:
    return ref.startswith("github:") or ref.startswith("git+")


def parse_remote_ref(ref: str) -> tuple[str, str | None]:
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
        raise RuntimeError(message)
    return completed.stdout.strip()


def current_revision(root: Path) -> str | None:
    return run_git(["rev-parse", "HEAD"], cwd=root)


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


def resolve_asset_ref(ref: str | Path) -> ResolvedAsset:
    if isinstance(ref, Path):
        root = ref.expanduser().resolve()
        return ResolvedAsset(ref=str(root), root=root)

    if is_remote_asset_ref(ref):
        return ensure_remote_asset(ref)

    path = Path(ref).expanduser()
    if path.exists():
        root = path.resolve()
        return ResolvedAsset(ref=str(root), root=root)

    root = path.resolve()
    return ResolvedAsset(ref=str(root), root=root)


def resolve_asset_refs(refs: str | Path | list[str | Path] | None) -> list[ResolvedAsset]:
    if refs is None:
        return []
    if isinstance(refs, (str, Path)):
        raw_refs: list[str | Path] = [refs]
    else:
        raw_refs = list(refs)
    return [resolve_asset_ref(ref) for ref in raw_refs]
