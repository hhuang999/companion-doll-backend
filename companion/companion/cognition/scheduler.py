"""Bounded fair scheduler; one active job per user, model slots are separate."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .models import CognitiveJob

logger = logging.getLogger(__name__)

REPAIR_TRIGGERS = {"refusal", "correction", "boundary", "feedback", "repeated_failure"}
DELIBERATION_TRIGGERS = REPAIR_TRIGGERS | {
    "ask_for_help",
    "missing_card",
    "cry",
    "emotion",
    "risk_watch",
    "exercise_recheck",
}


@dataclass
class Scheduled:
    job: CognitiveJob
    queued_mono: float = field(default_factory=time.monotonic)
    cancel: threading.Event = field(default_factory=threading.Event)


class CognitiveScheduler:
    def __init__(self, config, store, capture, run):
        self.settings, self.store, self.capture, self.run = config.settings, store, capture, run
        self.condition = threading.Condition()
        self.pending = {}
        self.active = {}
        self.served = {}
        self.sequence = 0
        self.closed = False
        self.pool = ThreadPoolExecutor(
            max_workers=self.settings.pools.reasoner_workers, thread_name_prefix="cognitive-job"
        )
        self.dispatcher = threading.Thread(
            target=self._dispatch, name="cognitive-dispatch", daemon=True
        )
        self.dispatcher.start()

    def submit(self, user_key, session_id, trigger, kind="normal"):
        triggers = (trigger,) if isinstance(trigger, str) else tuple(trigger)
        category = (
            "end_consolidation"
            if kind == "end"
            else "memory"
            if kind == "memory"
            else "deliberation"
            if set(triggers) & DELIBERATION_TRIGGERS
            else "routine"
        )
        priority = (
            0
            if category == "end_consolidation"
            else 1
            if set(triggers) & REPAIR_TRIGGERS
            else 2
            if category == "deliberation"
            else 4
            if category == "memory"
            else 3
        )
        job = self.capture(user_key, session_id, category, triggers, priority)
        if job is None:
            return None
        key = (
            user_key,
            session_id,
            "strategy" if category in ("routine", "deliberation") else category,
        )
        with self.condition:
            if self.closed:
                return None
            active = self.active.get(user_key)
            if (
                (set(triggers) & REPAIR_TRIGGERS or category == "end_consolidation")
                and active
                and active.job.session_id == session_id
            ):
                active.cancel.set()
            if category == "end_consolidation":
                for old_key, old in list(self.pending.items()):
                    if old.job.session_id == session_id:
                        self.store.finish_job(old.job.job_id, "cancelled", error="session_ended")
                        del self.pending[old_key]
            old = self.pending.get(key)
            if not old and category != "end_consolidation":
                for other_key, other in list(self.pending.items()):
                    if other_key[0] == user_key and other_key[2] == key[2]:
                        self.store.finish_job(
                            other.job.job_id, "superseded", error="newer_session_request"
                        )
                        del self.pending[other_key]
            if old:
                job = job.model_copy(
                    update={
                        "triggers": tuple(sorted(set(old.job.triggers) | set(triggers))),
                        "kind": "deliberation"
                        if "deliberation" in (category, old.job.kind)
                        else category,
                        "priority": min(priority, old.job.priority),
                        "queued_at": old.job.queued_at,
                    }
                )
                self.store.finish_job(
                    old.job.job_id, "superseded", error="merged_into:" + job.job_id
                )
            self.store.save_job(job)
            if not old and len(self.pending) >= self.settings.cognition.max_pending:
                if category != "end_consolidation":
                    self.store.finish_job(job.job_id, "rejected", error="queue_full")
                # Ends remain durable and are refilled from the database.
                self.condition.notify_all()
                return job.job_id
            self.pending[key] = Scheduled(job, old.queued_mono if old else time.monotonic())
            self.condition.notify_all()
            return job.job_id

    def _refill_ends(self):
        capacity = self.settings.cognition.max_pending - len(self.pending)
        if capacity <= 0:
            return
        known = {v.job.job_id for v in self.pending.values()} | {
            v.job.job_id for v in self.active.values()
        }
        rows = self.store.query(
            "SELECT data FROM cognitive_jobs WHERE kind='end_consolidation' AND status='queued' ORDER BY queued_at LIMIT ?",
            (self.settings.cognition.max_pending,),
        )
        for row in rows:
            job = CognitiveJob.model_validate_json(row["data"])
            if job.job_id not in known:
                self.pending[(job.user_key, job.session_id, job.kind)] = Scheduled(job)
                capacity -= 1
                if capacity == 0:
                    break

    def _dispatch(self):
        while True:
            with self.condition:
                if self.closed:
                    return
                self._refill_ends()
                choices = [
                    (key, item)
                    for key, item in self.pending.items()
                    if item.job.user_key not in self.active
                ]
                if not choices or len(self.active) >= self.settings.pools.reasoner_workers:
                    self.condition.wait(0.2)
                    continue
                now = time.monotonic()
                # Round-robin across ready users; priority orders that user's own jobs.
                key, item = min(
                    choices,
                    key=lambda pair: (
                        self.served.get(pair[1].job.user_key, -1),
                        max(1, pair[1].job.priority - int(now - pair[1].queued_mono > 15))
                        if pair[1].job.priority
                        else 0,
                        pair[1].queued_mono,
                    ),
                )
                del self.pending[key]
                if (
                    item.job.kind != "end_consolidation"
                    and now - item.queued_mono > self.settings.cognition.queue_timeout_s
                ):
                    self.store.finish_job(item.job.job_id, "expired", error="queue_timeout")
                    self.condition.notify_all()
                    continue
                self.active[item.job.user_key] = item
                self.sequence += 1
                self.served[item.job.user_key] = self.sequence
                self.store.finish_job(item.job.job_id, "running")
                self.pool.submit(self._execute, item)

    def _execute(self, item):
        try:
            self.run(item.job, item.cancel)
        except Exception as error:
            logger.exception("Cognitive worker failed for job %s", item.job.job_id)
            # Last-resort infrastructure boundary, not silent success.
            self.store.finish_job(item.job.job_id, "failed", error=type(error).__name__)
        finally:
            with self.condition:
                self.active.pop(item.job.user_key, None)
                self.condition.notify_all()

    def cancel_user(self, user_key, session_id=None, reason="cancelled"):
        with self.condition:
            active = self.active.get(user_key)
            if active and (session_id is None or active.job.session_id == session_id):
                active.cancel.set()
            for key, item in list(self.pending.items()):
                if item.job.user_key == user_key and (
                    session_id is None or item.job.session_id == session_id
                ):
                    self.store.finish_job(item.job.job_id, "cancelled", error=reason)
                    del self.pending[key]
            self.condition.notify_all()

    def wait_idle(self, timeout=25, user_key=None):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                busy = any(
                    user_key is None or item.job.user_key == user_key
                    for item in [*self.pending.values(), *self.active.values()]
                )
                durable = self.store.query(
                    "SELECT 1 FROM cognitive_jobs WHERE status='queued' AND kind='end_consolidation'"
                    + (" AND user_key=?" if user_key else "")
                    + " LIMIT 1",
                    (user_key,) if user_key else (),
                )
                if not busy and (not durable or self.closed):
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)

    def close(self):
        if not self.wait_idle(self.settings.timing.shutdown_grace_s):
            with self.condition:
                self.closed = True
                for item in self.active.values():
                    item.cancel.set()
                for item in self.pending.values():
                    if item.job.kind != "end_consolidation":
                        self.store.finish_job(item.job.job_id, "cancelled", error="shutdown")
                self.pending.clear()
                self.condition.notify_all()
            self.dispatcher.join(timeout=1)
            self.pool.shutdown(wait=False)
            # HTTP requests retain their real occupied slots until they exit.
            raise TimeoutError(
                "Shutdown grace elapsed; durable ends retained, requests still occupied"
            )
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.dispatcher.join(timeout=1)
        self.pool.shutdown(wait=True)
