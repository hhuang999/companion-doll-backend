"""Fixed synthetic v2 probe/replay. All raw evidence stays in the chosen local directory."""

import argparse
import json
import platform
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

from companion.adapters.cli import build_core
from companion.adapters.output import RecordingOutputPort
from companion.core.config import Config
from companion.core.models import TurnSignals


def export(core, samples, target, phase):
    tables = (
        "cognitive_jobs",
        "agent_runs",
        "support_plans",
        "memory_items",
        "interaction_events",
        "end_tasks",
    )
    report = {
        "phase": phase,
        "python": platform.python_version(),
        "samples": samples,
        "settings": core.config.settings.model_dump(mode="json"),
        "tables": {table: core.store.query(f"SELECT * FROM {table}") for table in tables},
    }
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["probe", "quality"])
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--only", help="Comma-separated fixed scenario IDs for a targeted repair check"
    )
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    args.output.mkdir(parents=True, exist_ok=True)
    config = Config()
    core = build_core(config, args.output / "acceptance.db", args.fake)
    scenarios = config.read("v2_scenarios.yaml")["scenarios"]
    if args.phase == "probe":
        scenarios = scenarios[:2]
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only.split(",")]
    samples = []
    report_path = args.output / "report.json"
    try:
        for scenario in scenarios:
            session = uuid.uuid4().hex
            port = RecordingOutputPort(core.on_playback_event)
            core.bind_output(session, "synthetic-" + scenario["id"], port)
            for index, text in enumerate(scenario["turns"]):
                previous = len(port.events)
                started = time.monotonic()
                identifier = core.on_input(session, str(index), text, TurnSignals())
                for event in core.respond(session, identifier):
                    core.dispatch(event)
                if index == 0 and core.sessions[session].state.mode == "normal":
                    core.reasoner.submit(
                        core.sessions[session].state.user_key,
                        session,
                        "periodic" if scenario["id"] == "Q01" else "ask_for_help",
                    )
                idle = core.wait_idle(25)
                row = core.store.query("SELECT * FROM turns WHERE id=?", (identifier,))[0]
                sample = {
                    "scenario": scenario["id"],
                    "index": index,
                    "input": text,
                    "outputs": [e.model_dump(mode="json") for e in port.events[previous:]],
                    "turn": row,
                    "background_idle": idle,
                    "elapsed_ms": (time.monotonic() - started) * 1000,
                    "policy": core.sessions[session]
                    .contexts[identifier]
                    .policy_frame.model_dump(mode="json"),
                }
                samples.append(sample)
                export(core, samples, report_path, args.phase)
                print(
                    f"{scenario['id']} turn={index + 1} idle={idle} outputs={len(sample['outputs'])}",
                    flush=True,
                )
            core.on_session_end(session, "synthetic_replay")
            core.wait_idle(25)
            export(core, samples, report_path, args.phase)
    finally:
        core.close()
        export(core, samples, report_path, args.phase)
        core.store.close()
    print(f"Evidence: {report_path}")


if __name__ == "__main__":
    main()
