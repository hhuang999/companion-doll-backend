"""Validate model proposals against current session and source evidence."""

from datetime import date

from .config import Config
from .models import CardSelection, MemoryUpdate, ReasonerOutput, Rejection, SessionState
from .state_machine import StateMachine


class Validator:
    def __init__(self, config: Config) -> None:
        self.config = config

    def validate(
        self,
        output: ReasonerOutput,
        state: SessionState,
        source_ids: set[int],
        today: date,
        *,
        ending: bool = False,
    ) -> tuple[ReasonerOutput, list[Rejection]]:
        rejected = []

        def reject(rule: str, detail: str) -> None:
            rejected.append(Rejection(rule=rule, detail=detail))

        def sourced(item: object) -> bool:
            identifiers = item.source_turn_ids
            valid = bool(identifiers) and set(identifiers) <= source_ids
            if not valid:
                reject("V6", type(item).__name__)
            return valid

        proposal = output.stage_proposal
        if proposal and (
            not sourced(proposal)
            or not StateMachine.can_reasoner_transition(state.stage, proposal.to)
        ):
            reject("V2", proposal.to.value)
            proposal = None
        assessment = output.assessment
        pressure = {item.type for item in assessment.pressure_types}
        pathways = set(assessment.pathway_signals)
        allowed = []
        evidence = {item.card_id: item for item in output.cards.evidence}
        for identifier in dict.fromkeys(output.cards.allowed):
            card = self.config.cards.get(identifier)
            item = evidence.get(identifier)
            if (
                not card
                or card.status == "draft"
                or (
                    card.status == "enabled"
                    and not self.config.content_reviewed(f"cards/{identifier}.yaml")
                )
                or not item
                or not sourced(item)
                or not item.when_met
                or item.exclusions_present
            ):
                reject("V3", identifier)
                continue
            targets = card.targets
            if (targets.pressure_types or targets.pathways) and not (
                pressure.intersection(targets.pressure_types)
                or pathways.intersection(targets.pathways)
            ):
                reject("V3", identifier)
                continue
            if (
                identifier in state.cards_refused
                or state.cards_used.get(identifier, 0) >= card.limits["per_session"]
                or assessment.seeker_state.emotion_intensity
                in card.constraints.get("excluded_emotion_intensities", [])
                or assessment.seeker_state.readiness
                in card.constraints.get("excluded_readiness", [])
            ):
                reject("V4", identifier)
                continue
            allowed.append(identifier)
        preferred = output.cards.preferred
        if preferred not in allowed:
            if preferred:
                reject("V5", preferred)
            preferred = allowed[0] if allowed else None
        profiles = tuple(item for item in output.memory.profile_updates if sourced(item))
        events = []
        for item in output.memory.events:
            if not sourced(item):
                continue
            if item.date:
                try:
                    date.fromisoformat(item.date)
                except ValueError:
                    reject("V1", "event_date")
                    continue
            events.append(item)
        followups = []
        for item in output.memory.followups:
            if not sourced(item):
                continue
            try:
                if date.fromisoformat(item.due_date) < today:
                    raise ValueError("past due date")
            except ValueError:
                reject("V7", item.content)
                continue
            followups.append(item)
        followups.sort(key=lambda item: -item.importance)
        for item in followups[2:]:
            reject("V7", item.content)
        memory = MemoryUpdate(
            profile_updates=profiles,
            events=tuple(events),
            followups=tuple(followups[:2]),
            followup_results=tuple(
                item for item in output.memory.followup_results if sourced(item)
            ),
        )
        cards = CardSelection(
            allowed=tuple(allowed),
            preferred=preferred,
            evidence=tuple(evidence[i] for i in allowed),
        )
        exercise = output.offer_exercise
        if state.mode == "crisis" or ending:
            if proposal or cards.allowed or exercise:
                reject("V8", "strategy_update")
            proposal, cards, exercise = None, CardSelection(), False
        return output.model_copy(
            update={
                "stage_proposal": proposal,
                "cards": cards,
                "offer_exercise": exercise,
                "memory": memory,
                "session_summary": output.session_summary if ending else None,
            }
        ), rejected
