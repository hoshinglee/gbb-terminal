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
