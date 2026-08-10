from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from .fact_models import FinancialFactQuery
from .fact_service import FinancialFactService
from .metric_definitions import (
    DEBT_COMPONENT_CONCEPTS,
    DEBT_COMPONENT_GROUPS,
    DERIVED_METRICS,
    METRIC_DEFINITION_VERSION,
    METRIC_DEFINITIONS,
    MetricBehavior,
    MetricDefinition,
)
from .metric_models import MetricPeriodKind, NormalizedMetric, NormalizedMetricSet
from .service import CompanyIdentityService


@dataclass
class _Period:
    kind: MetricPeriodKind
    start: date | None
    end: date
    fiscal_year: int | None
    fiscal_period: str | None
    metrics: dict[str, NormalizedMetric]


class UnitNormalizer:
    _UNITS = {
        "USD": ("USD", 1.0),
        "USDm": ("USD", 1_000_000.0),
        "USDth": ("USD", 1_000.0),
        "shares": ("shares", 1.0),
        "sharesm": ("shares", 1_000_000.0),
        "shares_thousands": ("shares", 1_000.0),
        "USD/shares": ("USD/share", 1.0),
        "USD/share": ("USD/share", 1.0),
    }

    @classmethod
    def normalize(cls, value: float, source_unit: str, target_unit: str) -> tuple[float | None, str | None]:
        normalized = cls._UNITS.get(source_unit)
        if normalized is None or normalized[0] != target_unit:
            return None, f"Unit {source_unit} cannot be normalized to {target_unit}."
        return value * normalized[1], None


class NormalizedMetricsService:
    def __init__(self, facts: FinancialFactService, identities: CompanyIdentityService) -> None:
        self.facts = facts
        self.identities = identities

    def calculate(
        self,
        ticker_or_cik: str,
        period_kind: MetricPeriodKind = MetricPeriodKind.ANNUAL,
        as_of: datetime | None = None,
    ) -> NormalizedMetricSet:
        effective_as_of = as_of or datetime.now(timezone.utc)
        if effective_as_of.tzinfo is None or effective_as_of.utcoffset() is None:
            raise ValueError("Metric as-of timestamps must include a timezone.")
        company = self._resolve_company(ticker_or_cik)
        concepts = sorted(
            {
                concept
                for definition in METRIC_DEFINITIONS.values()
                for concept in definition.concepts
            }
            | set(DEBT_COMPONENT_CONCEPTS)
        )
        facts = self.facts.history(
            company.cik,
            FinancialFactQuery(concepts=concepts, as_of=effective_as_of),
        )
        base_kind = MetricPeriodKind.QUARTERLY if period_kind == MetricPeriodKind.TTM else period_kind
        periods, warnings = self._base_periods(facts, base_kind)
        if period_kind == MetricPeriodKind.TTM:
            periods, ttm_warnings = self._ttm_periods(periods)
            warnings.extend(ttm_warnings)
        self._add_derived_metrics(periods)
        exposed = {
            definition.metric_id for definition in METRIC_DEFINITIONS.values() if definition.exposed
        } | set(DERIVED_METRICS)
        metrics = [
            metric
            for period in periods
            for metric_id, metric in period.metrics.items()
            if metric_id in exposed
        ]
        if not periods:
            warnings.append(f"No {period_kind.value} periods could be constructed from the available SEC facts.")
        return NormalizedMetricSet(
            company_id=company.company_id,
            cik=company.cik,
            primary_ticker=company.primary_ticker,
            period_kind=period_kind,
            as_of=effective_as_of.astimezone(timezone.utc),
            definition_version=METRIC_DEFINITION_VERSION,
            metrics=metrics,
            warnings=list(dict.fromkeys(warnings)),
        )

    def _resolve_company(self, ticker_or_cik: str):
        company = (
            self.identities.resolve_cik(ticker_or_cik)
            if ticker_or_cik.upper().removeprefix("CIK").strip().isdigit()
            else self.identities.resolve_ticker(ticker_or_cik)
        )
        if company is None:
            raise ValueError(f"No canonical company identity exists for {ticker_or_cik}.")
        return company

    def _base_periods(self, facts, kind: MetricPeriodKind) -> tuple[list[_Period], list[str]]:
        anchors = sorted({fact.period_end for fact in facts if self._flow_matches_kind(fact, kind)})
        periods = []
        warnings = []
        for period_end in anchors:
            period_facts = [fact for fact in facts if fact.period_end == period_end and self._fact_matches_kind(fact, kind)]
            flow_facts = [fact for fact in period_facts if fact.period_start is not None]
            if not flow_facts:
                continue
            period_start = min(fact.period_start for fact in flow_facts)
            fiscal_year = next((fact.fiscal_year for fact in reversed(flow_facts) if fact.fiscal_year is not None), None)
            fiscal_period = next((fact.fiscal_period for fact in reversed(flow_facts) if fact.fiscal_period), None)
            metrics = {
                metric_id: self._select_metric(definition, period_facts, kind, period_start, period_end, fiscal_year, fiscal_period)
                for metric_id, definition in METRIC_DEFINITIONS.items()
            }
            if metrics["debt"].value is None:
                metrics["debt"] = self._compose_debt(period_facts, kind, period_start, period_end, fiscal_year, fiscal_period)
            periods.append(_Period(kind, period_start, period_end, fiscal_year, fiscal_period, metrics))
        if kind == MetricPeriodKind.QUARTERLY and len(periods) < 4:
            warnings.append("Fewer than four discrete quarterly periods are available; TTM output may be unavailable.")
        return periods, warnings

    def _select_metric(
        self,
        definition: MetricDefinition,
        facts,
        kind: MetricPeriodKind,
        period_start: date,
        period_end: date,
        fiscal_year: int | None,
        fiscal_period: str | None,
    ) -> NormalizedMetric:
        warnings = []
        for concept in definition.concepts:
            candidates = [fact for fact in facts if fact.taxonomy == "us-gaap" and fact.concept == concept]
            normalized = []
            for fact in candidates:
                value, unit_warning = UnitNormalizer.normalize(fact.value, fact.unit, definition.unit)
                if unit_warning:
                    warnings.append(f"{definition.label}: {unit_warning}")
                else:
                    normalized.append((fact, abs(value) if definition.absolute_value else value))
            if normalized:
                selected, value = max(
                    normalized,
                    key=lambda item: (item[0].provenance.known_at, item[0].filed_date, item[0].fact_id),
                )
                latest_time = selected.provenance.known_at
                latest_values = {candidate_value for candidate, candidate_value in normalized if candidate.provenance.known_at == latest_time}
                if len(latest_values) > 1:
                    warnings.append(
                        f"{definition.label} has conflicting {concept} values at the same known_at timestamp; selected by stable fact identity."
                    )
                lower_precedence = [
                    candidate
                    for candidate in definition.concepts[definition.concepts.index(concept) + 1 :]
                    if any(fact.concept == candidate for fact in facts)
                ]
                if lower_precedence:
                    warnings.append(
                        f"Used {concept} by deterministic precedence over {', '.join(lower_precedence)}."
                    )
                if definition.metric_id == "diluted_shares" and concept == "WeightedAverageNumberOfSharesOutstandingBasic":
                    warnings.append("Diluted shares were unavailable; basic weighted-average shares are shown as a fallback.")
                return self._metric(
                    definition.metric_id,
                    definition.label,
                    value,
                    definition.unit,
                    kind,
                    period_start,
                    period_end,
                    fiscal_year,
                    fiscal_period,
                    [selected.fact_id],
                    warnings,
                )
        return self._metric(
            definition.metric_id,
            definition.label,
            None,
            definition.unit,
            kind,
            period_start,
            period_end,
            fiscal_year,
            fiscal_period,
            [],
            [f"{definition.label} is unavailable from the supported SEC concepts for this period.", *warnings],
        )

    def _compose_debt(
        self,
        facts,
        kind,
        period_start,
        period_end,
        fiscal_year,
        fiscal_period,
    ) -> NormalizedMetric:
        components = []
        warnings = []
        for concept_group in DEBT_COMPONENT_GROUPS:
            for concept in concept_group:
                candidates = [fact for fact in facts if fact.taxonomy == "us-gaap" and fact.concept == concept]
                if not candidates:
                    continue
                selected = max(
                    candidates,
                    key=lambda fact: (fact.provenance.known_at, fact.filed_date, fact.fact_id),
                )
                value, warning = UnitNormalizer.normalize(selected.value, selected.unit, "USD")
                if warning:
                    warnings.append(f"Debt: {warning}")
                else:
                    components.append((selected, value))
                    break
        if not components:
            return self._metric(
                "debt",
                "Debt",
                None,
                "USD",
                kind,
                period_start,
                period_end,
                fiscal_year,
                fiscal_period,
                [],
                ["Debt is unavailable from direct or supported component concepts.", *warnings],
            )
        warnings.append("Debt is composed from available current/noncurrent borrowing concepts and may omit unsupported instruments.")
        return self._metric(
            "debt",
            "Debt",
            sum(value for _, value in components),
            "USD",
            kind,
            period_start,
            period_end,
            fiscal_year,
            fiscal_period,
            [fact.fact_id for fact, _ in components],
            warnings,
        )

    def _ttm_periods(self, quarters: list[_Period]) -> tuple[list[_Period], list[str]]:
        if len(quarters) < 4:
            return [], ["TTM requires four discrete quarterly periods; the available fact history is insufficient."]
        periods = []
        warnings = []
        for index in range(3, len(quarters)):
            window = quarters[index - 3 : index + 1]
            if any((window[position].end - window[position - 1].end).days > 130 for position in range(1, 4)):
                warnings.append(f"Skipped TTM ending {window[-1].end}: quarterly periods are not contiguous.")
                continue
            metrics = {}
            for metric_id, definition in METRIC_DEFINITIONS.items():
                values = [quarter.metrics[metric_id] for quarter in window]
                available = [metric for metric in values if metric.value is not None]
                metric_warnings = [warning for metric in values for warning in metric.warnings]
                sources = list(dict.fromkeys(source for metric in values for source in metric.source_fact_ids))
                if definition.behavior in {MetricBehavior.FLOW, MetricBehavior.PER_SHARE}:
                    value = sum(metric.value for metric in values) if len(available) == 4 else None
                    if value is None:
                        metric_warnings.append(f"{definition.label} TTM requires all four quarterly values.")
                elif definition.behavior == MetricBehavior.AVERAGE:
                    value = sum(metric.value for metric in available) / len(available) if len(available) == 4 else None
                    if value is None:
                        metric_warnings.append(f"{definition.label} TTM requires all four quarterly values.")
                else:
                    value = values[-1].value
                    sources = values[-1].source_fact_ids
                    metric_warnings = values[-1].warnings
                metrics[metric_id] = self._metric(
                    metric_id,
                    definition.label,
                    value,
                    definition.unit,
                    MetricPeriodKind.TTM,
                    window[0].start,
                    window[-1].end,
                    window[-1].fiscal_year,
                    "TTM",
                    sources,
                    list(dict.fromkeys(metric_warnings)),
                )
            periods.append(
                _Period(
                    MetricPeriodKind.TTM,
                    window[0].start,
                    window[-1].end,
                    window[-1].fiscal_year,
                    "TTM",
                    metrics,
                )
            )
        return periods, warnings

    def _add_derived_metrics(self, periods: list[_Period]) -> None:
        for index, period in enumerate(periods):
            metrics = period.metrics
            metrics["free_cash_flow"] = self._binary_metric(period, "free_cash_flow", "operating_cash_flow", "capital_expenditure", lambda left, right: left - right)
            metrics["gross_margin"] = self._ratio_metric(period, "gross_margin", "gross_profit", "revenue")
            metrics["operating_margin"] = self._ratio_metric(period, "operating_margin", "operating_income", "revenue")
            metrics["fcf_margin"] = self._ratio_metric(period, "fcf_margin", "free_cash_flow", "revenue")
            metrics["net_debt"] = self._binary_metric(period, "net_debt", "debt", "cash", lambda left, right: left - right)
            previous_index = index - (4 if period.kind in {MetricPeriodKind.QUARTERLY, MetricPeriodKind.TTM} else 1)
            previous = periods[previous_index] if previous_index >= 0 else None
            metrics["revenue_growth"] = self._growth_metric(period, previous, "revenue_growth", "revenue")
            metrics["eps_growth"] = self._growth_metric(period, previous, "eps_growth", "diluted_eps")
            metrics["share_dilution"] = self._growth_metric(period, previous, "share_dilution", "diluted_shares")
            metrics["return_on_equity"] = self._return_on_equity(period, previous)
            metrics["return_on_invested_capital"] = self._return_on_invested_capital(period, previous)

    def _binary_metric(self, period, metric_id, left_id, right_id, operation):
        left, right = period.metrics[left_id], period.metrics[right_id]
        label, unit = DERIVED_METRICS[metric_id]
        if left.value is None or right.value is None:
            return self._derived_metric(period, metric_id, label, None, unit, [left, right], [f"{label} requires {left.label} and {right.label}."])
        return self._derived_metric(period, metric_id, label, operation(left.value, right.value), unit, [left, right])

    def _ratio_metric(self, period, metric_id, numerator_id, denominator_id):
        numerator, denominator = period.metrics[numerator_id], period.metrics[denominator_id]
        label, unit = DERIVED_METRICS[metric_id]
        if numerator.value is None or denominator.value in {None, 0}:
            return self._derived_metric(period, metric_id, label, None, unit, [numerator, denominator], [f"{label} requires non-zero {denominator.label} and available {numerator.label}."])
        return self._derived_metric(period, metric_id, label, numerator.value / denominator.value * 100, unit, [numerator, denominator])

    def _growth_metric(self, period, previous, metric_id, source_id):
        current = period.metrics[source_id]
        label, unit = DERIVED_METRICS[metric_id]
        if previous is None:
            return self._derived_metric(period, metric_id, label, None, unit, [current], [f"{label} requires a prior comparable period."])
        prior = previous.metrics[source_id]
        if current.value is None or prior.value in {None, 0}:
            return self._derived_metric(period, metric_id, label, None, unit, [current, prior], [f"{label} requires current and non-zero prior {current.label}."])
        return self._derived_metric(period, metric_id, label, (current.value / prior.value - 1) * 100, unit, [current, prior])

    def _return_on_equity(self, period, previous):
        income = period.metrics["net_income"]
        equity = period.metrics["stockholders_equity"]
        label, unit = DERIVED_METRICS["return_on_equity"]
        prior_equity = previous.metrics["stockholders_equity"] if previous else None
        available_equity = [metric.value for metric in (prior_equity, equity) if metric and metric.value is not None]
        if income.value is None or not available_equity or sum(available_equity) == 0:
            return self._derived_metric(period, "return_on_equity", label, None, unit, [income, equity], ["Return On Equity requires net income and usable equity observations."])
        average_equity = sum(available_equity) / len(available_equity)
        multiplier = 4 if period.kind == MetricPeriodKind.QUARTERLY else 1
        warnings = [] if previous else ["Return On Equity uses ending equity because no prior comparable balance is available."]
        return self._derived_metric(period, "return_on_equity", label, income.value * multiplier / average_equity * 100, unit, [income, equity, *([prior_equity] if prior_equity else [])], warnings)

    def _return_on_invested_capital(self, period, previous):
        operating = period.metrics["operating_income"]
        pretax = period.metrics["pretax_income"]
        tax = period.metrics["income_tax_expense"]
        debt = period.metrics["debt"]
        equity = period.metrics["stockholders_equity"]
        cash = period.metrics["cash"]
        label, unit = DERIVED_METRICS["return_on_invested_capital"]
        inputs = [operating, pretax, tax, debt, equity, cash]
        if any(metric.value is None for metric in inputs) or pretax.value == 0:
            return self._derived_metric(period, "return_on_invested_capital", label, None, unit, inputs, ["ROIC requires operating income, pretax income, tax, debt, equity, and cash."])
        tax_rate = min(max(tax.value / pretax.value, 0), 1)
        current_capital = debt.value + equity.value - cash.value
        prior_capital = None
        if previous:
            prior_values = [previous.metrics[metric_id].value for metric_id in ("debt", "stockholders_equity", "cash")]
            if all(value is not None for value in prior_values):
                prior_capital = prior_values[0] + prior_values[1] - prior_values[2]
        average_capital = (current_capital + prior_capital) / 2 if prior_capital is not None else current_capital
        if average_capital == 0:
            return self._derived_metric(period, "return_on_invested_capital", label, None, unit, inputs, ["ROIC invested capital is zero."])
        multiplier = 4 if period.kind == MetricPeriodKind.QUARTERLY else 1
        warnings = [] if prior_capital is not None else ["ROIC uses ending invested capital because no prior comparable balance is available."]
        return self._derived_metric(period, "return_on_invested_capital", label, operating.value * (1 - tax_rate) * multiplier / average_capital * 100, unit, inputs, warnings)

    @staticmethod
    def _flow_matches_kind(fact, kind):
        if fact.period_start is None:
            return False
        duration = (fact.period_end - fact.period_start).days + 1
        if kind == MetricPeriodKind.ANNUAL:
            return duration >= 250 and (fact.fiscal_period == "FY" or fact.form.startswith("10-K"))
        return 60 <= duration <= 120 and (fact.form.startswith("10-Q") or (fact.fiscal_period or "").startswith("Q") or "Q" in (fact.frame or ""))

    @classmethod
    def _fact_matches_kind(cls, fact, kind):
        if fact.period_start is not None:
            return cls._flow_matches_kind(fact, kind)
        if kind == MetricPeriodKind.ANNUAL:
            return fact.fiscal_period == "FY" or fact.form.startswith("10-K")
        return fact.form.startswith("10-Q") or (fact.fiscal_period or "").startswith("Q")

    @staticmethod
    def _metric(metric_id, label, value, unit, kind, start, end, fiscal_year, fiscal_period, sources, warnings):
        return NormalizedMetric(
            metric_id=metric_id,
            label=label,
            value=round(value, 8) if value is not None else None,
            unit=unit,
            period_kind=kind,
            period_start=start,
            period_end=end,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            definition_version=METRIC_DEFINITION_VERSION,
            source_fact_ids=list(dict.fromkeys(sources)),
            warnings=list(dict.fromkeys(warnings)),
        )

    def _derived_metric(self, period, metric_id, label, value, unit, inputs, warnings=None):
        sources = list(dict.fromkeys(source for metric in inputs for source in metric.source_fact_ids))
        return NormalizedMetric(
            metric_id=metric_id,
            label=label,
            value=round(value, 8) if value is not None else None,
            unit=unit,
            period_kind=period.kind,
            period_start=period.start,
            period_end=period.end,
            fiscal_year=period.fiscal_year,
            fiscal_period=period.fiscal_period,
            definition_version=METRIC_DEFINITION_VERSION,
            derived=True,
            source_fact_ids=sources,
            warnings=list(dict.fromkeys(warnings or [])),
        )
