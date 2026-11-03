"""Local plan selection. No network or background Future is awaited."""

import json

from companion.memory.models import MemoryCandidate
from companion.memory.service import estimate_tokens

from .base import utcnow
from .models import TurnPolicyFrame

NON_ACTION = {"listen", "clarify", "comfort", "reflect", "quiet"}


def plan_invalid_reason(plan, state, revisions, items, now=None):
    if plan is None:
        return "no_plan"
    now = now or utcnow()
    if state.lifecycle != "active" or state.mode != "normal":
        return "lifecycle_or_mode"
    if plan.user_key != state.user_key or plan.session_id != state.session_id:
        return "identity"
    if plan.status != "active":
        return plan.status
    if (
        plan.valid_until <= now
        or state.user_turns - plan.source_user_index > plan.max_user_turn_delta
    ):
        return "expired"
    if plan.topic_revision != state.topic_revision or plan.policy_revision != state.policy_revision:
        return "control_revision"
    if plan.boundary_revision != revisions["boundary_revision"]:
        return "boundary_revision"
    versions = {item.memory_id: item.version for item in items if item.status == "active"}
    if any(versions.get(i) != v for i, v in plan.memory_dependency_versions):
        return "memory_dependency"
    return None


def effective_boundaries(bundle):
    # A scoped latest exception masks a restriction without deleting its record.
    ordered = sorted(bundle.boundaries, key=lambda item: item.source_cursor, reverse=True)
    exceptions = {}
    result = []
    for item in ordered:
        if item.boundary_rule in ("allow", "revoke"):
            exceptions.setdefault(item.target, item.source_cursor)
        elif exceptions.get(item.target, -1) < item.source_cursor:
            result.append(item)
    return tuple(result)


def build_turn_policy(state, plan, bundle, all_items, *, now=None):
    boundaries = effective_boundaries(bundle)
    reason = plan_invalid_reason(plan, state, bundle.model_dump(), all_items, now)
    objective = "quiet" if state.stage.value == "quiet" else "listen"
    guidance = ()
    actions = ()
    avoid = ()
    question = None
    if not reason:
        checked = plan.checked_through_user_index >= state.user_turns
        objective = plan.objective if checked else "listen"
        guidance = (
            plan.response_guidance
            if checked
            else ("承接当前原话，先理解感受，不引入旧话题或新建议。",)
        )
        reason = "verified" if checked else "unchecked_delta_non_action"
        actions = tuple(a.action_id for a in plan.candidate_actions) if checked else ()
        if checked:
            avoid, question = plan.avoid, plan.open_question
            if any(a.kind == "no_advice" for a in avoid):
                actions = ()
                if objective not in NON_ACTION:
                    objective = "listen"
            actions = tuple(
                identifier
                for identifier in actions
                if not any(
                    a.kind == "no_repeat_offer" and a.target in (None, identifier) for a in avoid
                )
            )
    if boundaries:
        actions = ()
        if objective not in NON_ACTION:
            objective = "listen"
    return TurnPolicyFrame(
        effective_support_plan_id=plan.plan_id
        if plan and reason in ("verified", "unchecked_delta_non_action")
        else None,
        effective_support_plan_version=plan.version
        if plan and reason in ("verified", "unchecked_delta_non_action")
        else None,
        objective=objective,
        response_guidance=guidance,
        avoid=avoid,
        open_question=question,
        active_boundaries=tuple(
            MemoryCandidate.model_validate(b.model_dump(include=set(MemoryCandidate.model_fields)))
            for b in boundaries
        ),
        allowed_action_ids=actions,
        memory_projection=bundle,
        selection_reason=reason or "safe_default",
        checked_through_user_index=plan.checked_through_user_index if plan else 0,
    )


def prompt_projection(frame, budget=1200):
    from companion.memory.service import MemoryService

    value = {
        "objective": frame.objective,
        "guidance": frame.response_guidance,
        "avoid": [a.model_dump() for a in frame.avoid],
        "open_question": frame.open_question,
        "selection": frame.selection_reason,
        "boundaries": [
            {"rule": b.boundary_rule, "target": b.target, "scope": b.scope}
            for b in frame.active_boundaries
        ],
        "allowed_actions": frame.allowed_action_ids,
        "memory": [MemoryService.project(m) for m in frame.memory_projection.items],
    }
    while value["memory"] and estimate_tokens(value) > budget:
        value["memory"].pop()
    while value["guidance"] and estimate_tokens(value) > budget:
        value["guidance"] = value["guidance"][:-1]
    # Boundaries are mandatory. If extremely many exist, retain a conservative typed union.
    if estimate_tokens(value) > budget:
        value["boundaries"] = [
            {"rule": rule, "target": "all_topics", "scope": "current_turn"}
            for rule in sorted({b["rule"] for b in value["boundaries"]})
        ]
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
