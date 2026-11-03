"""Cancelable audio playback on the connection's asyncio loop.

Completion is the upstream server's paced-send estimate, not a device ACK.
The transport is injected so cancellation can be tested without hardware.
"""

import asyncio
import json
import logging
import tempfile
import threading
from pathlib import Path

from companion.core.models import OutputEvent, PlaybackEvent, PlaybackSegment

logger = logging.getLogger(__name__)


class XiaozhiTransport:
    def __init__(self, connection):
        self.connection = connection

    async def encode(self, data: bytes) -> list[bytes]:
        from core.utils.util import audio_to_data

        # Close the handle before ffmpeg opens it on Windows. Speech is transient.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
            path = Path(file.name)
            file.write(data)
        try:
            return await audio_to_data(str(path), use_cache=False)
        finally:
            path.unlink(missing_ok=True)

    async def start(self, event: OutputEvent) -> None:
        from core.handle.sendAudioHandle import send_tts_message
        from core.utils.textUtils import EMOJI_MAP

        conn = self.connection
        conn.sentence_id = event.output_id
        conn.client_abort = False
        conn.client_is_speaking = True
        await send_tts_message(conn, "start")
        await conn.websocket.send(
            json.dumps(
                {
                    "type": "llm",
                    "text": event.emoji,
                    "emotion": EMOJI_MAP.get(event.emoji, "neutral"),
                    "session_id": conn.session_id,
                }
            )
        )

    async def play(self, packets: list[bytes], text: str) -> None:
        from core.handle.sendAudioHandle import (
            _wait_for_audio_completion,
            send_tts_message,
            sendAudio,
        )

        await send_tts_message(self.connection, "sentence_start", text)
        await sendAudio(self.connection, packets)
        await _wait_for_audio_completion(self.connection)

    async def stop(self) -> None:
        from websockets.exceptions import ConnectionClosed

        conn = self.connection
        conn.client_abort = True
        controller = getattr(conn, "audio_rate_controller", None)
        if controller:
            controller.stop_sending()
            controller.reset()
        conn.clear_queues()
        conn.clearSpeakStatus()
        try:
            await conn.websocket.send(
                json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id})
            )
        except ConnectionClosed:
            # Disconnect is already a terminal stop; no device remains to notify.
            pass

    async def finish(self) -> None:
        # All frames have already drained before this call.
        await self.stop()


class XiaozhiOutputPort:
    def __init__(self, loop, callback, tts, transport, cache_dir: Path, metric=None):
        self.loop, self.callback, self.tts = loop, callback, tts
        self.transport, self.cache_dir, self.metric = transport, cache_dir, metric
        self.lock = threading.RLock()
        self.minimum = 0
        self.seen: set[str] = set()
        self.queue = asyncio.Queue()
        self.active = None
        self.active_event = None
        self.stop_task = None
        self.closed = False
        self.worker = loop.create_task(self._run())

    def valid(self, event):
        with self.lock:
            return not self.closed and event.generation >= self.minimum

    def acknowledge(self, event, status, **fields):
        self.callback(
            PlaybackEvent(
                output_id=event.output_id,
                session_id=event.session_id,
                generation=event.generation,
                status=status,
                **fields,
            )
        )

    def submit(self, event):
        with self.lock:
            if not self.valid(event) or event.output_id in self.seen:
                return
            self.seen.add(event.output_id)
            if self.metric:
                self.metric(event, "tts_submit_ms")
            self.loop.call_soon_threadsafe(self.queue.put_nowait, event)

    def cancel_before(self, session_id, generation):
        with self.lock:
            if self.loop.is_closed():
                self.closed = True
                return
            if generation <= self.minimum or self.closed:
                return
            self.minimum = generation
            self.loop.call_soon_threadsafe(self._cancel, generation)

    def _cancel(self, generation):
        if self.active_event and self.active_event.generation >= generation:
            return
        if self.active:
            self.active.cancel()
        previous = self.stop_task

        async def stop():
            if previous:
                await previous
            await self.transport.stop()

        self.stop_task = self.loop.create_task(stop())

    def _audio(self, segment, fixed):
        cached = self.cache_dir / f"{self.tts.cache_key(segment.text)}.wav"
        if segment.audio_path:
            data = Path(segment.audio_path).read_bytes()
        elif fixed or cached.is_file():
            # Fixed audio must be prepared before connecting a device, including
            # development crisis placeholders. Never synthesize it during takeover.
            data = cached.read_bytes()
        else:
            data = self.tts.synthesize(segment.text)
        return data, self.tts.duration(data)

    async def _play(self, event):
        segments = (
            event.plan.segments[event.plan.start_index :]
            if event.plan
            else (PlaybackSegment(text=event.text),)
        )
        fixed_audio = [self._audio(segment, True) for segment in segments] if event.plan else None
        if (
            event.type == "exercise_plan"
            and sum(audio[1] + segment.pause_s for audio, segment in zip(fixed_audio, segments))
            > 90
        ):
            raise ValueError("Measured exercise exceeds 90 seconds")
        started = False
        for index, segment in enumerate(segments, event.plan.start_index if event.plan else 0):
            if fixed_audio is not None:
                data, _ = fixed_audio[index - event.plan.start_index]
            else:
                data, _ = await asyncio.to_thread(self._audio, segment, False)
            packets = await self.transport.encode(data)
            if not self.valid(event):
                raise asyncio.CancelledError
            if not started:
                await self.transport.start(event)
                self.acknowledge(event, "started")
                if self.metric:
                    self.metric(event, "server_audio_start_ms")
                started = True
            self.acknowledge(event, "segment", segment_index=index)
            await self.transport.play(packets, segment.text)
            await asyncio.sleep(segment.pause_s)
        if self.valid(event):
            await self.transport.finish()
            self.acknowledge(event, "completed")

    async def _run(self):
        while True:
            event = await self.queue.get()
            try:
                if event is None:
                    return
                if self.stop_task:
                    await self.stop_task
                if not self.valid(event):
                    self.acknowledge(event, "cancelled")
                    continue
                self.active_event = event
                self.active = self.loop.create_task(self._play(event))
                try:
                    await self.active
                except asyncio.CancelledError:
                    self.acknowledge(event, "cancelled")
                finally:
                    self.active = self.active_event = None
            except Exception as error:
                logger.exception("Device playback failed")
                self.acknowledge(event, "failed", error=type(error).__name__)
                await self.transport.stop()
            finally:
                self.queue.task_done()

    async def close(self):
        with self.lock:
            self.closed = True
        if self.active:
            self.active.cancel()
        if self.stop_task:
            await self.stop_task
        await self.transport.stop()
        self.queue.put_nowait(None)
        await self.worker
