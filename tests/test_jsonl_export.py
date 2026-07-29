import json

from crypto_radar.models import Signal
from crypto_radar.jsonl_export import write_jsonl


def signal(asset="HYPE"):
    return Signal(
        asset=asset, signal_type="composite_market_risk", fact="fact", basis="basis",
        source_urls=["https://example.com"], severity="high", confidence=0.9,
    )


def test_write_jsonl_atomically_replaces_previous_output(tmp_path):
    output = tmp_path / "alerts.jsonl"
    output.write_text("old\n")
    write_jsonl(output, [signal("HYPE"), signal("ZEC")])
    lines = output.read_text().splitlines()
    assert [json.loads(line)["asset"] for line in lines] == ["HYPE", "ZEC"]
    assert all("basis" in json.loads(line) for line in lines)


def test_write_jsonl_empty_result_is_empty_file(tmp_path):
    output = tmp_path / "alerts.jsonl"
    write_jsonl(output, [])
    assert output.read_text() == ""
