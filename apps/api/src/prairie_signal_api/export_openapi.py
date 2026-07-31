"""Export the canonical OpenAPI contract.

Usage:
    python -m prairie_signal_api.export_openapi
    python -m prairie_signal_api.export_openapi --check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prairie_signal_api.config import Settings
from prairie_signal_api.main import create_app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "openapi.json"


def rendered_schema() -> str:
    app = create_app(
        Settings(
            nws_user_agent="PrairieSignal-ContractGenerator/1.0",
            nws_contact="contract-generator@localhost",
        )
    )
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Prairie Signal's OpenAPI schema.")
    parser.add_argument("--check", action="store_true", help="Fail if the schema has drifted.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    expected = rendered_schema()

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected:
            parser.error(f"{args.output} is stale; run python -m prairie_signal_api.export_openapi")
        return 0

    args.output.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
