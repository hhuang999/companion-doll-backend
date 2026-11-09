import argparse
from contextlib import closing
from pathlib import Path

from companion.store import Store
from companion.store.lease import WriterLease


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Purge an offline user's data. Stop the backend first."
    )
    parser.add_argument("user_key")
    parser.add_argument("--db", type=Path, default=Path("data/companion.db"))
    args = parser.parse_args()
    with closing(Store(args.db)) as store, closing(WriterLease(store.path)):
        active = store.query(
            "SELECT 1 FROM sessions WHERE user_key=? AND lifecycle IN ('active','ending')",
            (args.user_key,),
        )
        if active:
            raise RuntimeError(
                "User has active or unfinished sessions. Use CompanionCore.purge_user() in the running backend, or finish/recover sessions first."
            )
        store.purge_user(args.user_key)
        print("User data removed.")


if __name__ == "__main__":
    main()
