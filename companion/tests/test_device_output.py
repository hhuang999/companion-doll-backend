import asyncio
import threading

from companion.adapters.xiaozhi.output import XiaozhiOutputPort
from companion.core.models import OutputEvent, PlaybackPlan, PlaybackSegment


class FakeSpeech:
    @staticmethod
    def cache_key(text):
        return text

    def __init__(self):
        self.blocked = threading.Event()
        self.release = threading.Event()

    def synthesize(self, text):
        if text == "blocked":
            self.blocked.set()
            assert self.release.wait(3)
        return text.encode()

    def duration(self, data):
        return 0.001


class FakeTransport:
    def __init__(self):
        self.played = []
        self.stops = 0
        self.started = asyncio.Event()

    async def encode(self, data):
        return [data]

    async def start(self, event):
        self.started.set()

    async def play(self, packets, text):
        self.played.append(text)

    async def stop(self):
        self.stops += 1

    async def finish(self):
        pass


def event(identifier, generation, text="reply", **kwargs):
    return OutputEvent(
        output_id=identifier, session_id="s", turn_id=1, generation=generation, text=text, **kwargs
    )


def test_cancel_during_blocked_tts_never_plays_old_audio(tmp_path):
    async def run():
        speech, transport, callbacks = FakeSpeech(), FakeTransport(), []
        port = XiaozhiOutputPort(
            asyncio.get_running_loop(), callbacks.append, speech, transport, tmp_path
        )
        try:
            port.submit(event("old", 1, "blocked"))
            assert await asyncio.to_thread(speech.blocked.wait, 2)
            port.cancel_before("s", 2)
            port.submit(event("new", 2, "takeover"))
            await asyncio.wait_for(port.queue.join(), 2)
            assert transport.played == ["takeover"]
            assert transport.stops >= 1
            assert [(e.output_id, e.status) for e in callbacks if e.status == "completed"] == [
                ("new", "completed")
            ]
        finally:
            speech.release.set()
            await port.close()

    asyncio.run(run())


def test_prepared_greeting_avoids_network_synthesis(tmp_path):
    class OfflineSpeech(FakeSpeech):
        def synthesize(self, text):
            raise AssertionError("Prepared speech must not call TTS")

    (tmp_path / "greeting.wav").write_bytes(b"cached greeting")

    async def run():
        transport, callbacks = FakeTransport(), []
        port = XiaozhiOutputPort(
            asyncio.get_running_loop(), callbacks.append, OfflineSpeech(), transport, tmp_path
        )
        try:
            port.submit(event("greeting", 1, "greeting"))
            await asyncio.wait_for(port.queue.join(), 2)
            assert transport.played == ["greeting"]
            assert callbacks[-1].status == "completed"
        finally:
            await port.close()

    asyncio.run(run())


def test_cancel_exercise_pause_drops_remaining_segments(tmp_path):
    audio = tmp_path / "fixture.wav"
    audio.write_bytes(b"fixture")
    plan = PlaybackPlan(
        script_id="test",
        segments=(
            PlaybackSegment(text="first", pause_s=30, audio_path=str(audio)),
            PlaybackSegment(text="must not play", audio_path=str(audio)),
        ),
    )

    async def run():
        transport, callbacks = FakeTransport(), []
        port = XiaozhiOutputPort(
            asyncio.get_running_loop(), callbacks.append, FakeSpeech(), transport, tmp_path
        )
        try:
            port.submit(event("exercise", 1, type="exercise_plan", plan=plan))
            await asyncio.wait_for(transport.started.wait(), 2)
            await asyncio.sleep(0)
            port.cancel_before("s", 2)
            port.submit(event("new", 2))
            await asyncio.wait_for(port.queue.join(), 2)
            assert transport.played == ["first", "reply"]
            assert not any(e.output_id == "exercise" and e.status == "completed" for e in callbacks)
        finally:
            await port.close()

    asyncio.run(run())
