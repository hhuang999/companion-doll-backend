"""Fixed synthetic multi-turn course replay with explicit targeted/natural separation."""

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

from companion.adapters.cli import build_core
from companion.adapters.output import RecordingOutputPort
from companion.content.admission import package_digest
from companion.core.config import Config
from companion.core.models import TurnSignals


class ReplayPort(RecordingOutputPort):
    def __init__(self, callback):
        super().__init__(callback, auto_complete=False)

    def submit(self, event):
        super().submit(event)
        if self.valid(event) and event.type != "exercise_plan":
            self.acknowledge(event, "completed")


def run(args):
    load_dotenv(args.env_file, override=False)
    config = Config(args.config_dir, mode="development")
    suite_path = config.directory / "course_scenarios.yaml"
    suite = config.read(suite_path.name)
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "report.json"
    if report_path.exists():
        raise ValueError("Evidence already exists; use a new output directory")
    report = {
        "phase": "final" if args.final else "debug",
        "fake": args.fake,
        "suite_version": suite["version"],
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "package_digest": package_digest(config),
        "models": {
            "llm": config.settings.llm.model_dump(exclude={"base_url", "api_key_env"}),
            "cognition": config.settings.cognition.model_dump(),
        },
        "criteria": suite["criteria"],
        "playback": "Recording port simulates server execution only; audio/WS measured separately; no device ACK",
        "scenarios": [],
    }

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    scenarios = [
        case for case in suite["scenarios"] if not args.only or case["id"] in args.only.split(",")
    ]
    if not scenarios:
        raise ValueError("No matching scenarios")
    for case in scenarios:
        config = Config(args.config_dir, mode="development")
        if case.get("target_card"):
            config.cards = {case["target_card"]: config.cards[case["target_card"]]}
            config.exercises = {}
        if case.get("target_exercise"):
            config.exercises = {case["target_exercise"]: config.exercises[case["target_exercise"]]}
            config.cards = {}
        core = build_core(config, destination / f"{case['id']}.db", args.fake)
        if args.fake and case.get("target_exercise"):
            core.llm.exercise_id = case["target_exercise"]
        user = "synthetic-course-" + case["id"] + "-" + uuid.uuid4().hex[:8]
        session = uuid.uuid4().hex
        port = ReplayPort(core.on_playback_event)
        core.bind_output(session, user, port)
        result = {
            "id": case["id"],
            "selection_mode": case["mode"],
            "coverage": case["coverage"],
            "target_card": case.get("target_card"),
            "target_exercise": case.get("target_exercise"),
            "samples": [],
            "forced_catalog": case["mode"] == "targeted",
            "errors": [],
        }
        report["scenarios"].append(result)
        try:
            for index, step in enumerate(case["turns"]):
                step = {"text": step} if isinstance(step, str) else step
                if step.get("reconnect"):
                    core.on_session_end(session, "synthetic_reconnect")
                    core.wait_idle(50)
                    session = uuid.uuid4().hex
                    core.bind_output(session, user, port)
                elif step.get("interrupt"):
                    core.on_interrupt(
                        session, core.sessions[session].state.generation, "synthetic_interrupt"
                    )
                elif step.get("playback"):
                    exercises = [
                        event
                        for event in port.events
                        if event.session_id == session and event.type == "exercise_plan"
                    ]
                    if exercises:
                        port.acknowledge(exercises[-1], step["playback"])
                    else:
                        result["errors"].append(f"step {index}: no exercise to acknowledge")
                else:
                    before, started = len(port.events), time.monotonic()
                    turn = core.on_input(
                        session,
                        str(index),
                        step.get("text", ""),
                        TurnSignals(),
                        step.get("kind", "user"),
                    )
                    for event in core.respond(session, turn):
                        core.dispatch(event)
                    idle = core.wait_idle(50)
                    sample = {
                        "index": index,
                        "session": session,
                        "input": step,
                        "outputs": [
                            event.model_dump(mode="json") for event in port.events[before:]
                        ],
                        "turn": core.store.query("SELECT * FROM turns WHERE id=?", (turn,))[0],
                        "policy": core.sessions[session]
                        .contexts[turn]
                        .policy_frame.model_dump(mode="json"),
                        "state": core.sessions[session].state.model_dump(mode="json"),
                        "background_idle": idle,
                        "elapsed_ms": (time.monotonic() - started) * 1000,
                    }
                    result["samples"].append(sample)
                    print(
                        f"{case['id']} {index + 1}/{len(case['turns'])} idle={idle} outputs={len(sample['outputs'])}",
                        flush=True,
                    )
                    save()
            core.on_session_end(session, "synthetic_replay")
            if not core.wait_idle(50):
                result["errors"].append("end/background did not drain")
        except Exception as error:
            import logging

            logging.getLogger(__name__).exception("Synthetic scenario %s failed", case["id"])
            result["errors"].append(f"{type(error).__name__}: {error}")
        finally:
            core.close()
            result["tables"] = {
                name: core.store.query(f"SELECT * FROM {name}")
                for name in (
                    "cognitive_jobs",
                    "agent_runs",
                    "support_plans",
                    "memory_items",
                    "interaction_events",
                    "end_tasks",
                )
            }
            outputs = [output for sample in result["samples"] for output in sample["outputs"]]
            target = case.get("target_card") or case.get("target_exercise")
            result["automatic_checks"] = {
                "no_driver_error": not result["errors"],
                "background_drained": all(
                    sample["background_idle"] for sample in result["samples"]
                ),
                "target_executed": any(
                    output.get("support", {}).get("identifier") == target
                    for output in outputs
                    if output.get("support")
                )
                if target
                else None,
                "end_done": bool(result["tables"]["end_tasks"])
                and all(row["status"] == "done" for row in result["tables"]["end_tasks"]),
            }
            core.store.close()
            save()
    print(f"Evidence: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only")
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--final", action="store_true")
    report = run(parser.parse_args())
    if any(
        any(value is False for value in case["automatic_checks"].values())
        for case in report["scenarios"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
