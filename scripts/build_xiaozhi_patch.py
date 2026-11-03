"""Rebuild the reviewable patch using previously downloaded pinned sources."""

import difflib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
review = root / "artifacts/xiaozhi-review"
parts = []
for original in sorted((review / "original").rglob("*.py")):
    relative = original.relative_to(review / "original").as_posix()
    proposed = review / "proposed" / relative
    parts.extend(
        difflib.unified_diff(
            original.read_text(encoding="utf-8").splitlines(True),
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
