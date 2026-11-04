"""Export public, versioned content metadata for the static course project site."""

import argparse
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def export_data(root: Path, ref: str) -> dict:
    """Read metadata and linked files from one immutable Git tree."""
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", ref + "^{commit}"],
        cwd=root,
        text=True,
    ).strip()
    config = "companion/companion/config"

    def read_yaml(path):
        return yaml.safe_load(
            subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=root).decode("utf-8")
        )

    paths = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", revision, "--", config], cwd=root
        )
        .decode("utf-8")
        .split("\0")
    )
    manifest = read_yaml(f"{config}/content_manifest.yaml")
    cards = []
    for path in sorted(
        p for p in paths if p.startswith(f"{config}/cards/") and p.endswith(".yaml")
    ):
        card = read_yaml(path)
        if card["status"] == "enabled":
            cards.append(
                {
                    "id": card["id"],
                    "name": card["name"],
                    "targets": card["targets"],
                    "protocol": card["protocol"],
                    "steps": card["talker"]["steps"],
                    "examples": card["talker"]["examples"],
                    "not_when": card["reasoner"]["not_when"],
                    "path": path,
                }
            )
    exercises = []
    for path in sorted(
        p for p in paths if p.startswith(f"{config}/exercises/") and p.endswith(".yaml")
    ):
        item = read_yaml(path)
        if item["status"] == "enabled":
            exercises.append({"id": item["id"], "name": item["name"], "protocol": item["protocol"]})
    return {
        "revision": revision,
        "catalog_version": manifest["version"],
        "cards": cards,
        "exercises": exercises,
        "sources": manifest["sources"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    data = export_data(ROOT, args.revision)
    output = ROOT / "docs/assets/project-data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Exported {len(data['cards'])} strategies / {len(data['exercises'])} exercises at {data['revision']}"
    )


if __name__ == "__main__":
    main()
