from pathlib import Path
import json
import os
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_rss_launcher_runs_from_any_cwd_and_is_idempotent(tmp_path: Path) -> None:
    launcher = ROOT / "scripts" / "run_rss_pipeline.sh"
    assert launcher.is_file()
    assert os.access(launcher, os.X_OK)

    env = {**os.environ, "HISTORY": str(tmp_path / "rss.sqlite3"), "ASSET": "BTC", "RSS_TIMEOUT": "15"}
    first = subprocess.run([str(launcher)], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    second = subprocess.run([str(launcher)], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)

    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["sources"] == 10
    assert 0 <= first_payload["failed"] <= first_payload["sources"]
    assert first_payload["articles_seen"] >= first_payload["new_articles"] >= 0
    assert second_payload["sources"] == first_payload["sources"]
    assert second_payload["failed"] <= second_payload["sources"]
    assert second_payload["articles_seen"] >= second_payload["new_articles"] >= 0


def test_rss_launcher_rejects_invalid_timeout(tmp_path: Path) -> None:
    launcher = ROOT / "scripts" / "run_rss_pipeline.sh"
    result = subprocess.run(
        [str(launcher)],
        cwd=tmp_path,
        env={**os.environ, "HISTORY": str(tmp_path / "rss.sqlite3"), "RSS_TIMEOUT": "0"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "RSS_TIMEOUT must be positive" in result.stderr


def test_rss_launcher_accepts_custom_yaml_config_without_network(tmp_path: Path) -> None:
    launcher = ROOT / "scripts" / "run_rss_pipeline.sh"
    feed = tmp_path / "feed.xml"
    feed.write_text(
        "<?xml version='1.0'?><rss><channel><item>"
        "<title>Bitcoin local fixture</title><link>https://example.test/btc</link>"
        "<guid>fixture-1</guid></item></channel></rss>",
        encoding="utf-8",
    )
    config = tmp_path / "sources.yaml"
    config.write_text(
        "sources:\n"
        "  - name: Local fixture\n"
        f"    feed_url: {feed.as_uri()}\n"
        "    tier: technical\n"
        "    assets: [BTC]\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "HISTORY": str(tmp_path / "rss.sqlite3"),
        "RSS_CONFIG": str(config),
        "RSS_TIMEOUT": "5",
    }

    result = subprocess.run([str(launcher)], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["sources"] == 1
    assert payload["failed"] == 0
    assert payload["articles_seen"] == 1
    assert payload["new_articles"] == 1


def test_rss_launcher_strict_mode_fails_on_degraded_source(tmp_path: Path) -> None:
    launcher = ROOT / "scripts" / "run_rss_pipeline.sh"
    config = tmp_path / "sources.yaml"
    config.write_text(
        "sources:\n"
        "  - name: Missing fixture\n"
        f"    feed_url: {(tmp_path / 'missing.xml').as_uri()}\n"
        "    tier: technical\n"
        "    assets: [BTC]\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "HISTORY": str(tmp_path / "rss.sqlite3"),
        "RSS_CONFIG": str(config),
        "RSS_TIMEOUT": "1",
        "RSS_STRICT": "1",
    }

    result = subprocess.run([str(launcher)], cwd=tmp_path, env=env, capture_output=True, text=True)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    assert payload["source_health"] == {"technical": "error"}
