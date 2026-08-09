from __future__ import annotations

from .models import OptionType, PositionKind, PositionSide


def recipe(
    kind: PositionKind,
    name: str,
    category: str,
    description: str,
    capital_profile: str,
    risk_label: str,
    expiry_policy: str,
    strike_policy: str,
    legs: list[dict],
    shares: int = 0,
) -> dict:
    return {
        "kind": kind,
        "name": name,
        "category": category,
        "description": description,
        "capitalProfile": capital_profile,
        "riskLabel": risk_label,
        "expiryPolicy": expiry_policy,
        "strikePolicy": strike_policy,
        "shares": shares,
        "legs": legs,
    }


POSITION_TEMPLATES = [
    recipe(PositionKind.LONG_CALL, "Long Call", "Directional", "Bullish convex exposure with premium as the maximum loss.", "Net Debit", "Defined Loss", "One Expiry", "One Strike", [{"role": "Bullish Call", "optionType": OptionType.CALL, "side": PositionSide.LONG}]),
    recipe(PositionKind.LONG_PUT, "Long Put", "Directional", "Bearish convex exposure or downside protection.", "Net Debit", "Defined Loss", "One Expiry", "One Strike", [{"role": "Bearish Put", "optionType": OptionType.PUT, "side": PositionSide.LONG}]),
    recipe(PositionKind.SHORT_CALL, "Short Call", "Income", "Premium income with an obligation to deliver shares at the strike.", "Net Credit + Margin", "Uncapped Risk", "One Expiry", "One Strike", [{"role": "Short Call Obligation", "optionType": OptionType.CALL, "side": PositionSide.SHORT}]),
    recipe(PositionKind.SHORT_PUT, "Short Put", "Income", "Premium income with an obligation to acquire shares at the strike.", "Net Credit + Collateral", "Substantial Downside Risk", "One Expiry", "One Strike", [{"role": "Short Put Obligation", "optionType": OptionType.PUT, "side": PositionSide.SHORT}]),
    recipe(PositionKind.COVERED_CALL, "Covered Call", "Income", "Own shares and sell a call against them for premium income.", "Share Outlay + Net Credit", "Share Downside Risk", "One Expiry", "Short Call Against Shares", [{"role": "Covered Call", "optionType": OptionType.CALL, "side": PositionSide.SHORT}], shares=100),
    recipe(PositionKind.CASH_SECURED_PUT, "Cash-Secured Put", "Income", "Reserve strike cash while selling a put.", "Cash Collateral + Net Credit", "Assignment Downside Risk", "One Expiry", "One Put Strike", [{"role": "Cash-Secured Put", "optionType": OptionType.PUT, "side": PositionSide.SHORT}]),
    recipe(PositionKind.BULL_CALL_SPREAD, "Bull Call Spread", "Defined Risk", "Buy a lower-strike call and sell a higher-strike call.", "Net Debit", "Defined Gain And Loss", "Matching Expiry", "Long Strike Below Short Strike", [{"role": "Lower Long Call", "optionType": OptionType.CALL, "side": PositionSide.LONG}, {"role": "Higher Short Call", "optionType": OptionType.CALL, "side": PositionSide.SHORT}]),
    recipe(PositionKind.BEAR_CALL_SPREAD, "Bear Call Spread", "Defined Risk", "Sell a lower-strike call and buy a higher-strike call.", "Net Credit + Spread Collateral", "Defined Gain And Loss", "Matching Expiry", "Short Strike Below Long Strike", [{"role": "Lower Short Call", "optionType": OptionType.CALL, "side": PositionSide.SHORT}, {"role": "Higher Long Call", "optionType": OptionType.CALL, "side": PositionSide.LONG}]),
    recipe(PositionKind.BULL_PUT_SPREAD, "Bull Put Spread", "Defined Risk", "Sell a higher-strike put and buy a lower-strike put.", "Net Credit + Spread Collateral", "Defined Gain And Loss", "Matching Expiry", "Short Strike Above Long Strike", [{"role": "Higher Short Put", "optionType": OptionType.PUT, "side": PositionSide.SHORT}, {"role": "Lower Long Put", "optionType": OptionType.PUT, "side": PositionSide.LONG}]),
    recipe(PositionKind.BEAR_PUT_SPREAD, "Bear Put Spread", "Defined Risk", "Buy a higher-strike put and sell a lower-strike put.", "Net Debit", "Defined Gain And Loss", "Matching Expiry", "Long Strike Above Short Strike", [{"role": "Higher Long Put", "optionType": OptionType.PUT, "side": PositionSide.LONG}, {"role": "Lower Short Put", "optionType": OptionType.PUT, "side": PositionSide.SHORT}]),
    recipe(PositionKind.CONVERSION, "Conversion", "Financing / Parity", "Own shares, buy a put, and sell a call at the same strike and expiry to lock an idealized terminal value.", "Share Outlay + Net Option Premium", "Locked Payoff With Execution Risks", "Put And Call Must Match", "Put And Call Must Match", [{"role": "Protective Put", "optionType": OptionType.PUT, "side": PositionSide.LONG}, {"role": "Covered Short Call", "optionType": OptionType.CALL, "side": PositionSide.SHORT}], shares=100),
]


def list_position_templates() -> list[dict]:
    return POSITION_TEMPLATES
