from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .analysis import position_profile
from .models import (
    OptionLeg,
    OptionOutlook,
    OptionPlanRequest,
    OptionScenarioRequest,
    OptionSimulationRequest,
    OptionType,
    PositionKind,
    PositionSide,
)
from .simulation import position_comparison, position_greeks_at, position_pnl_at, position_value_at


PLANNER_KINDS = {
    PositionKind.LONG_CALL,
    PositionKind.LONG_PUT,
    PositionKind.COVERED_CALL,
    PositionKind.CASH_SECURED_PUT,
    PositionKind.BULL_CALL_SPREAD,
    PositionKind.BEAR_CALL_SPREAD,
    PositionKind.BULL_PUT_SPREAD,
    PositionKind.BEAR_PUT_SPREAD,
}

POSITION_NAMES = {
    PositionKind.LONG_CALL: "Long Call",
    PositionKind.LONG_PUT: "Long Put",
    PositionKind.COVERED_CALL: "Covered Call",
    PositionKind.CASH_SECURED_PUT: "Cash-Secured Put",
    PositionKind.BULL_CALL_SPREAD: "Bull Call Spread",
    PositionKind.BEAR_CALL_SPREAD: "Bear Call Spread",
    PositionKind.BULL_PUT_SPREAD: "Bull Put Spread",
    PositionKind.BEAR_PUT_SPREAD: "Bear Put Spread",
}

TRADEOFFS = {
    PositionKind.LONG_CALL: "Defined premium risk and uncapped theoretical upside, with time decay working against the position.",
    PositionKind.LONG_PUT: "Defined premium risk and convex downside exposure, with time decay working against the position.",
    PositionKind.COVERED_CALL: "Premium income against owned shares, but upside is capped and share downside remains.",
    PositionKind.CASH_SECURED_PUT: "Premium income with cash reserved for a possible share purchase at the strike.",
    PositionKind.BULL_CALL_SPREAD: "Lower debit than a long call, with both maximum loss and upside capped.",
    PositionKind.BEAR_CALL_SPREAD: "Defined-risk credit exposure that benefits when the stock stays below the short call.",
    PositionKind.BULL_PUT_SPREAD: "Defined-risk credit exposure that benefits when the stock stays above the short put.",
    PositionKind.BEAR_PUT_SPREAD: "Lower debit than a long put, with both maximum loss and downside gain capped.",
}


def select_plan_expiration(expirations: list[str], target_date: date, as_of: date | None = None) -> tuple[str, list[str]]:
    today = as_of or date.today()
    parsed = sorted({date.fromisoformat(value) for value in expirations if date.fromisoformat(value) >= today})
    if not parsed:
        raise ValueError("No current listed option expirations are available for this ticker.")
    warnings = []
    on_or_after = [expiration for expiration in parsed if expiration >= target_date]
    if on_or_after:
        selected = on_or_after[0]
    else:
        selected = parsed[-1]
        warnings.append("The requested horizon is beyond the longest listed expiration; the latest available expiry is shown.")
    return selected.isoformat(), warnings


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _premium(contract: dict[str, Any], side: PositionSide) -> tuple[float, str]:
    bid, ask, last, mid = (_number(contract.get(key)) for key in ("bid", "ask", "last", "mid"))
    choices = (
        [(ask, "ask"), (last, "last"), (mid, "mid"), (bid, "bid")]
        if side == PositionSide.LONG
        else [(bid, "bid"), (last, "last"), (mid, "mid"), (ask, "ask")]
    )
    return next(((value, source) for value, source in choices if value > 0), (0.0, "manual"))


def _contracts(chain: dict[str, Any], option_type: OptionType) -> list[dict[str, Any]]:
    key = "calls" if option_type == OptionType.CALL else "puts"
    return sorted(
        [contract for contract in chain.get(key, []) if _number(contract.get("strike")) > 0],
        key=lambda contract: _number(contract.get("strike")),
    )


def _nearest(contracts: list[dict[str, Any]], target: float, *, above: float | None = None, below: float | None = None) -> dict[str, Any] | None:
    eligible = [
        contract
        for contract in contracts
        if (above is None or _number(contract.get("strike")) > above)
        and (below is None or _number(contract.get("strike")) < below)
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda contract: (
            abs(_number(contract.get("strike")) - target),
            0 if contract.get("quoteQuality") == "Two-Sided" else 1,
            -int(_number(contract.get("openInterest"))),
        ),
    )


def _leg(contract: dict[str, Any], option_type: OptionType, side: PositionSide, expiration: str, index: int) -> OptionLeg:
    premium, source = _premium(contract, side)
    if premium <= 0:
        raise ValueError("A selected contract has no usable bid, ask, last, or midpoint quote.")
    return OptionLeg(
        leg_id=f"planner-leg-{index + 1}",
        option_type=option_type,
        side=side,
        strike=_number(contract.get("strike")),
        expiration=date.fromisoformat(expiration),
        premium=premium,
        implied_volatility=max(_number(contract.get("iv")) / 100, 0.0001),
        contract_symbol=str(contract.get("contract") or "") or None,
        premium_source=source,
    )


def _quote_snapshot(contract: dict[str, Any], leg: OptionLeg) -> dict[str, Any]:
    bid, ask = _number(contract.get("bid")), _number(contract.get("ask"))
    midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
    return {
        "legId": leg.leg_id,
        "contractSymbol": leg.contract_symbol,
        "optionType": leg.option_type,
        "side": leg.side,
        "strike": leg.strike,
        "bid": round(bid, 4),
        "ask": round(ask, 4),
        "last": round(_number(contract.get("last")), 4),
        "spread": round(max(ask - bid, 0), 4),
        "spreadPercent": round((ask - bid) / midpoint * 100, 2) if midpoint > 0 else None,
        "quoteQuality": contract.get("quoteQuality") or ("Two-Sided" if bid > 0 and ask > 0 else "Incomplete Quote"),
        "premiumUsed": leg.premium,
        "premiumSource": leg.premium_source,
        "impliedVolatility": round(leg.implied_volatility * 100, 2),
        "volume": int(_number(contract.get("volume"))),
        "openInterest": int(_number(contract.get("openInterest"))),
        "lastTradeAt": contract.get("lastTradeAt"),
    }


def _candidate_specs(request: OptionPlanRequest, spot: float, chain: dict[str, Any]) -> list[tuple[PositionKind, list[tuple[dict[str, Any], OptionType, PositionSide]]]]:
    calls, puts = _contracts(chain, OptionType.CALL), _contracts(chain, OptionType.PUT)
    call_at_money = _nearest(calls, spot)
    put_at_money = _nearest(puts, spot)
    upper_target = request.target_price_high or request.target_price or spot * 1.08
    lower_target = request.target_price_low or request.target_price or spot * 0.92
    specs = []

    def add(kind: PositionKind, legs: list[tuple[dict[str, Any] | None, OptionType, PositionSide]]) -> None:
        if all(contract is not None for contract, _, _ in legs):
            specs.append((kind, [(contract, option_type, side) for contract, option_type, side in legs if contract is not None]))

    if request.outlook == OptionOutlook.BULLISH:
        add(PositionKind.LONG_CALL, [(call_at_money, OptionType.CALL, PositionSide.LONG)])
        add(PositionKind.BULL_CALL_SPREAD, [
            (call_at_money, OptionType.CALL, PositionSide.LONG),
            (_nearest(calls, max(upper_target, spot * 1.03), above=_number(call_at_money.get("strike")) if call_at_money else spot), OptionType.CALL, PositionSide.SHORT),
        ])
        if request.acquiring_shares_acceptable:
            add(PositionKind.CASH_SECURED_PUT, [(_nearest(puts, min(lower_target, spot * 0.98)), OptionType.PUT, PositionSide.SHORT)])
        else:
            short_put = _nearest(puts, spot * 0.97)
            add(PositionKind.BULL_PUT_SPREAD, [
                (short_put, OptionType.PUT, PositionSide.SHORT),
                (_nearest(puts, min(lower_target, spot * 0.9), below=_number(short_put.get("strike")) if short_put else spot), OptionType.PUT, PositionSide.LONG),
            ])
    elif request.outlook == OptionOutlook.BEARISH:
        add(PositionKind.LONG_PUT, [(put_at_money, OptionType.PUT, PositionSide.LONG)])
        add(PositionKind.BEAR_PUT_SPREAD, [
            (put_at_money, OptionType.PUT, PositionSide.LONG),
            (_nearest(puts, min(lower_target, spot * 0.97), below=_number(put_at_money.get("strike")) if put_at_money else spot), OptionType.PUT, PositionSide.SHORT),
        ])
        short_call = _nearest(calls, spot * 1.03)
        add(PositionKind.BEAR_CALL_SPREAD, [
            (short_call, OptionType.CALL, PositionSide.SHORT),
            (_nearest(calls, max(upper_target, spot * 1.1), above=_number(short_call.get("strike")) if short_call else spot), OptionType.CALL, PositionSide.LONG),
        ])
    else:
        if request.shares_owned >= 100:
            add(PositionKind.COVERED_CALL, [(_nearest(calls, max(upper_target, spot * 1.03)), OptionType.CALL, PositionSide.SHORT)])
        if request.acquiring_shares_acceptable:
            add(PositionKind.CASH_SECURED_PUT, [(_nearest(puts, min(lower_target, spot * 0.97)), OptionType.PUT, PositionSide.SHORT)])
        short_call = _nearest(calls, max(upper_target, spot * 1.04))
        add(PositionKind.BEAR_CALL_SPREAD, [
            (short_call, OptionType.CALL, PositionSide.SHORT),
            (_nearest(calls, spot * 1.12, above=_number(short_call.get("strike")) if short_call else spot), OptionType.CALL, PositionSide.LONG),
        ])
        if len(specs) < 3:
            short_put = _nearest(puts, min(lower_target, spot * 0.96))
            add(PositionKind.BULL_PUT_SPREAD, [
                (short_put, OptionType.PUT, PositionSide.SHORT),
                (_nearest(puts, spot * 0.88, below=_number(short_put.get("strike")) if short_put else spot), OptionType.PUT, PositionSide.LONG),
            ])
    return specs[:3]


def _profit_character(kind: PositionKind) -> str:
    if kind == PositionKind.LONG_CALL:
        return "Uncapped Theoretical Upside"
    if kind == PositionKind.LONG_PUT:
        return "Capped At An Underlying Price Of Zero"
    return "Capped"


def _candidate(
    request: OptionPlanRequest,
    spot: float,
    expiration: str,
    chain: dict[str, Any],
    kind: PositionKind,
    leg_specs: list[tuple[dict[str, Any], OptionType, PositionSide]],
) -> dict[str, Any]:
    legs = [_leg(contract, option_type, side, expiration, index) for index, (contract, option_type, side) in enumerate(leg_specs)]
    shares = 100 if kind == PositionKind.COVERED_CALL else 0
    provenance = {
        "source": chain.get("source") or chain.get("dataStatus", {}).get("source") or "Yahoo Finance",
        "status": chain.get("dataStatus", {}).get("status") or "Delayed",
        "expiration": expiration,
        "observationTimestamp": chain.get("dataStatus", {}).get("observationTimestamp"),
        "knownAt": chain.get("dataStatus", {}).get("knownAt"),
        "retrievedAt": chain.get("dataStatus", {}).get("retrievedAt"),
        "qualityWarnings": chain.get("dataStatus", {}).get("qualityWarnings", []),
    }
    position = OptionSimulationRequest(
        run_name=f"{request.ticker.upper()} {POSITION_NAMES[kind]} Plan",
        ticker=request.ticker.upper(),
        underlying_price=spot,
        position_kind=kind,
        legs=legs,
        shares=shares,
        share_cost_basis=spot if shares else None,
        interest_rate=request.interest_rate,
        dividend_yield=request.dividend_yield,
        paths=200,
        seed=42,
        data_provenance=provenance,
    )
    comparison = position_comparison(position)
    profile = comparison["positionProfile"]
    summary = comparison["summary"]
    option_debit = profile["longPremiumDebit"]
    option_credit = profile["shortPremiumCredit"]
    maximum_loss = summary["maximumLoss"]
    numeric_loss = abs(float(maximum_loss)) if isinstance(maximum_loss, (int, float)) else None
    capital_required = max(float(profile["netCapitalCommitted"]), numeric_loss or 0)
    within_budget = not (
        (request.maximum_loss is not None and (numeric_loss is None or numeric_loss > request.maximum_loss))
        or (request.capital_budget is not None and capital_required > request.capital_budget)
    )
    quote_snapshots = [_quote_snapshot(contract, leg) for leg, (contract, _, _) in zip(legs, leg_specs, strict=True)]
    warnings = list(provenance["qualityWarnings"])
    if any(quote["quoteQuality"] != "Two-Sided" for quote in quote_snapshots):
        warnings.append("At least one leg has an incomplete quote; a labelled fallback premium was used.")
    if kind == PositionKind.COVERED_CALL:
        warnings.append("The planner assumes a current share cost basis because the actual owned-share basis was not supplied.")
    return {
        "candidateId": f"{kind}:{expiration}:{'-'.join(str(leg.strike) for leg in legs)}",
        "name": POSITION_NAMES[kind],
        "positionKind": kind,
        "tradeoff": TRADEOFFS[kind],
        "position": position.model_dump(mode="json"),
        "expiration": expiration,
        "strikes": [leg.strike for leg in legs],
        "netDebit": round(max(option_debit - option_credit, 0), 2),
        "netCredit": round(max(option_credit - option_debit, 0), 2),
        "capitalRequired": round(capital_required, 2),
        "collateral": summary["collateral"],
        "maximumLoss": maximum_loss,
        "maximumGain": summary["maximumGain"],
        "profitCharacter": _profit_character(kind),
        "breakEvens": summary["breakEvens"],
        "greeks": comparison["greeks"]["aggregate"],
        "quotes": quote_snapshots,
        "quoteQuality": "Two-Sided" if all(quote["quoteQuality"] == "Two-Sided" for quote in quote_snapshots) else "Incomplete Quote",
        "withinBudget": within_budget,
        "warnings": list(dict.fromkeys(warnings)),
    }


def option_implied_move(chain: dict[str, Any], spot: float) -> dict[str, Any] | None:
    call = _nearest(_contracts(chain, OptionType.CALL), spot)
    put = _nearest(_contracts(chain, OptionType.PUT), spot)
    if call is None or put is None:
        return None

    def mark(contract: dict[str, Any]) -> tuple[float, str]:
        bid, ask, last = _number(contract.get("bid")), _number(contract.get("ask")), _number(contract.get("last"))
        if bid > 0 and ask > 0:
            return (bid + ask) / 2, "mid"
        return (last, "last") if last > 0 else (max(bid, ask), "one-sided quote")

    call_mark, call_source = mark(call)
    put_mark, put_source = mark(put)
    if call_mark <= 0 or put_mark <= 0:
        return None
    return {
        "movePercent": round((call_mark + put_mark) / spot * 100, 2),
        "straddlePrice": round(call_mark + put_mark, 2),
        "strike": _number(call.get("strike")),
        "expiration": chain.get("expiration"),
        "quoteMethod": f"Call {call_source} + put {put_source}",
        "interpretation": "Selected-expiry at-the-money straddle context. The next earnings date is not verified, so this is not labelled an earnings-implied move.",
    }


def build_option_plan(
    request: OptionPlanRequest,
    underlying_price: float,
    chain: dict[str, Any],
    expiration_warnings: list[str] | None = None,
    earnings_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expiration = chain.get("expiration")
    if not expiration:
        raise ValueError("The selected option chain has no listed expiration.")
    specs = _candidate_specs(request, underlying_price, chain)
    candidates = []
    candidate_warnings = []
    for kind, leg_specs in specs:
        if kind not in PLANNER_KINDS:
            continue
        try:
            candidates.append(_candidate(request, underlying_price, expiration, chain, kind, leg_specs))
        except ValueError as error:
            candidate_warnings.append(f"{POSITION_NAMES[kind]} was omitted: {error}")
    if not candidates:
        raise ValueError("The current chain does not contain enough usable contracts to build a validated comparison.")
    warnings = [*(expiration_warnings or []), *candidate_warnings]
    if request.outlook == OptionOutlook.NEUTRAL and request.shares_owned < 100 and not request.acquiring_shares_acceptable:
        warnings.append("No supported fully neutral structure fits this ownership context; the shown defined-risk spreads retain directional exposure.")
    if not any(candidate["withinBudget"] for candidate in candidates) and (request.maximum_loss or request.capital_budget):
        warnings.append("No candidate fits every stated risk budget; the smallest available validated structures remain visible for comparison.")
    return {
        "ticker": request.ticker.upper(),
        "outlook": request.outlook,
        "targetDate": request.target_date.isoformat(),
        "underlyingPrice": round(underlying_price, 2),
        "expiration": expiration,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "earningsContext": earnings_context,
        "impliedMoveContext": option_implied_move(chain, underlying_price),
        "dataProvenance": {
            "source": chain.get("source") or chain.get("dataStatus", {}).get("source") or "Yahoo Finance",
            "status": chain.get("dataStatus", {}).get("status") or "Delayed",
            "observationTimestamp": chain.get("dataStatus", {}).get("observationTimestamp"),
            "knownAt": chain.get("dataStatus", {}).get("knownAt"),
            "retrievedAt": chain.get("dataStatus", {}).get("retrievedAt"),
        },
        "warnings": list(dict.fromkeys(warnings)),
        "limitations": [
            "These are educational comparisons, not recommendations or objectively optimal trades.",
            "Current public option quotes may be delayed, stale, wide, or non-executable.",
            "Taxes, commissions, early assignment, pin risk, and broker-specific margin are not included in this comparison.",
        ],
    }


def scenario_position(request: OptionScenarioRequest) -> dict[str, Any]:
    position = request.position
    values = position_value_at(position, request.scenario_price, request.scenario_date)
    pnl = position_pnl_at(position, request.scenario_price, request.scenario_date)
    comparison = position_comparison(position)
    break_evens = comparison["summary"]["breakEvens"]
    nearest_break_even = min(break_evens, key=lambda value: abs(value - request.scenario_price)) if break_evens else None
    if nearest_break_even is None:
        relation = "No expiry break-even was identified on the modeled payoff grid."
    elif abs(request.scenario_price - nearest_break_even) < 0.01:
        relation = "At the nearest modeled expiry break-even."
    elif request.scenario_price > nearest_break_even:
        relation = f"${request.scenario_price - nearest_break_even:.2f} above the nearest modeled expiry break-even."
    else:
        relation = f"${nearest_break_even - request.scenario_price:.2f} below the nearest modeled expiry break-even."
    expirations = sorted({leg.expiration for leg in position.legs})
    remaining_days = max((expirations[-1] - request.scenario_date).days, 0)
    warnings = [
        "The modeled value is theoretical and is not an executable bid or ask.",
        "Expiry break-even describes terminal payoff; pre-expiry P&L also depends on time and implied volatility.",
    ]
    if any(request.scenario_date > expiration for expiration in expirations):
        warnings.append("The scenario date is beyond at least one leg's expiry; that leg is valued at intrinsic value with no remaining time.")
    quality_warnings = position.data_provenance.get("qualityWarnings", [])
    warnings.extend(str(warning) for warning in quality_warnings)
    initial_capital = position_profile(position)["netCapitalCommitted"]
    return {
        "ticker": position.ticker.upper(),
        "positionKind": position.position_kind,
        "scenarioPrice": request.scenario_price,
        "scenarioDate": request.scenario_date.isoformat(),
        "modeledPositionValue": values["positionValue"],
        "modeledOptionValue": values["optionValue"],
        "modeledShareValue": values["shareValue"],
        "pnl": pnl,
        "pnlPercent": round(pnl / initial_capital * 100, 2) if initial_capital > 0 else None,
        "breakEvens": break_evens,
        "breakEvenRelation": relation,
        "remainingDays": remaining_days,
        "greeks": position_greeks_at(position, request.scenario_price, request.scenario_date)["aggregate"],
        "assumptions": {
            "model": "Cox-Ross-Rubinstein American Binomial",
            "interestRate": position.interest_rate,
            "dividendYield": position.dividend_yield,
            "impliedVolatilities": [round(leg.implied_volatility * 100, 2) for leg in position.legs],
            "contractMultiplier": 100,
        },
        "dataProvenance": position.data_provenance,
        "warnings": list(dict.fromkeys(warnings)),
    }
