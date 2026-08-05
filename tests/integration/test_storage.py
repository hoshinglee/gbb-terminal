from datetime import date, timedelta

import duckdb

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
    assert {"research_runs", "option_positions", "option_position_events", "provider_cache", "schema_migrations"} <= tables


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
    leg = state.legs[0]
    event = OptionLifecycleEvent(event_type="close", underlying_price=105, leg_id=leg.leg_id, option_marks={leg.leg_id: 7})
    closed = apply_event(state, event)
    store.append_option_event(state.position_id, event.model_dump(mode="json"), closed.model_dump(mode="json"))
    assert store.get_option_position(state.position_id)["status"] == "closed"
    assert len(store.list_option_events(state.position_id)) == 2


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
