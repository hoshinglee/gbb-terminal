from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import floor

from ..options.analysis import position_profile
from ..options.models import PositionKind, PositionSide
from ..options.simulation import position_comparison, position_pnl_at
from ..portfolio.models import PortfolioContext, RiskPolicy
from .models import (
    InstrumentExpression,
    InstrumentFitResult,
    PolicyCheck,
    PositionIntent,
    StressScenarioResult,
    StressTestResult,
    StressTestRequest,
)


OBJECTIVE_COPY = {
    "ownership_now": {
        "direct_shares": "Direct ownership participates immediately and can be sized share by share.",
        PositionKind.CASH_SECURED_PUT: "A cash-secured put delays ownership until assignment and may miss immediate upside.",
        PositionKind.LONG_CALL: "A long call participates in upside without current share ownership, but time and IV matter.",
        PositionKind.BULL_CALL_SPREAD: "A bull call spread defines loss but caps participation above the short strike.",
        PositionKind.COVERED_CALL: "A covered call keeps ownership but caps upside while the call remains open.",
    },
    "accumulate_lower": {
        "direct_shares": "Shares establish ownership now rather than conditionally at a lower effective basis.",
        PositionKind.CASH_SECURED_PUT: "Assignment can acquire 100-share blocks at the strike less premium.",
        PositionKind.LONG_CALL: "A long call does not satisfy the objective of accumulating shares lower.",
        PositionKind.BULL_CALL_SPREAD: "A call spread expresses upside but does not create a lower share-acquisition path.",
        PositionKind.COVERED_CALL: "A covered call produces premium against shares already owned; it does not add shares.",
    },
    "income": {
        "direct_shares": "Shares may receive dividends, but do not create option premium income.",
        PositionKind.CASH_SECURED_PUT: "Premium is paired with a full cash-backed obligation to acquire shares.",
        PositionKind.COVERED_CALL: "Premium is backed by existing shares and caps upside through the short strike.",
        PositionKind.LONG_CALL: "A long call pays premium and is not an income expression.",
        PositionKind.BULL_CALL_SPREAD: "A debit call spread is defined-risk upside, not recurring income.",
    },
    "defined_risk_upside": {
        "direct_shares": "Share downside extends to zero and is not contractually defined below entry cost.",
        PositionKind.CASH_SECURED_PUT: "A cash-secured put has substantial assignment downside despite the premium credit.",
        PositionKind.LONG_CALL: "Loss is limited to premium while upside remains theoretically uncapped.",
        PositionKind.BULL_CALL_SPREAD: "Both maximum loss and maximum gain are defined at entry.",
        PositionKind.COVERED_CALL: "Owned-share downside remains while upside is capped by the short call.",
    },
}


def analyze_expression(
    intent: PositionIntent,
    expression: InstrumentExpression,
    context: PortfolioContext | None,
    policy: RiskPolicy | None,
    objective: str,
) -> InstrumentFitResult:
    if expression.kind == "direct_shares":
        return _analyze_shares(intent, expression, context, policy, objective)
    return _analyze_option(intent, expression, context, policy, objective)


def _analyze_shares(
    intent: PositionIntent,
    expression: InstrumentExpression,
    context: PortfolioContext | None,
    policy: RiskPolicy | None,
    objective: str,
) -> InstrumentFitResult:
    price = float(expression.share_price or 0)
    current = intent.current_exposure_amount
    target = intent.target_amount
    maximum = intent.maximum_amount
    warnings: list[str] = []
    if target is None:
        quantity = expression.share_quantity or 0
        capital = quantity * price if quantity else None
        warnings.append("Target amount is unresolved because investable portfolio value is unavailable.")
    else:
        incremental = max(target - (current or 0), 0)
        quantity = expression.share_quantity if expression.share_quantity is not None else floor(incremental / price)
        capital = round(quantity * price, 2)
        if incremental == 0:
            warnings.append("Current exposure already meets or exceeds the saved target position.")
    resolved_expression = expression.model_copy(update={"share_quantity": quantity})
    post_exposure = None if current is None or capital is None else round(current + capital, 2)
    cash_remaining = None if context is None or capital is None else round(context.liquid_cash - capital, 2)
    checks = _policy_checks(
        context=context,
        policy=policy,
        post_exposure=post_exposure,
        maximum_intent=maximum,
        instrument_footprint=capital,
        assignment_obligation=0,
        collateral=0,
        cash_remaining=cash_remaining,
        maximum_loss=capital,
    )
    arithmetic = [f"{quantity} shares × ${price:,.2f} = ${capital:,.2f}" if capital is not None else "Share quantity is unresolved."]
    if current is not None and capital is not None:
        arithmetic.append(f"${current:,.2f} current exposure + ${capital:,.2f} new shares = ${post_exposure:,.2f}")
    return InstrumentFitResult(
        candidate_id=expression.source_candidate_id or "direct-shares",
        expression=resolved_expression,
        overall_status=_overall(checks),
        fit_label=_fit_label(checks),
        objective_fit=_objective_copy(objective, "direct_shares"),
        current_exposure=current,
        target_exposure=target,
        maximum_exposure=maximum,
        capital_required=capital,
        collateral_required=0,
        assignment_obligation=0,
        effective_acquisition_basis=price,
        existing_shares=intent.current_shares,
        shares_after_assignment=None,
        post_assignment_exposure=post_exposure,
        portfolio_footprint_percent=_percent(post_exposure, context.investable_value if context else None),
        cash_remaining=cash_remaining,
        maximum_loss=capital,
        break_evens=[price],
        sizing_flexibility="Flexible to one-share increments.",
        upside_character="Immediate uncapped share-price participation before dividends, costs, and taxes.",
        downside_character="Share value can decline to zero; loss is not structurally capped below purchase cost.",
        checks=checks,
        arithmetic=arithmetic,
        warnings=warnings,
    )


def _analyze_option(
    intent: PositionIntent,
    expression: InstrumentExpression,
    context: PortfolioContext | None,
    policy: RiskPolicy | None,
    objective: str,
) -> InstrumentFitResult:
    position = expression.option_position
    if position is None:
        raise ValueError("A validated Option Lab position is required for option fit analysis.")
    comparison = position_comparison(position)
    summary = comparison["summary"]
    profile = position_profile(position)
    maximum_loss = summary["maximumLoss"]
    numeric_loss = abs(float(maximum_loss)) if isinstance(maximum_loss, (int, float)) else None
    collateral = float(summary["collateral"])
    capital = round(max(float(profile["netCapitalCommitted"]), collateral, numeric_loss or 0), 2)
    short_puts = [
        leg
        for leg in position.legs
        if leg.side == PositionSide.SHORT and leg.option_type.value == "put"
    ]
    assignment = round(sum(leg.strike * leg.quantity * leg.multiplier for leg in short_puts), 2)
    premium_credit = round(sum(leg.premium * leg.quantity * leg.multiplier for leg in short_puts), 2)
    is_csp = position.position_kind == PositionKind.CASH_SECURED_PUT and bool(short_puts)
    effective_basis = (
        round(short_puts[0].strike - short_puts[0].premium, 2)
        if is_csp and len(short_puts) == 1
        else None
    )
    assigned_shares = sum(leg.quantity * leg.multiplier for leg in short_puts)
    shares_after = intent.current_shares + assigned_shares if assigned_shares else None
    footprint = assignment if is_csp else capital
    current = intent.current_exposure_amount
    post_exposure = None if current is None else round(current + footprint, 2)
    cash_use = assignment - premium_credit if is_csp else capital
    cash_remaining = None if context is None else round(context.liquid_cash - cash_use, 2)
    checks = _policy_checks(
        context=context,
        policy=policy,
        post_exposure=post_exposure,
        maximum_intent=intent.maximum_amount,
        instrument_footprint=footprint,
        assignment_obligation=assignment,
        collateral=collateral,
        cash_remaining=cash_remaining,
        maximum_loss=maximum_loss,
    )
    kind = position.position_kind
    arithmetic = [
        f"Capital footprint = max(net committed ${profile['netCapitalCommitted']:,.2f}, collateral ${collateral:,.2f}, defined loss {numeric_loss if numeric_loss is not None else str(maximum_loss)}) = ${capital:,.2f}."
    ]
    if is_csp:
        leg = short_puts[0]
        arithmetic.extend(
            [
                f"${leg.strike:,.2f} strike × {leg.quantity} contract × {leg.multiplier} shares = ${assignment:,.2f} gross assignment obligation.",
                f"Effective acquisition basis = ${leg.strike:,.2f} strike − ${leg.premium:,.2f} premium = ${effective_basis:,.2f} per share.",
                f"{intent.current_shares:g} existing shares + {assigned_shares} assigned shares = {shares_after:g} shares after assignment.",
            ]
        )
    warnings = [
        "Current public option marks may be delayed or non-executable.",
        "Policy checks use personal limits and deterministic arithmetic; they are not investment advice.",
    ]
    return InstrumentFitResult(
        candidate_id=expression.source_candidate_id or f"option:{kind.value}",
        expression=expression,
        overall_status=_overall(checks),
        fit_label=_fit_label(checks),
        objective_fit=_objective_copy(objective, kind),
        current_exposure=current,
        target_exposure=intent.target_amount,
        maximum_exposure=intent.maximum_amount,
        capital_required=capital,
        collateral_required=collateral,
        assignment_obligation=assignment,
        effective_acquisition_basis=effective_basis,
        existing_shares=intent.current_shares,
        shares_after_assignment=shares_after,
        post_assignment_exposure=post_exposure,
        portfolio_footprint_percent=_percent(post_exposure, context.investable_value if context else None),
        cash_remaining=cash_remaining,
        maximum_loss=maximum_loss,
        break_evens=[float(value) for value in summary["breakEvens"]],
        sizing_flexibility="Contract granularity is 100 underlying shares per standard contract.",
        upside_character=_upside(kind),
        downside_character=_downside(kind),
        checks=checks,
        arithmetic=arithmetic,
        warnings=warnings,
    )


def stress_expression(
    ticker: str,
    intent: PositionIntent,
    request: StressTestRequest,
    context: PortfolioContext | None,
    policy: RiskPolicy | None,
) -> StressTestResult:
    results: list[StressScenarioResult] = []
    expression = request.expression
    base_price = expression.share_price if expression.kind == "direct_shares" else expression.option_position.underlying_price  # type: ignore[union-attr]
    baseline_fit = analyze_expression(intent, expression, context, policy, "ownership_now")
    for scenario in request.scenarios:
        stressed_price = round(base_price * (1 + scenario.underlying_change_percent / 100), 2)
        if expression.kind == "direct_shares":
            quantity = expression.share_quantity or baseline_fit.expression.share_quantity or 0
            pnl = round(quantity * (stressed_price - base_price), 2)
            assumptions = [f"{quantity} shares repriced from ${base_price:,.2f} to ${stressed_price:,.2f}."]
        else:
            position = expression.option_position
            assert position is not None
            adjusted_legs = [
                leg.model_copy(
                    update={
                        "implied_volatility": min(
                            max(leg.implied_volatility * (1 + scenario.iv_change_percent / 100), 0.0001),
                            5,
                        )
                    }
                )
                for leg in position.legs
            ]
            adjusted = position.model_copy(update={"legs": adjusted_legs})
            valuation_date = date.today() + timedelta(days=scenario.days_forward)
            pnl = position_pnl_at(adjusted, stressed_price, valuation_date)
            assumptions = [
                "Option values use the server-side Cox-Ross-Rubinstein American binomial model.",
                f"Implied volatility changed {scenario.iv_change_percent:+.1f}% relative and time advanced {scenario.days_forward} days.",
            ]
        portfolio_pnl = _percent(pnl, context.investable_value if context else None)
        stressed_position_value = max((baseline_fit.capital_required or 0) + pnl, 0)
        post_concentration = _percent(
            (intent.current_exposure_amount or 0) + stressed_position_value,
            context.investable_value if context else None,
        )
        checks = _stress_checks(context, policy, pnl, post_concentration)
        results.append(
            StressScenarioResult(
                scenario=scenario,
                stressed_underlying_price=stressed_price,
                position_pnl=pnl,
                portfolio_pnl_percent=portfolio_pnl,
                post_stress_single_name_percent=post_concentration,
                cash_remaining=baseline_fit.cash_remaining,
                assignment_obligation=baseline_fit.assignment_obligation,
                collateral_exposure=baseline_fit.collateral_required or 0,
                checks=checks,
                assumptions=assumptions,
                warnings=["Stress results are deterministic scenarios, not probability forecasts."],
            )
        )
    return StressTestResult(
        ticker=ticker,
        expression=expression,
        generated_at=datetime.now(timezone.utc),
        scenarios=results,
        limitations=[
            "Stress testing does not model taxes, broker margin rules, liquidity, or execution slippage.",
            "Portfolio impact uses the saved investable value and manual exposure context without covariance assumptions.",
        ],
    )


def process_outcome_classification(process_quality: str, outcome: str | None) -> str | None:
    if process_quality not in {"good", "poor"} or outcome not in {"favorable", "unfavorable"}:
        return None
    return f"{process_quality}_process_{outcome}_outcome"


def _policy_checks(
    *,
    context: PortfolioContext | None,
    policy: RiskPolicy | None,
    post_exposure: float | None,
    maximum_intent: float | None,
    instrument_footprint: float | None,
    assignment_obligation: float,
    collateral: float,
    cash_remaining: float | None,
    maximum_loss: float | str | None,
) -> list[PolicyCheck]:
    if context is None or policy is None:
        missing = "portfolio context" if context is None else "risk policy"
        return [
            PolicyCheck(
                key=key,
                label=label,
                status="incomplete",
                arithmetic=f"Cannot calculate without {missing}.",
                reason=f"Define {missing} before treating this analysis as complete.",
            )
            for key, label in [
                ("instrument_size_mismatch", "Instrument Size Mismatch"),
                ("single_name", "Maximum Single-Name Exposure"),
                ("assignment", "Maximum Assignment Exposure"),
                ("cash_reserve", "Minimum Cash Reserve"),
                ("short_collateral", "Maximum Short-Option Collateral"),
                ("stress_loss", "Portfolio Stress-Loss Ceiling"),
            ]
        ]
    checks: list[PolicyCheck] = []
    mismatch = maximum_intent is not None and instrument_footprint is not None and instrument_footprint > maximum_intent
    checks.append(
        PolicyCheck(
            key="instrument_size_mismatch",
            label="Instrument Size Mismatch",
            status="fail" if mismatch else ("incomplete" if maximum_intent is None or instrument_footprint is None else "pass"),
            actual=instrument_footprint,
            limit=maximum_intent,
            unit="usd",
            arithmetic=f"Instrument footprint ${instrument_footprint:,.2f} compared with maximum intended position ${maximum_intent:,.2f}." if instrument_footprint is not None and maximum_intent is not None else "Maximum intended amount or instrument footprint is unresolved.",
            reason="One standard contract is larger than the saved maximum position." if mismatch else "The instrument footprint does not exceed the saved maximum position amount.",
        )
    )
    single_percent = _percent(post_exposure, context.investable_value)
    checks.append(_percent_check("single_name", "Maximum Single-Name Exposure", single_percent, policy.max_single_name_exposure_percent, "Post-expression company exposure"))
    assignment_percent = _percent(assignment_obligation, context.investable_value)
    checks.append(
        _percent_check("assignment", "Maximum Assignment Exposure", assignment_percent, policy.max_assignment_exposure_percent, "Gross put-assignment obligation")
        if assignment_obligation > 0
        else PolicyCheck(key="assignment", label="Maximum Assignment Exposure", status="not_applicable", actual=0, limit=policy.max_assignment_exposure_percent, unit="percent", arithmetic="No short-put assignment obligation.", reason="This expression does not create a share-acquisition assignment obligation.")
    )
    reserve = max(
        policy.min_unencumbered_cash_reserve_amount or 0,
        context.investable_value * (policy.min_unencumbered_cash_reserve_percent or 0) / 100,
    )
    checks.append(
        PolicyCheck(
            key="cash_reserve",
            label="Minimum Cash Reserve",
            status="incomplete" if cash_remaining is None else ("pass" if cash_remaining >= reserve else "fail"),
            actual=cash_remaining,
            limit=round(reserve, 2),
            unit="usd",
            arithmetic=f"Cash after expression ${cash_remaining:,.2f} compared with required reserve ${reserve:,.2f}." if cash_remaining is not None else "Cash remaining is unresolved.",
            reason="Required unencumbered cash remains available." if cash_remaining is not None and cash_remaining >= reserve else "The expression would reduce cash below the configured reserve.",
        )
    )
    collateral_percent = _percent(collateral, context.investable_value)
    checks.append(
        _percent_check("short_collateral", "Maximum Short-Option Collateral", collateral_percent, policy.max_short_option_collateral_percent, "Short-option collateral")
        if collateral > 0
        else PolicyCheck(key="short_collateral", label="Maximum Short-Option Collateral", status="not_applicable", actual=0, limit=policy.max_short_option_collateral_percent, unit="percent", arithmetic="No short-option collateral is required.", reason="This expression has no collateral gate to evaluate.")
    )
    loss_percent = None if maximum_loss is None or isinstance(maximum_loss, str) else _percent(abs(float(maximum_loss)), context.investable_value)
    checks.append(
        PolicyCheck(
            key="stress_loss",
            label="Portfolio Stress-Loss Ceiling",
            status="fail" if isinstance(maximum_loss, str) else ("incomplete" if loss_percent is None else ("pass" if loss_percent <= policy.portfolio_stress_loss_ceiling_percent else "fail")),
            actual=loss_percent,
            limit=policy.portfolio_stress_loss_ceiling_percent,
            unit="percent",
            arithmetic=f"Maximum modeled loss {loss_percent:.2f}% of investable value compared with {policy.portfolio_stress_loss_ceiling_percent:.2f}% ceiling." if loss_percent is not None else f"Maximum loss is {maximum_loss or 'unresolved'}.",
            reason="Modeled loss is inside the personal stress ceiling." if loss_percent is not None and loss_percent <= policy.portfolio_stress_loss_ceiling_percent else "Modeled loss exceeds or cannot be bounded inside the personal stress ceiling.",
        )
    )
    return checks


def _stress_checks(
    context: PortfolioContext | None,
    policy: RiskPolicy | None,
    pnl: float,
    post_concentration: float | None,
) -> list[PolicyCheck]:
    if context is None or policy is None:
        return [PolicyCheck(key="stress_loss", label="Portfolio Stress-Loss Ceiling", status="incomplete", arithmetic="Portfolio context and risk policy are required.", reason="Stress impact is incomplete.")]
    loss_percent = abs(min(pnl, 0)) / context.investable_value * 100 if context.investable_value else 0
    return [
        _percent_check("single_name", "Post-Stress Single-Name Exposure", post_concentration, policy.max_single_name_exposure_percent, "Post-stress company exposure"),
        _percent_check("stress_loss", "Portfolio Stress-Loss Ceiling", loss_percent, policy.portfolio_stress_loss_ceiling_percent, "Scenario loss contribution"),
    ]


def _percent_check(key: str, label: str, actual: float | None, limit: float, subject: str) -> PolicyCheck:
    return PolicyCheck(
        key=key,
        label=label,
        status="incomplete" if actual is None else ("pass" if actual <= limit else "fail"),
        actual=actual,
        limit=limit,
        unit="percent",
        arithmetic=f"{subject} {actual:.2f}% compared with configured limit {limit:.2f}%." if actual is not None else f"{subject} is unresolved.",
        reason=f"{subject} is inside the configured limit." if actual is not None and actual <= limit else f"{subject} exceeds or cannot be compared with the configured limit.",
    )


def _overall(checks: list[PolicyCheck]) -> str:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "incomplete" in statuses:
        return "incomplete"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _fit_label(checks: list[PolicyCheck]) -> str:
    status = _overall(checks)
    return {
        "pass": "Fits Saved Constraints",
        "warn": "Review Required",
        "fail": "Conflicts With Saved Constraints",
        "incomplete": "Incomplete Analysis",
    }[status]


def _objective_copy(objective: str, kind: object) -> str:
    return OBJECTIVE_COPY.get(objective, {}).get(kind, "Inspect the capital, assignment, payoff, and sizing trade-offs against the saved objective.")


def _upside(kind: PositionKind) -> str:
    if kind == PositionKind.LONG_CALL:
        return "Theoretical upside is uncapped above strike plus premium."
    if kind in {PositionKind.BULL_CALL_SPREAD, PositionKind.COVERED_CALL}:
        return "Upside is capped by the short-call strike."
    if kind == PositionKind.CASH_SECURED_PUT:
        return "Premium is capped; immediate share-price upside can be missed before assignment."
    return "Upside depends on the validated Option Lab payoff structure."


def _downside(kind: PositionKind) -> str:
    if kind in {PositionKind.LONG_CALL, PositionKind.BULL_CALL_SPREAD}:
        return "Loss is defined by the net premium paid."
    if kind == PositionKind.CASH_SECURED_PUT:
        return "Assignment creates 100-share downside from the effective acquisition basis toward zero."
    if kind == PositionKind.COVERED_CALL:
        return "Premium cushions but does not remove owned-share downside."
    return "Downside follows the validated Option Lab structure and modeled maximum loss."


def _percent(value: float | None, denominator: float | None) -> float | None:
    if value is None or denominator is None or denominator <= 0:
        return None
    return round(value / denominator * 100, 4)
