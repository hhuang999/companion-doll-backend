"""30 fixed ordinary dynamic replies through the actual local xiaozhi WebSocket server."""

import argparse
import asyncio
import json
import sqlite3
import statistics
import time
from pathlib import Path

from run_xiaozhi import ROOT, prepare_runtime


def rows(path, sql, args=()):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(sql, args)]


def distribution(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "p50": None, "p90": None}
    return {
        "n": len(values),
        "p50": statistics.median(values),
        "p90": values[int((len(values) - 1) * 0.9)],
    }


async def run(args):
    import opuslib_next
    from companion.adapters.xiaozhi.auth import client_headers
    from companion.core.config import Config
    from companion.tools.provision_device import simulation_credentials
    from websockets.asyncio.client import connect

    config = Config()
    prompts = config.read("bench.yaml")["prompts"]
    if args.credentials:
        user = json.loads(args.credentials.read_text(encoding="utf-8"))["user_key"]
        headers = client_headers(args.credentials)
    else:
        user, headers = simulation_credentials(ROOT, "voice")
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "user": user,
        "count_requested": args.count,
        "samples": [],
        "measurement": "loopback text input -> actual server WAV/TTS -> Opus -> WebSocket -> decode; no device speaker or ASR in these 30 samples",
        "conditions": "one sequential client; background cognition enabled; first request cold, later client reused; same host/Aihubmix network",
    }
    decoder = opuslib_next.Decoder(16000, 1)
    async with connect(args.url, additional_headers=headers) as ws:
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
        assert hello["type"] == "hello"
        session = hello["session_id"]
        report["session"] = session
        # Provider setup is asynchronous in the pinned upstream connection.
        await asyncio.sleep(3)
        for index in range(args.count):
            text = prompts[index % len(prompts)]
            sample = {
                "index": index + 1,
                "input": text,
                "packets": 0,
                "pcm_bytes": 0,
                "sentences": [],
                "status": "pending",
            }
            start = time.monotonic()
            try:
                await ws.send(json.dumps({"type": "listen", "state": "detect", "text": text}))
                while time.monotonic() - start < 75:
                    try:
                        message = await asyncio.wait_for(ws.recv(), 0.15)
                    except asyncio.TimeoutError:
                        message = None
                    if isinstance(message, bytes):
                        sample.setdefault(
                            "client_first_packet_ms", (time.monotonic() - start) * 1000
                        )
                        sample["packets"] += 1
                        sample["pcm_bytes"] += len(decoder.decode(message, 960))
                    elif message:
                        item = json.loads(message)
                        if item.get("type") == "tts" and item.get("state") == "sentence_start":
                            sample["sentences"].append(item.get("text"))
                    turns = rows(
                        args.db,
                        "SELECT * FROM turns WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
                        (session,),
                    )
                    if (
                        turns
                        and turns[0]["text"] == text
                        and turns[0]["output_status"] in ("generated", "error", "interrupted")
                    ):
                        turn = turns[0]
                        outputs = rows(
                            args.db,
                            "SELECT status FROM outputs WHERE turn_id=?",
                            (turn["id"],),
                        )
                        if outputs and all(
                            o["status"] in ("completed", "failed", "cancelled") for o in outputs
                        ):
                            sample["turn_id"] = turn["id"]
                            sample["metrics"] = json.loads(turn["latency"])
                            sample["violations"] = json.loads(turn["violations"])
                            sample["dynamic"] = (
                                "first_token_ms" in sample["metrics"]
                                and not sample["metrics"].get("fallback")
                                and "llm_error" not in sample["violations"]
                            )
                            sample["status"] = (
                                "completed"
                                if sample["packets"]
                                and sample["dynamic"]
                                and all(o["status"] == "completed" for o in outputs)
                                else "failed"
                            )
                            break
                else:
                    sample["status"] = "timed_out"
                    await ws.send(json.dumps({"type": "abort"}))
            except Exception as error:
                import logging

                logging.getLogger(__name__).exception("Voice sample %s failed", index + 1)
                sample["status"], sample["error"] = "failed", type(error).__name__
            sample["elapsed_ms"] = (time.monotonic() - start) * 1000
            report["samples"].append(sample)
            (args.output / "voice.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"voice {index + 1}/{args.count}: {sample['status']} first_packet={sample.get('client_first_packet_ms')}",
                flush=True,
            )
    # Disconnect schedules the durable end job; include its terminal usage.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        ends = rows(args.db, "SELECT status FROM end_tasks WHERE session_id=?", (session,))
        if ends and ends[0]["status"] in ("done", "failed"):
            break
        await asyncio.sleep(0.2)
    report["end_tasks"] = ends
    report["jobs"] = rows(args.db, "SELECT * FROM cognitive_jobs WHERE session_id=?", (session,))
    report["agent_runs"] = rows(
        args.db,
        "SELECT a.* FROM agent_runs a JOIN cognitive_jobs j USING(job_id) WHERE j.session_id=?",
        (session,),
    )
    report["summary"] = {
        key: distribution([s.get("metrics", {}).get(key) for s in report["samples"]])
        for key in (
            "first_token_ms",
            "first_sentence_ms",
            "gate_release_ms",
            "audio_queue_ms",
            "tts_start_ms",
            "tts_complete_ms",
            "opus_first_packet_ready_ms",
            "opus_first_packet_sent_ms",
            "server_completed_ms",
        )
    }
    report["summary"]["client_first_packet_ms"] = distribution(
        [s.get("client_first_packet_ms") for s in report["samples"]]
    )
    report["failures"] = sum(s["status"] != "completed" for s in report["samples"])
    (args.output / "voice.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--url", default="ws://127.0.0.1:8000/xiaozhi/v1/")
    parser.add_argument("--db", type=Path, default=ROOT / "data/xiaozhi.db")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/v2/voice1")
    parser.add_argument(
        "--credentials",
        type=Path,
        help="Private client credentials; omitted means provision a local synthetic identity",
    )
    args = parser.parse_args()
    args.output, args.db = args.output.resolve(), args.db.resolve()
    if args.credentials:
        args.credentials = args.credentials.resolve()
    prepare_runtime()
    asyncio.run(run(args))
