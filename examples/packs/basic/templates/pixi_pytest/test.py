from __future__ import annotations

import os
from pathlib import Path
import subprocess

os.environ.setdefault("NAME", "Pytest")

subprocess.run(["./run.sh"], check=True)

report_path = Path("pytest-report.xml")
assert report_path.is_file()
report_text = report_path.read_text()
assert 'tests="1"' in report_text
assert 'failures="0"' in report_text

report_path.unlink()
print("pixi_pytest template test passed")
