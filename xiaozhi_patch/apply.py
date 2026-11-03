"""Check or apply the reviewed integration against the exact upstream commit."""

import argparse
import subprocess
from pathlib import Path

PIN = "92337881a7b6553614b47e137a774d02bf40512f"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply six core hooks plus authenticated access/log redaction",
    )
    args = parser.parse_args()
    root = args.repository.resolve(strict=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if revision != PIN:
        raise SystemExit(f"Expected upstream {PIN}, found {revision}")
    for name in ("companion.patch", "access.patch"):
        patch = Path(__file__).with_name(name).resolve()
        applied = subprocess.run(
            ["git", "apply", "--reverse", "--check", str(patch)],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if applied.returncode == 0:
            print(f"Already applied: {name}")
            continue
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=root, check=True)
        if args.apply:
            subprocess.run(["git", "apply", str(patch)], cwd=root, check=True)
            print(f"Applied: {name}")
        else:
            print(f"Patch applies cleanly: {name}; no files changed.")


if __name__ == "__main__":
    main()
