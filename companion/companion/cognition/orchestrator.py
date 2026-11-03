"""Finite routine/deliberation protocols and separately validated publication."""

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from openai import APITimeoutError
from pydantic import BaseModel

from companion.content.catalog import StrategyCatalog
from companion.core.models import (
    Assessment,
    CardEvidence,
    CardSelection,
    Followup,
    MemoryUpdate,
    ReasonerOutput,
    SeekerState,
    Snapshot,
    TypedConfidence,
)
from companion.memory.service import MemoryService

from .agents import Agents
from .base import EvidenceRef, utcnow
from .budget import Budget, BudgetExceeded, JobCancelled
from .models import (
    CognitiveJob,
    Consolidation,
    DeltaResult,
    PlanCandidate,
    ReviewBrief,
    ReviewResult,
    SituationAssessment,
    SupportPlan,
)
from .policy import NON_ACTION, plan_invalid_reason
from .scheduler import CognitiveScheduler

logger = logging.getLogger(__name__)


def evidence_in(value):
    if isinstance(value, EvidenceRef):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from evidence_in(getattr(value, name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from evidence_in(item)


class Cognition:
    def __init__(self, core):
        self.core, self.store, self.config = core, core.store, core.config
        factory = getattr(core.llm, "background_client", None)
        self.llm = factory() if factory else core.llm
        self.agents = Agents(core.config, core.store, self.llm)
        self.catalog = StrategyCatalog(self.config)
        self.brief_pool = ThreadPoolExecutor(
            max_workers=core.config.settings.pools.reasoner_workers,
            thread_name_prefix="independent-brief",
        )
        self.memory = MemoryService(self.store, self.config.settings.runtime.timezone)
        self.scheduler = CognitiveScheduler(self.config, self.store, self.capture, self.run)

    def capture(self, user_key, session_id, kind, triggers, priority):
        rt = self.core.sessions.get(session_id)
        if rt is None:
            return None
        with self.core.user_lock(user_key), rt.lock:
            s = rt.state
            if user_key in self.core.purging or (
                kind != "end_consolidation" and (s.lifecycle != "active" or s.mode == "crisis")
            ):
                return None
            previous = (
                self.store.query(
                    "SELECT job_id,data FROM cognitive_jobs WHERE session_id=? AND kind='end_consolidation' ORDER BY queued_at DESC LIMIT 1",
                    (session_id,),
                )
                if kind == "end_consolidation"
                else []
            )
            return CognitiveJob(
                job_id=uuid.uuid4().hex,
                user_key=user_key,
                session_id=session_id,
                kind=kind,
                triggers=triggers,
                source_turn_id=s.latest_turn_id,
                source_user_index=s.user_turns,
                topic_revision=s.topic_revision,
                policy_revision=s.policy_revision,
                boundary_revision=self.store.revisions(user_key)["boundary_revision"],
                base_plan_version=s.support_plan_version,
                priority=priority,
                epoch=self.core.user_epochs.get(user_key, 0),
                retry_of=previous[0]["job_id"] if previous else None,
                attempt=json.loads(previous[0]["data"])["attempt"] + 1 if previous else 1,
                budget_limits={
                    **getattr(self.config.settings.cognition, kind).model_dump(),
                    "deadline_s": self.config.settings.timing.reasoner_timeout_s,
                },
            )

    def _payload(self, job, state):
        history = self.store.history(
            job.session_id, job.source_turn_id, self.config.settings.dialogue.reasoner_context_turns
        )
        bundle = self.memory.retrieve(
            state, " ".join(r["text"] for r in history if r["role"] == "user"), budget=2200
        )
        events = self.store.query(
            "SELECT data FROM interaction_events WHERE user_key=? AND session_id=? AND (turn_id<=? OR turn_id IS NULL) AND event_type NOT LIKE 'playback_%' ORDER BY recorded_at DESC LIMIT 6",
            (job.user_key, job.session_id, job.source_turn_id),
        )
        payload = {
            "history": [{"id": r["id"], "role": r["role"], "text": r["text"]} for r in history],
            "state": {
                "stage": state.stage.value,
                "mode": state.mode,
                "pending_offer": state.pending_offer.model_dump(mode="json")
                if state.pending_offer
                else None,
            },
            "memory": [
                m.model_dump(
                    mode="json",
                    include={
                        "memory_id",
                        "version",
                        "kind",
                        "key",
                        "value",
                        "scope",
                        "scope_ref",
                        "expires_at",
                        "source_refs",
                        "mention_policy",
                        "boundary_rule",
                        "target",
                    },
                )
                for m in (*bundle.boundaries, *bundle.items)
            ],
            "feedback": [
                {
                    key: value
                    for key, value in json.loads(r["data"]).items()
                    if key
                    in {
                        "event_id",
                        "event_type",
                        "origin",
                        "turn_id",
                        "output_id",
                        "support_plan_id",
                        "payload",
                    }
                }
                for r in events
            ],
            "kind": job.kind,
            "today": self.core.today(),
            "final_turn_id": job.source_turn_id,
        }
        allowed = {("user_turn", str(r["id"])) for r in history if r["role"] == "user"}
        allowed.update(("memory", m.memory_id) for m in (*bundle.boundaries, *bundle.items))
        allowed.update(("interaction_event", e["event_id"]) for e in payload["feedback"])
        return payload, bundle, allowed

    def _validate(self, job, value, allowed):
        self.store.validate_refs(job.user_key, tuple(evidence_in(value)), allowed)

    def run(self, job, cancel):
        rt = self.core.sessions.get(job.session_id)
        if rt is None:
            self.store.finish_job(job.job_id, "cancelled", error="session_removed")
            return
        budget = Budget(
            getattr(self.config.settings.cognition, job.kind),
            self.config.settings.timing.reasoner_timeout_s,
            cancel,
        )
        analysis = None
        candidates = ()
        plan = None
        summary = None
        followups = ()
        plan_reason = "not_produced"
        try:
            with self.core.user_lock(job.user_key), rt.lock:
                state = rt.state.model_copy(deep=True)
                if job.kind != "end_consolidation":
                    # Freeze at execution, after the preceding serial job committed.
                    # Queue age is retained; only genuinely available new evidence advances source.
                    job = job.model_copy(
                        update={
                            "source_turn_id": state.latest_turn_id,
                            "source_user_index": state.user_turns,
                            "topic_revision": state.topic_revision,
                            "policy_revision": state.policy_revision,
                            "base_plan_version": state.support_plan_version,
                            "boundary_revision": self.store.revisions(job.user_key)[
                                "boundary_revision"
                            ],
                            "status": "running",
                            "started_at": utcnow(),
                        }
                    )
                    with self.store.transaction() as db:
                        db.execute(
                            "UPDATE cognitive_jobs SET data=?,source_turn_id=? WHERE job_id=?",
                            (job.model_dump_json(), job.source_turn_id, job.job_id),
                        )
                # Queue captures are immutable. Never relabel old evidence as a new source.
                state.latest_turn_id = job.source_turn_id
                state.user_turns = job.source_user_index
                rt.state.last_reasoner_user_index = max(
                    rt.state.last_reasoner_user_index, job.source_user_index
                )
            payload, bundle, allowed = self._payload(job, state)
            if job.kind in ("memory", "end_consolidation"):
                if any(k == "user_turn" for k, _ in allowed):
                    result, _ = self.agents.call(
                        job,
                        "end" if job.kind == "end_consolidation" else "memory",
                        Consolidation,
                        payload,
                        budget,
                    )
                    self._validate(job, result, allowed)
                    candidates, summary = result.memory_candidates, result.summary
                    followups = result.followups
                else:
                    summary = ""
            else:
                brief_future = None
                if job.kind == "deliberation":
                    # This payload has no analysis, candidate, cards or another role's conclusions.
                    brief_future = self.brief_pool.submit(
                        self.agents.call, job, "brief", ReviewBrief, payload, budget
                    )
                try:
                    analysis, _ = self.agents.call(
                        job, "analysis", SituationAssessment, payload, budget
                    )
                    self._validate(job, analysis, allowed)
                    if analysis.risk_review_requested:
                        self.core.request_risk_review(job.session_id, job.source_turn_id)
                    candidates = (*analysis.memory_candidates, *analysis.boundary_candidates)
                    brief = None
                    if brief_future:
                        brief, _ = brief_future.result(
                            timeout=max(0, budget.deadline - time.monotonic())
                        )
                        self._validate(job, brief, allowed)
                    selection = self.catalog.select(
                        analysis,
                        state,
                        " ".join(
                            row["text"] for row in payload["history"] if row["role"] == "user"
                        ),
                    )
                    strategy_cards = self.catalog.project(selection)
                    self.store.record_strategy_selection(job.job_id, selection)
                    planner_input = {
                        **payload,
                        "analysis": analysis.model_dump(mode="json"),
                        "cards": strategy_cards,
                        "catalog_version": selection.catalog_version,
                        "exercises": list(self.config.exercises),
                    }
                    candidate_id = uuid.uuid4().hex
                    review_id = None
                    review_status = "not_required"
                    for version in (1, 2):
                        candidate, _ = self.agents.call(
                            job,
                            "planner",
                            PlanCandidate,
                            planner_input,
                            budget,
                            candidate_version=version,
                        )
                        self._validate(job, candidate, allowed)
                        if any(
                            action.kind == "card" and action.action_id not in selection.selected_ids
                            for action in candidate.candidate_actions
                        ):
                            raise ValueError("Candidate action was excluded by strategy retrieval")
                        if job.kind == "routine":
                            if candidate.objective not in NON_ACTION or candidate.candidate_actions:
                                raise ValueError("Routine cannot propose action/information")
                            break
                        review_input = {
                            **payload,
                            "analysis": analysis.model_dump(mode="json"),
                            "brief": brief.model_dump(mode="json"),
                            "candidate_id": candidate_id,
                            "candidate_version": version,
                            "candidate": candidate.model_dump(mode="json"),
                            "cards": strategy_cards,
                            "exercises": list(self.config.exercises),
                        }
                        review, review_id = self.agents.call(
                            job,
                            "critic",
                            ReviewResult,
                            review_input,
                            budget,
                            candidate_version=version,
                        )
                        self._validate(job, review, allowed)
                        if (
                            review.candidate_id != candidate_id
                            or review.candidate_version != version
                        ):
                            raise ValueError("Review candidate/version mismatch")
                        if review.verdict == "approve" and not any(
                            i.severity == "blocking" for i in review.issues
                        ):
                            review_status = "approved"
                            break
                        if review.verdict == "revise" and version == 1:
                            planner_input = {
                                **planner_input,
                                "previous_candidate": candidate.model_dump(mode="json"),
                                "required_changes": review.required_changes,
                            }
                            continue
                        raise ValueError("Review did not approve exact final candidate")
                    dependencies = {
                        str(r.id) for r in evidence_in((candidate, analysis)) if r.kind == "memory"
                    }
                    plan = SupportPlan(
                        **candidate.model_dump(),
                        plan_id=candidate_id,
                        version=job.base_plan_version + 1,
                        candidate_version=version,
                        user_key=job.user_key,
                        session_id=job.session_id,
                        topic_revision=job.topic_revision,
                        source_turn_id=job.source_turn_id,
                        source_user_index=job.source_user_index,
                        checked_through_user_index=job.source_user_index,
                        policy_revision=job.policy_revision,
                        base_plan_version=job.base_plan_version,
                        boundary_revision=job.boundary_revision,
                        memory_dependency_versions=tuple(
                            (m.memory_id, m.version)
                            for m in (*bundle.items, *bundle.boundaries)
                            if m.memory_id in dependencies
                        ),
                        created_at=job.queued_at,
                        valid_until=job.queued_at
                        + timedelta(seconds=self.config.settings.cognition.plan_ttl_s),
                        max_user_turn_delta=self.config.settings.cognition.plan_turn_delta,
                        review_status=review_status,
                        review_run_id=review_id,
                        strategy_selection=selection,
                    )
                    plan, plan_reason = self._delta(job, plan, budget)
                finally:
                    if brief_future and not brief_future.done():
                        # Keep the per-user slot occupied until an actual HTTP call exits.
                        brief_future.result()
            budget.check()
            self.publish(
                job,
                state,
                plan,
                analysis,
                candidates,
                summary,
                allowed,
                plan_reason,
                budget,
                followups=followups,
            )
            if (
                job.kind in ("routine", "deliberation")
                and plan is None
                and plan_reason.startswith("delta_")
            ):
                current = self.core.sessions.get(job.session_id)
                if current and current.state.latest_turn_id > job.source_turn_id:
                    self.scheduler.submit(job.user_key, job.session_id, "delta_refresh")
        except Exception as error:
            logger.exception("Cognitive job %s failed", job.job_id)
            status = (
                "cancelled"
                if isinstance(error, JobCancelled) or cancel.is_set()
                else "timed_out"
                if isinstance(error, (TimeoutError, APITimeoutError))
                else "rejected"
                if isinstance(error, (ValueError, BudgetExceeded))
                else "failed"
            )
            # Sourced independent memories survive plan rejection/timeout, never cancellation.
            if candidates and status != "cancelled":
                self.publish(
                    job,
                    state,
                    None,
                    analysis,
                    candidates,
                    None,
                    allowed,
                    type(error).__name__ + ":" + str(error)[:240],
                    budget,
                    failure_status=status,
                )
            else:
                self.store.finish_job(
                    job.job_id,
                    status,
                    error=type(error).__name__ + ":" + str(error)[:240],
                    result={"budget": budget.report()},
                )
            if job.kind == "end_consolidation":
                self.store.fail_end(job.session_id, type(error).__name__)
                with rt.lock:
                    rt.state.lifecycle = "closed"
                self.core.sessions.pop(job.session_id, None)

    def _delta(self, job, plan, budget):
        rt = self.core.sessions[job.session_id]
        with self.core.user_lock(job.user_key), rt.lock:
            state = rt.state.model_copy(deep=True)
            invalid = plan_invalid_reason(
                plan,
                state,
                self.store.revisions(job.user_key),
                self.store.memory_items(job.user_key),
            )
        if invalid:
            return None, invalid
        if state.user_turns == job.source_user_index:
            return plan, "ready"
        rows = self.store.query(
            "SELECT id,text FROM turns WHERE session_id=? AND role='user' AND id>? AND id<=? ORDER BY id",
            (job.session_id, job.source_turn_id, state.latest_turn_id),
        )
        delta, _ = self.agents.call(
            job,
            "delta",
            DeltaResult,
            {"candidate": plan.model_dump(mode="json"), "new_turns": rows},
            budget,
        )
        self._validate(job, delta, {("user_turn", str(r["id"])) for r in rows})
        if delta.verdict != "compatible":
            return None, "delta_" + delta.verdict
        return plan.model_copy(
            update={"checked_through_user_index": state.user_turns}
        ), "delta_compatible"

    def publish(
        self,
        job,
        source_state,
        plan,
        analysis,
        candidates,
        summary,
        allowed,
        plan_reason,
        budget,
        failure_status=None,
        followups=(),
    ):
        rt = self.core.sessions.get(job.session_id)
        if rt is None:
            self.store.finish_job(job.job_id, "cancelled", error="session_removed")
            return
        with self.core.user_lock(job.user_key), rt.lock:
            with self.store.transaction() as db:
                state = rt.state
                if (
                    job.user_key in self.core.purging
                    or job.epoch != self.core.user_epochs.get(job.user_key, 0)
                    or budget.cancel.is_set()
                ):
                    self.store.finish_job(job.job_id, "cancelled", error="purge_or_cancel", db=db)
                    return
                if plan:
                    plan_reason = (
                        plan_invalid_reason(
                            plan,
                            state,
                            self.store.revisions(job.user_key, db),
                            self.store.memory_items(job.user_key, db),
                        )
                        or "accepted"
                    )
                    if (
                        state.support_plan_version != job.base_plan_version
                        or state.user_turns != plan.checked_through_user_index
                    ):
                        plan_reason = "final_cas_conflict"
                    if plan_reason != "accepted":
                        plan = None
                # Commit memories independently; newer sources/versions are checked per item.
                memory_results = self.memory.commit(
                    candidates, source_state, job.source_turn_id, allowed, db
                )
                if plan:
                    invalid_after_memory = plan_invalid_reason(
                        plan,
                        state,
                        self.store.revisions(job.user_key, db),
                        self.store.memory_items(job.user_key, db),
                    )
                    if invalid_after_memory:
                        plan, plan_reason = None, invalid_after_memory
                if (
                    plan
                    and self.store.revisions(job.user_key, db)["boundary_revision"]
                    != plan.boundary_revision
                ):
                    plan, plan_reason = None, "boundary_changed_in_publication"
                next_state = state.model_copy(deep=True)
                snapshot = None
                if plan:
                    assessment = Assessment(
                        pressure_types=tuple(
                            TypedConfidence(type=p, confidence=1) for p in analysis.pressure_types
                        ),
                        pathway_signals=analysis.pathway_signals,
                        seeker_state=SeekerState(
                            emotion_intensity=analysis.emotion_intensity,
                            readiness=analysis.readiness,
                        ),
                        user_pref="solve"
                        if analysis.expressed_need == "solve"
                        else "listen"
                        if analysis.expressed_need == "listen"
                        else "unknown",
                        user_state=analysis.topic_summary,
                    )
                    cards = tuple(a for a in plan.candidate_actions if a.kind == "card")
                    legacy = ReasonerOutput(
                        assessment=assessment,
                        cards=CardSelection(
                            allowed=tuple(a.action_id for a in cards),
                            preferred=cards[0].action_id if cards else None,
                            evidence=tuple(
                                CardEvidence(
                                    card_id=a.action_id,
                                    when_met=a.when_met,
                                    exclusions_present=a.exclusions_present,
                                    source_turn_ids=tuple(
                                        int(r.id) for r in a.evidence if r.kind == "user_turn"
                                    ),
                                )
                                for a in cards
                            ),
                        ),
                        offer_exercise=any(a.kind == "exercise" for a in plan.candidate_actions),
                    )
                    validated, rejections = self.core.validator.validate(
                        legacy,
                        state,
                        {int(i) for k, i in allowed if k == "user_turn"},
                        utcnow().date(),
                    )
                    if rejections or any(
                        a.action_id not in self.config.exercises
                        for a in plan.candidate_actions
                        if a.kind == "exercise"
                    ):
                        plan, plan_reason = None, "card_or_exercise_validation"
                    else:
                        db.execute(
                            "UPDATE support_plans SET status='superseded' WHERE session_id=? AND status='active'",
                            (job.session_id,),
                        )
                        db.execute(
                            "INSERT INTO support_plans VALUES (?,?,?,?,?,?,?)",
                            (
                                plan.plan_id,
                                plan.version,
                                plan.user_key,
                                plan.session_id,
                                plan.status,
                                plan.valid_until.isoformat(),
                                plan.model_dump_json(),
                            ),
                        )
                        next_state.active_support_plan_id = plan.plan_id
                        next_state.support_plan_version = plan.version
                        snapshot = Snapshot(
                            session_id=job.session_id,
                            user_key=job.user_key,
                            version=rt.snapshot.version + 1,
                            source_turn_id=job.source_turn_id,
                            trigger=",".join(job.triggers),
                            assessment=validated.assessment,
                            allowed_cards=validated.cards.allowed,
                            preferred_card=validated.cards.preferred,
                            offer_exercise=validated.offer_exercise,
                            support_plan_id=plan.plan_id,
                            support_plan_version=plan.version,
                        )
                        db.execute(
                            "INSERT INTO snapshots VALUES (?,?,?,?,?,?,?)",
                            (
                                snapshot.session_id,
                                snapshot.version,
                                snapshot.user_key,
                                snapshot.source_turn_id,
                                snapshot.model_dump_json(),
                                snapshot.trigger,
                                utcnow().isoformat(),
                            ),
                        )
                summary_result = "not_produced"
                if job.kind == "end_consolidation" and summary is not None:
                    end = db.execute(
                        "SELECT final_turn_id,status FROM end_tasks WHERE session_id=?",
                        (job.session_id,),
                    ).fetchone()
                    if end and end[0] == job.source_turn_id and end[1] == "pending":
                        proposals = MemoryUpdate(
                            followups=tuple(
                                Followup(
                                    content=f.content,
                                    due_date=f.due_date,
                                    importance=f.importance,
                                    source_turn_ids=tuple(
                                        int(r.id) for r in f.evidence if r.kind == "user_turn"
                                    ),
                                )
                                for f in followups
                            )
                        )
                        validated_end, _ = self.core.validator.validate(
                            ReasonerOutput(memory=proposals),
                            source_state,
                            {int(i) for k, i in allowed if k == "user_turn"},
                            utcnow().date(),
                            ending=True,
                        )
                        self.store._write_memory(db, job.user_key, validated_end.memory)
                        db.execute(
                            "UPDATE sessions SET summary=?,lifecycle='closed' WHERE session_id=?",
                            (summary, job.session_id),
                        )
                        db.execute(
                            "UPDATE end_tasks SET status='done',last_error=NULL,attempt_count=attempt_count+1,updated_at=? WHERE session_id=?",
                            (utcnow().isoformat(), job.session_id),
                        )
                        next_state.lifecycle = "closed"
                        summary_result = "accepted"
                accepted_memory = any(
                    r.startswith(("accepted:", "duplicate:")) for r in memory_results
                )
                rejected_memory = any(r.startswith("rejected:") for r in memory_results)
                goal = (
                    bool(plan)
                    if job.kind in ("routine", "deliberation")
                    else summary_result == "accepted"
                    if job.kind == "end_consolidation"
                    else accepted_memory
                )
                status = (
                    "completed"
                    if goal and not rejected_memory
                    else "partial"
                    if goal or accepted_memory
                    else failure_status or "superseded"
                    if plan_reason == "final_cas_conflict"
                    else failure_status or "rejected"
                )
                self.store.save_state(next_state)
                self.store.finish_job(
                    job.job_id,
                    status,
                    result={
                        "plan": plan_reason,
                        "memory": memory_results,
                        "summary": summary_result,
                        "budget": budget.report(),
                    },
                    db=db,
                )
            rt.state = next_state
            if snapshot:
                rt.snapshot = snapshot
        if next_state.lifecycle == "closed":
            with self.core.registry_lock:
                self.core.sessions.pop(job.session_id, None)

    def close(self):
        self.scheduler.close()
        self.brief_pool.shutdown(wait=True)
        if self.llm is not self.core.llm:
            self.llm.close()
