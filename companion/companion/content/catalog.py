"""Filter before ranking: semantic relevance never grants permission."""

from .models import SelectionDecision, StrategySelection


class StrategyCatalog:
    def __init__(self, config):
        self.config = config

    def select(self, assessment, state, text: str, *, limit: int = 3) -> StrategySelection:
        decisions = []
        pressure, pathways = set(assessment.pressure_types), set(assessment.pathway_signals)
        for card in self.config.cards.values():
            reasons = []
            protocol = card.protocol
            if card.status == "draft":
                reasons.append("draft")
            if card.status == "enabled" and not self.config.content_reviewed(
                f"cards/{card.id}.yaml"
            ):
                reasons.append("content_not_checked")
            if card.id in state.cards_refused:
                reasons.append("refused_this_session")
            if state.cards_used.get(card.id, 0) >= card.limits["per_session"]:
                reasons.append("session_limit")
            if assessment.emotion_intensity in card.constraints.get(
                "excluded_emotion_intensities", []
            ):
                reasons.append("emotion_excluded")
            if assessment.readiness in card.constraints.get("excluded_readiness", []):
                reasons.append("readiness_excluded")
            if assessment.expressed_need in ("listen", "quiet"):
                reasons.append("current_need_has_no_action")
            if protocol and set(protocol.excluded_contexts).intersection(
                assessment.support_constraints
            ):
                reasons.append("context_excluded")
            matched = pressure.intersection(card.targets.pressure_types)
            matched_paths = pathways.intersection(card.targets.pathways)
            if (card.targets.pressure_types or card.targets.pathways) and not (
                matched or matched_paths
            ):
                reasons.append("no_target_match")
            # Chinese lexical ties are only ranked after all business exclusions.
            score = len(matched) * 2 + len(matched_paths) * 3
            if protocol:
                score += min(3, sum(word in text for word in protocol.keywords))
            decisions.append(
                SelectionDecision(
                    strategy_id=card.id,
                    version=protocol.version if protocol else "legacy-fixture",
                    eligible=not reasons,
                    reasons=tuple(reasons) or ("target_and_constraints_matched",),
                    score=score,
                )
            )
        ranked = sorted(
            (d for d in decisions if d.eligible), key=lambda d: (-d.score, d.strategy_id)
        )
        return StrategySelection(
            catalog_version=self.config.content.version if self.config.content else "legacy",
            selected_ids=tuple(d.strategy_id for d in ranked[:limit]),
            decisions=tuple(decisions),
        )

    def project(self, selection: StrategySelection) -> list[dict]:
        result = []
        for identifier in selection.selected_ids:
            card = self.config.cards[identifier]
            value = card.model_dump(
                include={
                    "id",
                    "name",
                    "status",
                    "requires_permission",
                    "targets",
                    "constraints",
                    "reasoner",
                    "limits",
                }
            )
            if card.protocol:
                value["protocol"] = card.protocol.model_dump(
                    include={
                        "version",
                        "mechanism",
                        "evidence_ids",
                        "prerequisites",
                        "excluded_contexts",
                        "burden",
                        "stop",
                        "feedback_limits",
                    }
                )
            result.append(value)
        return result
