"""Run with an isolated wheel environment: python -I scripts/check_v2_wheel.py OUT."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from companion.adapters.cli import build_core
from companion.adapters.output import RecordingOutputPort
from companion.core.config import Config
from companion.core.models import SessionState, TurnSignals
from companion.store import Store
from companion.tools.upgrade_config import upgrade

import companion


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = Path(companion.__file__).resolve().parent
    assert "site-packages" in str(package), package
    config = Config()
    assert config.directory.is_relative_to(package)
    for role in ("analysis", "brief", "planner", "critic", "delta", "memory", "end"):
        assert (config.directory / "prompts" / f"{role}.j2").is_file()
    assert (package / "store/migrations/002.sql").is_file()
    assert (package / "tools/resources/config-v2-baseline.json").is_file()
    assert len(config.cards) == 6 and len(config.exercises) == 3
    assert config.read("course_scenarios.yaml")["version"] == "course-quality-1"
    deployment = output / "config"
    upgrade(deployment)
    settings = deployment / "settings.yaml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace("history_turns: 10", "history_turns: 8"),
        encoding="utf-8",
    )
    upgrade(deployment)
    assert Config(deployment).settings.dialogue.history_turns == 8
    assert upgrade(deployment)["changed"] == []
    core = build_core(config, output / "empty.db", fake=True)
    core.bind_output("wheel", "synthetic-wheel", RecordingOutputPort(core.on_playback_event))
    turn = core.on_input("wheel", "1", "我一直反复想那次考试，怎么办", TurnSignals())
    for event in core.respond("wheel", turn):
        core.dispatch(event)
    assert core.wait_idle()
    roles = {r["role"] for r in core.store.query("SELECT role FROM agent_runs")}
    assert {"analysis", "brief", "planner", "critic"} <= roles
    assert core.store.query("SELECT * FROM support_plans")
    core.close()
    assert core.store.query("SELECT status FROM end_tasks")[0]["status"] == "done"
    core.store.close()

    legacy = output / "legacy.db"
    with sqlite3.connect(legacy) as db:
        db.executescript((package / "store/schema.sql").read_text(encoding="utf-8"))
        state = SessionState(session_id="legacy", user_key="synthetic-old")
        db.execute(
            "INSERT INTO users VALUES ('synthetic-old',?,1)",
            (state.started_at.isoformat(),),
        )
        db.execute(
            "INSERT INTO sessions(session_id,user_key,started_at,state) VALUES (?,?,?,?)",
            (
                state.session_id,
                state.user_key,
                state.started_at.isoformat(),
                state.model_dump_json(),
            ),
        )
        db.execute(
            "INSERT INTO turns(id,session_id,user_key,input_id,role,text,created_at) VALUES (1,'legacy','synthetic-old','1','user','我叫小林',?)",
            (state.started_at.isoformat(),),
        )
        db.execute(
            "INSERT INTO profile VALUES ('synthetic-old','nickname','小林',1,'[1]',?)",
            (state.started_at.isoformat(),),
        )
    upgraded = Store(legacy)
    assert upgraded.query("PRAGMA user_version")[0]["user_version"] == 2
    items = upgraded.memory_items("synthetic-old")
    assert len(items) == 1 and items[0].value == "小林" and items[0].epistemic_status == "stated"
    backup = upgraded.migration_backup
    assert backup.is_file()
    upgraded.close()
    again = Store(legacy)
    assert len(again.memory_items("synthetic-old")) == 1 and again.migration_backup is None
    again.close()
    cli = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "companion.adapters.cli",
            "--fake",
            "--db",
            str(output / "cli.db"),
        ],
        input="/policy\n/memory\n/jobs\n/quit\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    (output / "cli.txt").write_text(cli.stdout + cli.stderr, encoding="utf-8")
    assert cli.returncode == 0, cli.stderr
    report = {
        "package": str(package),
        "python": sys.executable,
        "roles": sorted(roles),
        "empty": "passed",
        "v1_upgrade": "passed",
        "repeat": "passed",
        "cli": "passed",
        "backup": str(backup),
        "content_resources": "six strategies, three exercises, fixed replay suite",
        "config_upgrade": "customized settings preserved; idempotent",
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
