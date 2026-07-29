from crypto_radar.cli import severity_at_least


def test_severity_filter_is_ordered():
    assert severity_at_least("high", "medium") is True
    assert severity_at_least("low", "medium") is False
    assert severity_at_least("medium", "medium") is True


def test_default_asset_allowlist_includes_hype_and_zec():
    from pathlib import Path
    cli_source = Path(__file__).parents[1].joinpath("src", "crypto_radar", "cli.py").read_text()
    assert 'DEFAULT_ASSETS = "BTC,ETH,SOL,HYPE,ZEC"' in cli_source
