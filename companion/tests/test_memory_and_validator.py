import sqlite3
from datetime import date

import pytest
from companion.core.models import (
    Assessment,
    CardEvidence,
    CardSelection,
    Followup,
    MemoryUpdate,
    ProfileUpdate,
    ReasonerOutput,
    ReasonerTask,
    SessionState,
    Snapshot,
    Stage,
    StageProposal,
    TurnSignals,
    TypedConfidence,
)
from companion.core.validator import Validator


def task():
    return ReasonerTask(
        session_id="s",
        user_key="u",
        kind="normal",
        trigger_reasons=("test",),
        source_turn_id=1,
        state_revision=1,
        topic_revision=0,
        base_snapshot_version=0,
        user_index=1,
    )


def test_validator_rejects_unsourced_memory_and_illegal_action(config):
    state = SessionState(session_id="s", user_key="u", stage=Stage.comfort)
    output = ReasonerOutput(
        stage_proposal=StageProposal(to="action", reason="test", source_turn_ids=(1,)),
        memory=MemoryUpdate(
            profile_updates=(ProfileUpdate(field="nickname", value="name", source_turn_ids=(999,)),)
        ),
    )
    validated, rejected = Validator(config).validate(output, state, {1}, date.today())
    assert validated.stage_proposal is None
    assert not validated.memory.profile_updates
    assert {r.rule for r in rejected} >= {"V2", "V6"}


def test_empty_target_side_does_not_match_everything(config):
    # This rule is independent of S16's expanded course target set.
    config.cards["S16"].targets.pressure_types = []
    output = ReasonerOutput(
        assessment=Assessment(pressure_types=(TypedConfidence(type="academic", confidence=1),)),
        cards=CardSelection(
            allowed=("S16",),
            preferred="S16",
            evidence=(
                CardEvidence(
                    card_id="S16", when_met=True, exclusions_present=False, source_turn_ids=(1,)
                ),
            ),
        ),
    )
    validated, rejected = Validator(config).validate(
        output, SessionState(session_id="s", user_key="u"), {1}, date.today()
    )
    assert not validated.cards.allowed
    assert "V3" in {r.rule for r in rejected}


def test_crisis_rejects_strategy_but_keeps_sourced_memory(config):
    state = SessionState(session_id="s", user_key="u", mode="crisis", stage=Stage.explore)
    output = ReasonerOutput(
        stage_proposal=StageProposal(to="comfort", reason="test", source_turn_ids=(1,)),
        offer_exercise=True,
        memory=MemoryUpdate(
            profile_updates=(ProfileUpdate(field="nickname", value="name", source_turn_ids=(1,)),)
        ),
    )
    validated, rejected = Validator(config).validate(output, state, {1}, date.today())
    assert not validated.offer_exercise
    assert validated.stage_proposal is None
    assert validated.memory.profile_updates
    assert "V8" in {r.rule for r in rejected}


def test_invalid_dates_and_followup_count(config):
    followups = [
        Followup(
            content=str(i),
            due_date=date.today().isoformat(),
            importance=i + 1,
            source_turn_ids=(1,),
        )
        for i in range(3)
    ]
    followups.append(Followup(content="bad", due_date="not-a-date", source_turn_ids=(1,)))
    validated, rejected = Validator(config).validate(
        ReasonerOutput(memory=MemoryUpdate(followups=tuple(followups))),
        SessionState(session_id="s", user_key="u"),
        {1},
        date.today(),
    )
    assert [item.content for item in validated.memory.followups] == ["2", "1"]
    assert len([r for r in rejected if r.rule == "V7"]) == 2


def test_snapshot_and_memory_publish_is_atomic(store):
    state = SessionState(session_id="s", user_key="u")
    store.create_session(state)
    store.add_input(state, "1", "name", "user", TurnSignals())
    snapshot = Snapshot(session_id="s", user_key="u", version=1)
    store.publish(task(), snapshot, MemoryUpdate(), None, {}, [], 1)
    memory = MemoryUpdate(
        profile_updates=(
            ProfileUpdate(field="nickname", value="must-rollback", source_turn_ids=(1,)),
        )
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.publish(task(), snapshot, memory, None, {}, [], 1)
    assert not store.query("SELECT * FROM profile")
    assert len(store.query("SELECT * FROM snapshots")) == 1


def test_followup_reservation_asked_once_and_old_profile_cannot_overwrite(store):
    state = SessionState(session_id="s", user_key="u")
    store.create_session(state)
    first = store.add_input(state, "1", "old", "user", TurnSignals())
    second = store.add_input(state, "2", "new", "user", TurnSignals())
    today = date.today().isoformat()
    new = MemoryUpdate(
        profile_updates=(ProfileUpdate(field="nickname", value="new", source_turn_ids=(second,)),),
        followups=(Followup(content="exam", due_date=today, source_turn_ids=(second,)),),
    )
    store.publish(task(), None, new, None, {}, [], 1)
    old = MemoryUpdate(
        profile_updates=(ProfileUpdate(field="nickname", value="old", source_turn_ids=(first,)),)
    )
    store.publish(task(), None, old, None, {}, [], 1)
    assert store.query("SELECT value FROM profile")[0]["value"] == "new"
    reserved = store.reserve_followup("u", "s", today)
    assert reserved and not store.reserve_followup("u", "s", today)
    store.mark_followup_asked(reserved["id"], "s")
    assert not store.reserve_followup("u", "s", today)
