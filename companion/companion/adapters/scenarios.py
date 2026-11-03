"""Replay user-authored YAML scenarios through the same public API as devices."""

import time
import uuid
from pathlib import Path

import yaml

from companion.core.api import CompanionCore
from companion.core.models import Followup, MemoryUpdate, SessionState, TurnSignals
from companion.llm.fake import FakeLLM

from .output import RecordingOutputPort


def replay(core: CompanionCore, path: Path, user_key: str = "scenario") -> dict:
    scenario = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict) or not isinstance(scenario.get("steps"), list):
        raise TypeError("Scenario must contain steps")
    fixture = scenario.get("fixture", {})
    if fixture and not isinstance(core.llm, FakeLLM):
        raise ValueError("Scenario fixtures require --fake")
    if "pressure" in fixture:
        core.llm.pressure = fixture["pressure"]
    if "exercise" in fixture:
        core.llm.exercise_id = fixture["exercise"]
    session_id = uuid.uuid4().hex
    output = RecordingOutputPort(core.on_playback_event, scenario.get("auto_complete", True))
    core.bind_output(session_id, user_key, output)
    if fixture.get("followup"):
        old = SessionState(session_id=uuid.uuid4().hex, user_key=user_key, lifecycle="closed")
        core.store.create_session(old)
        source = core.store.add_input(old, "fixture", fixture["followup"], "user", TurnSignals())
        with core.store.transaction() as db:
            core.store._write_memory(
                db,
                user_key,
                MemoryUpdate(
                    followups=(
                        Followup(
                            content=fixture["followup"],
                            due_date=core.today(),
                            source_turn_ids=(source,),
                        ),
                    )
                ),
            )
        core.store.mark_onboarding(user_key)
    if fixture.get("elapsed_s"):
        core.sessions[session_id].state.started_mono = time.monotonic() - fixture["elapsed_s"]
    results = []
    for index, step in enumerate(scenario["steps"]):
        if step.get("wait") and not core.wait_idle():
            raise TimeoutError("Scenario background work timed out")
        if "user" in step or "kind" in step:
            turn_id = core.on_input(
                session_id,
                str(index),
                step.get("user", ""),
                TurnSignals.model_validate(step.get("signals", {})),
                step.get("kind", "user"),
            )
            for event in core.respond(session_id, turn_id):
                core.dispatch(event)
        if "playback" in step:
            output.acknowledge(output.events[step.get("output_index", -1)], step["playback"])
        if step.get("interrupt"):
            core.on_interrupt(session_id, core.sessions[session_id].state.generation, "scenario")
        if step.get("end"):
            core.on_session_end(session_id, "scenario")
        if step.get("reconnect"):
            session_id = uuid.uuid4().hex
            core.bind_output(session_id, user_key, output)
        row = core.store.query(
            "SELECT state,lifecycle,summary FROM sessions WHERE session_id=?", (session_id,)
        )[0]
        state = SessionState.model_validate_json(row["state"])
        actual = {
            "stage": state.stage.value,
            "mode": state.mode,
            "card": state.card_in_use,
            "offer": state.pending_offer.kind if state.pending_offer else None,
            "offer_status": state.pending_offer.status if state.pending_offer else None,
            "onboarding": core.store.onboarding_done(user_key),
            "rest_reminded": state.rest_reminded,
            "lifecycle": row["lifecycle"],
            "has_summary": bool(row["summary"]),
            "last_type": output.events[-1].type if output.events else None,
            "last_purpose": output.events[-1].purpose if output.events else None,
            "followups_asked": len(
                core.store.query(
                    "SELECT id FROM followups WHERE user_key=? AND status='asked'", (user_key,)
                )
            ),
        }
        for key, expected in step.get("expect", {}).items():
            if actual[key] != expected:
                raise AssertionError(
                    f"Step {index}: {key}: expected {expected!r}, got {actual[key]!r}"
                )
        results.append(actual)
    texts = [event.text for event in output.events]
    for phrase in scenario.get("forbid", []):
        if any(phrase in text for text in texts):
            raise AssertionError(f"Forbidden phrase: {phrase}")
    core.on_session_end(session_id, "scenario_complete")
    if not core.wait_idle():
        raise TimeoutError("Scenario finalization timed out")
    return {"session_id": session_id, "steps": results, "outputs": texts, "passed": True}
