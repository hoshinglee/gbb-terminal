from __future__ import annotations

from copy import deepcopy

from .models import (
    LifecycleEventType,
    OptionLifecycleEvent,
    OptionPositionCreate,
    OptionType,
    PositionLedgerState,
    PositionSide,
)


def classify_position(legs, closed_quantities: dict[str, int], shares: int) -> str:
    open_legs = [leg for leg in legs if leg.quantity > closed_quantities.get(leg.leg_id, 0)]
    long_calls = [leg for leg in open_legs if leg.option_type == OptionType.CALL and leg.side == PositionSide.LONG]
    short_calls = [leg for leg in open_legs if leg.option_type == OptionType.CALL and leg.side == PositionSide.SHORT]
    long_puts = [leg for leg in open_legs if leg.option_type == OptionType.PUT and leg.side == PositionSide.LONG]
    short_puts = [leg for leg in open_legs if leg.option_type == OptionType.PUT and leg.side == PositionSide.SHORT]
    conversion_share_requirement = sum(leg.quantity * leg.multiplier for leg in short_calls)
    conversion_put_cover = sum(
        leg.quantity * leg.multiplier
        for leg in long_puts
        if short_calls and leg.strike == short_calls[0].strike and leg.expiration == short_calls[0].expiration
    )
    if shares == conversion_share_requirement and conversion_share_requirement > 0 and conversion_put_cover >= conversion_share_requirement:
        return "Conversion"
    if short_calls and shares >= sum(leg.quantity * leg.multiplier for leg in short_calls):
        return "Covered Call" if not short_puts else "Covered Call + Short Put"
    if short_calls and shares > 0:
        return "Partially Covered Short Call"
    if short_calls and short_puts:
        return "Short Call + Short Put"
    if short_calls and any(long_call.strike > short_call.strike and long_call.expiration == short_call.expiration for short_call in short_calls for long_call in long_calls):
        return "Bear Call Spread"
    if short_calls and any(long_call.strike < short_call.strike and long_call.expiration == short_call.expiration for short_call in short_calls for long_call in long_calls):
        return "Bull Call Spread"
    if short_puts and any(long_put.strike < short_put.strike and long_put.expiration == short_put.expiration for short_put in short_puts for long_put in long_puts):
        return "Bull Put Spread"
    if short_puts and any(long_put.strike > short_put.strike and long_put.expiration == short_put.expiration for short_put in short_puts for long_put in long_puts):
        return "Bear Put Spread"
    if len(open_legs) == 1:
        leg = open_legs[0]
        return f"{leg.side.title()} {leg.option_type.title()}"
    if not open_legs and shares:
        return "Long Shares" if shares > 0 else "Short Shares"
    if not open_legs:
        return "Cash"
    return "Custom Multi-Leg"


def apply_share_trade(state: PositionLedgerState, quantity: int, price: float) -> None:
    if quantity == 0:
        return
    existing_shares = state.shares
    existing_basis = state.share_cost_basis
    resulting_shares = existing_shares + quantity
    state.cash -= quantity * price
    if existing_shares == 0 or (existing_shares > 0) == (quantity > 0):
        total_cost = abs(existing_shares) * existing_basis + abs(quantity) * price
        state.share_cost_basis = total_cost / abs(resulting_shares)
    else:
        closing_quantity = min(abs(existing_shares), abs(quantity))
        if existing_shares > 0:
            state.realized_pnl += closing_quantity * (price - existing_basis)
        else:
            state.realized_pnl += closing_quantity * (existing_basis - price)
        if resulting_shares == 0:
            state.share_cost_basis = 0.0
        elif (resulting_shares > 0) != (existing_shares > 0):
            state.share_cost_basis = price
    state.shares = resulting_shares


def has_open_exposure(state: PositionLedgerState) -> bool:
    return state.shares != 0 or any(
        leg.quantity > state.closed_quantities.get(leg.leg_id, 0)
        for leg in state.legs
    )


def initial_state(request: OptionPositionCreate) -> PositionLedgerState:
    premium_cash = 0.0
    for leg in request.legs:
        direction = -1 if leg.side == PositionSide.LONG else 1
        premium_cash += direction * leg.premium * leg.quantity * leg.multiplier
    share_basis = request.share_cost_basis or request.underlying_price
    cash = premium_cash - request.shares * share_basis
    collateral = position_collateral(request.legs, {}, request.shares)
    state = PositionLedgerState(
        name=request.name,
        ticker=request.ticker.upper(),
        position_kind=request.position_kind,
        research_run_id=request.research_run_id,
        underlying_price=request.underlying_price,
        cash=round(cash, 2),
        shares=request.shares,
        share_cost_basis=share_basis if request.shares else 0.0,
        collateral=round(collateral, 2),
        legs=request.legs,
    )
    state.current_structure = classify_position(state.legs, state.closed_quantities, state.shares)
    return state


def apply_event(state: PositionLedgerState, event: OptionLifecycleEvent) -> PositionLedgerState:
    if state.status != "open":
        raise ValueError("Only an open paper position can receive lifecycle events.")
    updated = state.model_copy(deep=True)
    updated.updated_at = event.event_at
    updated.underlying_price = event.underlying_price
    if event.event_type == LifecycleEventType.HOLD:
        return updated
    if event.event_type == LifecycleEventType.BUY_SHARES:
        quantity = int(event.quantity or 0)
        if quantity <= 0:
            raise ValueError("Buying shares requires a positive share quantity.")
        apply_share_trade(updated, quantity, event.underlying_price)
    elif event.event_type == LifecycleEventType.SELL_SHARES:
        quantity = int(event.quantity or 0)
        if quantity <= 0 or quantity > updated.shares:
            raise ValueError("Share sale quantity exceeds the paper shares held.")
        apply_share_trade(updated, -quantity, event.underlying_price)
    elif event.event_type == LifecycleEventType.ADD_LEG:
        if event.new_leg is None:
            raise ValueError("Adding an option leg requires a complete validated new leg.")
        if any(leg.leg_id == event.new_leg.leg_id for leg in updated.legs):
            raise ValueError("The new option leg identifier already exists.")
        direction = -1 if event.new_leg.side == PositionSide.LONG else 1
        updated.cash += direction * event.new_leg.premium * event.new_leg.quantity * event.new_leg.multiplier
        updated.legs.append(event.new_leg)
    else:
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
        replacement.contract_symbol = None
        replacement.premium_source = "manual"
        updated.cash += (-1 if replacement.side == PositionSide.LONG else 1) * replacement.premium * quantity * replacement.multiplier
        replacement.quantity = quantity
        updated.closed_quantities[leg.leg_id] = leg.quantity
        updated.legs.append(replacement)
    elif event.event_type in {LifecycleEventType.EXERCISE, LifecycleEventType.EARLY_ASSIGNMENT, LifecycleEventType.EXPIRY_ASSIGNMENT}:
        if len(legs) != 1:
            raise ValueError("Select one leg for exercise or assignment.")
        leg = legs[0]
        open_quantity = leg.quantity - updated.closed_quantities.get(leg.leg_id, 0)
        quantity = event.quantity or open_quantity
        if quantity <= 0 or quantity > open_quantity:
            raise ValueError("Exercise or assignment quantity exceeds the open contracts.")
        shares = quantity * leg.multiplier
        if leg.option_type == OptionType.CALL:
            share_change = shares if leg.side == PositionSide.LONG else -shares
        else:
            share_change = -shares if leg.side == PositionSide.LONG else shares
        apply_share_trade(updated, share_change, leg.strike)
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
    if has_open_exposure(updated):
        updated.status = "open"
    elif event.event_type in {LifecycleEventType.BUY_SHARES, LifecycleEventType.SELL_SHARES}:
        updated.status = "closed"
    updated.cash = round(updated.cash, 2)
    updated.share_cost_basis = round(updated.share_cost_basis, 6)
    updated.realized_pnl = round(updated.realized_pnl, 2)
    updated.collateral = round(position_collateral(updated.legs, updated.closed_quantities, updated.shares), 2)
    updated.current_structure = classify_position(updated.legs, updated.closed_quantities, updated.shares)
    updated.updated_at = event.event_at
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
