"""Rebuild the six-point patch from the pinned local checkout and provider sources."""

import difflib
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repository = root / "vendor/xiaozhi-esp32-server"
pin = "92337881a7b6553614b47e137a774d02bf40512f"
parts = []
for path in (
    "core/handle/abortHandle.py",
    "core/handle/receiveAudioHandle.py",
    "core/handle/textHandler/listenMessageHandler.py",
    "core/providers/asr/utils.py",
):
    relative = "main/xiaozhi-server/" + path
    original = subprocess.check_output(["git", "show", f"{pin}:{relative}"], cwd=repository).decode(
        "utf-8"
    )
    proposed = repository / relative
    parts.extend(
        difflib.unified_diff(
            original.splitlines(True),
            proposed.read_text(encoding="utf-8").splitlines(True),
            fromfile="a/" + relative,
            tofile="b/" + relative,
        )
    )
for source in sorted((root / "xiaozhi_patch/files").rglob("*.py")):
    relative = "main/xiaozhi-server/" + source.relative_to(root / "xiaozhi_patch/files").as_posix()
    parts.extend(
        difflib.unified_diff(
            [],
            source.read_text(encoding="utf-8").splitlines(True),
            fromfile="/dev/null",
            tofile="b/" + relative,
        )
    )
with (root / "xiaozhi_patch/companion.patch").open("w", encoding="utf-8", newline="\n") as output:
    output.writelines(parts)
