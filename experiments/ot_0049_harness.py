from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from open_trajectory_harness.ot0049 import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
