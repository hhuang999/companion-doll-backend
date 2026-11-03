import argparse
import json
import platform
import statistics
import uuid
from pathlib import Path

from dotenv import load_dotenv

from companion.adapters.cli import build_core
from companion.adapters.output import RecordingOutputPort
from companion.core.config import Config
from companion.core.models import TurnSignals


def distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "p90": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "median": round(statistics.median(values), 2),
        "p90": round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.9))], 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--model", help="Override Talker model for a controlled comparison")
    parser.add_argument("--output", type=Path, default=Path("artifacts/latency.json"))
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    if args.count < 1:
        parser.error("count must be positive")
    config = Config()
    if args.model:
        config.settings.llm.talker_model = args.model
    prompts = config.read("bench.yaml")["prompts"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    core = build_core(config, args.output.with_suffix(".db"), args.fake)
    session_id = uuid.uuid4().hex
    port = RecordingOutputPort(core.on_playback_event)
    core.bind_output(session_id, "benchmark", port)
    samples = []
    try:
        ordinary = 0
        for index in range(args.count * 3):
            start_events = len(port.events)
            identifier = core.on_input(
                session_id, str(index), prompts[index % len(prompts)], TurnSignals()
            )
            for event in core.respond(session_id, identifier):
                core.dispatch(event)
            core.wait_idle()
            row = core.store.query(
                "SELECT latency,violations FROM turns WHERE id=?", (identifier,)
            )[0]
            metrics = json.loads(row["latency"])
            model_reply = (
                "first_token_ms" in metrics
                and not metrics.get("fallback")
                and "llm_error" not in json.loads(row["violations"])
            )
            sample = {
                "turn_id": identifier,
                "model_reply": model_reply,
                "metrics": metrics,
                "violations": json.loads(row["violations"]),
                "outputs": len(port.events) - start_events,
            }
            samples.append(sample)
            if model_reply:
                ordinary += 1
            print(
                f"normal={ordinary}/{args.count} total={len(samples)} gate_ms={metrics.get('gate_release_ms')}",
                flush=True,
            )
            if ordinary >= args.count:
                break
        model_samples = [s for s in samples if s["model_reply"]]
        report = {
            "fake": args.fake,
            "model": config.settings.llm.talker_model,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "context_user_turn_limit": config.settings.dialogue.history_turns,
            "generation": {
                "temperature": 0.7,
                "max_tokens": 160,
                "enable_thinking": config.settings.llm.enable_thinking,
            },
            "warmth": "SDK initialized before timing; first request cold, later requests reuse client",
            "network": "Current host network to configured Aihubmix endpoint",
            "samples": samples,
            "model_reply_count": len(model_samples),
            "total_turns": len(samples),
            "errors": sum("llm_error" in s["violations"] for s in samples),
            "risk_degraded_turns": core.store.query(
                "SELECT COUNT(*) AS n FROM risk_events WHERE session_id=? AND detection_status IN ('timeout','error')",
                (session_id,),
            )[0]["n"],
            "fallback_turns": sum(
                bool(s["metrics"].get("fallback")) or "llm_error" in s["violations"]
                for s in samples
            ),
            "metrics": {
                name: distribution(
                    [s["metrics"][name] for s in model_samples if name in s["metrics"]]
                )
                for name in (
                    "first_token_ms",
                    "first_sentence_ms",
                    "gate_release_ms",
                    "output_submit_ms",
                    "total_ms",
                )
            },
            "scope": "text core with risk and reasoner enabled; output_submit is a recording port, not TTS or device first audio",
        }
        report["core_900ms_target_met"] = (
            len(model_samples) >= args.count
            and report["metrics"]["gate_release_ms"]["median"] <= 900
        )
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {k: v for k, v in report.items() if k != "samples"}, ensure_ascii=False, indent=2
            )
        )
    finally:
        core.close()
        core.store.close()


if __name__ == "__main__":
    main()
