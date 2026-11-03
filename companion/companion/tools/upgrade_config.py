"""Upgrade deployment configuration with three-way defaults and a restorable backup."""

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from companion.core.config import Config

BASELINE = ".companion-config-baseline.json"


def merge_settings(old, current, new):
    if current == old:
        return new
    if all(isinstance(value, dict) for value in (old, current, new)):
        result = dict(current)
        for key, value in new.items():
            if key not in current:
                result[key] = value
            elif key in old:
                result[key] = merge_settings(old[key], current[key], value)
        return result
    return current


def upgrade(directory: Path, source: Path | None = None):
    directory = directory.resolve()
    source = (source or Path(__file__).parents[1] / "config").resolve()
    if directory == source or source.is_relative_to(directory):
        raise ValueError("Use a separate deployment directory, not the packaged source")
    previous = directory / BASELINE
    if not previous.is_file():
        previous = Path(__file__).parent / "resources/config-v2-baseline.json"
    baseline = json.loads(previous.read_text(encoding="utf-8"))["files"]
    resources = {
        path.relative_to(source).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(source.rglob("*"))
        if path.is_file() and path.suffix in (".yaml", ".j2")
    }
    changed, preserved = {}, []
    for name, new in resources.items():
        path = directory / name
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        old = baseline.get(name)
        if current is None or current == old or current == new:
            result = new
        elif name == "settings.yaml":
            result = yaml.safe_dump(
                merge_settings(
                    yaml.safe_load(old or "{}"), yaml.safe_load(current), yaml.safe_load(new)
                ),
                allow_unicode=True,
                sort_keys=False,
            )
            preserved.append(name)
        elif name.startswith("exercises/") and old:
            deployed, original, latest = (yaml.safe_load(value) for value in (current, old, new))
            stripped = {
                **deployed,
                "lines": [
                    {
                        key: value
                        for key, value in line.items()
                        if key not in ("audio_path", "audio_duration_s")
                    }
                    for line in deployed["lines"]
                ],
            }
            if stripped == original:
                for line in latest["lines"]:
                    measured = next(
                        (
                            item
                            for item in deployed["lines"]
                            if item["text"] == line["text"]
                            and item.get("pause_s", 0) == line.get("pause_s", 0)
                        ),
                        None,
                    )
                    if measured:
                        line.update(
                            {
                                key: measured[key]
                                for key in ("audio_path", "audio_duration_s")
                                if key in measured
                            }
                        )
                result = yaml.safe_dump(latest, allow_unicode=True, sort_keys=False)
            else:
                result = current
                preserved.append(name)
        else:
            result = current
            preserved.append(name)
        if result != current:
            changed[name] = result
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Validate the proposed complete copy before touching the deployment.
    with tempfile.TemporaryDirectory(prefix="companion-config-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        if directory.exists():
            shutil.copytree(directory, staging, dirs_exist_ok=True)
        for name, value in changed.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
        Config(staging, mode="development")
        backup = None
        if changed and directory.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = directory.parent / f"{directory.name}.backup-{stamp}"
            shutil.copytree(directory, backup)
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in changed.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
        (directory / BASELINE).write_text(
            json.dumps({"files": resources}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {
        "changed": sorted(changed),
        "customized_preserved": sorted(preserved),
        "backup": str(backup) if backup else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(upgrade(args.directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
