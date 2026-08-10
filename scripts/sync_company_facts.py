from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from gbb_terminal.api.dependencies import build_services


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize point-in-time SEC Company Facts for one company.")
    parser.add_argument("ticker_or_cik", help="A ticker already present in the company registry, or its SEC CIK.")
    arguments = parser.parse_args()
    result = build_services().financial_facts.sync_company_facts(arguments.ticker_or_cik)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
