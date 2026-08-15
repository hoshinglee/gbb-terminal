from datetime import date, datetime, timedelta, timezone

import duckdb
import pandas as pd

from gbb_terminal.intelligence import CompanyIdentityRepository, CompanyProvenance, CompanyRegistration
from gbb_terminal.options.lifecycle import apply_event, initial_state
from gbb_terminal.options.models import OptionLifecycleEvent, OptionPositionCreate
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.strategy.catalogue import catalogue


def test_existing_database_migrates_without_losing_prices(tmp_path):
    path = tmp_path / "existing.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("""CREATE TABLE price_history (symbol VARCHAR, price_date DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, fetched_at TIMESTAMP, PRIMARY KEY(symbol, price_date))""")
    connection.execute("INSERT INTO price_history VALUES ('AAPL', '2024-01-02', 100, 102, 99, 101, 1000000, current_timestamp)")
    connection.close()
    store = LocalMarketStore(path)
    assert store.connection.execute("SELECT close FROM price_history WHERE symbol = 'AAPL'").fetchone()[0] == 101
    tables = {row[0] for row in store.connection.execute("SHOW TABLES").fetchall()}
    assert {
        "research_runs",
        "option_positions",
        "option_position_events",
        "provider_cache",
        "schema_migrations",
        "companies",
        "company_security_mappings",
            "sec_financial_facts",
            "valuation_series",
            "earnings_events",
            "earnings_reactions",
            "evidence_documents",
            "evidence_spans",
            "evidence_claim_links",
            "business_relationships",
            "relationship_observations",
            "operating_metric_definitions",
            "operating_metric_observations",
            "guidance_statements",
            "guidance_evaluations",
        } <= tables
    assert store.connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 13
    research_columns = {row[1] for row in store.connection.execute("PRAGMA table_info('research_runs')").fetchall()}
    assert {"strategy_key", "reproducibility_key"} <= research_columns
    assert "option_simulation_runs" in tables


def test_max_price_cache_supports_newer_listings_and_preserves_long_history(tmp_path):
    store = LocalMarketStore(tmp_path / "prices.duckdb")
    dates = pd.bdate_range(end=date.today(), periods=30)
    history = pd.DataFrame(
        {
            "Open": range(30),
            "High": range(1, 31),
            "Low": range(30),
            "Close": range(1, 31),
            "Volume": [1_000_000] * 30,
        },
        index=dates,
    )
    store.save_history("NEW", history)

    cached = store.load_history("NEW", "max")
    assert cached is not None
    assert len(cached) == 30

    store.save_history("NEW", history.tail(20).assign(Close=99))
    preserved = store.load_history("NEW", "max")
    assert preserved is not None
    assert len(preserved) == 30
    assert preserved.iloc[0]["Close"] == 1
    assert preserved.iloc[-1]["Close"] == 99


def test_company_identity_persists_across_database_reopen(tmp_path):
    path = tmp_path / "company-identity.duckdb"
    first_store = LocalMarketStore(path)
    identities = CompanyIdentityRepository(first_store.connection)
    observed = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    identity = identities.upsert_company(
        CompanyRegistration(
            cik="1045810",
            legal_name="NVIDIA CORP",
            primary_ticker="nvda",
            exchange="Nasdaq",
            effective_from=date(1999, 1, 22),
            provenance=CompanyProvenance(
                source="SEC EDGAR",
                dataset="sec_company_tickers",
                observation_timestamp=observed,
                known_at=observed,
                retrieved_at=observed,
            ),
        )
    )
    first_store.connection.close()

    reopened = CompanyIdentityRepository(LocalMarketStore(path).connection)
    assert reopened.resolve_ticker("NVDA").company_id == identity.company_id
    assert reopened.resolve_cik("0001045810").company_id == identity.company_id


def test_strategy_deduplication_and_option_event_persistence(tmp_path):
    store = LocalMarketStore(tmp_path / "terminal.duckdb")
    instance = catalogue.create_instance("sma-crossover", ticker="AAPL")
    strategy = catalogue.build(instance)
    first = store.save_strategy(instance.description, strategy.spec().to_dict(), "v2", strategy.to_yaml(), instance.semantic_key(), strategy_json=instance.model_dump(mode="json"), family="Trend", template_id=instance.template_id, template_version=2)
    second = store.save_strategy(instance.description, strategy.spec().to_dict(), "v2", strategy.to_yaml(), instance.semantic_key(), strategy_json=instance.model_dump(mode="json"), family="Trend", template_id=instance.template_id, template_version=2)
    assert first["id"] == second["id"]
    request = OptionPositionCreate.model_validate({"name": "Persistent Call", "ticker": "AAPL", "underlying_price": 100, "position_kind": "long_call", "paths": 50, "legs": [{"option_type": "call", "side": "long", "strike": 100, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 4, "quantity": 1, "implied_volatility": 0.25}]})
    state = initial_state(request)
    store.create_option_position(state.model_dump(mode="json"))
    assert store.list_option_positions()[0]["position_id"] == state.position_id
    leg = state.legs[0]
    event = OptionLifecycleEvent(event_type="close", underlying_price=105, leg_id=leg.leg_id, option_marks={leg.leg_id: 7})
    closed = apply_event(state, event)
    store.append_option_event(state.position_id, event.model_dump(mode="json"), closed.model_dump(mode="json"))
    assert store.get_option_position(state.position_id)["status"] == "closed"
    assert len(store.list_option_events(state.position_id)) == 2


def test_option_expiry_snapshots_do_not_replace_default_chain(tmp_path):
    store = LocalMarketStore(tmp_path / "option-expiries.duckdb")
    default_payload = {"expiration": "2026-09-18", "expirations": ["2026-09-18", "2026-12-18"], "calls": [{"contract": "DEFAULT"}], "puts": []}
    later_payload = {"expiration": "2026-12-18", "expirations": ["2026-09-18", "2026-12-18"], "calls": [{"contract": "LATER"}], "puts": []}

    store.save_options("NVDA", default_payload)
    store.save_options("NVDA", later_payload)

    assert store.load_options("NVDA")["expiration"] == "2026-09-18"
    assert store.load_options("NVDA", expiration="2026-12-18")["calls"][0]["contract"] == "LATER"


def test_strategy_cleanup_handles_legacy_key_collisions(tmp_path):
    store = LocalMarketStore(tmp_path / "collision.duckdb")
    first_instance = catalogue.create_instance("sma-crossover", {"fast_window": 5, "slow_window": 20})
    second_instance = catalogue.create_instance("sma-crossover", {"fast_window": 10, "slow_window": 50})
    first_strategy = catalogue.build(first_instance)
    second_strategy = catalogue.build(second_instance)
    first = store.save_strategy(first_instance.description, first_strategy.spec().to_dict(), "v2", first_strategy.to_yaml(), first_instance.semantic_key(), strategy_json=first_instance.model_dump(mode="json"))
    second = store.save_strategy(second_instance.description, second_strategy.spec().to_dict(), "v2", second_strategy.to_yaml(), second_instance.semantic_key(), strategy_json=second_instance.model_dump(mode="json"))

    store.connection.execute("UPDATE strategy_catalogue SET strategy_key = ?, fingerprint = ? WHERE strategy_id = ?", ["temporary-first", "temporary-first", first["id"]])
    store.connection.execute("UPDATE strategy_catalogue SET strategy_key = ?, fingerprint = ? WHERE strategy_id = ?", [first["key"], first["key"], second["id"]])
    store.connection.execute("UPDATE strategy_catalogue SET strategy_key = ?, fingerprint = ? WHERE strategy_id = ?", [second["key"], second["key"], first["id"]])
    expected_keys = {first["id"]: first["key"], second["id"]: second["key"]}

    def resolve(item):
        return {
            "key": expected_keys[item["id"]],
            "definition": {"name": item["name"], "description": item["description"], "strategy_type": item["strategy_type"], "direction": item["direction"], "parameters": item["parameters"]},
            "strategy_yaml": item["strategyYaml"],
            "strategy_json": item["strategyJson"],
        }

    assert store.deduplicate_strategies(resolve) == 0
    assert {item["id"]: item["key"] for item in store.list_strategies()} == expected_keys


def test_local_job_records_progress_result_and_cancellation(tmp_path):
    store = LocalMarketStore(tmp_path / "jobs.duckdb")
    completed_id = store.create_job("parameter_search", {"ticker": "AAPL"})
    store.update_job(completed_id, progress=0.5)
    assert store.get_job(completed_id)["progress"] == 0.5
    store.update_job(completed_id, result={"best": 20})
    assert store.get_job(completed_id)["status"] == "completed"
    cancelled_id = store.create_job("parameter_search", {"ticker": "MSFT"})
    assert store.request_job_cancellation(cancelled_id) is True
    assert store.job_cancellation_requested(cancelled_id) is True
