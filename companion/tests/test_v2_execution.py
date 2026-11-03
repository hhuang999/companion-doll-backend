import asyncio
import json
import threading

from companion.adapters.output import RecordingOutputPort
from companion.adapters.xiaozhi.output import XiaozhiOutputPort
from companion.core.api import CompanionCore
from companion.core.models import SessionState
from companion.llm.fake import FakeLLM
from test_device_output import FakeSpeech, FakeTransport, event
from test_v2_cognition import input_turn


def test_v2_22_prefetch_overlaps_send_and_cannot_activate_offer(tmp_path):
    class Speech(FakeSpeech):
        def __init__(self):
            super().__init__()
            self.second_ready = threading.Event()

        def synthesize(self, text):
            if text == "second":
                self.second_ready.set()
            return super().synthesize(text)

    class Transport(FakeTransport):
        def __init__(self):
            super().__init__()
            self.sending_first = asyncio.Event()
            self.finish_first = asyncio.Event()

        async def play(self, packets, text):
            if text == "first":
                self.sending_first.set()
                await self.finish_first.wait()
            await super().play(packets, text)

    async def run():
        speech, transport, callbacks = Speech(), Transport(), []
        port = XiaozhiOutputPort(
            asyncio.get_running_loop(), callbacks.append, speech, transport, tmp_path
        )
        try:
            port.submit(event("first", 1, "first"))
            await asyncio.wait_for(transport.sending_first.wait(), 2)
            port.submit(event("second", 1, "second", offer_id="offer"))
            assert await asyncio.to_thread(speech.second_ready.wait, 2)
            assert not any(e.output_id == "second" and e.status == "started" for e in callbacks)
            transport.finish_first.set()
            await asyncio.wait_for(port.queue.join(), 2)
            assert transport.played == ["first", "second"]
        finally:
            await port.close()

    asyncio.run(run())


def test_v2_22_blocked_prefetch_fixed_takeover_does_not_wait(tmp_path):
    from companion.core.models import PlaybackPlan, PlaybackSegment

    class Transport(FakeTransport):
        async def play(self, packets, text):
            self.played.append(text)
            if text == "first":
                await asyncio.Event().wait()

    (tmp_path / "crisis.wav").write_bytes(b"fixed")

    async def run():
        speech, transport, callbacks = FakeSpeech(), Transport(), []
        port = XiaozhiOutputPort(
            asyncio.get_running_loop(), callbacks.append, speech, transport, tmp_path
        )
        try:
            port.submit(event("first", 1, "first"))
            await asyncio.wait_for(transport.started.wait(), 2)
            port.submit(event("prefetch", 1, "blocked"))
            assert await asyncio.to_thread(speech.blocked.wait, 2)
            port.cancel_before("s", 2)
            plan = PlaybackPlan(script_id="crisis", segments=(PlaybackSegment(text="crisis"),))
            port.submit(event("crisis", 2, type="crisis_plan", plan=plan))
            await asyncio.wait_for(port.queue.join(), 2)
            assert transport.played[-1] == "crisis"
            assert "blocked" not in transport.played
            assert not any(e.output_id == "prefetch" and e.status == "started" for e in callbacks)
        finally:
            speech.release.set()
            await port.close()

    asyncio.run(run())


def test_v2_17_explicit_feedback_attribution_and_ambiguous_feedback(config, store):
    core = CompanionCore(config, store, FakeLLM())
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output("s", "u", port)
    try:
        input_turn(core, "今天有点累")
        input_turn(core, "挺好的")
        events = store.query(
            "SELECT data FROM interaction_events WHERE event_type='explicit_feedback'"
        )
        assert json.loads(events[-1]["data"])["payload"]["attribution"] == "unattributed"
        assert not [m for m in store.memory_items("u") if m.kind == "support_experience"]
        input_turn(core, "刚才这样问有帮助")
        events = store.query(
            "SELECT data FROM interaction_events WHERE event_type='explicit_feedback'"
        )
        explicit = json.loads(events[-1]["data"])
        assert explicit["output_id"] and explicit["payload"]["attribution"] == "explicit"
        assert [m for m in store.memory_items("u") if m.kind == "support_experience"]
    finally:
        core.close()


def test_v2_03_refusal_and_boundary_withdraw_offer_immediately(config, store):
    fake = FakeLLM()
    fake.reasoner_release = threading.Event()
    core = CompanionCore(config, store, fake)
    core.bind_output("s", "u", RecordingOutputPort(core.on_playback_event))
    try:
        input_turn(core, "怎么办")
        assert core.sessions["s"].state.pending_offer
        input_turn(core, "不要再教我安排时间，只想让你听听")
        state = core.sessions["s"].state
        assert state.pending_offer is None and state.policy_revision > 0
        assert core.sessions["s"].contexts[state.latest_turn_id].policy_frame.active_boundaries
    finally:
        fake.reasoner_release.set()
        core.close()


def test_v2_02_scheduler_fairness_queue_limit_and_terminal_states(config, store):
    import uuid

    from companion.cognition.models import CognitiveJob
    from companion.cognition.scheduler import CognitiveScheduler

    config.settings.pools.reasoner_workers = 1
    config.settings.cognition.max_pending = 2
    for user in ("a", "b", "c", "d"):
        store.create_session(SessionState(session_id=user, user_key=user))
    started, release = threading.Event(), threading.Event()
    order = []

    def capture(user, session, kind, triggers, priority):
        return CognitiveJob(
            job_id=uuid.uuid4().hex,
            user_key=user,
            session_id=session,
            kind=kind,
            triggers=triggers,
            source_turn_id=0,
            source_user_index=0,
            topic_revision=0,
            policy_revision=0,
            boundary_revision=0,
            base_plan_version=0,
            priority=priority,
        )

    def run(job, cancel):
        order.append(job.user_key)
        if len(order) == 1:
            started.set()
            assert release.wait(3)
        store.finish_job(job.job_id, "completed", result={"synthetic": True})

    scheduler = CognitiveScheduler(config, store, capture, run)
    try:
        scheduler.submit("a", "a", "periodic")
        assert started.wait(2)
        scheduler.submit("a", "a", "periodic")
        scheduler.submit("b", "b", "periodic")
        rejected = scheduler.submit("c", "c", "periodic")
        assert (
            store.query("SELECT error FROM cognitive_jobs WHERE job_id=?", (rejected,))[0]["error"]
            == "queue_full"
        )
        release.set()
        assert scheduler.wait_idle()
        assert order[:3] == ["a", "b", "a"]
        assert not store.finish_job(rejected, "running")
    finally:
        release.set()
        scheduler.close()


def test_v2_13_prefetch_does_not_change_consent_without_started(config, store):
    core = CompanionCore(config, store, FakeLLM())
    port = RecordingOutputPort(core.on_playback_event, auto_complete=False)
    core.bind_output("s", "u", port)
    try:
        input_turn(core, "怎么办")
        assert core.wait_idle()
        # RecordingOutputPort does emit started on submit. Explicitly create a
        # not-yet-started offer to represent queued/prepared audio at the boundary.
        core.sessions["s"].state.pending_offer.active = False
        input_turn(core, "好，你说")
        assert core.sessions["s"].state.stage.value != "action"
    finally:
        core.close()
