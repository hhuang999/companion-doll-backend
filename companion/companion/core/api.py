"""Session orchestration. Model and playback I/O never owns dialogue state."""

import json
import logging
import threading
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined

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
    ReasonerOutput,
    ReasonerTask,
    RiskResult,
    SessionState,
    Snapshot,
    Stage,
    TurnContext,
    TurnSignals,
)
from .reasoner import ReasonerScheduler
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


class CompanionCore:
    def __init__(
        self, config: Config, store: Store, llm: LLMClient, *, recover: bool = True
    ) -> None:
        self.config, self.store, self.llm = config, store, llm
        self.sessions: dict[str, SessionRuntime] = {}
        self.registry_lock = threading.RLock()
        self.closing = False
        self.purging: set[str] = set()
        self._notifications = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="risk-notify")
            if config.settings.alert_webhook
            else None
        )
        self.machine = StateMachine(config)
        self.talker = Talker(config, llm)
        self.validator = Validator(config)
        self.exercise = ExercisePlayer(config)
        self.risk = RiskDetector(config, llm)
        self.reasoner = ReasonerScheduler(
            config.settings.pools.reasoner_workers, self._run_reasoner
        )
        self.templates = Environment(
            loader=FileSystemLoader(config.directory / "prompts"),
            undefined=StrictUndefined,
            autoescape=False,
        )
        if recover:
            for row in store.recover():
                state = SessionState.model_validate_json(row["state"])
                state.lifecycle = "ending"
                state.latest_turn_id = row["final_turn_id"] or 0
                snapshot = Snapshot(session_id=state.session_id, user_key=state.user_key)
                self.sessions[state.session_id] = SessionRuntime(state, snapshot, None)
                self.reasoner.submit(state.user_key, state.session_id, "process_restart", "end")

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
        with runtime.lock:
            state = runtime.state
            if state.lifecycle != "active" or state.user_key in self.purging:
                raise RuntimeError("Session is not active")
            existing = self.store.existing_input(session_id, input_id)
            if existing:
                if existing["text"] != text or existing["input_kind"] != kind:
                    raise ValueError("Input id reused for different content")
                return existing["id"]
            for cancel in runtime.cancels.values():
                cancel.set()
            if state.mode == "exercise":
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
            runtime.snapshot = runtime.snapshot.model_copy(
                update={"core_memory": self.store.core_memory(state.user_key, self.today())}
            )
            if state.mode != "crisis" and initial.level != "high" and kind == "user":
                result = self.machine.apply_rules(state, text, signals, runtime.snapshot)
                directive, triggers = result.directive, result.trigger_reasons
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
                    and not state.pending_offer
                    and state.stage in (Stage.explore, Stage.comfort)
                ):
                    self.machine.offer(state, "exercise", "breathing_60s")
                    directive = "exercise_offer"
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
            )
            runtime.contexts[turn_id] = context
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
            )
            with runtime.lock:
                runtime.risk_futures[turn_id] = future
        for trigger in triggers:
            self.reasoner.submit(runtime.state.user_key, session_id, trigger)
        return turn_id

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
        with runtime.lock:
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
        with runtime.lock:
            self.store.save_state(runtime.state)
            self.store.update_turn(turn_id, latency=dict(metrics))
            if first:
                self.store.update_turn(turn_id, mode="crisis")
        if risk.level == "watch" and active and runtime.state.mode != "crisis":
            self.reasoner.submit(runtime.state.user_key, session_id, "risk_watch")

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
        with runtime.lock:
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
        with runtime.lock:
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
            **fields,
        )

    def respond(self, session_id: str, turn_id: int) -> Iterator[OutputEvent]:
        runtime = self.sessions.get(session_id)
        if runtime is None:
            return
        with runtime.lock:
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
            with runtime.lock:
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
        with runtime.lock:
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
        with runtime.lock:
            state = runtime.state
            output = runtime.outputs.get(event.output_id)
            if not output or event.generation != state.generation or state.lifecycle != "active":
                return
            stored = self.store.query(
                "SELECT status FROM outputs WHERE output_id=?", (event.output_id,)
            )
            if not stored or stored[0]["status"] in ("completed", "cancelled", "failed"):
                return
            if event.status == "segment":
                if output.type == "exercise_plan" and event.segment_index is not None:
                    state.resume_index = event.segment_index
                return
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
        if should_end:
            self.on_session_end(event.session_id, "idle_timeout")

    def on_interrupt(self, session_id: str, generation: int, reason: str) -> None:
        runtime = self.sessions.get(session_id)
        if not runtime:
            return
        with runtime.lock:
            state = runtime.state
            if state.lifecycle != "active" or generation != state.generation:
                return
            state.generation += 1
            state.state_revision += 1
            for cancel in runtime.cancels.values():
                cancel.set()
            if state.mode == "exercise":
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
        with runtime.lock:
            state = runtime.state
            if state.lifecycle != "active":
                return
            state.lifecycle = "ending"
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
        self.reasoner.submit(state.user_key, session_id, reason, "end")

    def _run_reasoner(self, session_id: str, kind: str, triggers: tuple[str, ...]) -> None:
        runtime = self.sessions.get(session_id)
        if runtime is None:
            return
        with runtime.lock:
            state = runtime.state.model_copy(deep=True)
            if state.user_key in self.purging or (
                kind == "normal" and (state.lifecycle != "active" or state.mode == "crisis")
            ):
                return
            task = ReasonerTask(
                session_id=session_id,
                user_key=state.user_key,
                kind=kind,
                trigger_reasons=triggers,
                source_turn_id=state.latest_turn_id,
                state_revision=state.state_revision,
                topic_revision=state.topic_revision,
                base_snapshot_version=runtime.snapshot.version,
                user_index=state.user_turns,
            )
            snapshot = runtime.snapshot
            runtime.state.last_reasoner_user_index = state.user_turns
        started = time.monotonic()
        deadline = started + self.config.settings.timing.reasoner_timeout_s
        history = self.store.history(
            session_id, task.source_turn_id, self.config.settings.dialogue.reasoner_context_turns
        )
        source_ids = {r["id"] for r in history if r["role"] == "user"}
        payload = {
            "history": history,
            "state": state.model_dump(mode="json"),
            "snapshot": snapshot.model_dump(mode="json"),
            "cards": [
                card.model_dump() for card in self.config.cards.values() if card.status != "draft"
            ],
            "ending": kind == "end",
            "today": self.today(),
            "followups": self.store.query(
                "SELECT id,content,status FROM followups WHERE user_key=?", (state.user_key,)
            ),
        }
        prompt = self.templates.get_template("reasoner.j2").render(
            schema=json.dumps(ReasonerOutput.model_json_schema(), ensure_ascii=False),
            ending=kind == "end",
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            if kind == "end" and not source_ids:
                output = ReasonerOutput(session_summary="")
            else:
                from pydantic import ValidationError

                for attempt in range(2):
                    try:
                        output = self.llm.complete_json(
                            self.config.settings.llm.reasoner_model,
                            messages,
                            ReasonerOutput,
                            deadline,
                            temperature=0.2,
                            max_tokens=1800,
                        )
                        break
                    except (ValidationError, json.JSONDecodeError):
                        if attempt == 1:
                            raise
                        messages.append(
                            {
                                "role": "user",
                                "content": "Return valid JSON matching the supplied schema.",
                            }
                        )
            validated, rejected = self.validator.validate(
                output,
                state,
                source_ids,
                datetime.fromisoformat(self.today()).date(),
                ending=kind == "end",
            )
            with runtime.lock:
                current = runtime.state
                if current.user_key in self.purging:
                    return
                stale = kind == "normal" and (
                    current.lifecycle != "active"
                    or current.mode == "crisis"
                    or current.latest_turn_id != task.source_turn_id
                    or current.state_revision != task.state_revision
                    or runtime.snapshot.version != task.base_snapshot_version
                )
                duration = (time.monotonic() - started) * 1000
                if stale:
                    self.store.record_run(
                        task, "superseded", duration, result=output.model_dump(mode="json")
                    )
                    if current.lifecycle == "active" and current.mode != "crisis":
                        self.reasoner.submit(current.user_key, session_id, "superseded")
                    return
                next_snapshot = None
                if kind == "normal":
                    next_snapshot = Snapshot(
                        session_id=session_id,
                        user_key=state.user_key,
                        version=snapshot.version + 1,
                        source_turn_id=task.source_turn_id,
                        trigger=",".join(triggers),
                        assessment=validated.assessment,
                        stage_proposal=validated.stage_proposal,
                        allowed_cards=validated.cards.allowed,
                        preferred_card=validated.cards.preferred,
                        offer_exercise=validated.offer_exercise,
                        topic_changed=validated.topic_changed,
                        core_memory=snapshot.core_memory,
                    )
                self.store.publish(
                    task,
                    next_snapshot,
                    validated.memory,
                    validated.session_summary,
                    output.model_dump(mode="json"),
                    [r.model_dump() for r in rejected],
                    duration,
                )
                if next_snapshot:
                    runtime.snapshot = next_snapshot
                if kind == "end":
                    current.lifecycle = "closed"
                    self.store.save_state(current)
                    with self.registry_lock:
                        self.sessions.pop(session_id, None)
        except Exception as error:
            logger.exception("Reasoner failed for %s", session_id)
            status = "timeout" if isinstance(error, TimeoutError) else "error"
            self.store.record_run(
                task, status, (time.monotonic() - started) * 1000, error=type(error).__name__
            )
            if kind == "end":
                self.store.fail_end(session_id, type(error).__name__)
                with self.registry_lock:
                    self.sessions.pop(session_id, None)

    def wait_idle(self, timeout: float = 25) -> bool:
        started = time.monotonic()
        return self.risk.wait_idle(timeout) and self.reasoner.wait_idle(
            max(0, timeout - (time.monotonic() - started))
        )

    def purge_user(self, user_key: str) -> None:
        with self.registry_lock:
            self.purging.add(user_key)
            sessions = [key for key, rt in self.sessions.items() if rt.state.user_key == user_key]
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
        self.reasoner.close()
        if self._notifications:
            self._notifications.shutdown(wait=True)
        close = getattr(self.llm, "close", None)
        if close:
            close()
