from __future__ import annotations

from .models import OptionType, PositionKind, PositionSide


POSITION_TEMPLATES = [
    {"kind": PositionKind.LONG_CALL, "name": "Long Call", "legs": [{"optionType": OptionType.CALL, "side": PositionSide.LONG}]},
    {"kind": PositionKind.LONG_PUT, "name": "Long Put", "legs": [{"optionType": OptionType.PUT, "side": PositionSide.LONG}]},
    {"kind": PositionKind.SHORT_CALL, "name": "Short Call", "legs": [{"optionType": OptionType.CALL, "side": PositionSide.SHORT}]},
    {"kind": PositionKind.SHORT_PUT, "name": "Short Put", "legs": [{"optionType": OptionType.PUT, "side": PositionSide.SHORT}]},
    {"kind": PositionKind.COVERED_CALL, "name": "Covered Call", "shares": 100, "legs": [{"optionType": OptionType.CALL, "side": PositionSide.SHORT}]},
    {"kind": PositionKind.CASH_SECURED_PUT, "name": "Cash-Secured Put", "legs": [{"optionType": OptionType.PUT, "side": PositionSide.SHORT}]},
    {"kind": PositionKind.BULL_CALL_SPREAD, "name": "Bull Call Spread", "legs": [{"optionType": OptionType.CALL, "side": PositionSide.LONG}, {"optionType": OptionType.CALL, "side": PositionSide.SHORT}]},
    {"kind": PositionKind.BEAR_CALL_SPREAD, "name": "Bear Call Spread", "legs": [{"optionType": OptionType.CALL, "side": PositionSide.SHORT}, {"optionType": OptionType.CALL, "side": PositionSide.LONG}]},
    {"kind": PositionKind.BULL_PUT_SPREAD, "name": "Bull Put Spread", "legs": [{"optionType": OptionType.PUT, "side": PositionSide.SHORT}, {"optionType": OptionType.PUT, "side": PositionSide.LONG}]},
    {"kind": PositionKind.BEAR_PUT_SPREAD, "name": "Bear Put Spread", "legs": [{"optionType": OptionType.PUT, "side": PositionSide.LONG}, {"optionType": OptionType.PUT, "side": PositionSide.SHORT}]},
]


def list_position_templates() -> list[dict]:
    return POSITION_TEMPLATES

