from __future__ import annotations

from datetime import date
from typing import Any

from .models import OptionSimulationRequest, OptionType, PositionKind, PositionSide


def position_profile(request: OptionSimulationRequest) -> dict[str, Any]:
    share_basis = request.share_cost_basis or request.underlying_price
    share_outlay = request.shares * share_basis
    long_premium_debit = sum(leg.premium * leg.quantity * leg.multiplier for leg in request.legs if leg.side == PositionSide.LONG)
    short_premium_credit = sum(leg.premium * leg.quantity * leg.multiplier for leg in request.legs if leg.side == PositionSide.SHORT)
    net_cash_at_entry = short_premium_credit - long_premium_debit - share_outlay
    available_call_hedges = {
        leg.leg_id: leg.quantity
        for leg in request.legs
        if leg.option_type == OptionType.CALL and leg.side == PositionSide.LONG
    }
    uncovered_short_calls = max(
        sum(leg.quantity * leg.multiplier for leg in request.legs if leg.option_type == OptionType.CALL and leg.side == PositionSide.SHORT) - request.shares,
        0,
    )
    for short_call in [leg for leg in request.legs if leg.option_type == OptionType.CALL and leg.side == PositionSide.SHORT]:
        for long_call in [leg for leg in request.legs if leg.option_type == OptionType.CALL and leg.side == PositionSide.LONG and leg.expiration == short_call.expiration and leg.strike > short_call.strike]:
            protected_contracts = min(short_call.quantity, available_call_hedges[long_call.leg_id])
            uncovered_short_calls = max(uncovered_short_calls - protected_contracts * short_call.multiplier, 0)
            available_call_hedges[long_call.leg_id] -= protected_contracts
            if uncovered_short_calls == 0:
                break
    uncapped_short_calls = uncovered_short_calls > 0
    return {
        "shareOutlay": round(share_outlay, 2),
        "longPremiumDebit": round(long_premium_debit, 2),
        "shortPremiumCredit": round(short_premium_credit, 2),
        "netCashAtEntry": round(net_cash_at_entry, 2),
        "netCapitalCommitted": round(max(-net_cash_at_entry, 0), 2),
        "netCreditReceived": round(max(net_cash_at_entry, 0), 2),
        "riskLabel": "Uncapped Upside Risk" if uncapped_short_calls else "Structure-Dependent Risk",
    }


def conversion_financing_analysis(request: OptionSimulationRequest) -> dict[str, Any] | None:
    if request.position_kind != PositionKind.CONVERSION:
        return None
    profile = position_profile(request)
    strike = request.legs[0].strike
    contracts = request.legs[0].quantity
    terminal_proceeds = strike * contracts * request.legs[0].multiplier
    capital = profile["netCapitalCommitted"]
    holding_days = max((request.legs[0].expiration - date.today()).days, 0)
    nominal_profit = terminal_proceeds - capital
    nominal_return = nominal_profit / capital if capital > 0 else 0
    annualized_return = (terminal_proceeds / capital) ** (365 / holding_days) - 1 if capital > 0 and terminal_proceeds > 0 and holding_days > 0 else 0
    return {
        "lockedTerminalProceeds": round(terminal_proceeds, 2),
        "netCapitalCommitted": round(capital, 2),
        "nominalProfit": round(nominal_profit, 2),
        "nominalReturnPercent": round(nominal_return * 100, 4),
        "holdingDays": holding_days,
        "annualizedReturnPercent": round(annualized_return * 100, 4),
        "configuredCashRatePercent": round(request.interest_rate * 100, 4),
        "annualizedExcessVsCashPercent": round((annualized_return - request.interest_rate) * 100, 4),
        "dividendYieldAssumptionPercent": round(request.dividend_yield * 100, 4),
        "interpretation": "The idealized terminal payoff is locked by put-call parity, but execution, financing, dividends, early assignment, taxes, fees, and corporate actions can change realized results.",
    }


def management_playbook(request: OptionSimulationRequest) -> dict[str, Any]:
    if request.position_kind == PositionKind.CONVERSION:
        return {
            "title": "Conversion Financing And Assignment",
            "riskLabel": "Locked Idealized Payoff · Operational Risks Remain",
            "branches": [
                {"id": "hold-conversion", "title": "Hold To Expiry", "trigger": "Options remain open", "action": "Keep matched shares, put, and call", "eventType": "hold", "impact": "Terminal shares are economically exchanged at the common strike.", "warnings": ["Funding and opportunity cost continue until expiry."]},
                {"id": "early-assignment", "title": "Short Call Assigned Early", "trigger": "Assignment notice", "action": "Deliver covered shares and revalue the remaining long put", "eventType": "early_assignment", "impact": "Strike cash arrives early; the long put remains an owned asset.", "warnings": ["A dividend may be missed and reinvestment timing changes."]},
                {"id": "close-conversion", "title": "Close Before Expiry", "trigger": "Financing edge or execution conditions change", "action": "Close every leg using observed marks", "eventType": "close", "impact": "Realized return depends on executable stock and option prices.", "warnings": ["Do not infer locked expiry proceeds for an early close."]},
            ],
        }
    if request.position_kind == PositionKind.SHORT_CALL:
        short_call = request.legs[0]
        required_shares = short_call.quantity * short_call.multiplier
        assumed_cover_cash = required_shares * request.underlying_price
        covered_break_even = request.underlying_price - short_call.premium
        return {
            "title": "Short LEAP Call Management Branches",
            "riskLabel": "Uncapped Risk Until Covered Or Hedged",
            "branches": [
                {"id": "continue-short-call", "title": "Continue Current Exposure", "trigger": "No transformation", "action": "Hold or close the short call", "eventType": "hold", "impact": "Premium remains capped while upside loss remains uncapped.", "warnings": ["Margin can expand sharply as the stock rises."]},
                {"id": "buy-cover", "title": "Buy Shares To Become Covered", "trigger": "User-entered stock price", "action": f"Buy {required_shares} shares", "eventType": "buy_shares", "requiredCash": round(assumed_cover_cash, 2), "impact": f"At the current assumed share price, covered break-even is approximately ${covered_break_even:.2f} before costs.", "warnings": ["Future shares are not guaranteed at the strike or current price."]},
                {"id": "add-call-hedge", "title": "Add Higher-Strike Long Call", "trigger": "User selects a same-expiry hedge", "action": "Add a validated long call", "eventType": "add_leg", "impact": "Transforms the upside tail into a defined-width call spread.", "warnings": ["The hedge debit reduces collected premium."]},
                {"id": "roll-call", "title": "Roll Strike Or Expiry", "trigger": "User supplies executable old and replacement marks", "action": "Close the old call and open its replacement", "eventType": "roll_expiry", "impact": "Changes strike, time exposure, credit/debit, and assignment horizon.", "warnings": ["Rolling realizes the old-leg P&L; it does not erase a loss."]},
                {"id": "add-csp", "title": "Add Cash-Secured Put", "trigger": "Separate downside entry thesis", "action": "Add a short put with full cash collateral", "eventType": "add_leg", "impact": "Adds premium and a separate obligation to acquire shares.", "warnings": ["This increases downside capital at risk and is not a hedge for an uncapped short call."]},
            ],
        }
    return {
        "title": "Position Lifecycle Choices",
        "riskLabel": "Review Structure And Collateral",
        "branches": [
            {"id": "hold", "title": "Record Hold Observation", "trigger": "Thesis unchanged", "action": "Record the observed underlying price", "eventType": "hold", "impact": "Keeps the current paper exposure without claiming an executable option revaluation.", "warnings": ["Model value is not an executable quote."]},
            {"id": "close", "title": "Close Fully Or Partially", "trigger": "Risk or target changes", "action": "Use observed option marks", "eventType": "close", "impact": "Realizes selected contracts and updates cash.", "warnings": ["Bid/ask and fees affect realized results."]},
            {"id": "roll", "title": "Roll", "trigger": "More time or a different strike is desired", "action": "Close one leg and open a replacement", "eventType": "roll_expiry", "impact": "Preserves the earlier state and creates a replacement leg.", "warnings": ["A roll is two economic trades."]},
        ],
    }
