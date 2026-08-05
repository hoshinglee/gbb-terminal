from datetime import date, timedelta

from gbb_terminal.options.lifecycle import apply_event, initial_state
from gbb_terminal.options.models import OptionLifecycleEvent, OptionPositionCreate


def position_request(side="long", option_type="call", strike=100, premium=4):
    return OptionPositionCreate.model_validate({
        "name": "Golden Position",
        "ticker": "TEST",
        "underlying_price": 100,
        "position_kind": f"{side}_{option_type}",
        "paths": 50,
        "legs": [{"option_type": option_type, "side": side, "strike": strike, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": premium, "quantity": 1, "implied_volatility": 0.25}],
    })


def test_long_call_close_reconciles_cash_and_realized_pnl():
    state = initial_state(position_request())
    leg = state.legs[0]
    closed = apply_event(state, OptionLifecycleEvent(event_type="close", underlying_price=108, leg_id=leg.leg_id, option_marks={leg.leg_id: 9}))
    assert state.cash == -400
    assert closed.cash == 500
    assert closed.realized_pnl == 500
    assert closed.status == "closed"


def test_short_put_assignment_acquires_shares_and_releases_collateral():
    state = initial_state(position_request("short", "put", strike=95, premium=2))
    leg = state.legs[0]
    assigned = apply_event(state, OptionLifecycleEvent(event_type="expiry_assignment", underlying_price=90, leg_id=leg.leg_id))
    assert state.cash == 200
    assert assigned.cash == -9300
    assert assigned.shares == 100
    assert assigned.collateral == 0
    assert assigned.status == "assigned"


def test_out_of_money_expiry_preserves_premium():
    state = initial_state(position_request("short", "put", strike=95, premium=2))
    expired = apply_event(state, OptionLifecycleEvent(event_type="expire", underlying_price=100))
    assert expired.cash == 200
    assert expired.status == "expired"

