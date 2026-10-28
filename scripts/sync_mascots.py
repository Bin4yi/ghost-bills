"""Copy the chosen asset thumbnails (.webp) into the frontend.

    uv run python -m scripts.sync_mascots [path/to/assets_ghost_bills_meta]

Pick versions first with the asset script (--pick name=N); this copies the
web-size copies of whatever is picked. The app shows placeholders for missing art.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "frontend" / "src" / "assets" / "mascots"


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "assets_ghost_bills_meta"
    if not src.is_dir():
        sys.exit(f"No asset folder at {src}")
    DEST.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src.glob("*.webp") if "_v" not in p.stem)
    for p in files:
        shutil.copy2(p, DEST / p.name)
    print(f"Copied {len(files)} files to {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
