"""One command to run Ghost Bills: seeds the demo if needed, starts API + web.

    uv run python -m scripts.dev        (or: make dev)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from backend import db, settings

ROOT = settings.ROOT
API_PORT = os.environ.get("GHOST_API_PORT", "8765")


def main() -> None:
    if not db.db_path().exists():
        print("No data yet: loading the demo statement...")
        from backend import seed_demo
        seed_demo.seed()

    npm = shutil.which("npm")
    if npm is None:
        sys.exit("Node.js is missing. Install it from https://nodejs.org and run again.")
    if not (ROOT / "frontend" / "node_modules").exists():
        subprocess.run([npm, "install"], cwd=ROOT / "frontend", check=True)

    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app",
                            "--port", API_PORT], cwd=ROOT)
    web = subprocess.Popen([npm, "run", "dev", "--", "--port", "5173"], cwd=ROOT / "frontend",
                           env={**os.environ, "GHOST_API_PORT": API_PORT})
    print(f"\nGhost Bills is starting: open http://localhost:5173  (API on port {API_PORT})")
    print("Press Ctrl+C to stop.\n")
    try:
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (api, web):
            p.terminate()


if __name__ == "__main__":
    main()
