from pathlib import Path


def test_browser_contains_primary_labs_and_hides_internal_keys():
    document = Path("app/index.html").read_text()
    script = Path("app/static/app.js").read_text()
    market_chart_script = Path("app/static/market-chart.js").read_text()
    assert "Strategy Lab" in document
    assert "Option Lab" in document
    assert 'id="benchmark-evidence"' in document
    assert 'id="validation-evidence"' in document
    assert 'id="parameter-heatmap"' in document
    assert "TRADE LEDGER" in document
    assert "Advanced · Edit or Export YAML" in document
    assert "STRATEGY KEY" not in document
    assert "PERSISTED YAML DEFINITIONS" not in document
    assert 'id="run-simulation"' not in document
    assert 'id="relative-strength-reference"' in document
    assert 'data-step="4"' in document
    assert "function setWorkflowStep(step)" in script
    assert "clearStrategyConfiguration();" in script
    assert 'id="research-market-chart"' in document
    assert 'data-market-interval="year"' in document
    assert 'data-market-overlay="sma"' in document
    assert 'data-market-overlay="ema"' in document
    assert 'data-market-overlay="bollinger"' in document
    assert '/static/market-chart.js' in document
    assert "class ResearchMarketChart" in market_chart_script
    assert "drawPrice(points, highlightIndex)" in market_chart_script
    assert "drawVolume(points, highlightIndex)" in market_chart_script
    assert "drawMomentum(points, highlightIndex)" in market_chart_script


def test_runtime_data_is_git_ignored():
    ignore = Path(".gitignore").read_text().splitlines()
    assert "data/" in ignore
    assert "log/" in ignore
    assert ".env" in ignore


def test_react_research_canvas_sources_are_present():
    package = Path("app/web/package.json").read_text()
    application = Path("app/web/src/app.tsx").read_text()
    strategy_lab = Path("app/web/src/features/strategy-lab/strategy-lab.tsx").read_text()
    evidence = Path("app/web/src/features/strategy-lab/evidence-workspace.tsx").read_text()
    chart = Path("app/web/src/features/strategy-lab/market-workspace-chart.tsx").read_text()
    option_lab = Path("app/web/src/features/option-lab/option-lab.tsx").read_text()
    options_planner = Path("app/web/src/features/option-lab/options-planner.tsx").read_text()
    lifecycle = Path("app/web/src/features/option-lab/lifecycle-workspace.tsx").read_text()
    market_pulse = Path("app/web/src/features/market-pulse/market-pulse.tsx").read_text()
    company_intelligence = Path("app/web/src/features/company-intelligence/company-intelligence.tsx").read_text()
    decision_center = Path("app/web/src/features/decision-center/decision-center.tsx").read_text()
    earnings_chart = Path("app/web/src/features/company-intelligence/earnings-reaction-chart.tsx").read_text()
    financial_history = Path("app/web/src/features/company-intelligence/financial-history.tsx").read_text()
    valuation_chart = Path("app/web/src/features/company-intelligence/valuation-history-chart.tsx").read_text()
    relationship_network = Path("app/web/src/features/company-intelligence/relationship-network.tsx").read_text()
    operations_intelligence = Path("app/web/src/features/company-intelligence/operations-intelligence.tsx").read_text()
    guidance_timeline = Path("app/web/src/features/company-intelligence/guidance-timeline.tsx").read_text()
    source_dialog = Path("app/web/src/features/company-intelligence/source-evidence-dialog.tsx").read_text()
    assert '"version": "0.10.0"' in package
    assert '"react"' in package
    assert '"lightweight-charts"' in package
    assert 'import("@/features/strategy-lab/strategy-lab")' in application
    assert 'import("@/features/option-lab/option-lab")' in application
    assert 'import("@/features/market-pulse/market-pulse")' in application
    assert 'import("@/features/company-intelligence/company-intelligence")' in application
    assert 'import("@/features/decision-center/decision-center")' in application
    assert "<StrategyLab />" in application
    assert "<OptionLab initialTicker={initialTicker} />" in application
    assert "<MarketPulse />" in application
    assert "<CompanyIntelligence initialTicker={initialTicker} />" in application
    assert "<DecisionCenter initialTicker={initialTicker} />" in application
    assert "PositionBuilder" in option_lab
    assert "ScenarioWorkspace" in option_lab
    assert "LifecycleWorkspace" in option_lab
    assert "OptionsPlanner" in option_lab
    assert "What if {plan?.ticker} is $X on date Y?" in options_planner
    assert "Use In Detailed Builder" in options_planner
    assert "The normal planner never suggests an uncovered short call" in options_planner
    assert "applyOptionLifecycleEvent" in option_lab
    assert "Journal Next Decision" in lifecycle
    assert "summarizeSectors" in market_pulse
    assert "Provider Readiness" in market_pulse
    assert "Historical Earnings Reaction" in company_intelligence
    assert "Complete Normalized Financial History" in financial_history
    assert "Trailing Twelve Months" in financial_history
    assert "Quarterly History" in financial_history
    assert "Annual History" in financial_history
    assert "Historical Valuation Path" in company_intelligence
    assert "Historical context · not a trading signal" in valuation_chart
    assert "Reported Facts" in company_intelligence
    assert "Calculated Market Reaction" in company_intelligence
    assert "Historical Evidence, Not A Forecast" in company_intelligence
    assert "EarningsReactionChart" in company_intelligence
    assert "RelationshipNetwork" in company_intelligence
    assert "OperationsIntelligence" in company_intelligence
    assert "GuidanceTimeline" in company_intelligence
    assert "Evidence-Backed Business Network" in relationship_network
    assert "min-w-[640px]" in relationship_network
    assert "Unresolved public-company mapping" in relationship_network
    assert "complete keyboard-accessible table" in relationship_network
    assert "Reporting Definitions Changed" in operations_intelligence
    assert "compatible disclosed total" in operations_intelligence
    assert "Original Qualitative Wording" in guidance_timeline
    assert "Historical Record, Not Model Forecast" in guidance_timeline
    assert "Exact source excerpts remain authoritative" in source_dialog
    assert 'aria-keyshortcuts="ArrowLeft ArrowRight Home End"' in earnings_chart
    assert "CandlestickSeries" in earnings_chart
    assert "createSeriesMarkers" in earnings_chart
    assert "StrategyCommand" in strategy_lab
    assert "ProposalReviewDialog" in strategy_lab
    assert 'value="advanced"' in evidence
    assert "CurrentSignalPanel" in evidence
    assert "createSeriesMarkers" in chart
    assert 'marketChart?.intervals[interval]' in chart
    assert 'maxSize="68%"' in strategy_lab
    assert 'minSize="32%"' in strategy_lab
    assert "Side By Side" in strategy_lab
    assert "Stacked" in strategy_lab
    assert 'symbol={state.ticker}' in strategy_lab
    assert 'ticker: "NVDA"' in Path("app/web/src/features/strategy-lab/workspace.tsx").read_text()
    assert "TrailingStopChip" in Path("app/web/src/features/strategy-lab/strategy-composer.tsx").read_text()
    assert "Darvas Ceiling" in Path("app/web/src/lib/indicators.ts").read_text()
    assert "Fib Resistance" in Path("app/web/src/lib/indicators.ts").read_text()
    assert '"darvas", "fibonacci"' in chart
    assert 'aria-keyshortcuts="ArrowLeft ArrowRight Home End"' in chart
    assert "market-chart-current-value" in chart
    assert "prefers-reduced-motion: reduce" in Path("app/web/src/index.css").read_text()
    app_shell = Path("app/web/src/components/app-shell.tsx").read_text()
    assert 'const mainId = mainIds[activeLab]' in app_shell
    assert 'href: "/?lab=options"' in app_shell
    assert 'href: "/?lab=market"' in app_shell
    assert 'href: "/?lab=intelligence"' in app_shell
    assert 'href: "/?lab=decision"' in app_shell
    assert "Stock Observatory" not in app_shell
    assert "v0.11 decision context" in app_shell
    assert "Investment Thesis" in decision_center
    assert "Instrument Fit Comparator" in decision_center
    assert "Staged Entry Planner" in decision_center
    assert "Process Quality" in decision_center
    assert 'legacy?panel=stock' not in app_shell
    assert 'legacy?panel=market' not in app_shell
    assert 'aria-label="Mobile research laboratories"' in app_shell
    assert "id={mainId}" in app_shell


def test_legacy_page_can_return_to_research_canvas():
    document = Path("app/index.html").read_text()
    assert 'class="canvas-return" href="/"' in document
    assert 'id="stock-ticker" value="NVDA"' in document


def test_system_diagrams_cover_runtime_frontend_research_and_storage():
    diagrams = Path("docs/system-diagrams.md").read_text()
    assert "## Runtime Architecture" in diagrams
    assert "## Frontend Research Canvas" in diagrams
    assert "sequenceDiagram" in diagrams
    assert "erDiagram" in diagrams
    assert "## Frontend Build And Fallback" in diagrams
    assert "## Company Evidence And Business Network Pipeline" in diagrams
