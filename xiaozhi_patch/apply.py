"""Check or apply the reviewed integration against the exact upstream commit."""

import argparse
import subprocess
from pathlib import Path

PIN = "92337881a7b6553614b47e137a774d02bf40512f"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply all six integration points")
    args = parser.parse_args()
    root = args.repository.resolve(strict=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if revision != PIN:
        raise SystemExit(f"Expected upstream {PIN}, found {revision}")
    patch = Path(__file__).with_name("companion.patch").resolve()
    applied = subprocess.run(
        ["git", "apply", "--reverse", "--check", str(patch)],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if applied.returncode == 0:
        print("All six integration points are already applied.")
        return
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=root, check=True)
    if args.apply:
        subprocess.run(["git", "apply", str(patch)], cwd=root, check=True)
        print(
            "Applied Companion integration. Merge config.example.yaml and install companion next."
        )
    else:
        print("Patch applies cleanly; no files changed.")


if __name__ == "__main__":
    main()
