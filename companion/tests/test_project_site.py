import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def builder():
    path = Path(__file__).parents[2] / "scripts/build_project_site.py"
    spec = importlib.util.spec_from_file_location("project_site_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_uses_selected_commit_even_with_dirty_worktree(tmp_path, builder):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path).decode().strip()

    def write(name, value):
        path = tmp_path / "companion/companion/config" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")

    def commit():
        git("add", ".")
        git(
            "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "test"
        )
        return git("rev-parse", "HEAD")

    git("init", "-q")
    write("content_manifest.yaml", {"version": "old", "sources": [{"id": "old-source"}]})
    card = {
        "id": "first",
        "name": "原策略",
        "status": "enabled",
        "targets": {},
        "protocol": {"version": "old"},
        "talker": {"steps": ["原步骤"], "examples": []},
        "reasoner": {"not_when": []},
    }
    write("cards/first.yaml", card)
    write(
        "exercises/rest.yaml",
        {"id": "rest", "name": "原练习", "status": "enabled", "protocol": {"version": "old"}},
    )
    old = commit()
    write("content_manifest.yaml", {"version": "new", "sources": [{"id": "new-source"}]})
    write("cards/first.yaml", {**card, "name": "新策略"})
    write("cards/second.yaml", {**card, "id": "second"})
    write(
        "exercises/rest.yaml",
        {"id": "rest", "name": "新练习", "status": "enabled", "protocol": {"version": "new"}},
    )
    latest = commit()
    write("cards/first.yaml", {**card, "name": "未提交修改"})
    write("cards/third.yaml", {**card, "id": "third"})
    write("content_manifest.yaml", {"version": "dirty", "sources": []})
    previous = builder.export_data(tmp_path, old)
    assert previous["revision"] == old
    assert previous["catalog_version"] == "old"
    assert previous["sources"] == [{"id": "old-source"}]
    assert [c["name"] for c in previous["cards"]] == ["原策略"]
    assert previous["exercises"][0]["name"] == "原练习"
    current = builder.export_data(tmp_path, "HEAD")
    assert current["revision"] == latest
    assert current["catalog_version"] == "new"
    assert [c["id"] for c in current["cards"]] == ["first", "second"]
    assert current["cards"][0]["name"] == "新策略"
    assert current["exercises"][0]["protocol"]["version"] == "new"
    for data in (previous, current):
        for entry in data["cards"]:
            assert (
                yaml.safe_load(git("show", f"{data['revision']}:{entry['path']}"))["name"]
                == entry["name"]
            )


def test_export_failure_preserves_existing_site_data(tmp_path, builder, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    output = tmp_path / "docs/assets/project-data.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps({"keep": "previous deployment"}), encoding="utf-8")
    original = output.read_bytes()
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_project_site.py", "--revision", "missing-ref"])
    with pytest.raises(subprocess.CalledProcessError):
        builder.main()
    assert output.read_bytes() == original
