"""Immediate explicit controls and attributable execution/user events."""

import json
import re
import uuid

from companion.memory.models import MemoryCandidate

from .base import EvidenceRef
from .models import EventPayload, InteractionEvent


class Interactions:
    def __init__(self, core, memory):
        self.core, self.store, self.memory = core, core.store, memory

    def record(
        self,
        state,
        event_type,
        origin,
        *,
        turn_id=None,
        output=None,
        payload=None,
        evidence=(),
        suffix="",
    ):
        support_plan_id = state.active_support_plan_id
        if output:
            policies = self.store.query(
                "SELECT data FROM turn_policies WHERE turn_id=?", (output.turn_id,)
            )
            if policies:
                support_plan_id = json.loads(policies[0]["data"]).get("effective_support_plan_id")
        payload = payload or EventPayload()
        if output and output.support:
            payload = payload.model_copy(update={"support": output.support})
        event = InteractionEvent(
            event_id=uuid.uuid4().hex,
            idempotency_key=f"{state.session_id}:{turn_id}:{output.output_id if output else ''}:{event_type}:{suffix}",
            user_key=state.user_key,
            session_id=state.session_id,
            turn_id=turn_id,
            output_id=output.output_id if output else None,
            offer_id=output.offer_id
            if output
            else state.pending_offer.offer_id
            if state.pending_offer
            else None,
            support_plan_id=support_plan_id,
            event_type=event_type,
            origin=origin,
            payload=payload,
            evidence=evidence,
        )
        if self.store.record_interaction(event):
            return event
        return InteractionEvent.model_validate_json(
            self.store.query(
                "SELECT data FROM interaction_events WHERE idempotency_key=?",
                (event.idempotency_key,),
            )[0]["data"]
        )

    def input(self, state, text, turn_id):
        triggers = []
        machine = self.core.machine
        evidence = (
            EvidenceRef(kind="user_turn", id=turn_id, claim="当前用户明确表达", quote=text[:300]),
        )
        boundary = self.memory.explicit_boundary(text, state, turn_id)
        correction = machine.matches("correct", text) or bool(
            re.search(r"你(?:记|说)错|(?:刚才|之前)(?:我)?说错了|更正|记错了|不是.*是", text)
        )
        refusal = machine.matches("refuse", text) or bool(re.search(r"别再.*建议|不要.*教我", text))
        negative = bool(re.search(r"(?:刚才|这个|这样|那个).*(?:没用|没帮助|不舒服|不喜欢)", text))
        positive = bool(re.search(r"有帮助|帮到我|挺好|好多了", text))
        if boundary:
            self.memory.commit((boundary,), state, turn_id)
            self.record(
                state,
                "boundary_requested",
                "user_explicit",
                turn_id=turn_id,
                evidence=evidence,
                payload=EventPayload(text=text[:500], target=boundary.target, scope=boundary.scope),
            )
            triggers.append("boundary")
        if correction:
            self.record(
                state,
                "user_correction",
                "user_explicit",
                turn_id=turn_id,
                evidence=evidence,
                payload=EventPayload(text=text[:500]),
            )
            triggers.append("correction")
            # Immediate protection of recalled facts. A later sourced correction creates a successor.
            with self.store.transaction() as db:
                for item in self.store.memory_items(state.user_key, db):
                    if item.kind in ("fact_preference", "episodic_event") and (
                        item.value in text or item.key in text or re.search(r"记错|说错|更正", text)
                    ):
                        self.store.set_memory_status(db, item, "invalidated")
                        db.execute(
                            "INSERT INTO memory_corrections VALUES (?,?,?,?) ON CONFLICT(user_key,kind,key) DO UPDATE SET source_turn_id=MAX(memory_corrections.source_turn_id,excluded.source_turn_id)",
                            (state.user_key, item.kind, item.key, turn_id),
                        )
                db.execute(
                    "UPDATE user_revisions SET memory_revision=memory_revision+1 WHERE user_key=?",
                    (state.user_key,),
                )
        if refusal:
            refused_card = state.card_in_use or (
                state.pending_offer.target_id if state.pending_offer else None
            )
            if refused_card in self.core.config.cards:
                state.cards_refused.add(refused_card)
            if refused_card in self.core.config.exercises:
                state.exercises_refused.add(refused_card)
            self.record(
                state,
                "support_refused",
                "user_explicit",
                turn_id=turn_id,
                evidence=evidence,
                payload=EventPayload(text=text[:500], action_id=refused_card, valence="negative"),
            )
            triggers.append("refusal")
        if positive or negative:
            outputs = self.store.query(
                "SELECT data FROM outputs WHERE session_id=? AND status IN ('started','completed') AND turn_id<? ORDER BY created_at DESC LIMIT 2",
                (state.session_id, turn_id),
            )
            explicit = bool(
                re.search(r"刚才.*(?:问|建议|练习)|这个(?:办法|练习)|这样(?:问|说)", text)
            )
            target = json.loads(outputs[0]["data"]) if explicit and outputs else None
            from companion.core.models import OutputEvent

            output = OutputEvent.model_validate(target) if target else None
            payload = EventPayload(
                text=text[:500],
                attribution="explicit" if output else "unattributed",
                valence="negative" if negative else "positive",
            )
            event = self.record(
                state,
                "explicit_feedback",
                "user_explicit",
                turn_id=turn_id,
                output=output,
                payload=payload,
                evidence=evidence,
            )
            if output:
                if negative and output.support:
                    if output.support.kind == "card":
                        state.cards_refused.add(output.support.identifier)
                    else:
                        state.exercises_refused.add(output.support.identifier)
                candidate = MemoryCandidate(
                    kind="support_experience",
                    key="feedback:" + output.output_id,
                    value=text[:500],
                    source_refs=(
                        *evidence,
                        EvidenceRef(
                            kind="interaction_event",
                            id=event.event_id,
                            claim="明确反馈与原输出关联",
                        ),
                    ),
                    scope="persistent",
                    mention_policy="only_when_raised",
                    support=output.support,
                    feedback_valence=payload.valence,
                )
                self.memory.commit((candidate,), state, turn_id)
                triggers.append("feedback")
        if self.repeated_failure(state):
            triggers.append("repeated_failure")
        nickname = re.search(
            r"(?:我叫|叫我|我的名字(?:是|叫))([\u4e00-\u9fffA-Za-z]{1,12})(?:[，。！!]|$)", text
        )
        if nickname:
            self.memory.commit(
                (
                    MemoryCandidate(
                        kind="fact_preference",
                        key="nickname",
                        value=nickname.group(1),
                        source_refs=evidence,
                        scope="persistent",
                        mention_policy="allowed",
                    ),
                ),
                state,
                turn_id,
            )
        control = (
            bool(triggers)
            or machine.matches("quiet", text)
            or machine.matches("change_topic", text)
        )
        if control:
            state.policy_revision += 1
            state.active_support_plan_id = None
            self.store.invalidate_plans(state.session_id)
            if boundary or correction or negative:
                state.pending_offer = None
                state.resume_script_id = None
                if state.stage.value in ("action", "permission"):
                    from companion.core.models import Stage

                    machine.move(state, Stage.explore)
        return tuple(triggers), control

    def repeated_failure(self, state):
        """Two explicit failures on the same attributable target in four user turns."""
        rows = self.store.query(
            "SELECT data FROM interaction_events WHERE session_id=? AND turn_id IN "
            "(SELECT id FROM turns WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 4) "
            "AND event_type IN ('support_refused','user_correction','explicit_feedback')",
            (state.session_id, state.session_id),
        )
        failures = {}
        for row in rows:
            event = json.loads(row["data"])
            if event["event_type"] == "explicit_feedback" and (
                event["payload"]["attribution"] != "explicit"
                or event["payload"]["valence"] != "negative"
            ):
                continue
            target = event["offer_id"] or event["support_plan_id"]
            if target:
                failures.setdefault(target, set()).add(event["turn_id"])
        return any(len(turns) >= 2 for turns in failures.values())

    def playback(self, state, output, event):
        self.record(
            state,
            "playback_" + event.status,
            "server_playback",
            turn_id=output.turn_id,
            output=output,
            payload=EventPayload(attribution="execution", detail=event.error),
        )
        if output.type == "exercise_plan" and event.status in ("completed", "cancelled"):
            self.record(
                state,
                "exercise_completed" if event.status == "completed" else "exercise_interrupted",
                "server_playback",
                turn_id=output.turn_id,
                output=output,
                payload=EventPayload(
                    attribution="execution",
                    detail="server estimate; no device ACK or benefit inference",
                ),
            )

    def cancelling(self, state, reason):
        from companion.core.models import OutputEvent

        for row in self.store.query(
            "SELECT data FROM outputs WHERE session_id=? AND status IN ('submitted','started')",
            (state.session_id,),
        ):
            output = OutputEvent.model_validate_json(row["data"])
            self.record(
                state,
                "playback_cancelled",
                "deterministic_rule",
                turn_id=output.turn_id,
                output=output,
                payload=EventPayload(attribution="execution", detail=reason),
            )
            if output.type == "exercise_plan":
                self.record(
                    state,
                    "exercise_interrupted",
                    "deterministic_rule",
                    turn_id=output.turn_id,
                    output=output,
                    payload=EventPayload(attribution="execution", detail=reason),
                )
