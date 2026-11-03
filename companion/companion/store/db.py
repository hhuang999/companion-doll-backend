"""SQLite persistence. All mutations use short, serialized transactions."""

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from companion.core.models import (
    CoreMemory,
    MemoryUpdate,
    OutputEvent,
    ReasonerTask,
    RiskResult,
    SessionState,
    Snapshot,
    TurnSignals,
    utcnow,
)

from .cognition import CognitionStore
from .migrate import migrate


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store(CognitionStore):
    def __init__(self, path: str | Path, busy_timeout_ms: int = 5000) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.busy_timeout_ms = busy_timeout_ms
        self._local = threading.local()
        self._lock = threading.RLock()
        self._connections: list[sqlite3.Connection] = []
        connection = self.connection()
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            self.migration_backup = migrate(connection, self.path)
        except BaseException:
            self.close()
            raise

    def connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection"):
            connection = sqlite3.connect(
                self.path, check_same_thread=False, timeout=self.busy_timeout_ms / 1000
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
            self._local.connection = connection
            with self._lock:
                self._connections.append(connection)
        return self._local.connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self.connection()
            if connection.in_transaction:
                # Core can group input, controls, memory and state into one atomic unit.
                import uuid

                name = "nested_" + uuid.uuid4().hex
                connection.execute(f"SAVEPOINT {name}")
                try:
                    yield connection
                    connection.execute(f"RELEASE {name}")
                except BaseException:
                    connection.execute(f"ROLLBACK TO {name}")
                    connection.execute(f"RELEASE {name}")
                    raise
                return
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                yield connection

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(row) for row in self.connection().execute(sql, params).fetchall()]

    def create_session(self, state: SessionState) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO users(user_key,created_at) VALUES (?,?)",
                (state.user_key, utcnow().isoformat()),
            )
            db.execute(
                "INSERT OR IGNORE INTO user_revisions(user_key) VALUES (?)", (state.user_key,)
            )
            db.execute(
                "INSERT INTO sessions(session_id,user_key,started_at,state) VALUES (?,?,?,?)",
                (
                    state.session_id,
                    state.user_key,
                    state.started_at.isoformat(),
                    state.model_dump_json(),
                ),
            )

    def save_state(self, state: SessionState) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE sessions SET state=?,lifecycle=? WHERE session_id=?",
                (state.model_dump_json(), state.lifecycle, state.session_id),
            )

    def existing_input(self, session_id: str, input_id: str) -> dict | None:
        rows = self.query(
            "SELECT * FROM turns WHERE session_id=? AND input_id=?", (session_id, input_id)
        )
        return rows[0] if rows else None

    def add_input(
        self, state: SessionState, input_id: str, text: str, kind: str, signals: TurnSignals
    ) -> int:
        with self.transaction() as db:
            cursor = db.execute(
                "INSERT INTO turns(session_id,user_key,input_id,role,input_kind,text,signals,generation,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    state.session_id,
                    state.user_key,
                    input_id,
                    "user" if kind == "user" else "control",
                    kind,
                    text,
                    signals.model_dump_json(),
                    state.generation,
                    utcnow().isoformat(),
                ),
            )
            return cursor.lastrowid

    def update_turn(self, turn_id: int, **values: object) -> None:
        allowed = {
            "stage",
            "mode",
            "card",
            "snapshot_version",
            "risk_level",
            "latency",
            "violations",
            "output_status",
            "interrupted",
            "generation",
        }
        if not values.keys() <= allowed:
            raise ValueError("Unsupported turn fields")
        params = [
            dump(value) if name in {"latency", "violations"} else value
            for name, value in values.items()
        ]
        with self.transaction() as db:
            if "latency" in values:
                row = db.execute("SELECT latency FROM turns WHERE id=?", (turn_id,)).fetchone()
                merged = json.loads(row[0]) if row else {}
                merged.update(values["latency"])
                params[list(values).index("latency")] = dump(merged)
            db.execute(
                f"UPDATE turns SET {','.join(name + '=?' for name in values)} WHERE id=?",
                (*params, turn_id),
            )

    def history(self, session_id: str, through: int | None = None, limit: int = 12) -> list[dict]:
        through = through if through is not None else 2**63 - 1
        inputs = self.query(
            "SELECT * FROM turns WHERE session_id=? AND role='user' AND id<=? ORDER BY id DESC LIMIT ?",
            (session_id, through, limit),
        )[::-1]
        history = []
        for row in inputs:
            history.append(row)
            outputs = self.query(
                "SELECT data,status FROM outputs WHERE session_id=? AND turn_id=? AND status NOT IN ('cancelled','failed') ORDER BY created_at",
                (session_id, row["id"]),
            )
            texts = [json.loads(item["data"])["text"] for item in outputs]
            if any(texts):
                history.append(
                    {
                        "id": None,
                        "role": "assistant",
                        "text": "".join(texts),
                        "playback": [item["status"] for item in outputs],
                    }
                )
        return history

    def add_output(self, event: OutputEvent) -> bool:
        with self.transaction() as db:
            now = utcnow().isoformat()
            cursor = db.execute(
                "INSERT OR IGNORE INTO outputs(output_id,session_id,turn_id,generation,data,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    event.output_id,
                    event.session_id,
                    event.turn_id,
                    event.generation,
                    event.model_dump_json(),
                    now,
                    now,
                ),
            )
            return cursor.rowcount == 1

    def output_status(self, output_id: str, status: str) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE outputs SET status=?,updated_at=? WHERE output_id=? AND status NOT IN ('completed','cancelled','failed')",
                (status, utcnow().isoformat(), output_id),
            )

    def cancel_outputs(self, session_id: str, generation: int) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE outputs SET status='cancelled',updated_at=? WHERE session_id=? AND generation<? AND status IN ('submitted','started')",
                (utcnow().isoformat(), session_id, generation),
            )
            db.execute(
                "UPDATE followups SET status='pending',reservation_session_id=NULL WHERE reservation_session_id=? AND status='reserved'",
                (session_id,),
            )

    def onboarding_done(self, user_key: str) -> bool:
        return bool(
            self.query("SELECT onboarding_done FROM users WHERE user_key=?", (user_key,))[0][
                "onboarding_done"
            ]
        )

    def mark_onboarding(self, user_key: str) -> None:
        with self.transaction() as db:
            db.execute("UPDATE users SET onboarding_done=1 WHERE user_key=?", (user_key,))

    def reserve_followup(self, user_key: str, session_id: str, today: str) -> dict | None:
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM followups WHERE user_key=? AND status='pending' AND due_date<=? ORDER BY importance DESC,id LIMIT 1",
                (user_key, today),
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE followups SET status='reserved',reservation_session_id=? WHERE id=?",
                    (session_id, row["id"]),
                )
                return dict(row)
        return None

    def mark_followup_asked(self, followup_id: int, session_id: str) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE followups SET status='asked',asked_at=? WHERE id=? AND status='reserved' AND reservation_session_id=?",
                (utcnow().isoformat(), followup_id, session_id),
            )

    def core_memory(self, user_key: str, today: str) -> CoreMemory:
        profile = self.query(
            "SELECT field,value FROM profile WHERE user_key=? ORDER BY field", (user_key,)
        )
        events = self.query(
            "SELECT summary FROM events WHERE user_key=? AND status='active' ORDER BY importance DESC,id DESC LIMIT 3",
            (user_key,),
        )
        followups = self.query(
            "SELECT content FROM followups WHERE user_key=? AND status='pending' AND due_date<=? ORDER BY importance DESC LIMIT 2",
            (user_key, today),
        )
        summaries = self.query(
            "SELECT summary FROM sessions WHERE user_key=? AND summary IS NOT NULL ORDER BY started_at DESC LIMIT 1",
            (user_key,),
        )
        return CoreMemory(
            profile_brief="; ".join(f"{r['field']}: {r['value']}" for r in profile)[:120],
            active_stressors=tuple(r["summary"] for r in events),
            followups_due=tuple(r["content"] for r in followups),
            last_session_summary=summaries[0]["summary"] if summaries else "",
        )

    def record_risk(
        self, session_id: str, turn_id: int, risk: RiskResult, timings: dict | None = None
    ) -> int:
        with self.transaction() as db:
            old = db.execute(
                "SELECT id,level FROM risk_events WHERE session_id=? AND turn_id=?",
                (session_id, turn_id),
            ).fetchone()
            ranks = {"none": 0, "watch": 1, "high": 2}
            if old and ranks[old["level"]] > ranks[risk.level]:
                return old["id"]
            db.execute(
                "INSERT INTO risk_events(session_id,turn_id,level,source,category,reason,detection_status,timings,created_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(session_id,turn_id) DO UPDATE SET level=excluded.level,source=excluded.source,category=excluded.category,reason=excluded.reason,detection_status=excluded.detection_status,timings=excluded.timings,handled=CASE WHEN risk_events.level<>excluded.level THEN 0 ELSE risk_events.handled END,handled_at=CASE WHEN risk_events.level<>excluded.level THEN NULL ELSE risk_events.handled_at END",
                (
                    session_id,
                    turn_id,
                    risk.level,
                    risk.source,
                    risk.category,
                    risk.reason,
                    risk.status,
                    dump(timings or {}),
                    utcnow().isoformat(),
                ),
            )
            db.execute("UPDATE turns SET risk_level=? WHERE id=?", (risk.level, turn_id))
            return db.execute(
                "SELECT id FROM risk_events WHERE session_id=? AND turn_id=?", (session_id, turn_id)
            ).fetchone()[0]

    def record_run(
        self,
        task: ReasonerTask,
        status: str,
        duration_ms: float,
        result: dict | None = None,
        rejected: list | None = None,
        version: int | None = None,
        error: str | None = None,
    ) -> None:
        with self.transaction() as db:
            self._run(db, task, status, duration_ms, result, rejected, version, error)

    def _run(
        self,
        db: sqlite3.Connection,
        task: ReasonerTask,
        status: str,
        duration_ms: float,
        result: dict | None,
        rejected: list | None,
        version: int | None,
        error: str | None,
    ) -> None:
        db.execute(
            "INSERT INTO reasoner_runs(session_id,user_key,kind,triggers,source_turn_id,base_snapshot_version,started_at,duration_ms,status,result,rejected,published_version,error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                task.session_id,
                task.user_key,
                task.kind,
                dump(task.trigger_reasons),
                task.source_turn_id,
                task.base_snapshot_version,
                utcnow().isoformat(),
                duration_ms,
                status,
                dump(result) if result else None,
                dump(rejected or []),
                version,
                error,
            ),
        )

    def publish(
        self,
        task: ReasonerTask,
        snapshot: Snapshot | None,
        memory: MemoryUpdate,
        summary: str | None,
        result: dict,
        rejected: list,
        duration_ms: float,
    ) -> None:
        with self.transaction() as db:
            self._write_memory(db, task.user_key, memory)
            if snapshot:
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
            if task.kind == "end":
                db.execute(
                    "UPDATE sessions SET summary=?,lifecycle='closed' WHERE session_id=?",
                    (summary, task.session_id),
                )
                db.execute(
                    "UPDATE end_tasks SET status='done',last_error=NULL,updated_at=? WHERE session_id=?",
                    (utcnow().isoformat(), task.session_id),
                )
            self._run(
                db,
                task,
                "ok",
                duration_ms,
                result,
                rejected,
                snapshot.version if snapshot else None,
                None,
            )

    def _write_memory(self, db: sqlite3.Connection, user_key: str, memory: MemoryUpdate) -> None:
        now = utcnow().isoformat()
        for item in memory.profile_updates:
            db.execute(
                "INSERT INTO profile VALUES (?,?,?,?,?,?) ON CONFLICT(user_key,field) DO UPDATE SET value=excluded.value,source_turn_id=excluded.source_turn_id,source_turn_ids=excluded.source_turn_ids,updated_at=excluded.updated_at WHERE excluded.source_turn_id>=profile.source_turn_id",
                (
                    user_key,
                    item.field,
                    item.value,
                    max(item.source_turn_ids),
                    dump(item.source_turn_ids),
                    now,
                ),
            )
        for item in memory.events:
            db.execute(
                "INSERT OR IGNORE INTO events(user_key,summary,pressure_type,event_date,importance,source_turn_ids,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    user_key,
                    item.summary.strip(),
                    item.pressure_type,
                    item.date,
                    item.importance,
                    dump(item.source_turn_ids),
                    now,
                ),
            )
        for item in memory.followups:
            db.execute(
                "INSERT OR IGNORE INTO followups(user_key,kind,content,due_date,importance,source_turn_ids,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    user_key,
                    item.kind,
                    item.content.strip(),
                    item.due_date,
                    item.importance,
                    dump(item.source_turn_ids),
                    now,
                ),
            )
        db.execute(
            "UPDATE followups SET status='dropped' WHERE user_key=? AND status='pending' AND id NOT IN (SELECT id FROM followups WHERE user_key=? AND status IN ('pending','reserved') ORDER BY importance DESC,id LIMIT 2)",
            (user_key, user_key),
        )
        for item in memory.followup_results:
            db.execute(
                "UPDATE followups SET result=?,status='done' WHERE id=? AND user_key=? AND status='asked'",
                (item.result, item.followup_id, user_key),
            )

    def record_card(self, state: SessionState, turn_id: int, outcome: str) -> bool:
        with self.transaction() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO card_usage(session_id,action_id,card_id,outcome,turn_id,created_at) VALUES (?,?,?,?,?,?)",
                (
                    state.session_id,
                    state.action_id,
                    state.card_in_use,
                    outcome,
                    turn_id,
                    utcnow().isoformat(),
                ),
            )
            return cursor.rowcount == 1

    def end_session(self, state: SessionState, reason: str) -> None:
        with self.transaction() as db:
            now = utcnow().isoformat()
            db.execute(
                "UPDATE sessions SET lifecycle='ending',ended_at=COALESCE(ended_at,?),end_reason=COALESCE(end_reason,?),final_turn_id=?,state=? WHERE session_id=?",
                (now, reason, state.latest_turn_id, state.model_dump_json(), state.session_id),
            )
            db.execute(
                "INSERT OR IGNORE INTO end_tasks(session_id,final_turn_id,updated_at) VALUES (?,?,?)",
                (state.session_id, state.latest_turn_id, now),
            )

    def fail_end(self, session_id: str, error: str) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE end_tasks SET status='failed',last_error=?,attempt_count=attempt_count+1,updated_at=? WHERE session_id=?",
                (error, utcnow().isoformat(), session_id),
            )
            db.execute("UPDATE sessions SET lifecycle='closed' WHERE session_id=?", (session_id,))

    def recover(self) -> list[dict]:
        with self.transaction() as db:
            for row in db.execute(
                "SELECT job_id FROM cognitive_jobs WHERE status IN ('running','queued')"
            ).fetchall():
                self.finish_job(row[0], "interrupted", error="process_restart", db=db)
            db.execute("UPDATE support_plans SET status='invalidated' WHERE status='active'")
            db.execute(
                "UPDATE followups SET status='pending',reservation_session_id=NULL WHERE status='reserved'"
            )
            db.execute(
                "UPDATE outputs SET status='cancelled' WHERE status IN ('submitted','started')"
            )
            rows = db.execute(
                "SELECT * FROM sessions WHERE lifecycle IN ('active','ending')"
            ).fetchall()
            for row in rows:
                final = db.execute(
                    "SELECT COALESCE(MAX(id),0) FROM turns WHERE session_id=? AND role IN ('user','control')",
                    (row["session_id"],),
                ).fetchone()[0]
                db.execute(
                    "UPDATE sessions SET lifecycle='ending',ended_at=COALESCE(ended_at,?),end_reason=COALESCE(end_reason,'process_restart'),final_turn_id=? WHERE session_id=?",
                    (utcnow().isoformat(), final, row["session_id"]),
                )
                db.execute(
                    "INSERT OR IGNORE INTO end_tasks(session_id,final_turn_id,updated_at) VALUES (?,?,?)",
                    (row["session_id"], final, utcnow().isoformat()),
                )
            return [
                dict(r)
                for r in db.execute(
                    "SELECT sessions.* FROM sessions JOIN end_tasks USING(session_id) WHERE end_tasks.status='pending'"
                )
            ]

    def purge_user(self, user_key: str) -> None:
        with self.transaction() as db:
            db.execute(
                "DELETE FROM memory_sources WHERE memory_id IN (SELECT memory_id FROM memory_items WHERE user_key=?)",
                (user_key,),
            )
            db.execute("UPDATE memory_items SET supersedes_id=NULL WHERE user_key=?", (user_key,))
            for table in (
                "memory_corrections",
                "memory_items",
                "interaction_events",
                "support_plans",
                "cognitive_jobs",
                "user_revisions",
            ):
                db.execute(f"DELETE FROM {table} WHERE user_key=?", (user_key,))
            sessions = [
                r[0]
                for r in db.execute("SELECT session_id FROM sessions WHERE user_key=?", (user_key,))
            ]
            for session_id in sessions:
                for table in (
                    "turn_policies",
                    "outputs",
                    "risk_events",
                    "card_usage",
                    "snapshots",
                    "reasoner_runs",
                    "end_tasks",
                    "turns",
                ):
                    db.execute(f"DELETE FROM {table} WHERE session_id=?", (session_id,))
            for table in ("sessions", "profile", "events", "followups", "users"):
                db.execute(f"DELETE FROM {table} WHERE user_key=?", (user_key,))

    def close(self) -> None:
        with self._lock:
            for connection in self._connections:
                connection.close()
            self._connections.clear()
