import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/companion.db"))
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    from streamlit.web import cli

    sys.argv = [
        "streamlit",
        "run",
        str(Path(__file__).with_name("app.py")),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
        "--",
        "--db",
        str(args.db.resolve()),
    ]
    cli.main()


if __name__ == "__main__":
    main()
