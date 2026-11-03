"""Launch the pinned server with project-local native libraries and temporary files."""

import os
import runpy
import shutil
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "vendor/xiaozhi-esp32-server/main/xiaozhi-server"


def prepare_runtime():
    temporary = ROOT / "artifacts/tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(temporary), TMP=str(temporary))
    if sys.platform == "win32":
        libraries = Path(sysconfig.get_path("platlib")) / "av.libs"
        sources = list(libraries.glob("libopus-*.dll"))
        if len(sources) != 1:
            raise RuntimeError("Install the pinned PyAV wheel in the xiaozhi environment first")
        native = ROOT / "vendor/native"
        native.mkdir(exist_ok=True)
        target = native / "opus.dll"
        if not target.exists() or target.read_bytes() != sources[0].read_bytes():
            shutil.copy2(sources[0], target)
        os.environ["PATH"] = str(native) + os.pathsep + os.environ["PATH"]
    os.chdir(SERVER)
    sys.path.insert(0, str(SERVER))


if __name__ == "__main__":
    prepare_runtime()
    runpy.run_path(str(SERVER / "app.py"), run_name="__main__")
