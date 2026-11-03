"""Persistence helpers shared by cognition and memory; no model calls here."""

import json
import uuid

from companion.cognition.base import utcnow
from companion.cognition.models import CognitiveJob, InteractionEvent, SupportPlan
from companion.memory.models import MemoryItem


class CognitionStore:
    def revisions(self, user_key, db=None):
        row = (
            (db or self.connection())
            .execute(
                "SELECT memory_revision,boundary_revision FROM user_revisions WHERE user_key=?",
                (user_key,),
            )
            .fetchone()
        )
        if row is None:
            raise ValueError("Unknown user")
        return dict(row)

    def validate_refs(self, user_key, refs, allowed=None, db=None):
        connection = db or self.connection()
        for ref in refs:
            key = (ref.kind, str(ref.id))
            if allowed is not None and key not in allowed:
                raise ValueError(f"Evidence outside supplied context: {ref.kind}")
            if ref.kind == "user_turn":
                row = connection.execute(
                    "SELECT text FROM turns WHERE id=? AND user_key=? AND role='user'",
                    (ref.id, user_key),
                ).fetchone()
                text = row[0] if row else None
            elif ref.kind == "memory":
                row = connection.execute(
                    "SELECT data FROM memory_items WHERE memory_id=? AND user_key=? AND status='active'",
                    (str(ref.id), user_key),
                ).fetchone()
                text = json.loads(row[0])["value"] if row else None
            else:
                row = connection.execute(
                    "SELECT data FROM interaction_events WHERE event_id=? AND user_key=?",
                    (str(ref.id), user_key),
                ).fetchone()
                text = json.loads(row[0])["payload"].get("text") or "" if row else None
            if text is None or (ref.quote and ref.quote not in text):
                raise ValueError(f"Invalid evidence or quote: {ref.kind}")

    def record_interaction(self, event: InteractionEvent, db=None):
        if db is None:
            with self.transaction() as connection:
                return self.record_interaction(event, connection)
        session = db.execute(
            "SELECT 1 FROM sessions WHERE session_id=? AND user_key=?",
            (event.session_id, event.user_key),
        ).fetchone()
        if not session:
            raise ValueError("Event session identity mismatch")
        if (
            event.turn_id is not None
            and not db.execute(
                "SELECT 1 FROM turns WHERE id=? AND session_id=?",
                (event.turn_id, event.session_id),
            ).fetchone()
        ):
            raise ValueError("Event turn identity mismatch")
        if (
            event.output_id
            and not db.execute(
                "SELECT 1 FROM outputs WHERE output_id=? AND session_id=?",
                (event.output_id, event.session_id),
            ).fetchone()
        ):
            raise ValueError("Event output identity mismatch")
        if (
            event.support_plan_id
            and not db.execute(
                "SELECT 1 FROM support_plans WHERE plan_id=? AND user_key=? AND session_id=?",
                (event.support_plan_id, event.user_key, event.session_id),
            ).fetchone()
        ):
            raise ValueError("Event plan identity mismatch")
        self.validate_refs(event.user_key, event.evidence, db=db)
        old = db.execute(
            "SELECT data FROM interaction_events WHERE idempotency_key=?", (event.idempotency_key,)
        ).fetchone()
        if old:
            previous = InteractionEvent.model_validate_json(old[0])
            fields = (
                "user_key",
                "session_id",
                "turn_id",
                "output_id",
                "event_type",
                "origin",
                "payload",
            )
            if any(getattr(previous, f) != getattr(event, f) for f in fields):
                raise ValueError("Event idempotency key reused for different content")
            return False
        db.execute(
            "INSERT INTO interaction_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event.event_id,
                event.idempotency_key,
                event.user_key,
                event.session_id,
                event.turn_id,
                event.event_type,
                event.origin,
                event.recorded_at.isoformat(),
                event.model_dump_json(),
            ),
        )
        return True

    def save_job(self, job: CognitiveJob):
        with self.transaction() as db:
            db.execute(
                "INSERT INTO cognitive_jobs(job_id,user_key,session_id,kind,status,priority,queued_at,source_turn_id,data) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    job.job_id,
                    job.user_key,
                    job.session_id,
                    job.kind,
                    job.status,
                    job.priority,
                    job.queued_at.isoformat(),
                    job.source_turn_id,
                    job.model_dump_json(),
                ),
            )

    def finish_job(self, job_id, status, *, result=None, error=None, db=None):
        if db is None:
            with self.transaction() as connection:
                return self.finish_job(job_id, status, result=result, error=error, db=connection)
        row = db.execute(
            "SELECT data,status FROM cognitive_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if not row or row["status"] not in ("queued", "running"):
            return False
        now = utcnow()
        job = CognitiveJob.model_validate_json(row["data"]).model_copy(
            update={
                "status": status,
                "error": error,
                "started_at" if status == "running" else "finished_at": now,
            }
        )
        db.execute(
            "UPDATE cognitive_jobs SET status=?,data=?,started_at=?,finished_at=?,error=?,result=? WHERE job_id=?",
            (
                status,
                job.model_dump_json(),
                job.started_at.isoformat() if job.started_at else None,
                job.finished_at.isoformat() if job.finished_at else None,
                error,
                json.dumps(result, ensure_ascii=False) if result is not None else None,
                job_id,
            ),
        )
        return True

    def agent_run(
        self,
        job_id,
        role,
        attempt,
        model,
        candidate_version,
        started_at,
        duration_ms,
        status,
        usage,
        result=None,
        error=None,
    ):
        run_id = uuid.uuid4().hex
        with self.transaction() as db:
            db.execute(
                "INSERT INTO agent_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    job_id,
                    role,
                    attempt,
                    model,
                    "v2.1",
                    candidate_version,
                    started_at,
                    duration_ms,
                    status,
                    json.dumps(usage),
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                ),
            )
        return run_id

    def active_support_plan(self, session_id):
        rows = self.query(
            "SELECT data FROM support_plans WHERE session_id=? AND status='active' ORDER BY version DESC LIMIT 1",
            (session_id,),
        )
        return SupportPlan.model_validate_json(rows[0]["data"]) if rows else None

    def memory_items(self, user_key, db=None):
        rows = (
            (db or self.connection())
            .execute(
                "SELECT data FROM memory_items WHERE user_key=? AND status='active'", (user_key,)
            )
            .fetchall()
        )
        return [MemoryItem.model_validate_json(row[0]) for row in rows]

    def set_memory_status(self, db, item, status):
        updated = item.model_copy(update={"status": status})
        db.execute(
            "UPDATE memory_items SET status=?,data=? WHERE memory_id=?",
            (status, updated.model_dump_json(), item.memory_id),
        )

    def invalidate_plans(self, session_id, db=None):
        if db is None:
            with self.transaction() as connection:
                return self.invalidate_plans(session_id, connection)
        db.execute(
            "UPDATE support_plans SET status='invalidated' WHERE session_id=? AND status='active'",
            (session_id,),
        )

    def cognitive_diagnostics(self, user_key, session_id):
        return {
            "revisions": self.revisions(user_key),
            "plans": self.query(
                "SELECT data,status FROM support_plans WHERE session_id=? ORDER BY version DESC LIMIT 5",
                (session_id,),
            ),
            "jobs": self.query(
                "SELECT * FROM cognitive_jobs WHERE user_key=? ORDER BY queued_at DESC LIMIT 20",
                (user_key,),
            ),
            "reviews": self.query(
                "SELECT a.* FROM agent_runs a JOIN cognitive_jobs j USING(job_id) WHERE j.user_key=? AND a.role='critic' ORDER BY a.started_at DESC LIMIT 5",
                (user_key,),
            ),
            "events": self.query(
                "SELECT data FROM interaction_events WHERE user_key=? ORDER BY recorded_at DESC LIMIT 12",
                (user_key,),
            ),
        }
