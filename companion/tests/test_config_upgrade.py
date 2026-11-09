import json
from pathlib import Path

import pytest
import yaml
from companion.core.config import Config
from companion.tools.upgrade_config import BASELINE, merge_settings, upgrade


def test_v2_config_upgrade_preserves_customization_and_is_idempotent(tmp_path):
    directory = tmp_path / "deployed"
    baseline = Path(__file__).parents[1] / "companion/tools/resources/config-v2-baseline.json"
    files = json.loads(baseline.read_text(encoding="utf-8"))["files"]
    for name, value in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    settings = yaml.safe_load((directory / "settings.yaml").read_text(encoding="utf-8"))
    settings["storage"]["db_path"] = "data/custom.db"
    settings["llm"]["talker_model"] = "custom-model"
    (directory / "settings.yaml").write_text(yaml.safe_dump(settings), encoding="utf-8")
    prompt = directory / "prompts/talker.j2"
    prompt.write_text(prompt.read_text(encoding="utf-8") + "\n# custom", encoding="utf-8")
    result = upgrade(directory)
    loaded = Config(directory)
    assert len(loaded.cards) == 6 and loaded.exercises["bedtime"].protocol
    assert loaded.settings.storage.db_path == "data/custom.db"
    assert loaded.settings.llm.talker_model == "custom-model"
    assert prompt.read_text(encoding="utf-8").endswith("# custom")
    assert Path(result["backup"]).is_dir()
    assert (directory / BASELINE).is_file()
    repeated = upgrade(directory)
    assert repeated["changed"] == [] and repeated["backup"] is None
    assert "prompts/talker.j2" in repeated["customized_preserved"]


def test_invalid_custom_content_does_not_partially_upgrade(tmp_path):
    directory = tmp_path / "deployed"
    upgrade(directory)
    card = directory / "cards/S16.yaml"
    data = yaml.safe_load(card.read_text(encoding="utf-8"))
    data["name"] = "changed without review"
    card.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="stale"):
        upgrade(directory)
    assert before == {
        p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }


def test_settings_merge_adopts_new_defaults_only_for_unchanged_fields():
    assert merge_settings(
        {"a": 1, "b": {"x": 1}}, {"a": 7, "b": {"x": 1}}, {"a": 2, "b": {"x": 3, "y": 4}}
    ) == {"a": 7, "b": {"x": 3, "y": 4}}


def test_mode_override_preserves_the_configured_timezone(tmp_path):
    directory = tmp_path / "deployed"
    upgrade(directory)
    path = directory / "settings.yaml"
    settings = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings["runtime"]["timezone"] = "Pacific/Auckland"
    path.write_text(yaml.safe_dump(settings), encoding="utf-8")
    assert Config(directory, mode="development").settings.runtime.timezone == "Pacific/Auckland"


@pytest.mark.parametrize("location", ["same", "parent", "child"])
def test_upgrade_rejects_overlapping_source_and_deployment(tmp_path, location):
    source = tmp_path / "source"
    source.mkdir()
    destination = {
        "same": source,
        "parent": tmp_path,
        "child": source / "deployed",
    }[location]
    with pytest.raises(ValueError, match="separate deployment"):
        upgrade(destination, source)
    assert not list(source.iterdir())
