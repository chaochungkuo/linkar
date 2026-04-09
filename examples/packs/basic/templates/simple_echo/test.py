#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parent


def main() -> None:
    text = (TEMPLATE_DIR / "linkar_template.yaml").read_text(encoding="utf-8")
    assert "command:" in text
    assert "path: greeting.txt" in text
    assert 'printf \'Hello, %s\\n\' "${param:name}" > "${LINKAR_RESULTS_DIR}/greeting.txt"' in text
    print("simple_echo template test passed")


if __name__ == "__main__":
    main()
