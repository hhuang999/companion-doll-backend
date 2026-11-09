"""Sourced memory commits and bounded Chinese-aware retrieval."""

import json
import re
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from companion.cognition.base import EvidenceRef, utcnow

from .models import MemoryBundle, MemoryCandidate, MemoryItem


def estimate_tokens(value: object) -> int:
    # Conservative reservation heuristic: 2 tokens/non-ASCII character and
    # 1 token/2 ASCII characters plus message overhead. Provider usage is authoritative.
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    ascii_count = sum(ord(char) < 128 for char in text)
    return (ascii_count + 1) // 2 + 2 * (len(text) - ascii_count) + 32


def terms(text):
    words = set(re.findall(r"[a-z0-9_]+", text.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        words.update(run[i : i + 2] for i in range(len(run) - 1))
    return words


def applicable(item, state, now):
    if (
        item.status != "active"
        or item.valid_from > now
        or (item.expires_at and item.expires_at <= now)
    ):
        return False
    return {
        "persistent": True,
        "until_time": True,
        "session": item.scope_ref == state.session_id,
        "topic": item.scope_ref == f"{state.session_id}:{state.topic_revision}",
        "turn": item.scope_ref == f"{state.session_id}:{state.latest_turn_id}",
    }[item.scope]


class MemoryService:
    def __init__(self, store, timezone_name="Asia/Shanghai", clock=utcnow):
        self.store, self.timezone, self.clock = store, ZoneInfo(timezone_name), clock

    def scope_candidate(self, candidate, state):
        refs = {
            "session": state.session_id,
            "topic": f"{state.session_id}:{state.topic_revision}",
            "turn": f"{state.session_id}:{state.latest_turn_id}",
        }
        if candidate.scope in refs:
            if candidate.scope_ref and candidate.scope_ref != refs[candidate.scope]:
                raise ValueError("Memory scope does not match source context")
            return candidate.model_copy(update={"scope_ref": refs[candidate.scope]})
        return candidate

    def commit(self, candidates, state, source_cursor, allowed=None, db=None):
        if db is None:
            with self.store.transaction() as connection:
                return self.commit(candidates, state, source_cursor, allowed, connection)
        results = []
        changed = boundary_changed = False
        for candidate in candidates:
            try:
                candidate = self.scope_candidate(candidate, state)
                self.store.validate_refs(state.user_key, candidate.source_refs, allowed, db)
                if candidate.support or candidate.feedback_valence != "unknown":
                    events = [
                        json.loads(
                            db.execute(
                                "SELECT data FROM interaction_events WHERE event_id=? AND user_key=?",
                                (str(ref.id), state.user_key),
                            ).fetchone()[0]
                        )
                        for ref in candidate.source_refs
                        if ref.kind == "interaction_event"
                    ]
                    if candidate.kind != "support_experience" or not any(
                        event["event_type"] == "explicit_feedback"
                        and event["payload"]["attribution"] == "explicit"
                        and event["payload"]["valence"] == candidate.feedback_valence
                        and event["payload"].get("support")
                        == (candidate.support.model_dump() if candidate.support else None)
                        for event in events
                    ):
                        raise ValueError("Support attribution requires matching explicit feedback")
                for ref in candidate.source_refs:
                    if (
                        ref.kind == "memory"
                        and not db.execute(
                            "SELECT 1 FROM memory_items WHERE memory_id=? AND user_key=? AND status='active'",
                            (str(ref.id), state.user_key),
                        ).fetchone()
                    ):
                        raise ValueError("Referenced memory has been corrected")
                if candidate.epistemic_status in ("hypothesized", "legacy_unverified"):
                    raise ValueError("Unconfirmed candidate cannot become a long-term fact")
                if candidate.expires_at and candidate.expires_at <= self.clock():
                    raise ValueError("Memory scope expired")
                # Observed execution is distinct from explicit subjective benefit.
                if candidate.kind in ("interaction_boundary", "fact_preference") and not any(
                    ref.kind == "user_turn" for ref in candidate.source_refs
                ):
                    raise ValueError("Boundary/preference requires explicit user evidence")
                if (
                    candidate.kind == "support_experience"
                    and candidate.epistemic_status == "stated"
                    and not any(ref.kind == "user_turn" for ref in candidate.source_refs)
                ):
                    raise ValueError("Support benefit requires user evidence")
                corrected = db.execute(
                    "SELECT source_turn_id FROM memory_corrections WHERE user_key=? AND kind=? AND key=?",
                    (state.user_key, candidate.kind, candidate.key),
                ).fetchone()
                if corrected and corrected[0] > source_cursor:
                    raise ValueError("Explicit correction invalidated this old source")
                active = [
                    MemoryItem.model_validate_json(row[0])
                    for row in db.execute(
                        "SELECT data FROM memory_items WHERE user_key=? AND status IN ('active','invalidated')",
                        (state.user_key,),
                    )
                ]
                previous = next((m for m in active if m.memory_id == candidate.supersedes_id), None)
                if candidate.supersedes_id and (
                    previous is None or candidate.expected_version != previous.version
                ):
                    raise ValueError("Memory dependency conflict")
                same = [
                    m
                    for m in active
                    if m.kind == candidate.kind
                    and m.key == candidate.key
                    and m.scope == candidate.scope
                    and m.scope_ref == candidate.scope_ref
                ]
                if same:
                    newest = max(same, key=lambda m: m.source_cursor)
                    if newest.source_cursor > source_cursor:
                        raise ValueError("A later correction owns this key")
                    if (
                        newest.value == candidate.value
                        and newest.boundary_rule == candidate.boundary_rule
                    ):
                        results.append("duplicate:" + newest.memory_id)
                        continue
                    previous = previous or newest
                # A key corrected in any session also blocks late results in an old scope.
                newer = db.execute(
                    "SELECT 1 FROM memory_items WHERE user_key=? AND kind=? AND key=? AND source_cursor>?",
                    (state.user_key, candidate.kind, candidate.key, source_cursor),
                ).fetchone()
                if newer:
                    raise ValueError("Later source supersedes this candidate")
                item = MemoryItem(
                    **candidate.model_dump(exclude={"supersedes_id"}),
                    memory_id=uuid.uuid4().hex,
                    user_key=state.user_key,
                    source_cursor=source_cursor,
                    supersedes_id=previous.memory_id if previous else None,
                    version=previous.version + 1 if previous else 1,
                )
                if previous:
                    self.store.set_memory_status(db, previous, "superseded")
                db.execute(
                    "INSERT INTO memory_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item.memory_id,
                        item.user_key,
                        item.kind,
                        item.key,
                        item.scope,
                        item.scope_ref,
                        item.expires_at.isoformat() if item.expires_at else None,
                        item.status,
                        item.version,
                        item.supersedes_id,
                        source_cursor,
                        item.model_dump_json(),
                        None,
                    ),
                )
                for ref in item.source_refs:
                    db.execute(
                        "INSERT OR IGNORE INTO memory_sources VALUES (?,?,?)",
                        (item.memory_id, ref.kind, str(ref.id)),
                    )
                changed = True
                boundary_changed |= item.kind == "interaction_boundary"
                results.append("accepted:" + item.memory_id)
            except ValueError as error:
                results.append("rejected:" + str(error))
        if changed:
            db.execute(
                "UPDATE user_revisions SET memory_revision=memory_revision+1,boundary_revision=boundary_revision+? WHERE user_key=?",
                (int(boundary_changed), state.user_key),
            )
        return tuple(results)

    def retrieve(self, state, query, budget=1200, *, proactive=False):
        now = self.clock()
        revisions = self.store.revisions(state.user_key)
        items = [m for m in self.store.memory_items(state.user_key) if applicable(m, state, now)]
        boundaries = tuple(
            m for m in items if m.kind == "interaction_boundary" and m.epistemic_status == "stated"
        )
        candidates = []
        query_terms = terms(query)
        for item in items:
            if item.kind == "interaction_boundary" or item.epistemic_status == "legacy_unverified":
                continue
            relevance = len(terms(item.value + item.key) & query_terms)
            raised = relevance > 0
            blocked = any(
                b.target
                and b.target in (item.value + item.key)
                and b.boundary_rule in ("no_topic_probe", "no_memory_mention")
                for b in boundaries
            )
            if (item.mention_policy != "allowed" or blocked) and (proactive or not raised):
                continue
            if item.sensitivity == "sensitive" and not raised:
                continue
            age_days = max(0, (now - item.recorded_at).total_seconds() / 86400)
            recent = self.store.query(
                "SELECT data FROM turn_policies WHERE session_id=? ORDER BY turn_id DESC LIMIT 3",
                (state.session_id,),
            )
            repeated = sum(item.memory_id in r["data"] for r in recent)
            score = (
                relevance * 8
                + item.importance
                + (3 if item.kind == "support_experience" else 0)
                - min(age_days, 30) / 10
                - repeated * 4
            )
            candidates.append((score, item))
        selected = []
        for _, item in sorted(candidates, key=lambda x: (-x[0], -x[1].source_cursor)):
            projection = [self.project(m) for m in selected + [item]]
            if estimate_tokens(projection) <= budget:
                selected.append(item)
        return MemoryBundle(
            boundaries=boundaries,
            items=tuple(selected),
            **revisions,
            estimated_tokens=estimate_tokens([self.project(m) for m in selected]),
        )

    @staticmethod
    def project(item):
        return {
            "id": item.memory_id,
            "kind": item.kind,
            "key": item.key,
            "value": item.value,
            "scope": item.scope,
            "source": [(r.kind, r.id) for r in item.source_refs],
            "mention": item.mention_policy,
            "support": item.support.model_dump() if item.support else None,
            "feedback_valence": item.feedback_valence,
        }

    def explicit_boundary(self, text, state, turn_id):
        """Conservative Chinese controls; uncertain targets protect the current session."""
        negative = re.search(
            r"(?<![分区个识])别(?:再|主动)?(?:问|提|给|教|说|聊|追|管|劝|建议)|不要(?:再|主动)?|不想.*(?:建议|问)|不希望.*(?:问|建议)",
            text,
        )
        allow = re.search(r"可以问我|允许.*问|可以.*建议", text)
        revoke = re.search(r"(?:取消|撤销).*(?:限制|边界|不要|别问)", text)
        if not (negative or allow or revoke):
            return None
        target_match = re.search(
            r"论文|时间(?:管理|安排)?|安排时间|进度|学习|考试|工作|家人|父母|感情", text
        )
        target = target_match.group() if target_match else "current_topic"
        target = "时间管理" if target in ("时间", "安排时间", "时间安排") else target
        rule = (
            "revoke"
            if revoke
            else "allow"
            if allow
            else "no_advice"
            if re.search(r"建议|教我|安排时间|办法", text)
            else "no_topic_probe"
        )
        scope, expiry = "session", None
        if re.search(r"以后|永远|长期|一直", text) and target_match:
            scope = "persistent"
        elif "今天" in text:
            scope = "until_time"
            tomorrow = self.clock().astimezone(self.timezone).date() + timedelta(days=1)
            expiry = datetime.combine(tomorrow, time.min, self.timezone).astimezone(timezone.utc)
        elif re.search(r"这(?:个|件).*话题|这个话题", text):
            scope = "topic"
        # An exception has its own key so it cannot erase a broader restriction.
        return MemoryCandidate(
            kind="interaction_boundary",
            key=f"{rule}:{target}",
            value=text[:500],
            source_refs=(
                EvidenceRef(kind="user_turn", id=turn_id, claim="明确交互边界", quote=text[:300]),
            ),
            scope=scope,
            expires_at=expiry,
            valid_from=self.clock(),
            target=target,
            boundary_rule=rule,
            mention_policy="avoid_proactive",
        )
