"""Run reproducible offline checks from the project root."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
temporary = root / "artifacts/tmp"
temporary.mkdir(parents=True, exist_ok=True)
environment = dict(
    os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", TEMP=str(temporary), TMP=str(temporary)
)
targets = ["companion", "xiaozhi_patch", "scripts"]
subprocess.run(
    [sys.executable, "-m", "ruff", "check", "--config", "companion/pyproject.toml", *targets],
    cwd=root,
    check=True,
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "ruff",
        "format",
        "--check",
        "--config",
        "companion/pyproject.toml",
        *targets,
    ],
    cwd=root,
    check=True,
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "not online and not hardware",
        "--basetemp",
        str(root / "artifacts" / f"pytest-{uuid.uuid4().hex[:8]}"),
        *sys.argv[1:],
    ],
    cwd=root / "companion",
    env=environment,
    check=True,
)
