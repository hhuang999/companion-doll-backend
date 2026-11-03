"""Export public, versioned content metadata for the static course project site."""

import argparse
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "rev-parse", args.revision], cwd=ROOT, text=True
    ).strip()
    config = ROOT / "companion/companion/config"
    manifest = yaml.safe_load((config / "content_manifest.yaml").read_text(encoding="utf-8"))
    cards = []
    for path in sorted((config / "cards").glob("*.yaml")):
        card = yaml.safe_load(path.read_text(encoding="utf-8"))
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
                    "path": path.relative_to(ROOT).as_posix(),
                }
            )
    exercises = []
    for path in sorted((config / "exercises").glob("*.yaml")):
        item = yaml.safe_load(path.read_text(encoding="utf-8"))
        if item["status"] == "enabled":
            exercises.append({"id": item["id"], "name": item["name"], "protocol": item["protocol"]})
    output = ROOT / "docs/assets/project-data.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "revision": revision,
                "catalog_version": manifest["version"],
                "cards": cards,
                "exercises": exercises,
                "sources": manifest["sources"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Exported {len(cards)} strategies / {len(exercises)} exercises at {revision}")


if __name__ == "__main__":
    main()
