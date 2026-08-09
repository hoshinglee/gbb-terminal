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
    lifecycle = Path("app/web/src/features/option-lab/lifecycle-workspace.tsx").read_text()
    stock_observatory = Path("app/web/src/features/stock-observatory/stock-observatory.tsx").read_text()
    market_pulse = Path("app/web/src/features/market-pulse/market-pulse.tsx").read_text()
    assert '"version": "0.6.0"' in package
    assert '"react"' in package
    assert '"lightweight-charts"' in package
    assert 'import("@/features/strategy-lab/strategy-lab")' in application
    assert 'import("@/features/option-lab/option-lab")' in application
    assert 'import("@/features/stock-observatory/stock-observatory")' in application
    assert 'import("@/features/market-pulse/market-pulse")' in application
    assert "<StrategyLab />" in application
    assert "<OptionLab initialTicker={initialTicker} />" in application
    assert "<StockObservatory initialTicker={initialTicker} />" in application
    assert "<MarketPulse />" in application
    assert "PositionBuilder" in option_lab
    assert "ScenarioWorkspace" in option_lab
    assert "LifecycleWorkspace" in option_lab
    assert "applyOptionLifecycleEvent" in option_lab
    assert "Journal Next Decision" in lifecycle
    assert "MarketWorkspaceChart" in stock_observatory
    assert "Current Option Context" in stock_observatory
    assert "summarizeSectors" in market_pulse
    assert "Provider Readiness" in market_pulse
    assert "StrategyCommand" in strategy_lab
    assert "ProposalReviewDialog" in strategy_lab
    assert 'value="robustness"' in evidence
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
    assert 'href: "/?lab=stock"' in app_shell
    assert 'href: "/?lab=market"' in app_shell
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
