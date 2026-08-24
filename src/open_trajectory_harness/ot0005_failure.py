from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .ot0002 import canonical_json, load_json


def reconstruct_failure(raw: dict[str, Any]) -> dict[str, Any]:
    if (
        raw.get("schema_version") != 1
        or raw.get("experiment_id") != "OT-0005"
        or raw.get("run_id") != "ot-0005-hosted-epoch-001"
        or not isinstance(raw.get("public_summary"), dict)
    ):
        raise ValueError("invalid OT-0005 failure aggregate")
    return raw["public_summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ot-0005-failure")
    parser.add_argument("--reconstruct", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = reconstruct_failure(load_json(args.reconstruct))
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
