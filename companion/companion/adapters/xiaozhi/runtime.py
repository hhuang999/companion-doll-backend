"""Provider singleton and explicit immutable turn registration."""

import asyncio
import atexit
import logging
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

from companion.adapters.cli import build_core
from companion.core.config import Config
from companion.core.models import TurnSignals
from companion.llm.tts import TTSClient

from .output import XiaozhiOutputPort, XiaozhiTransport

logger = logging.getLogger(__name__)
_instances = {}
_lock = threading.Lock()


def get_core(options):
    root = Path(options["project_root"]).resolve()
    directory = Path(options.get("config_dir") or root / "companion/companion/config").resolve()
    key = (str(root), str(directory))
    with _lock:
        if key not in _instances:
            load_dotenv(root / ".env", override=False)
            config = Config(directory)
            core = build_core(config, root / config.settings.storage.db_path)
            core.device_tts = TTSClient(config)
            core.audio_cache_dir = root / "data/fixed_audio"
            # Check fixed audio before accepting connections.
            texts = {line.text for script in config.exercises.values() for line in script.lines}
            texts.update(
                config.persona[name] for name in ("onboarding", "greeting", "rest", "idle_end")
            )
            crisis = config.crisis
            texts.update([crisis["opening"], crisis["closing"], *crisis["responses"]])
            texts.update(text + crisis["resources"] for text in crisis["responses"])
            missing = [
                text
                for text in texts
                if not (core.audio_cache_dir / f"{core.device_tts.cache_key(text)}.wav").is_file()
            ]
            if missing:
                core.close()
                core.store.close()
                core.device_tts.close()
                raise ValueError(
                    "Fixed audio cache is incomplete; run companion.tools.prepare_audio"
                )
            _instances[key] = core
        return _instances[key]


def _close_instances():
    for core in _instances.values():
        core.close()
        core.device_tts.close()
        core.store.close()


atexit.register(_close_instances)


def interrupt_connection(conn, reason="device_abort"):
    core = getattr(conn, "_companion_core", None)
    runtime = core.sessions.get(conn.session_id) if core else None
    if runtime:
        core.on_interrupt(conn.session_id, runtime.state.generation, reason)


async def handle_input(conn, text, raw_signals, kind="user"):
    from core.handle.sendAudioHandle import send_stt_message

    core = conn.llm.companion_core
    if not getattr(conn, "_companion_port", None):
        conn._companion_core = core

        def metric(event, name):
            runtime = core.sessions.get(event.session_id)
            if runtime:
                with runtime.lock:
                    values = runtime.metrics[event.turn_id]
                    values.setdefault(
                        name, (time.monotonic() - runtime.contexts[event.turn_id].t0) * 1000
                    )
                    core.store.update_turn(event.turn_id, latency=dict(values))

        def playback(event):
            runtime = core.sessions.get(event.session_id)
            output = runtime.outputs.get(event.output_id) if runtime else None
            current = runtime and runtime.state.generation == event.generation
            core.on_playback_event(event)
            if current and output and output.purpose == "idle_end" and event.status == "completed":
                conn.loop.create_task(conn.close())

        port = XiaozhiOutputPort(
            conn.loop,
            playback,
            core.device_tts,
            XiaozhiTransport(conn),
            core.audio_cache_dir,
            metric,
        )
        core.bind_output(conn.session_id, conn.device_id, port)
        conn._companion_port = port

        async def disconnected():
            await conn.websocket.wait_closed()
            core.on_session_end(conn.session_id, "disconnect")
            await port.close()

        conn._companion_disconnect = conn.loop.create_task(disconnected())
    if kind == "user" and text.strip().rstrip("。！？!? ") in core.config.persona["exit_commands"]:
        core.on_session_end(conn.session_id, "user_exit")
        await conn.close()
        return
    signals = TurnSignals.model_validate(raw_signals)
    # Input registration runs off-loop; cancellation has its own independent hook.
    turn_id = await asyncio.to_thread(
        core.on_input, conn.session_id, uuid.uuid4().hex, text, signals, kind
    )
    if kind == "user":
        await send_stt_message(conn, text)

    def reply(session_id=conn.session_id, identifier=turn_id):
        try:
            for event in core.respond(session_id, identifier):
                core.dispatch(event)
        except Exception:
            logger.exception("Companion response task failed: %s/%s", session_id, identifier)

    conn.executor.submit(reply)
