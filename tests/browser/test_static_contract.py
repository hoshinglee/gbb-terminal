from pathlib import Path


def test_browser_contains_primary_labs_and_hides_internal_keys():
    document = Path("app/index.html").read_text()
    assert "Strategy Lab" in document
    assert "Option Lab" in document
    assert "TRADE LEDGER" in document
    assert "Advanced · Edit or Export YAML" in document
    assert "STRATEGY KEY" not in document
    assert "PERSISTED YAML DEFINITIONS" not in document


def test_runtime_data_is_git_ignored():
    ignore = Path(".gitignore").read_text().splitlines()
    assert "data/" in ignore
    assert "log/" in ignore
    assert ".env" in ignore

