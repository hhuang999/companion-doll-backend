"""Offline schema upgrade using the same writer lock and migration as normal startup."""

import argparse
import json
from pathlib import Path

from companion.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    store = Store(args.db)
    try:
        print(
            json.dumps(
                {
                    "schema_version": store.query("PRAGMA user_version")[0]["user_version"],
                    "backup": str(store.migration_backup) if store.migration_backup else None,
                    "database": str(args.db.resolve()),
                },
                ensure_ascii=False,
            )
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
