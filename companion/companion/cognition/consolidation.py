"""Source-bound extraction, bounded claim review and verbatim session summaries."""

import logging

from openai import APIError

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
                "hypothesis": f"用户的{candidate.key}是{candidate.value}。",
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
        return (
            tuple(item for index, item in enumerate(candidates) if ("memory", index) in accepted),
            tuple(item for index, item in enumerate(followups) if ("followup", index) in accepted),
            {
                "status": "passed" if accepted == expected else "filtered",
                "decisions": [item.model_dump(mode="json") for item in review.decisions],
            },
        )
