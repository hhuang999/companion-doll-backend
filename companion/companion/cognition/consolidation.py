"""Source-bound extraction, bounded claim review and verbatim session summaries."""

import logging

from openai import APIError

from .base import EvidenceRef
from .budget import BudgetExceeded, JobCancelled
from .models import GroundingReview

logger = logging.getLogger(__name__)


def validate_summary_sources(proposal):
    for reference in proposal.summary_evidence:
        if reference.kind != "user_turn":
            raise ValueError("Summary evidence requires a user turn")


def bind_quotes(references, history):
    """Fill omitted excerpts from already validated, frozen user source IDs."""
    sources = {str(row["id"]): row["text"] for row in history if row["role"] == "user"}
    return tuple(
        ref.model_copy(update={"quote": sources[str(ref.id)][:300]})
        if ref.kind == "user_turn" and not ref.quote
        else ref
        for ref in references
    )


def extractive_summary(references):
    """Render verified excerpts without accepting a separate model-written assertion."""
    quotes = list(dict.fromkeys(ref.quote for ref in references))
    if not quotes:
        return ""
    text = "；".join(f"“{quote}”" for quote in quotes)
    prefix = "用户原话："
    limit = 150 - len(prefix)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return prefix + text


class ConsolidationGrounder:
    def __init__(self, agents):
        self.agents = agents

    def filter(self, job, candidates, followups, payload, budget):
        candidates = tuple(
            item.model_copy(
                update={"source_refs": bind_quotes(item.source_refs, payload["history"])}
            )
            for item in candidates
        )
        followups = tuple(
            item.model_copy(update={"evidence": bind_quotes(item.evidence, payload["history"])})
            for item in followups
        )
        source_ids = {
            (ref.kind, str(ref.id)) for item in candidates for ref in item.source_refs
        } | {(ref.kind, str(ref.id)) for item in followups for ref in item.evidence}
        claims = [
            {
                "kind": "memory",
                "index": index,
                "hypothesis": (
                    f"用户的{candidate.key}是{candidate.value}。"
                    if candidate.kind == "fact_preference"
                    else candidate.value
                ),
                "source_ids": [{"kind": ref.kind, "id": ref.id} for ref in candidate.source_refs],
            }
            for index, candidate in enumerate(candidates)
        ] + [
            {
                "kind": "followup",
                "index": index,
                "hypothesis": (
                    f"用户明确提到的未来事件支持在{followup.due_date}跟进：{followup.content}。"
                ),
                "source_ids": [{"kind": ref.kind, "id": ref.id} for ref in followup.evidence],
            }
            for index, followup in enumerate(followups)
        ]
        if not claims:
            return (), (), {"status": "not_needed", "decisions": []}
        expected = {(claim["kind"], claim["index"]) for claim in claims}

        def validate(review):
            actual = [(item.kind, item.index) for item in review.decisions]
            if len(actual) != len(expected) or set(actual) != expected:
                raise ValueError("Grounding decisions must cover each exact candidate once")
            if any(
                item.kind == "memory" and item.verdict == "entailed" and item.memory_type is None
                for item in review.decisions
            ):
                raise ValueError("Memory decisions require a semantic memory type")

        try:
            review, _ = self.agents.call(
                job,
                "memory",
                GroundingReview,
                {
                    "phase": "grounding",
                    "history": [
                        row
                        for row in payload["history"]
                        if row["role"] == "user" and ("user_turn", str(row["id"])) in source_ids
                    ],
                    "memory": [
                        item
                        for item in payload["memory"]
                        if ("memory", item["memory_id"]) in source_ids
                    ],
                    "feedback": [
                        item
                        for item in payload["feedback"]
                        if ("interaction_event", item["event_id"]) in source_ids
                    ],
                    "today": payload["today"],
                    "claims": claims,
                },
                budget,
                validate=validate,
            )
            budget.check()
        except JobCancelled:
            raise
        except (TimeoutError, APIError, BudgetExceeded, ValueError) as error:
            # A repair and a review share the same two-call budget. Unreviewed
            # claims stay out; verified raw excerpts can still close the session.
            logger.warning("Consolidation review unavailable: %s", type(error).__name__)
            return (
                (),
                (),
                {
                    "status": "unavailable",
                    "decisions": [],
                    "error": type(error).__name__ + ":" + str(error)[:240],
                },
            )
        accepted = {
            (item.kind, item.index) for item in review.decisions if item.verdict == "entailed"
        }
        classified = {
            item.index: item.memory_type for item in review.decisions if item.kind == "memory"
        }

        def normalize(index, candidate):
            # Typed controls and attributed feedback retain their existing contracts.
            if (
                candidate.kind == "interaction_boundary"
                or candidate.support
                or candidate.feedback_valence != "unknown"
            ):
                return candidate
            category = classified[index]
            excerpts = tuple(ref for ref in candidate.source_refs if ref.kind == "user_turn")
            quoted = (
                {
                    "value": extractive_summary(excerpts),
                    "key": "user_turn:" + ",".join(str(ref.id) for ref in excerpts),
                }
                if excerpts
                else {}
            )
            if category == "session_context":
                changes = {"kind": "fact_preference", **quoted}
                if candidate.scope == "persistent":
                    changes.update(scope="session", scope_ref=None)
                return candidate.model_copy(update=changes)
            if candidate.kind == "support_experience" or category == "support_feedback":
                turn_ids = {str(ref.id) for ref in candidate.source_refs if ref.kind == "user_turn"}
                events = [
                    event
                    for event in payload["feedback"]
                    if event["event_type"] == "explicit_feedback"
                    and event["payload"]["attribution"] == "explicit"
                    and str(event["turn_id"]) in turn_ids
                ]
                if len(events) == 1:
                    event = events[0]
                    # Core owns attribution. Recover its identity even when the
                    # extractor omitted the event reference or renamed the key.
                    return type(candidate).model_validate(
                        {
                            **candidate.model_dump(),
                            "kind": "support_experience",
                            "support": event["payload"].get("support"),
                            "feedback_valence": event["payload"]["valence"],
                            "value": event["payload"]["text"] or candidate.value,
                            "source_refs": (
                                next(
                                    ref
                                    for ref in candidate.source_refs
                                    if ref.kind == "user_turn"
                                    and str(ref.id) == str(event["turn_id"])
                                ),
                                EvidenceRef(
                                    kind="interaction_event",
                                    id=event["event_id"],
                                    claim="Core 明确反馈归因",
                                ),
                            ),
                        }
                    )
            if category == "episode":
                return candidate.model_copy(update={"kind": "episodic_event", **quoted})
            return candidate

        return (
            tuple(
                normalize(index, item)
                for index, item in enumerate(candidates)
                if ("memory", index) in accepted
            ),
            tuple(item for index, item in enumerate(followups) if ("followup", index) in accepted),
            {
                "status": "passed" if accepted == expected else "filtered",
                "decisions": [item.model_dump(mode="json") for item in review.decisions],
            },
        )
