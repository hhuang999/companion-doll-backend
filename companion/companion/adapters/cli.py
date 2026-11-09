import argparse
import json
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv

from companion.core.api import CompanionCore
from companion.core.config import Config
from companion.core.models import TurnSignals
from companion.llm.client import AihubmixClient
from companion.llm.fake import FakeLLM
from companion.store import Store

from .output import ConsoleOutputPort


def build_core(
    config: Config, db_path: Path | None = None, fake: bool = False, *, recover: bool = True
) -> CompanionCore:
    store = Store(
        db_path or config.settings.storage.db_path, config.settings.storage.busy_timeout_ms
    )
    llm = None
    try:
        llm = FakeLLM() if fake else AihubmixClient(config.settings.llm)
        return CompanionCore(config, store, llm, recover=recover)
    except BaseException:
        close = getattr(llm, "close", None)
        if close:
            close()
        store.close()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Companion development console")
    parser.add_argument(
        "--fake", action="store_true", help="Use deterministic development fixtures"
    )
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--device", default="cli-local")
    parser.add_argument("--mode", choices=["development", "demo"])
    parser.add_argument("--realtime", action="store_true", help="Observe exercise pauses")
    parser.add_argument("--scenario", type=Path)
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    logging.basicConfig(level=logging.WARNING)
    config = Config(args.config_dir, mode=args.mode)
    core = build_core(config, args.db, args.fake)
    if args.scenario:
        from .scenarios import replay

        try:
            print(
                json.dumps(replay(core, args.scenario, args.device), ensure_ascii=False, indent=2)
            )
        finally:
            core.close()
            core.store.close()
        return
    session_id = uuid.uuid4().hex
    output = ConsoleOutputPort(core.on_playback_event, realtime=args.realtime)
    core.bind_output(session_id, args.device, output)
    print(
        f"mode={config.settings.runtime.mode}; model={'fake fixtures' if args.fake else config.settings.llm.talker_model}"
    )
    print(
        "Commands: /state, /policy, /memory, /jobs, /wait, /cry TEXT, /emotion SAD TEXT, /end, /quit"
    )

    def turn(text: str, kind: str = "user", signals: TurnSignals | None = None) -> None:
        identifier = core.on_input(
            session_id, uuid.uuid4().hex, text, signals or TurnSignals(), kind
        )
        for event in core.respond(session_id, identifier):
            core.dispatch(event)
        if not args.realtime:
            output.wait_idle()

    try:
        turn("", "wake")
        while session_id in core.sessions and core.sessions[session_id].state.lifecycle == "active":
            try:
                text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text == "/quit" or text.rstrip("。！？!? ") in config.persona["exit_commands"]:
                break
            if text == "/state":
                print(core.sessions[session_id].state.model_dump_json(indent=2))
                continue
            if text == "/wait":
                print(f"background_idle={core.wait_idle()}")
                continue
            if text in ("/policy", "/memory", "/jobs"):
                state = core.sessions[session_id].state
                if text == "/memory":
                    value = core.cognition.memory.retrieve(state, "").model_dump(mode="json")
                elif text == "/policy":
                    context = core.sessions[session_id].contexts.get(state.latest_turn_id)
                    value = {
                        "active_plan": core.store.active_support_plan(session_id).model_dump(
                            mode="json"
                        )
                        if core.store.active_support_plan(session_id)
                        else None,
                        "last_turn_policy": context.policy_frame.model_dump(mode="json")
                        if context
                        else None,
                    }
                else:
                    value = core.store.cognitive_diagnostics(state.user_key, session_id)
                print(json.dumps(value, ensure_ascii=False, indent=2))
                continue
            if text == "/end":
                turn("", "idle_end")
                break
            signals = TurnSignals()
            if text.startswith("/cry "):
                text = text[5:]
                signals = TurnSignals(events=("Cry",), emotion="SAD")
            elif text.startswith("/emotion "):
                _, emotion, text = text.split(" ", 2)
                signals = TurnSignals(emotion=emotion)
            if text:
                turn(text, signals=signals)
    finally:
        core.on_session_end(session_id, "user_exit")
        core.close()
        output.close()
        core.store.close()


if __name__ == "__main__":
    main()
