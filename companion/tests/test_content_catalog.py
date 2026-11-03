import json
import shutil
import wave
from collections import deque

import pytest
import yaml
from companion.adapters.output import RecordingOutputPort
from companion.cognition.models import SituationAssessment
from companion.content.admission import item_digest, package_digest
from companion.content.catalog import StrategyCatalog
from companion.content.models import StrategyProtocol
from companion.core.api import CompanionCore
from companion.core.config import Config
from companion.core.models import SessionState, TurnSignals
from companion.llm.fake import FakeLLM


def test_filter_before_ranking_and_user_state_isolation(config):
    config.cards = {"S16": config.cards["S16"]}
    catalog = StrategyCatalog(config)
    assessment = SituationAssessment(
        expressed_need="solve", pathway_signals=("rumination",), readiness="medium"
    )
    a, b = SessionState(session_id="a", user_key="a"), SessionState(session_id="b", user_key="b")
    a.cards_refused.add("S16")
    assert catalog.select(assessment, a, "反复想").selected_ids == ()
    assert catalog.select(assessment, b, "反复想").selected_ids == ("S16",)
    for changes, expected in [
        ({"expressed_need": "listen"}, "current_need_has_no_action"),
        ({"emotion_intensity": "high"}, "emotion_excluded"),
        ({"pathway_signals": (), "pressure_types": ("future",)}, "no_target_match"),
    ]:
        result = catalog.select(assessment.model_copy(update=changes), b, "反复想")
        assert not result.selected_ids
        assert expected in result.decisions[0].reasons


def test_protocol_context_exclusion_is_not_overridden_by_keywords(config):
    config.cards["S16"].protocol = StrategyProtocol(
        version="test",
        mechanism="test",
        evidence_ids=("E1",),
        adaptation="synthetic",
        minimum_information=("用户愿望",),
        prerequisites=("安全",),
        excluded_contexts=("unsafe_relationship",),
        burden="一步",
        permission="先问",
        stop="随时停",
        followup="用户提出才跟进",
        feedback_limits="不能证明效果",
        counterexample="不能强迫",
        keywords=("反复",),
    )
    result = StrategyCatalog(config).select(
        SituationAssessment(
            pathway_signals=("rumination",), support_constraints=("unsafe_relationship",)
        ),
        SessionState(session_id="s", user_key="u"),
        "反复反复",
    )
    assert not result.selected_ids
    assert "context_excluded" in result.decisions[0].reasons


def test_retrieval_reaches_planner_and_independent_critic_and_persists(config, store):
    fake = FakeLLM()
    core = CompanionCore(config, store, fake)
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)
    try:
        turn = core.on_input("s", "one", "我反复想这件事，怎么办", TurnSignals())
        for event in core.respond("s", turn):
            core.dispatch(event)
        assert core.wait_idle()
        requests = {r["role"]: r["payload"] for r in fake.requests}
        assert "cards" not in requests["brief"]
        assert requests["planner"]["cards"] == requests["critic"]["cards"]
        assert requests["critic"]["cards"][0]["id"] == "S16"
        plan = store.active_support_plan("s")
        assert "S16" in plan.strategy_selection.selected_ids
        job = json.loads(
            store.query("SELECT data FROM cognitive_jobs WHERE kind='deliberation'")[0]["data"]
        )
        assert next(d for d in job["strategy_selection"]["decisions"] if d["strategy_id"] == "S16")[
            "eligible"
        ]
    finally:
        core.close()


def test_model_cannot_propose_a_filtered_card(config, store):
    fake = FakeLLM(
        roles={
            "planner": deque(
                [
                    lambda p: {
                        "objective": "invite_action",
                        "understanding": "无依据的策略",
                        "evidence": p["analysis"]["facts"][0]["evidence"],
                        "candidate_actions": [
                            {
                                "action_id": "invented",
                                "when_met": True,
                                "exclusions_present": False,
                                "evidence": p["analysis"]["facts"][0]["evidence"],
                            }
                        ],
                    }
                ]
            )
        }
    )
    core = CompanionCore(config, store, fake)
    core.bind_output("s", "u", RecordingOutputPort(core.on_playback_event))
    try:
        core.on_input("s", "one", "反复想这件事，怎么办", TurnSignals())
        assert core.wait_idle()
        assert not store.active_support_plan("s")
        job = store.query("SELECT * FROM cognitive_jobs")[0]
        assert job["status"] == "rejected"
        assert "excluded by strategy retrieval" in job["error"]
        assert json.loads(job["data"])["strategy_selection"]
    finally:
        core.close()


def test_content_digests_follow_semantics_and_prompt_changes(config, tmp_path):
    directory = tmp_path / "config"
    shutil.copytree(config.directory, directory)
    copied = Config(directory)
    original = package_digest(copied)
    exercise = directory / "exercises/grounding.yaml"
    data = yaml.safe_load(exercise.read_text(encoding="utf-8"))
    before = item_digest(directory, "exercises/grounding.yaml")
    data["lines"][0]["audio_path"] = "local.wav"
    data["lines"][0]["audio_duration_s"] = 1.5
    exercise.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert item_digest(directory, "exercises/grounding.yaml") == before
    data["lines"][0]["pause_s"] += 1
    exercise.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert item_digest(directory, "exercises/grounding.yaml") != before
    assert package_digest(copied) != original
    prior = package_digest(copied)
    prompt = directory / "prompts/talker.j2"
    prompt.write_text(prompt.read_text(encoding="utf-8") + "\nChanged rule", encoding="utf-8")
    assert package_digest(copied) != prior


def test_enabled_content_never_uses_missing_review_default(config, tmp_path):
    directory = tmp_path / "config"
    shutil.copytree(config.directory, directory)
    card = directory / "cards/S16.yaml"
    data = yaml.safe_load(card.read_text(encoding="utf-8"))
    data["name"] = "changed without new review"
    card.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete/stale content review"):
        Config(directory)


@pytest.fixture
def synthetic_admitted_config(config, tmp_path):
    """Fabricated receipts exist only inside this isolated validation unit test."""
    directory = tmp_path / "admission"
    shutil.copytree(config.directory, directory)
    for path in (directory / "cards").glob("*.yaml"):
        if path.stem != "S16":
            path.unlink()
    with wave.open(str(directory / "unit.wav"), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 1600)
    paths = ["cards/S16.yaml", "crisis.yaml"]
    paths += [f"exercises/{identifier}.yaml" for identifier in config.exercises]
    for relative in paths:
        path = directory / relative
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["status"] = "enabled"
        if relative.startswith("cards/"):
            data["protocol"] = {
                "version": "unit",
                "mechanism": "unit",
                "evidence_ids": ["UNIT"],
                "adaptation": "synthetic fixture",
                "minimum_information": ["test"],
                "prerequisites": ["test"],
                "burden": "test",
                "permission": "test",
                "stop": "test",
                "followup": "test",
                "feedback_limits": "test",
                "counterexample": "test",
            }
        for line in data.get("lines", []):
            line.update(audio_path="unit.wav", audio_duration_s=0.1)
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    manifest = {
        "version": "unit-only",
        "scope": "course_synthetic_adult_roleplay",
        "sources": [
            {
                "id": "UNIT",
                "citation": "Synthetic test source",
                "url": "https://example.com",
                "read_scope": "fixture",
                "population": "none",
                "supports": "none",
                "limitations": "test only",
                "verification": "checked",
                "checked_on": "2026-11-04",
            }
        ],
        "reviews": [
            {
                "item": path,
                "sha256": item_digest(directory, path),
                "evidence_ids": ["UNIT"],
                "source_check": "passed",
                "automatic_review": "passed",
                "reviewer": "codex_automated",
                "reviewed_on": "2026-11-04",
                "rationale": "synthetic unit fixture, not actual approval",
            }
            for path in paths
        ],
    }
    target = directory / "content_manifest.yaml"
    target.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    manifest["acceptance"] = {
        "package_digest": package_digest(Config(directory)),
        "check_version": "unit",
        "deterministic": "passed",
        "live_replay": "passed",
        "scenario_ids": ["unit"],
        "evidence_path": "synthetic-unit-only",
        "items": [
            {
                "item": path,
                "deterministic_cases": ["unit"],
                "live_scenarios": ["unit"],
                "result": "passed",
                "covered_behaviors": [
                    "applicable",
                    "excluded",
                    "permission_refusal",
                    "exit",
                    "feedback",
                ],
            }
            for path in paths
        ],
    }
    target.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    return directory, manifest


def test_demo_admits_complete_course_package_without_seventeen_cards(synthetic_admitted_config):
    directory, _ = synthetic_admitted_config
    value = Config(directory, mode="demo")
    assert value.settings.runtime.mode == "demo"
    assert len(value.cards) == 1


@pytest.mark.parametrize("failure", ["source", "review", "live", "coverage", "stale", "audio"])
def test_demo_rejects_each_missing_or_stale_evidence(synthetic_admitted_config, failure):
    directory, manifest = synthetic_admitted_config
    if failure == "source":
        manifest["sources"][0]["verification"] = "pending"
    elif failure == "review":
        manifest["reviews"][0]["automatic_review"] = "failed"
    elif failure == "live":
        manifest["acceptance"]["live_replay"] = "pending"
    elif failure == "coverage":
        manifest["acceptance"]["items"][0]["covered_behaviors"].remove("feedback")
    elif failure == "stale":
        prompt = directory / "prompts/talker.j2"
        prompt.write_text(prompt.read_text(encoding="utf-8") + "\nnew", encoding="utf-8")
    else:
        with wave.open(str(directory / "unit.wav"), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 16000)
    (directory / "content_manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        Config(directory, mode="demo")
