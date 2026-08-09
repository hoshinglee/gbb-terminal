from datetime import date, timedelta

from gbb_terminal.options.lifecycle import apply_event, initial_state
from gbb_terminal.options.models import OptionLeg, OptionLifecycleEvent, OptionPositionCreate


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
    assert assigned.share_cost_basis == 95
    assert assigned.collateral == 0
    assert assigned.status == "open"
    assert assigned.current_structure == "Long Shares"


def test_out_of_money_expiry_preserves_premium():
    state = initial_state(position_request("short", "put", strike=95, premium=2))
    expired = apply_event(state, OptionLifecycleEvent(event_type="expire", underlying_price=100))
    assert expired.cash == 200
    assert expired.status == "expired"


def test_short_call_can_buy_shares_and_become_covered():
    state = initial_state(position_request("short", "call", strike=120, premium=4))
    covered = apply_event(state, OptionLifecycleEvent(event_type="buy_shares", underlying_price=105, quantity=100))

    assert covered.cash == -10100
    assert covered.shares == 100
    assert covered.share_cost_basis == 105
    assert covered.current_structure == "Covered Call"
    assert covered.status == "open"


def test_short_call_can_add_higher_call_to_cap_upside_risk():
    state = initial_state(position_request("short", "call", strike=100, premium=4))
    hedge = OptionLeg.model_validate({
        "option_type": "call",
        "side": "long",
        "strike": 120,
        "expiration": state.legs[0].expiration,
        "premium": 1.5,
        "quantity": 1,
        "implied_volatility": 0.25,
    })
    spread = apply_event(state, OptionLifecycleEvent(event_type="add_leg", underlying_price=105, quantity=1, new_leg=hedge))

    assert spread.cash == 250
    assert spread.collateral == 2000
    assert spread.current_structure == "Bear Call Spread"


def test_short_call_can_add_cash_secured_put_as_separate_obligation():
    state = initial_state(position_request("short", "call", strike=120, premium=4))
    short_put = OptionLeg.model_validate({
        "option_type": "put",
        "side": "short",
        "strike": 90,
        "expiration": state.legs[0].expiration,
        "premium": 2,
        "quantity": 1,
        "implied_volatility": 0.25,
    })
    combined = apply_event(state, OptionLifecycleEvent(event_type="add_leg", underlying_price=100, quantity=1, new_leg=short_put))

    assert combined.cash == 600
    assert combined.collateral == 9000
    assert combined.current_structure == "Short Call + Short Put"


def test_conversion_early_call_assignment_keeps_long_put_open():
    expiration = date.today() + timedelta(days=30)
    state = initial_state(OptionPositionCreate.model_validate({
        "name": "Conversion",
        "ticker": "TEST",
        "underlying_price": 100,
        "position_kind": "conversion",
        "shares": 100,
        "share_cost_basis": 100,
        "paths": 50,
        "legs": [
            {"option_type": "put", "side": "long", "strike": 100, "expiration": expiration, "premium": 4, "quantity": 1, "implied_volatility": 0.25},
            {"option_type": "call", "side": "short", "strike": 100, "expiration": expiration, "premium": 5, "quantity": 1, "implied_volatility": 0.25},
        ],
    }))
    call = state.legs[1]
    assigned = apply_event(state, OptionLifecycleEvent(event_type="early_assignment", underlying_price=110, leg_id=call.leg_id))

    assert assigned.shares == 0
    assert assigned.realized_pnl == 0
    assert assigned.status == "open"
    assert assigned.current_structure == "Long Put"


def test_assignment_rejects_more_contracts_than_remain_open():
    state = initial_state(position_request("short", "call", strike=100, premium=4))
    leg = state.legs[0]

    try:
        apply_event(state, OptionLifecycleEvent(event_type="early_assignment", underlying_price=110, leg_id=leg.leg_id, quantity=2))
    except ValueError as error:
        assert "exceeds the open contracts" in str(error)
    else:
        raise AssertionError("Expected an oversized assignment to be rejected.")


def test_buying_back_assigned_short_shares_closes_flat_ledger():
    state = initial_state(position_request("short", "call", strike=100, premium=4))
    leg = state.legs[0]
    assigned = apply_event(state, OptionLifecycleEvent(event_type="early_assignment", underlying_price=110, leg_id=leg.leg_id))
    covered = apply_event(assigned, OptionLifecycleEvent(event_type="buy_shares", underlying_price=90, quantity=100))

    assert assigned.current_structure == "Short Shares"
    assert assigned.share_cost_basis == 100
    assert covered.shares == 0
    assert covered.realized_pnl == 1000
    assert covered.status == "closed"
