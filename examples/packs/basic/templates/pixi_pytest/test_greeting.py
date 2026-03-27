from __future__ import annotations

import os

from greeting import build_greeting


def test_greeting_uses_name_from_environment() -> None:
    name = os.environ["NAME"]
    assert build_greeting(name) == f"Hello from pytest, {name}"
