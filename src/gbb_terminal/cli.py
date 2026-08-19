from __future__ import annotations

import argparse
import asyncio
import json

from .api.dependencies import build_services
from .intelligence.collection_models import IntelligenceRefreshRequest
from .universe.models import UniverseKey, UniverseRefreshRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gbb-terminal", description="Local GBB Terminal research workflows")
    commands = parser.add_subparsers(dest="command", required=True)
    intelligence = commands.add_parser("intelligence", help="Collect and inspect Company Intelligence sources")
    intelligence_commands = intelligence.add_subparsers(dest="intelligence_command", required=True)
    refresh = intelligence_commands.add_parser("refresh", help="Refresh SEC-backed intelligence for one company")
    refresh.add_argument("ticker")
    refresh.add_argument("--max-filings", type=int, default=24)
    refresh.add_argument("--form", action="append", dest="forms")
    refresh.add_argument("--no-exhibits", action="store_true")
    refresh.add_argument("--force", action="store_true")
    health = intelligence_commands.add_parser("health", help="Show the latest source coverage for one company")
    health.add_argument("ticker")
    universe = commands.add_parser("universe", help="Manage local research-universe data")
    universe_commands = universe.add_subparsers(dest="universe_command", required=True)
    universe_refresh = universe_commands.add_parser("refresh", help="Refresh a local research universe")
    universe_refresh.add_argument("universe", choices=[UniverseKey.SP500.value])
    universe_refresh.add_argument("--max-companies", type=int)
    universe_refresh.add_argument("--concurrency", type=int, default=4)
    universe_refresh.add_argument("--max-attempts", type=int, default=2)
    universe_refresh.add_argument("--fresh-hours", type=int, default=24)
    universe_refresh.add_argument("--force", action="store_true")
    universe_refresh.add_argument("--no-snapshot-refresh", action="store_true")
    universe_status = universe_commands.add_parser("status", help="Show local research-universe status")
    universe_status.add_argument("universe", choices=[UniverseKey.SP500.value])
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    services = build_services()
    try:
        if arguments.command == "intelligence" and arguments.intelligence_command == "refresh":
            request = IntelligenceRefreshRequest(
                forms=arguments.forms or IntelligenceRefreshRequest().forms,
                max_filings=arguments.max_filings,
                include_exhibits=not arguments.no_exhibits,
                force=arguments.force,
            )
            result = services.company_intelligence.refresh_sources(
                arguments.ticker,
                request,
                progress=lambda value, current: print(
                    f"{value * 100:5.1f}% {current or 'complete'}",
                    flush=True,
                ),
            )
        elif arguments.command == "intelligence":
            result = services.company_intelligence.source_health(arguments.ticker)
        elif arguments.universe_command == "refresh":
            request = UniverseRefreshRequest(
                refresh_snapshot=not arguments.no_snapshot_refresh,
                force=arguments.force,
                max_companies=arguments.max_companies,
                concurrency=arguments.concurrency,
                max_attempts=arguments.max_attempts,
                fresh_hours=arguments.fresh_hours,
            )
            result = asyncio.run(
                services.universe_research.refresh(
                    UniverseKey(arguments.universe),
                    request,
                    progress=lambda value, current: print(
                        f"{value * 100:5.1f}% {current or 'complete'}",
                        flush=True,
                    ),
                )
            )
        else:
            result = services.universe_research.status(UniverseKey(arguments.universe))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return 0
    finally:
        services.store.connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
