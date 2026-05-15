from __future__ import annotations

from linkar.assets import parse_remote_ref


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
