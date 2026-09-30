from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from linkar.errors import ProjectValidationError
from linkar.runtime.config import (
    add_global_pack,
    clear_global_author,
    get_active_global_pack_entry,
    get_global_author,
    global_config_path,
    global_pack_entries,
    list_global_packs,
    load_global_config,
    remove_global_pack,
    set_active_global_pack,
    set_global_author,
    update_global_pack,
)


def write_config(home: Path, data: object) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"packs": {}}, "packs.*must be a list"),
        ({"packs": [], "active_pack": 3}, "active_pack.*must be a string"),
        ({"packs": [], "author": "bad"}, "author.*must be a mapping"),
        ({"packs": [], "author": {"email": 3}}, "author.email.*must be a string"),
    ],
)
def test_load_global_config_rejects_invalid_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    data: object,
    message: str,
) -> None:
    home = tmp_path / "linkar-home"
    monkeypatch.setenv("LINKAR_HOME", str(home))
    write_config(home, data)

    with pytest.raises(ProjectValidationError, match=message):
        load_global_config()


def test_global_author_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "linkar-home"
    monkeypatch.setenv("LINKAR_HOME", str(home))

    assert global_config_path() == home.resolve() / "config.yaml"
    assert get_global_author() is None
    with pytest.raises(ProjectValidationError, match="at least one author field"):
        set_global_author()

    assert set_global_author(name="Ada") == {"name": "Ada"}
    assert set_global_author(email="ada@example.org", organization="Lab") == {
        "name": "Ada",
        "email": "ada@example.org",
        "organization": "Lab",
    }
    assert get_global_author() == {
        "name": "Ada",
        "email": "ada@example.org",
        "organization": "Lab",
    }

    clear_global_author()
    assert get_global_author() is None


def test_global_pack_lifecycle_and_active_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINKAR_HOME", str(tmp_path / "linkar-home"))
    pack_one = tmp_path / "pack-one"
    pack_two = tmp_path / "pack-two"
    pack_one.mkdir()
    pack_two.mkdir()

    first = add_global_pack(str(pack_one), pack_id="one")
    second = add_global_pack(str(pack_two), pack_id="two", activate=True)
    assert first["active"] is True
    assert second["active"] is True
    assert get_active_global_pack_entry().id == "two"
    assert [entry["id"] for entry in list_global_packs()] == ["one", "two"]

    with pytest.raises(ProjectValidationError, match="Pack id already exists"):
        add_global_pack(str(pack_one), pack_id="one")
    with pytest.raises(ProjectValidationError, match="Pack already exists"):
        add_global_pack(str(pack_two), pack_id="duplicate-ref")

    assert set_active_global_pack("one")["active"] is True
    removed = remove_global_pack("one")
    assert removed["id"] == "one"
    assert get_active_global_pack_entry().id == "two"

    local_update = update_global_pack("two")
    assert local_update[0]["action"] == "local"
    remove_global_pack("two")
    assert get_active_global_pack_entry() is None


def test_global_pack_entries_accept_legacy_strings_and_reject_bad_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "linkar-home"
    pack = tmp_path / "legacy-pack"
    pack.mkdir()
    monkeypatch.setenv("LINKAR_HOME", str(home))

    write_config(home, {"packs": [str(pack)]})
    entries = global_pack_entries()
    assert len(entries) == 1
    assert entries[0].asset.root == pack.resolve()

    for bad_entry, message in [
        (3, "entries must be strings or mappings"),
        ({"id": "missing-ref"}, "field 'ref' is required"),
        ({"id": 3, "ref": str(pack)}, "field 'id' must be a string"),
    ]:
        write_config(home, {"packs": [bad_entry]})
        with pytest.raises(ProjectValidationError, match=message):
            global_pack_entries()


def test_global_pack_commands_report_missing_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINKAR_HOME", str(tmp_path / "linkar-home"))

    with pytest.raises(ProjectValidationError, match="No active global pack configured"):
        update_global_pack()
    with pytest.raises(ProjectValidationError, match="No global packs configured"):
        update_global_pack(all_packs=True)
    with pytest.raises(ProjectValidationError, match="Pack not found"):
        set_active_global_pack("missing")
    with pytest.raises(ProjectValidationError, match="Pack not found"):
        remove_global_pack("missing")
