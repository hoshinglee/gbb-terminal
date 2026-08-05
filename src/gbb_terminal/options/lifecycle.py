from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from .models import (
    LifecycleEventType,
    OptionLifecycleEvent,
    OptionPositionCreate,
    OptionType,
    PositionLedgerState,
    PositionSide,
)


def initial_state(request: OptionPositionCreate) -> PositionLedgerState:
    premium_cash = 0.0
    for leg in request.legs:
        direction = -1 if leg.side == PositionSide.LONG else 1
        premium_cash += direction * leg.premium * leg.quantity * leg.multiplier
    share_basis = request.share_cost_basis or request.underlying_price
    cash = premium_cash - request.shares * share_basis
    collateral = position_collateral(request.legs, {}, request.shares)
    return PositionLedgerState(
        name=request.name,
        ticker=request.ticker.upper(),
        position_kind=request.position_kind,
        underlying_price=request.underlying_price,
        cash=round(cash, 2),
        shares=request.shares,
        share_cost_basis=share_basis if request.shares else 0.0,
        collateral=round(collateral, 2),
        legs=request.legs,
    )


def apply_event(state: PositionLedgerState, event: OptionLifecycleEvent) -> PositionLedgerState:
    if state.status != "open":
        raise ValueError("Only an open paper position can receive lifecycle events.")
    updated = state.model_copy(deep=True)
    updated.updated_at = event.event_at
    updated.underlying_price = event.underlying_price
    if event.event_type == LifecycleEventType.HOLD:
        return updated
    legs = updated.legs if event.leg_id is None else [leg for leg in updated.legs if leg.leg_id == event.leg_id]
    if not legs:
        raise ValueError("The selected option leg does not exist.")
    if event.event_type in {LifecycleEventType.CLOSE, LifecycleEventType.PARTIAL_CLOSE}:
        for leg in legs:
            already_closed = updated.closed_quantities.get(leg.leg_id, 0)
            open_quantity = leg.quantity - already_closed
            close_quantity = open_quantity if event.event_type == LifecycleEventType.CLOSE else int(event.quantity or 0)
            if close_quantity <= 0 or close_quantity > open_quantity:
                raise ValueError("Close quantity exceeds the open contracts.")
            if leg.leg_id not in event.option_marks:
                raise ValueError(f"Provide a current mark for leg {leg.leg_id}.")
            mark = event.option_marks[leg.leg_id]
            direction = 1 if leg.side == PositionSide.LONG else -1
            pnl = direction * (mark - leg.premium) * close_quantity * leg.multiplier
            cash_change = direction * mark * close_quantity * leg.multiplier
            updated.cash += cash_change
            updated.realized_pnl += pnl
            updated.closed_quantities[leg.leg_id] = already_closed + close_quantity
        if all(updated.closed_quantities.get(leg.leg_id, 0) == leg.quantity for leg in updated.legs):
            updated.status = "closed"
    elif event.event_type in {LifecycleEventType.ROLL_STRIKE, LifecycleEventType.ROLL_EXPIRY}:
        if len(legs) != 1:
            raise ValueError("Select one leg to roll.")
        leg = legs[0]
        mark = event.option_marks.get(leg.leg_id)
        if mark is None or event.new_premium is None:
            raise ValueError("Rolling requires the old mark and new premium.")
        quantity = leg.quantity - updated.closed_quantities.get(leg.leg_id, 0)
        direction = 1 if leg.side == PositionSide.LONG else -1
        updated.cash += direction * mark * quantity * leg.multiplier
        updated.realized_pnl += direction * (mark - leg.premium) * quantity * leg.multiplier
        replacement = deepcopy(leg)
        replacement.strike = event.new_strike or leg.strike
        replacement.expiration = event.new_expiration or leg.expiration
        replacement.premium = event.new_premium
        replacement.leg_id = f"{leg.leg_id}-roll-{int(event.event_at.timestamp())}"
        updated.cash += (-1 if replacement.side == PositionSide.LONG else 1) * replacement.premium * quantity * replacement.multiplier
        replacement.quantity = quantity
        updated.closed_quantities[leg.leg_id] = leg.quantity
        updated.legs.append(replacement)
    elif event.event_type in {LifecycleEventType.EXERCISE, LifecycleEventType.EARLY_ASSIGNMENT, LifecycleEventType.EXPIRY_ASSIGNMENT}:
        if len(legs) != 1:
            raise ValueError("Select one leg for exercise or assignment.")
        leg = legs[0]
        quantity = event.quantity or (leg.quantity - updated.closed_quantities.get(leg.leg_id, 0))
        shares = quantity * leg.multiplier
        if leg.option_type == OptionType.CALL:
            share_change = shares if leg.side == PositionSide.LONG else -shares
            cash_change = -share_change * leg.strike
        else:
            share_change = -shares if leg.side == PositionSide.LONG else shares
            cash_change = -share_change * leg.strike
        updated.shares += share_change
        updated.cash += cash_change
        updated.closed_quantities[leg.leg_id] = updated.closed_quantities.get(leg.leg_id, 0) + quantity
        updated.status = "exercised" if event.event_type == LifecycleEventType.EXERCISE else "assigned"
    elif event.event_type == LifecycleEventType.EXPIRE:
        for leg in legs:
            quantity = leg.quantity - updated.closed_quantities.get(leg.leg_id, 0)
            intrinsic = max(event.underlying_price - leg.strike, 0) if leg.option_type == OptionType.CALL else max(leg.strike - event.underlying_price, 0)
            if intrinsic > 0:
                raise ValueError("An in-the-money option requires an exercise or assignment event.")
            updated.closed_quantities[leg.leg_id] = updated.closed_quantities.get(leg.leg_id, 0) + quantity
        updated.status = "expired"
    updated.cash = round(updated.cash, 2)
    updated.realized_pnl = round(updated.realized_pnl, 2)
    updated.collateral = round(position_collateral(updated.legs, updated.closed_quantities, updated.shares), 2)
    updated.updated_at = datetime.now(timezone.utc)
    return updated


def position_collateral(legs, closed_quantities: dict[str, int], shares: int) -> float:
    collateral = 0.0
    covered_calls = shares // 100
    for short_leg in [leg for leg in legs if leg.side == PositionSide.SHORT]:
        open_quantity = max(short_leg.quantity - closed_quantities.get(short_leg.leg_id, 0), 0)
        if not open_quantity:
            continue
        if short_leg.option_type == OptionType.CALL and covered_calls:
            covered = min(open_quantity, covered_calls)
            open_quantity -= covered
            covered_calls -= covered
        protective = [
            leg for leg in legs
            if leg.side == PositionSide.LONG
            and leg.option_type == short_leg.option_type
            and leg.expiration == short_leg.expiration
            and (leg.strike > short_leg.strike if short_leg.option_type == OptionType.CALL else leg.strike < short_leg.strike)
            and leg.quantity > closed_quantities.get(leg.leg_id, 0)
        ]
        if protective and open_quantity:
            long_leg = min(protective, key=lambda leg: abs(leg.strike - short_leg.strike))
            protected_quantity = min(open_quantity, long_leg.quantity - closed_quantities.get(long_leg.leg_id, 0))
            collateral += abs(long_leg.strike - short_leg.strike) * protected_quantity * short_leg.multiplier
            open_quantity -= protected_quantity
        if short_leg.option_type == OptionType.PUT:
            collateral += short_leg.strike * open_quantity * short_leg.multiplier
    return collateral
