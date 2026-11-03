"""Deterministic consent and dialogue transitions."""

import re
import time
import uuid

from .config import Config
from .models import PendingOffer, RuleResult, SessionState, Snapshot, Stage, TurnSignals

Q_TRANSITIONS = {
    (Stage.explore, Stage.comfort),
    (Stage.comfort, Stage.permission),
    (Stage.action, Stage.closing),
    (Stage.comfort, Stage.explore),
    (Stage.permission, Stage.explore),
    (Stage.action, Stage.explore),
    (Stage.closing, Stage.explore),
}


class StateMachine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.rules = {
            name: tuple(re.compile(p) for p in patterns)
            for name, patterns in config.rules["transitions"].items()
        }

    def matches(self, name: str, text: str) -> bool:
        return any(pattern.search(text.strip()) for pattern in self.rules[name])

    @staticmethod
    def can_reasoner_transition(current: Stage, target: Stage) -> bool:
        return (current, target) in Q_TRANSITIONS

    @staticmethod
    def move(state: SessionState, target: Stage) -> None:
        if state.stage != target:
            if state.stage in (Stage.action, Stage.quiet) or target in (Stage.action, Stage.quiet):
                state.policy_revision += 1
            state.stage = target
            state.state_revision += 1
            if target == Stage.closing:
                state.closing_turns = 0
        if target != Stage.action:
            state.card_in_use = None
            state.action_id = None
            state.action_turns = 0

    def offer(self, state: SessionState, kind: str, target: str | None = None) -> None:
        state.pending_offer = PendingOffer(
            offer_id=uuid.uuid4().hex,
            kind=kind,
            target_id=target,
            topic_revision=state.topic_revision,
            offered_turn_id=state.latest_turn_id,
            offered_user_index=state.user_turns,
        )
        if kind == "action":
            state.permission_asked_topic = state.topic_revision

    def eligible(self, state: SessionState, snapshot: Snapshot) -> list[str]:
        if snapshot.assessment.seeker_state.emotion_intensity == "high":
            return []
        result = []
        for identifier in snapshot.allowed_cards:
            card = self.config.cards.get(identifier)
            if (
                card
                and card.status != "draft"
                and (
                    card.status != "enabled"
                    or self.config.content_reviewed(f"cards/{identifier}.yaml")
                )
                and identifier not in state.cards_refused
                and state.cards_used.get(identifier, 0) < card.limits["per_session"]
                and snapshot.assessment.seeker_state.emotion_intensity
                not in card.constraints.get("excluded_emotion_intensities", [])
                and snapshot.assessment.seeker_state.readiness
                not in card.constraints.get("excluded_readiness", [])
            ):
                result.append(identifier)
        return result

    def apply_rules(
        self,
        state: SessionState,
        text: str,
        signals: TurnSignals,
        snapshot: Snapshot,
        now: float | None = None,
    ) -> RuleResult:
        now = time.monotonic() if now is None else now
        settings = self.config.settings.dialogue
        refusal = self.matches("refuse", text)
        correction = self.matches("correct", text)
        triggers = ["correction"] if correction else []
        crying = "Cry" in signals.events
        if crying:
            triggers.append("cry")
        if refusal:
            triggers.append("refusal")
        if self.matches("quiet", text):
            state.pending_offer = None
            self.move(state, Stage.quiet)
            return RuleResult(
                fired_rules=("R4",), trigger_reasons=tuple(triggers), directive="quiet"
            )
        if self.matches("change_topic", text):
            state.topic_revision += 1
            state.pending_offer = None
            self.move(state, Stage.explore)
            return RuleResult(fired_rules=("topic_changed",), trigger_reasons=("topic_changed",))
        if state.stage == Stage.action and (crying or refusal or correction):
            if refusal and state.card_in_use:
                state.cards_refused.add(state.card_in_use)
            state.pending_offer = None
            self.move(state, Stage.explore)
            return RuleResult(fired_rules=("R6",), trigger_reasons=tuple(triggers))
        if (
            snapshot.version > state.applied_snapshot_version
            and snapshot.topic_changed
            and snapshot.stage_proposal
            and snapshot.stage_proposal.to == Stage.explore
            and self.can_reasoner_transition(state.stage, Stage.explore)
        ):
            state.applied_snapshot_version = snapshot.version
            state.topic_revision += 1
            state.pending_offer = None
            self.move(state, Stage.explore)
            return RuleResult(fired_rules=("Q4",), trigger_reasons=("topic_changed",))
        offer = state.pending_offer
        if offer:
            expired = offer.topic_revision != state.topic_revision
            if offer.accepted_at is not None:
                expired |= now - offer.accepted_at >= settings.accepted_wait_s
                expired |= (
                    state.user_turns - offer.accepted_user_index > settings.accepted_wait_turns
                )
            else:
                expired |= state.user_turns - offer.offered_user_index > settings.offer_valid_turns
            if offer.kind == "action" and (
                crying or correction or snapshot.assessment.seeker_state.emotion_intensity == "high"
            ):
                expired = True
            if refusal or expired:
                if refusal and offer.target_id and offer.kind == "action":
                    state.cards_refused.add(offer.target_id)
                if refusal and offer.target_id and offer.kind in ("exercise", "resume_exercise"):
                    state.exercises_refused.add(offer.target_id)
                state.pending_offer = None
                self.move(state, Stage.explore)
                return RuleResult(
                    fired_rules=("R3",), trigger_reasons=tuple(triggers), directive="offer_expired"
                )
            if offer.active and self.matches("agree", text):
                if offer.kind in ("exercise", "resume_exercise"):
                    state.mode = "exercise"
                    state.policy_revision += 1
                    state.pending_offer = None
                    return RuleResult(
                        fired_rules=("exercise_accepted",), directive=f"exercise:{offer.target_id}"
                    )
                offer.accepted_at = now
                offer.accepted_user_index = state.user_turns
                offer.status = "accepted_waiting_card"
            if offer.status == "accepted_waiting_card":
                exercise_id = snapshot.preferred_exercise
                if (
                    snapshot.offer_exercise
                    and exercise_id in self.config.exercises
                    and exercise_id not in state.exercises_refused
                ):
                    # A generic request for help is not consent to a particular exercise.
                    self.offer(state, "exercise", exercise_id)
                    return RuleResult(directive="exercise_offer")
                cards = self.eligible(state, snapshot)
                if cards:
                    selected = (
                        snapshot.preferred_card if snapshot.preferred_card in cards else cards[0]
                    )
                    self.move(state, Stage.action)
                    state.card_in_use = selected
                    state.action_id = uuid.uuid4().hex
                    state.pending_offer = None
                    return RuleResult(fired_rules=("R2",), trigger_reasons=tuple(triggers))
                return RuleResult(
                    trigger_reasons=tuple(triggers + ["missing_card"]), directive="waiting_card"
                )
            return RuleResult(trigger_reasons=tuple(triggers), directive="clarify_offer")
        card = self.config.cards.get(state.card_in_use)
        action_limit = (
            min(settings.max_action_turns, len(card.talker.steps))
            if card
            else settings.max_action_turns
        )
        if state.stage == Stage.action and state.action_turns >= action_limit:
            self.move(state, Stage.closing)
            return RuleResult(fired_rules=("R8",), trigger_reasons=tuple(triggers))
        if state.stage == Stage.closing and state.closing_turns >= 2:
            self.move(state, Stage.quiet)
            return RuleResult(fired_rules=("closing_limit",), directive="quiet")
        if (
            (self.matches("ask", text) or re.search(r"(?:想|要|可以).*(?:做|试).{0,8}练习", text))
            and not refusal
            and state.stage in (Stage.explore, Stage.comfort, Stage.quiet, Stage.opening)
        ):
            self.move(state, Stage.permission)
            self.offer(state, "action")
            return RuleResult(
                fired_rules=("R1",),
                trigger_reasons=tuple(triggers + ["ask_for_help"]),
                directive="action_offer",
            )
        if crying and not refusal:
            # Crying requests reassessment; it does not establish that body focus is suitable.
            self.move(state, Stage.comfort)
            return RuleResult(trigger_reasons=tuple(triggers))
        if state.resume_script_id and not refusal and not correction:
            self.offer(state, "resume_exercise", state.resume_script_id)
            state.resume_script_id = None
            return RuleResult(directive="resume_offer")
        if state.stage == Stage.quiet:
            if len(text.strip()) >= 15 and not refusal:
                self.move(state, Stage.explore)
                return RuleResult(fired_rules=("R5",), trigger_reasons=tuple(triggers))
            return RuleResult(trigger_reasons=tuple(triggers), directive="quiet")
        if snapshot.version > state.applied_snapshot_version:
            state.applied_snapshot_version = snapshot.version
            proposal = snapshot.stage_proposal
            if (
                proposal
                and not (refusal or correction)
                and self.can_reasoner_transition(state.stage, proposal.to)
            ):
                if proposal.to == Stage.permission:
                    if (
                        snapshot.assessment.seeker_state.emotion_intensity != "high"
                        and state.permission_asked_topic != state.topic_revision
                    ):
                        self.move(state, Stage.permission)
                        self.offer(state, "action")
                        return RuleResult(
                            fired_rules=("Q2",),
                            trigger_reasons=tuple(triggers),
                            directive="action_offer",
                        )
                else:
                    self.move(state, proposal.to)
                    return RuleResult(fired_rules=("Q",), trigger_reasons=tuple(triggers))
        if state.stage == Stage.opening:
            self.move(state, Stage.explore)
        return RuleResult(trigger_reasons=tuple(triggers))
