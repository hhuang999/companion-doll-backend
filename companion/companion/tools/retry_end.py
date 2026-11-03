"""Explicitly retry one failed end analysis while the backend is stopped."""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from companion.adapters.cli import build_core
from companion.core.config import Config
from companion.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id")
    parser.add_argument("--db", type=Path, default=Path("data/companion.db"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    store = Store(args.db)
    try:
        with store.transaction() as db:
            if db.execute(
                "SELECT 1 FROM sessions WHERE lifecycle IN ('active','ending')"
            ).fetchone():
                raise RuntimeError("Stop and finalize active sessions before retrying")
            result = db.execute(
                "UPDATE end_tasks SET status='pending' WHERE session_id=? AND status='failed'",
                (args.session_id,),
            )
            if result.rowcount != 1:
                raise ValueError("Session does not have a failed end task")
    finally:
        store.close()
    core = build_core(Config(args.config_dir), args.db, args.fake)
    try:
        if not core.wait_idle():
            raise TimeoutError("End analysis is still pending")
        row = core.store.query(
            "SELECT status,last_error FROM end_tasks WHERE session_id=?", (args.session_id,)
        )[0]
        if row["status"] != "done":
            raise RuntimeError(f"Retry failed: {row['last_error']}")
        print("End analysis completed.")
    finally:
        core.close()
        core.store.close()


if __name__ == "__main__":
    main()
