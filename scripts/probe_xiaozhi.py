"""Exercise the running local server with synthetic input (calls paid AI APIs)."""

import asyncio
import json
import sqlite3
import time

from run_xiaozhi import ROOT, SERVER, prepare_runtime


async def main():
    import opuslib_next
    from companion.tools.provision_device import simulation_credentials
    from core.providers.asr.utils import lang_tag_filter
    from core.utils.textUtils import EMOJI_MAP
    from core.utils.util import audio_to_data
    from websockets.asyncio.client import connect

    tagged = lang_tag_filter("<|zh|><|SAD|><|Cry|><|withitn|>我很难过")
    assert tagged["raw_emotion"] == "SAD" and tagged["event"] == "Cry"
    assert lang_tag_filter("<|zh|>你好")["raw_emotion"] is None
    crying = lang_tag_filter("<|zh|><|SAD|><|Cry|><|withitn|>")
    assert crying["event"] == "Cry" and crying["content"] == "[检测到哭声，无可识别文字]"
    user, headers = simulation_credentials(ROOT, "integration")
    report = {"user_key": user, "tag_parser": "passed", "rounds": []}
    decoder = opuslib_next.Decoder(16000, 1)

    async def receive_reply(ws, name, *, abort=False):
        started = time.monotonic()
        result = {"name": name, "sentences": [], "packets": 0, "pcm_bytes": 0}
        abort_at = None
        while True:
            message = await asyncio.wait_for(
                ws.recv(), max(0.01, 90 - (time.monotonic() - started))
            )
            if isinstance(message, bytes):
                result["packets"] += 1
                result["pcm_bytes"] += len(decoder.decode(message, 960))
                result.setdefault("first_packet_ms", (time.monotonic() - started) * 1000)
                if abort and abort_at is None:
                    abort_at = time.monotonic()
                    await ws.send(json.dumps({"type": "abort", "reason": "wake_word_detected"}))
            else:
                event = json.loads(message)
                if event.get("type") == "stt":
                    result["transcript"] = event.get("text")
                if event.get("type") == "llm":
                    result["expression"] = {key: event[key] for key in ("text", "emotion")}
                if event.get("type") == "tts" and event.get("state") == "sentence_start":
                    result["sentences"].append(event.get("text"))
                if (
                    event.get("type") == "tts"
                    and event.get("state") == "stop"
                    and result["packets"]
                ):
                    if abort_at:
                        result["abort_to_stop_ms"] = (time.monotonic() - abort_at) * 1000
                    break
        assert result["pcm_bytes"] > 0 and result["sentences"], result
        assert result["expression"]["emotion"] == EMOJI_MAP.get(
            result["expression"]["text"], "neutral"
        )
        report["rounds"].append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result

    async def send_text(ws, text):
        await ws.send(json.dumps({"type": "listen", "state": "detect", "text": text}))

    async def open_connection():
        ws = await connect("ws://127.0.0.1:8000/xiaozhi/v1/", additional_headers=headers)
        await ws.send(
            json.dumps(
                {
                    "type": "hello",
                    "version": 1,
                    "transport": "websocket",
                    "audio_params": {
                        "format": "opus",
                        "sample_rate": 16000,
                        "channels": 1,
                        "frame_duration": 60,
                    },
                }
            )
        )
        hello = json.loads(await asyncio.wait_for(ws.recv(), 15))
        assert hello["type"] == "hello", hello
        # Upstream initializes connection providers on an executor after accepting it.
        await asyncio.sleep(3)
        return ws, hello["session_id"]

    ws, first_session = await open_connection()
    report["first_session"] = first_session
    try:
        await send_text(ws, "你好小智")
        opening = await receive_reply(ws, "wake_onboarding")
        assert "AI" in "".join(opening["sentences"])
        await send_text(ws, "今天写作业有点累，想和你说说。")
        await receive_reply(ws, "normal_response")
        await send_text(ws, "我现在要跳楼")
        await receive_reply(ws, "crisis_abort", abort=True)
        # Drain the second idempotent stop emitted by the upstream abort handler.
        while True:
            try:
                event = await asyncio.wait_for(ws.recv(), 0.5)
                assert not isinstance(event, bytes), "Old audio continued after stop"
            except asyncio.TimeoutError:
                break
    finally:
        await ws.close()
    ws, second_session = await open_connection()
    report["second_session"] = second_session
    assert second_session != first_session
    try:
        await send_text(ws, "你好小智")
        returning = await receive_reply(ws, "returning_wake")
        assert "我是 AI" not in "".join(returning["sentences"])
        # Feed upstream's official Chinese example through the actual Opus ASR route.
        await asyncio.sleep(2.1)
        packets = await audio_to_data(
            str(SERVER / "models/SenseVoiceSmall/example/zh.mp3"), use_cache=False
        )
        await ws.send(json.dumps({"type": "listen", "state": "start", "mode": "manual"}))
        for packet in packets:
            await ws.send(packet)
            await asyncio.sleep(0.06)
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({"type": "listen", "state": "stop"}))
        recognized = await receive_reply(ws, "real_asr")
        assert recognized.get("transcript"), recognized
    finally:
        await ws.close()
    await asyncio.sleep(1)
    deadline = time.monotonic() + 45
    while True:
        with sqlite3.connect(ROOT / "data/xiaozhi.db") as db:
            jobs = db.execute(
                "SELECT session_id,status,last_error FROM end_tasks WHERE session_id IN (?,?)",
                (first_session, second_session),
            ).fetchall()
        if len(jobs) == 2 and all(job[1] in ("done", "failed") for job in jobs):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("Session end jobs did not complete")
        await asyncio.sleep(0.5)
    report["end_tasks"] = jobs
    with sqlite3.connect(ROOT / "data/xiaozhi.db") as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT input_kind,text,signals,interrupted,risk_level FROM turns WHERE user_key=? ORDER BY id",
            (user,),
        ).fetchall()
        report["turns"] = [dict(row) for row in rows]
        for table, columns in (
            ("reasoner_runs", "kind,status,error,duration_ms"),
            ("risk_events", "level,detection_status,source"),
        ):
            report[table] = [
                dict(row)
                for row in db.execute(
                    f"SELECT {columns} FROM {table} WHERE session_id IN (?,?)",
                    (first_session, second_session),
                )
            ]
        assert any(row["input_kind"] == "wake" for row in rows)
        assert any(row["risk_level"] == "high" for row in rows)
        assert (
            db.execute("SELECT onboarding_done FROM users WHERE user_key=?", (user,)).fetchone()[0]
            == 1
        )
        assert (
            db.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_key=? AND ended_at IS NOT NULL", (user,)
            ).fetchone()[0]
            == 2
        )
    (ROOT / "artifacts/xiaozhi-integration.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert all(job[1] == "done" for job in jobs), jobs
    print("Integration probe passed; report: artifacts/xiaozhi-integration.json")


if __name__ == "__main__":
    prepare_runtime()
    from config.settings import check_config_file

    check_config_file()
    asyncio.run(main())
