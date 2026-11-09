"""Session orchestration. Model and playback I/O never owns dialogue state."""

import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from companion.llm.client import LLMClient
from companion.store import Store

from .config import Config
from .exercise import ExercisePlayer
from .models import (
    InputKind,
    OutputEvent,
    PlaybackEvent,
    PlaybackPlan,
    PlaybackSegment,
    RiskResult,
    SessionState,
    Snapshot,
    Stage,
    TurnContext,
    TurnSignals,
)
from .risk import RiskDetector
from .state_machine import StateMachine
from .talker import Talker
from .validator import Validator

logger = logging.getLogger(__name__)
RANK = {"none": 0, "watch": 1, "high": 2}


class OutputPort(Protocol):
    def submit(self, event: OutputEvent) -> None: ...
    def cancel_before(self, session_id: str, generation: int) -> None: ...


@dataclass
class SessionRuntime:
    state: SessionState
    snapshot: Snapshot
    port: OutputPort | None
    lock: threading.RLock = field(default_factory=threading.RLock)
    contexts: dict[int, TurnContext] = field(default_factory=dict)
    cancels: dict[int, threading.Event] = field(default_factory=dict)
    risks: dict[int, RiskResult] = field(default_factory=dict)
    risk_futures: dict[int, Future] = field(default_factory=dict)
    metrics: dict[int, dict] = field(default_factory=dict)
    outputs: dict[str, OutputEvent] = field(default_factory=dict)
    crisis_sent: set[int] = field(default_factory=set)
    action_counted: set[int] = field(default_factory=set)
    responded: set[int] = field(default_factory=set)
    risk_deliveries: set[tuple[int, str, str, str]] = field(default_factory=set)
    closing_counted: set[int] = field(default_factory=set)
    persistence_failed: bool = False
    risk_reviews: set[int] = field(default_factory=set)


class CompanionCore:
    def __init__(
        self, config: Config, store: Store, llm: LLMClient, *, recover: bool = True
    ) -> None:
        self.config, self.store, self.llm = config, store, llm
        self.sessions: dict[str, SessionRuntime] = {}
        self.registry_lock = threading.RLock()
        self.closing = False
        self.purging: set[str] = set()
        from collections import defaultdict

        from companion.store.lease import WriterLease

        self.user_locks = defaultdict(threading.RLock)
        self.user_epochs = {}
        from companion.cognition.interaction import Interactions
        from companion.cognition.orchestrator import Cognition

        with ExitStack() as cleanup:
            self.writer_lease = WriterLease(store.path)
            cleanup.callback(self.writer_lease.close)
            self._notifications = (
                ThreadPoolExecutor(max_workers=1, thread_name_prefix="risk-notify")
                if config.settings.alert_webhook
                else None
            )
            if self._notifications:
                cleanup.callback(self._notifications.shutdown, wait=True)
            self.machine = StateMachine(config)
            self.talker = Talker(config, llm)
            self.validator = Validator(config)
            self.exercise = ExercisePlayer(config)
            self.risk = RiskDetector(config, llm)
            cleanup.callback(self.risk.close)
            self.cognition = Cognition(self)
            cleanup.callback(self.cognition.close)
            self.reasoner = self.cognition.scheduler
            self.interactions = Interactions(self, self.cognition.memory)
            if recover:
                self.recover()
            cleanup.pop_all()

    def recover(self) -> None:
        """Recover durable sessions at startup while this Core owns the writer lease."""
        for row in self.store.recover():
            state = SessionState.model_validate_json(row["state"])
            state.lifecycle = "ending"
            state.latest_turn_id = row["final_turn_id"] or 0
            snapshot = Snapshot(session_id=state.session_id, user_key=state.user_key)
            self.sessions[state.session_id] = SessionRuntime(state, snapshot, None)
            self.reasoner.submit(state.user_key, state.session_id, "process_restart", "end")

    def user_lock(self, user_key):
        return self.user_locks[user_key]

    def today(self) -> str:
        return datetime.now(ZoneInfo(self.config.settings.runtime.timezone)).date().isoformat()

    def bind_output(self, session_id: str, device_id: str, output: OutputPort) -> None:
        if not session_id or not device_id:
            raise ValueError("Session and device identifiers are required")
        with self.registry_lock:
            if self.closing or device_id in self.purging:
                raise RuntimeError("Core is closing or user is being purged")
            if session_id in self.sessions:
                runtime = self.sessions[session_id]
                if runtime.state.user_key != device_id or runtime.state.lifecycle != "active":
                    raise ValueError("Session identity/lifecycle mismatch")
                runtime.port = output
                return
            if self.store.query("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)):
                raise ValueError("A reconnect must use a new session_id")
            state = SessionState(
                session_id=session_id, user_key=device_id, started_mono=time.monotonic()
            )
            self.store.create_session(state)
            snapshot = Snapshot(
                session_id=session_id,
                user_key=device_id,
                core_memory=self.store.core_memory(device_id, self.today()),
            )
            self.sessions[session_id] = SessionRuntime(state, snapshot, output)

    def on_input(
        self,
        session_id: str,
        input_id: str,
        text: str,
        signals: TurnSignals,
        kind: InputKind = "user",
    ) -> int:
        runtime = self.sessions[session_id]
        if runtime.persistence_failed:
            raise RuntimeError("Session stopped after a persistence failure; reconnect")
        previous_snapshot = runtime.snapshot
        try:
            return self._on_input(session_id, input_id, text, signals, kind)
        except sqlite3.Error:
            with self.user_lock(runtime.state.user_key), runtime.lock:
                runtime.snapshot = previous_snapshot
                runtime.persistence_failed = True
                for cancel in runtime.cancels.values():
                    cancel.set()
                if runtime.port:
                    runtime.port.cancel_before(session_id, runtime.state.generation + 1)
            raise

    def _on_input(
        self,
        session_id: str,
        input_id: str,
        text: str,
        signals: TurnSignals,
        kind: InputKind = "user",
    ) -> int:
        if (
            kind not in ("user", "wake", "idle_end")
            or not input_id
            or not isinstance(text, str)
            or len(text) > 12000
        ):
            raise ValueError("Invalid input envelope")
        if kind == "user" and not text.strip():
            raise ValueError("User input cannot be empty")
        runtime = self.sessions[session_id]
        t0 = time.monotonic()
        with self.user_lock(runtime.state.user_key), runtime.lock:
            with self.store.transaction():
                state = runtime.state.model_copy(deep=True)
                if state.lifecycle != "active" or state.user_key in self.purging:
                    raise RuntimeError("Session is not active")
                existing = self.store.existing_input(session_id, input_id)
                if existing:
                    if existing["text"] != text or existing["input_kind"] != kind:
                        raise ValueError("Input id reused for different content")
                    return existing["id"]
                for cancel in runtime.cancels.values():
                    cancel.set()
                self.interactions.cancelling(state, "new_input")
                if state.mode == "exercise":
                    state.policy_revision += 1
                    plan_event = runtime.outputs.get(state.active_plan_id or "")
                    state.resume_script_id = (
                        plan_event.plan.script_id if plan_event and plan_event.plan else None
                    )
                    state.mode = "normal"
                    state.active_plan_id = None
                state.generation += 1
                state.state_revision += 1
                turn_id = self.store.add_input(state, input_id, text, kind, signals)
                state.latest_turn_id = turn_id
                if kind == "user":
                    state.user_turns += 1
                runtime.cancels[turn_id] = threading.Event()
                runtime.metrics[turn_id] = {}
                initial = self.risk.lexicon(text) if kind == "user" else RiskResult()
                runtime.risks[turn_id] = initial
                directive = None
                triggers = ()
                control_triggers = ()
                control_changed = False
                if kind == "user" and state.mode != "crisis" and initial.level != "high":
                    control_triggers, control_changed = self.interactions.input(
                        state, text, turn_id
                    )
                from companion.cognition.policy import (
                    build_turn_policy,
                    exercise_eligibility,
                    plan_invalid_reason,
                )

                bundle = self.cognition.memory.retrieve(
                    state, text, self.config.settings.cognition.context_tokens
                )
                plan = self.store.active_support_plan(state.session_id)
                policy = build_turn_policy(
                    state, plan, bundle, self.store.memory_items(state.user_key)
                )
                if plan_invalid_reason(
                    plan, state, bundle.model_dump(), self.store.memory_items(state.user_key)
                ):
                    runtime.snapshot = runtime.snapshot.model_copy(
                        update={
                            "allowed_cards": (),
                            "preferred_card": None,
                            "offer_exercise": False,
                            "stage_proposal": None,
                            "topic_changed": False,
                        }
                    )
                runtime.snapshot = runtime.snapshot.model_copy(
                    update={"core_memory": self.store.core_memory(state.user_key, self.today())}
                )
                if state.mode != "crisis" and initial.level != "high" and kind == "user":
                    prior_offer = (
                        state.pending_offer.model_copy(deep=True) if state.pending_offer else None
                    )
                    unchecked_inputs = self.store.query(
                        "SELECT text,signals FROM turns WHERE session_id=? AND role='user' "
                        "ORDER BY id DESC LIMIT ?",
                        (
                            session_id,
                            max(0, state.user_turns - plan.checked_through_user_index)
                            if plan and policy.selection_reason == "unchecked_delta_non_action"
                            else 0,
                        ),
                    )
                    exercise_ids, exercise_conditions_current = exercise_eligibility(
                        plan, policy, unchecked_inputs, self.machine.matches
                    )
                    exercise_pending = (
                        runtime.snapshot.offer_exercise
                        or state.resume_script_id
                        or (prior_offer and prior_offer.kind in ("exercise", "resume_exercise"))
                    )
                    # Only a consent-only delta may carry reviewed exercise conditions forward.
                    if policy.selection_reason == "unchecked_delta_non_action" and not prior_offer:
                        runtime.snapshot = runtime.snapshot.model_copy(
                            update={
                                "allowed_cards": (),
                                "preferred_card": None,
                                "offer_exercise": runtime.snapshot.offer_exercise
                                and runtime.snapshot.preferred_exercise in exercise_ids,
                                "stage_proposal": None,
                            }
                        )
                    if policy.selection_reason == "verified" or policy.active_boundaries:
                        runtime.snapshot = runtime.snapshot.model_copy(
                            update={
                                "allowed_cards": tuple(
                                    c
                                    for c in runtime.snapshot.allowed_cards
                                    if c in policy.allowed_action_ids
                                ),
                                "preferred_card": runtime.snapshot.preferred_card
                                if runtime.snapshot.preferred_card in policy.allowed_action_ids
                                else None,
                            }
                        )
                    result = self.machine.apply_rules(
                        state,
                        text,
                        signals,
                        runtime.snapshot,
                        allowed_exercise_ids=exercise_ids,
                        exercise_conditions_current=exercise_conditions_current,
                    )
                    directive, triggers = (
                        result.directive,
                        tuple(dict.fromkeys((*control_triggers, *result.trigger_reasons))),
                    )
                    if (
                        exercise_pending
                        and not exercise_conditions_current
                        and not control_triggers
                        and not self.machine.matches("refuse", text)
                        and state.stage != Stage.quiet
                    ):
                        triggers = tuple(dict.fromkeys((*triggers, "exercise_recheck")))
                    if (
                        policy.active_boundaries or any(a.kind == "no_advice" for a in policy.avoid)
                    ) and directive in ("action_offer", "exercise_offer", "resume_offer"):
                        state.pending_offer = None
                        self.machine.move(state, Stage.explore)
                        directive = "boundary_hold"
                    if control_changed and not triggers:
                        triggers = ("boundary",)
                    if (
                        not triggers
                        and state.user_turns - state.last_reasoner_user_index
                        >= self.config.settings.dialogue.reasoner_every_n_turns
                    ):
                        triggers = ("periodic",)
                    if (
                        signals.emotion in ("SAD", "ANGRY", "FEARFUL")
                        and state.user_turns - state.last_reasoner_user_index >= 2
                    ):
                        triggers += ("emotion",)
                    if (
                        not directive
                        and runtime.snapshot.offer_exercise
                        and runtime.snapshot.preferred_exercise in exercise_ids
                        and runtime.snapshot.preferred_exercise not in state.exercises_refused
                        and not control_triggers
                        and not self.machine.matches("refuse", text)
                        and not state.pending_offer
                        and state.stage in (Stage.explore, Stage.comfort)
                    ):
                        self.machine.offer(state, "exercise", runtime.snapshot.preferred_exercise)
                        directive = "exercise_offer"
                    if (
                        prior_offer
                        and prior_offer.active
                        and self.machine.matches("agree", text)
                        and (
                            state.stage == Stage.action
                            or state.mode == "exercise"
                            or (state.pending_offer and state.pending_offer.accepted_at)
                        )
                    ):
                        self.interactions.record(
                            state, "offer_accepted", "user_explicit", turn_id=turn_id
                        )
                    if (
                        prior_offer
                        and not state.pending_offer
                        and state.stage != Stage.action
                        and state.mode != "exercise"
                    ):
                        self.interactions.record(
                            state, "offer_withdrawn", "deterministic_rule", turn_id=turn_id
                        )
                    if "topic_changed" in result.trigger_reasons:
                        self.interactions.record(
                            state, "topic_changed", "deterministic_rule", turn_id=turn_id
                        )
                policy = build_turn_policy(
                    state, plan, bundle, self.store.memory_items(state.user_key)
                )
                if state.stage == Stage.action and state.card_in_use:
                    from companion.content.models import SupportReference

                    card = self.config.cards[state.card_in_use]
                    policy = policy.model_copy(
                        update={
                            "allowed_action_ids": (state.card_in_use,),
                            "selection_reason": "current_consented_action",
                            "support": SupportReference(
                                identifier=card.id,
                                version=card.protocol.version if card.protocol else "legacy",
                                kind="card",
                                step=state.action_turns + 1,
                            ),
                        }
                    )
                elif directive and directive.startswith("exercise:"):
                    from companion.content.models import SupportReference

                    exercise = self.config.exercises[directive.split(":", 1)[1]]
                    policy = policy.model_copy(
                        update={
                            "support": SupportReference(
                                identifier=exercise.id,
                                version=exercise.protocol.version
                                if exercise.protocol
                                else "legacy",
                                kind="exercise",
                                step=state.resume_index + 1,
                            )
                        }
                    )
                context = TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    generation=state.generation,
                    text=text,
                    kind=kind,
                    stage=state.stage,
                    mode=state.mode,
                    card_id=state.card_in_use,
                    snapshot=runtime.snapshot,
                    signals=signals,
                    trigger_reasons=triggers,
                    directive=directive,
                    t0=t0,
                    policy_frame=policy,
                )
                runtime.contexts[turn_id] = context
                self.store.connection().execute(
                    "INSERT INTO turn_policies VALUES (?,?,?)",
                    (turn_id, session_id, policy.model_dump_json()),
                )
                self.store.update_turn(
                    turn_id,
                    stage=state.stage.value,
                    mode=state.mode,
                    card=state.card_in_use,
                    snapshot_version=runtime.snapshot.version,
                    generation=state.generation,
                )
                self.store.save_state(state)
                port, generation = runtime.port, state.generation
            runtime.state = state
        self.store.cancel_outputs(session_id, generation)
        if port:
            port.cancel_before(session_id, generation)
        if initial.level != "none":
            self._risk_result(session_id, turn_id, initial, 0)
        if runtime.state.mode == "crisis":
            self._crisis_reply(runtime, context, first=False)
            return turn_id
        if kind == "user":
            previous = [
                r["text"]
                for r in self.store.history(session_id, turn_id - 1, 2)
                if r["role"] == "user"
            ]
            future = self.risk.classify(
                text,
                previous,
                lambda result, elapsed: self._risk_result(session_id, turn_id, result, elapsed),
                usage_callback=lambda usage: self.record_usage(
                    session_id, turn_id, "risk_usage", usage
                ),
            )
            with self.user_lock(runtime.state.user_key), runtime.lock:
                runtime.risk_futures[turn_id] = future
        if control_changed:
            self.reasoner.cancel_user(runtime.state.user_key, session_id, "explicit_control")
        if triggers:
            self.reasoner.submit(runtime.state.user_key, session_id, triggers)
        if control_triggers and any(
            t in control_triggers for t in ("boundary", "correction", "feedback")
        ):
            self.reasoner.submit(runtime.state.user_key, session_id, "interaction_memory", "memory")
        return turn_id

    def record_usage(self, session_id, turn_id, name, usage):
        runtime = self.sessions.get(session_id)
        if runtime is None:
            return
        with self.user_lock(runtime.state.user_key), runtime.lock:
            if runtime.state.user_key not in self.purging and turn_id in runtime.metrics:
                runtime.metrics[turn_id][name] = usage.model_dump()
                self.store.update_turn(turn_id, latency={name: usage.model_dump()})

    def _risk_result(self, session_id: str, turn_id: int, risk: RiskResult, elapsed: float) -> None:
        with self.registry_lock:
            runtime = self.sessions.get(session_id)
        if runtime is None:
            rows = self.store.query(
                "SELECT user_key FROM sessions WHERE session_id=?", (session_id,)
            )
            if rows and rows[0]["user_key"] not in self.purging:
                self.store.update_turn(
                    turn_id,
                    latency={
                        "risk_l2_ms": elapsed,
                        "risk_status": risk.status,
                        "risk_model_level": risk.level,
                    },
                )
                if risk.level != "none":
                    event_id = self.store.record_risk(
                        session_id, turn_id, risk, {"risk_l2_ms": elapsed}
                    )
                    self._notify_risk(event_id, risk)
            return
        with self.user_lock(runtime.state.user_key), runtime.lock:
            if runtime.state.user_key in self.purging:
                return
            previous = runtime.risks.get(turn_id, RiskResult())
            metrics = runtime.metrics.get(turn_id, {})
            if risk.source == "model":
                metrics.update(
                    risk_l2_ms=elapsed, risk_status=risk.status, risk_model_level=risk.level
                )
            if RANK[risk.level] < RANK[previous.level]:
                self.store.update_turn(turn_id, latency=dict(metrics))
                return
            delivery = (turn_id, risk.level, risk.source, risk.status)
            if delivery in runtime.risk_deliveries:
                return
            runtime.risk_deliveries.add(delivery)
            runtime.risks[turn_id] = risk
            active = runtime.state.lifecycle == "active"
            first = risk.level == "high" and runtime.state.mode != "crisis" and active
            if first:
                runtime.state.mode = "crisis"
                runtime.state.policy_revision += 1
                runtime.state.active_support_plan_id = None
                self.store.invalidate_plans(session_id)
                runtime.state.state_revision += 1
                runtime.state.generation += 1
                runtime.state.pending_offer = None
                runtime.state.active_plan_id = None
                runtime.state.resume_script_id = None
                for cancel in runtime.cancels.values():
                    cancel.set()
                port, generation = runtime.port, runtime.state.generation
            else:
                port, generation = None, runtime.state.generation
        if first:
            self.reasoner.cancel_user(runtime.state.user_key, session_id, "risk_high")
            if port:
                port.cancel_before(session_id, generation)
            self.store.cancel_outputs(session_id, generation)
            self._crisis_reply(runtime, runtime.contexts[turn_id], first=True)
            metrics["crisis_dispatch_ms"] = (
                time.monotonic() - runtime.contexts[turn_id].t0
            ) * 1000 - elapsed
        if risk.level != "none":
            event_id = self.store.record_risk(session_id, turn_id, risk, dict(metrics))
            self._notify_risk(event_id, risk)
        with self.user_lock(runtime.state.user_key), runtime.lock:
            self.store.save_state(runtime.state)
            self.store.update_turn(turn_id, latency=dict(metrics))
            if first:
                self.store.update_turn(turn_id, mode="crisis")
        if risk.level == "watch" and active and runtime.state.mode != "crisis":
            self.reasoner.submit(runtime.state.user_key, session_id, "risk_watch")

    def request_risk_review(self, session_id, turn_id):
        runtime = self.sessions.get(session_id)
        if runtime is None:
            return
        with self.user_lock(runtime.state.user_key), runtime.lock:
            if (
                runtime.state.lifecycle != "active"
                or runtime.state.mode == "crisis"
                or turn_id in runtime.risk_reviews
                or runtime.state.user_key in self.purging
            ):
                return
            runtime.risk_reviews.add(turn_id)
        rows = self.store.query(
            "SELECT text FROM turns WHERE id=? AND session_id=? AND role='user'",
            (turn_id, session_id),
        )
        if rows:
            self.risk.classify(
                rows[0]["text"],
                [],
                lambda result, elapsed: self._risk_result(session_id, turn_id, result, elapsed),
            )

    def _notify_risk(self, event_id: int, risk: RiskResult) -> None:
        url = self.config.settings.alert_webhook
        if not url:
            return

        # Notifications run outside the critical output path and have a bounded timeout.
        def send() -> None:
            import httpx

            status = "sent"
            try:
                response = httpx.post(
                    url, json={"event_id": event_id, "level": risk.level}, timeout=3
                )
                response.raise_for_status()
            except httpx.HTTPError:
                status = "failed"
                logger.warning("Risk webhook failed for event %s", event_id)
            with self.store.transaction() as db:
                db.execute(
                    "UPDATE risk_events SET notification_status=? WHERE id=?", (status, event_id)
                )

        self._notifications.submit(send)

    def _crisis_reply(self, runtime: SessionRuntime, context: TurnContext, *, first: bool) -> None:
        with self.user_lock(runtime.state.user_key), runtime.lock:
            state = runtime.state
            if context.turn_id in runtime.crisis_sent or state.lifecycle != "active":
                return
            runtime.crisis_sent.add(context.turn_id)
            templates = self.config.crisis
            if context.kind == "idle_end":
                text = templates["closing"]
            elif first:
                text = templates["opening"]
            else:
                state.crisis_turns += 1
                text = templates["responses"][
                    (state.crisis_turns - 1) % len(templates["responses"])
                ]
                if state.crisis_turns % 3 == 0:
                    text += templates["resources"]
            event = OutputEvent(
                output_id=uuid.uuid4().hex,
                session_id=state.session_id,
                turn_id=context.turn_id,
                generation=state.generation,
                type="crisis_plan",
                text=text,
                emoji=templates["emoji"],
                plan=PlaybackPlan(script_id="crisis", segments=(PlaybackSegment(text=text),)),
                purpose="idle_end" if context.kind == "idle_end" else "crisis",
                template_version=templates["version"],
            )
        self.dispatch(event)

    def _valid(self, runtime: SessionRuntime, context: TurnContext) -> bool:
        state = runtime.state
        return (
            state.lifecycle == "active"
            and not runtime.persistence_failed
            and state.mode != "crisis"
            and state.generation == context.generation
            and not runtime.cancels[context.turn_id].is_set()
        )

    def _gate(self, runtime: SessionRuntime, context: TurnContext) -> bool:
        future = runtime.risk_futures.get(context.turn_id)
        if future is not None:
            try:
                result = future.result(
                    timeout=max(
                        0,
                        context.t0
                        + self.config.settings.timing.gate_timeout_ms / 1000
                        - time.monotonic(),
                    )
                )
                self._risk_result(
                    context.session_id,
                    context.turn_id,
                    result,
                    runtime.metrics[context.turn_id].get("risk_l2_ms", 0),
                )
            except FutureTimeout:
                runtime.metrics[context.turn_id]["gate_pending"] = True
        with self.user_lock(runtime.state.user_key), runtime.lock:
            if not self._valid(runtime, context):
                return False
            runtime.metrics[context.turn_id].setdefault(
                "gate_release_ms", (time.monotonic() - context.t0) * 1000
            )
            return True

    def _text_event(
        self, context: TurnContext, text: str, emoji: str = "😶", **fields: object
    ) -> OutputEvent:
        return OutputEvent(
            output_id=uuid.uuid4().hex,
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation=context.generation,
            text=text,
            emoji=emoji,
            support=context.policy_frame.support
            if fields.get("purpose", "reply") in ("reply", "exercise")
            else None,
            **fields,
        )

    def respond(self, session_id: str, turn_id: int) -> Iterator[OutputEvent]:
        runtime = self.sessions.get(session_id)
        if runtime is None:
            return
        with self.user_lock(runtime.state.user_key), runtime.lock:
            context = runtime.contexts[turn_id]
            if turn_id in runtime.responded or not self._valid(runtime, context):
                return
            runtime.responded.add(turn_id)
            cancel = runtime.cancels[turn_id]
            metrics = runtime.metrics[turn_id]
            metrics["signal_to_respond_ms"] = (time.monotonic() - context.t0) * 1000
            state = runtime.state
        violations: list[str] = []
        emitted = False
        completed = False
        failed = False
        try:
            if context.kind == "wake":
                if not self.store.onboarding_done(state.user_key):
                    event = self._text_event(
                        context, self.config.persona["onboarding"], purpose="onboarding"
                    )
                else:
                    followup = self.store.reserve_followup(state.user_key, session_id, self.today())
                    if followup:
                        from companion.cognition.policy import effective_boundaries

                        boundaries = effective_boundaries(
                            self.cognition.memory.retrieve(state, "", proactive=True)
                        )
                        if any(
                            b.target == "current_topic"
                            or (b.target and b.target in followup["content"])
                            for b in boundaries
                        ):
                            with self.store.transaction() as db:
                                db.execute(
                                    "UPDATE followups SET status='pending',reservation_session_id=NULL WHERE id=? AND status='reserved'",
                                    (followup["id"],),
                                )
                            followup = None
                    text = (
                        self.config.persona["followup"].format(content=followup["content"])
                        if followup
                        else self.config.persona["greeting"]
                    )
                    event = self._text_event(
                        context,
                        text,
                        purpose="opening",
                        followup_id=followup["id"] if followup else None,
                    )
                if self._gate(runtime, context):
                    emitted = True
                    yield event
            elif context.kind == "idle_end":
                if self._gate(runtime, context):
                    emitted = True
                    yield self._text_event(
                        context, self.config.persona["idle_end"], purpose="idle_end"
                    )
            elif context.directive and context.directive.startswith("exercise:"):
                script_id = context.directive.split(":", 1)[1]
                plan = self.exercise.build_plan(script_id, state.resume_index)
                if self._gate(runtime, context):
                    emitted = True
                    yield self._text_event(
                        context,
                        "",
                        self.config.exercises[script_id].emo,
                        type="exercise_plan",
                        plan=plan,
                        purpose="exercise",
                    )
            elif context.directive:
                if context.directive == "quiet":
                    text = self.config.stages["quiet"]["fallback"]
                else:
                    text = self.config.stages["templates"][context.directive]
                offer = state.pending_offer
                if context.directive == "exercise_offer" and offer:
                    exercise = self.config.exercises.get(offer.target_id)
                    if exercise and exercise.protocol:
                        text = exercise.protocol.invitation
                if self._gate(runtime, context):
                    emitted = True
                    yield self._text_event(
                        context,
                        text,
                        purpose=context.directive,
                        offer_id=offer.offer_id
                        if offer
                        and context.directive
                        in ("action_offer", "exercise_offer", "resume_offer", "clarify_offer")
                        else None,
                    )
            else:
                history = self.store.history(
                    session_id, turn_id, self.config.settings.dialogue.history_turns
                )
                limit = self.config.settings.dialogue.max_sentences
                if (
                    not state.rest_reminded
                    and time.monotonic() - state.started_mono
                    >= self.config.settings.timing.rest_reminder_s
                ):
                    limit = max(1, limit - 1)
                for sentence, emoji in self.talker.run(
                    context,
                    history,
                    cancel,
                    metrics,
                    violations,
                    step=state.action_turns + 1,
                    sentence_limit=limit,
                ):
                    if not self._gate(runtime, context):
                        return
                    emitted = True
                    yield self._text_event(
                        context,
                        sentence,
                        emoji,
                        purpose="fallback" if metrics.get("fallback") else "reply",
                    )
            with self.user_lock(runtime.state.user_key), runtime.lock:
                reminder_due = (
                    context.kind == "user"
                    and not context.directive
                    and self._valid(runtime, context)
                    and not state.rest_reminded
                    and time.monotonic() - state.started_mono
                    >= self.config.settings.timing.rest_reminder_s
                )
            if reminder_due:
                yield self._text_event(context, self.config.persona["rest"], purpose="rest")
            completed = True
        except Exception as error:
            failed = True
            logger.exception("Reply failed for session %s turn %s", session_id, turn_id)
            violations.append("llm_error")
            metrics["error_type"] = type(error).__name__
            if not emitted and self._gate(runtime, context):
                yield self._text_event(
                    context, self.config.stages[context.stage.value]["fallback"], purpose="fallback"
                )
            completed = True
        finally:
            metrics["total_ms"] = (time.monotonic() - context.t0) * 1000
            interrupted = cancel.is_set() or not completed
            self.store.update_turn(
                turn_id,
                latency=dict(metrics),
                violations=violations,
                interrupted=int(interrupted),
                output_status="error" if failed else ("generated" if completed else "interrupted"),
            )

    def dispatch(self, event: OutputEvent) -> bool:
        runtime = self.sessions.get(event.session_id)
        if runtime is None:
            return False
        with self.user_lock(runtime.state.user_key), runtime.lock:
            state = runtime.state
            if (
                state.lifecycle != "active"
                or event.generation != state.generation
                or (state.mode == "crisis" and event.type != "crisis_plan")
            ):
                return False
            if not self.store.add_output(event):
                return False
            runtime.outputs[event.output_id] = event
            if event.type == "exercise_plan":
                state.active_plan_id = event.output_id
            context = runtime.contexts[event.turn_id]
            if (
                event.type == "text"
                and context.stage == Stage.action
                and event.purpose == "reply"
                and event.turn_id not in runtime.action_counted
            ):
                runtime.action_counted.add(event.turn_id)
                if self.store.record_card(state, event.turn_id, "used"):
                    state.cards_used[state.card_in_use] = (
                        state.cards_used.get(state.card_in_use, 0) + 1
                    )
                state.action_turns += 1
            runtime.metrics[event.turn_id].setdefault(
                "output_submit_ms", (time.monotonic() - context.t0) * 1000
            )
            self.store.save_state(state)
            port = runtime.port
        if port:
            try:
                port.submit(event)
            except Exception as error:
                self.on_playback_event(
                    PlaybackEvent(
                        output_id=event.output_id,
                        session_id=event.session_id,
                        generation=event.generation,
                        status="failed",
                        error=type(error).__name__,
                    )
                )
                logger.exception("Output submission failed")
                return False
        return True

    def on_playback_event(self, event: PlaybackEvent) -> None:
        runtime = self.sessions.get(event.session_id)
        if runtime is None:
            return
        should_end = False
        with self.user_lock(runtime.state.user_key), runtime.lock:
            with self.store.transaction():
                state = runtime.state.model_copy(deep=True)
                output = runtime.outputs.get(event.output_id)
                if (
                    not output
                    or event.generation != state.generation
                    or state.lifecycle != "active"
                ):
                    return
                stored = self.store.query(
                    "SELECT status FROM outputs WHERE output_id=?", (event.output_id,)
                )
                if not stored or stored[0]["status"] in ("completed", "cancelled", "failed"):
                    return
                if event.status == "segment":
                    if output.type == "exercise_plan" and event.segment_index is not None:
                        state.resume_index = event.segment_index
                        self.store.save_state(state)
                        runtime.state = state
                    return
                self.interactions.playback(state, output, event)
                self.store.output_status(event.output_id, event.status)
                if event.status == "started":
                    if (
                        output.offer_id
                        and state.pending_offer
                        and output.offer_id == state.pending_offer.offer_id
                    ):
                        state.pending_offer.active = True
                    if output.followup_id:
                        self.store.mark_followup_asked(output.followup_id, state.session_id)
                    if output.purpose == "rest":
                        state.rest_reminded = True
                elif event.status == "completed":
                    context = runtime.contexts[output.turn_id]
                    if (
                        context.stage == Stage.closing
                        and output.purpose == "reply"
                        and output.turn_id not in runtime.closing_counted
                    ):
                        runtime.closing_counted.add(output.turn_id)
                        state.closing_turns += 1
                    if output.purpose == "onboarding":
                        self.store.mark_onboarding(state.user_key)
                    if (
                        output.purpose in ("onboarding", "opening")
                        and state.mode == "normal"
                        and state.stage == Stage.opening
                    ):
                        self.machine.move(state, Stage.explore)
                    if output.type == "exercise_plan" and state.active_plan_id == output.output_id:
                        state.active_plan_id = None
                        state.mode = "normal"
                        state.policy_revision += 1
                        state.resume_index = 0
                        self.machine.move(state, Stage.comfort)
                    should_end = output.purpose == "idle_end"
                elif event.status in ("failed", "cancelled"):
                    if output.type == "exercise_plan" and state.active_plan_id == output.output_id:
                        state.active_plan_id = None
                        state.mode = "normal"
                    if output.offer_id and state.pending_offer and not state.pending_offer.active:
                        state.pending_offer = None
                    if output.followup_id and stored[0]["status"] == "submitted":
                        with self.store.transaction() as db:
                            db.execute(
                                "UPDATE followups SET status='pending',reservation_session_id=NULL WHERE id=? AND status='reserved'",
                                (output.followup_id,),
                            )
                self.store.save_state(state)
            runtime.state = state
        if should_end:
            self.on_session_end(event.session_id, "idle_timeout")

    def on_interrupt(self, session_id: str, generation: int, reason: str) -> None:
        runtime = self.sessions.get(session_id)
        if not runtime:
            return
        with self.user_lock(runtime.state.user_key), runtime.lock:
            state = runtime.state
            if state.lifecycle != "active" or generation != state.generation:
                return
            self.interactions.cancelling(state, reason)
            state.generation += 1
            state.state_revision += 1
            for cancel in runtime.cancels.values():
                cancel.set()
            if state.mode == "exercise":
                state.policy_revision += 1
                output = runtime.outputs.get(state.active_plan_id or "")
                state.resume_script_id = output.plan.script_id if output and output.plan else None
                state.mode = "normal"
                state.active_plan_id = None
            self.store.save_state(state)
            port, new_generation = runtime.port, state.generation
        self.store.cancel_outputs(session_id, new_generation)
        if port:
            port.cancel_before(session_id, new_generation)

    def on_session_end(self, session_id: str, reason: str = "disconnect") -> None:
        runtime = self.sessions.get(session_id)
        if runtime is None:
            return
        with self.user_lock(runtime.state.user_key), runtime.lock:
            state = runtime.state
            if state.lifecycle != "active":
                return
            self.interactions.cancelling(state, reason)
            state.lifecycle = "ending"
            state.policy_revision += 1
            state.active_support_plan_id = None
            self.store.invalidate_plans(session_id)
            state.state_revision += 1
            state.generation += 1
            state.pending_offer = None
            for cancel in runtime.cancels.values():
                cancel.set()
            self.store.end_session(state, reason)
            port, generation = runtime.port, state.generation
            runtime.port = None
        self.store.cancel_outputs(session_id, generation)
        if port:
            port.cancel_before(session_id, generation)
        self.reasoner.cancel_user(state.user_key, session_id, "session_ended")
        self.interactions.record(
            state, "session_ended", "deterministic_rule", turn_id=state.latest_turn_id or None
        )
        self.reasoner.submit(state.user_key, session_id, reason, "end")

    def wait_idle(self, timeout: float = 25) -> bool:
        started = time.monotonic()
        return self.risk.wait_idle(timeout) and self.reasoner.wait_idle(
            max(0, timeout - (time.monotonic() - started))
        )

    def purge_user(self, user_key: str) -> None:
        with self.registry_lock:
            self.purging.add(user_key)
            self.user_epochs[user_key] = self.user_epochs.get(user_key, 0) + 1
            sessions = [key for key, rt in self.sessions.items() if rt.state.user_key == user_key]
        self.reasoner.cancel_user(user_key, reason="purge")
        for session_id in sessions:
            self.on_session_end(session_id, "purge")
        if not self.risk.wait_idle(
            self.config.settings.timing.shutdown_grace_s
        ) or not self.reasoner.wait_idle(self.config.settings.timing.shutdown_grace_s, user_key):
            raise TimeoutError("Cannot purge while callbacks are still running")
        self.store.purge_user(user_key)
        with self.registry_lock:
            for session_id in sessions:
                self.sessions.pop(session_id, None)
            self.purging.discard(user_key)

    def close(self) -> None:
        self.closing = True
        for session_id in list(self.sessions):
            self.on_session_end(session_id, "shutdown")
        self.risk.close()
        self.cognition.close()
        if self._notifications:
            self._notifications.shutdown(wait=True)
        close = getattr(self.llm, "close", None)
        if close:
            close()
        self.writer_lease.close()
