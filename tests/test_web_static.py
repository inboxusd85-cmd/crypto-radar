from pathlib import Path

from fastapi.testclient import TestClient

from crypto_radar.web.app import create_app


def test_production_app_preserves_spa_routes_api_namespace_and_static_assets(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>Crypto Radar SPA</body></html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('spa')", encoding="utf-8")
    client = TestClient(create_app(history_path=tmp_path / "history.sqlite3", static_dir=dist))

    for route in ("/", "/signals", "/events", "/health", "/asset/BTC"):
        response = client.get(route)
        assert response.status_code == 200
        assert "Crypto Radar SPA" in response.text
        assert response.headers["content-type"].startswith("text/html")

    api = client.get("/api/v1/health")
    assert api.status_code == 200
    assert api.headers["content-type"].startswith("application/json")
    assert api.json()["status"] == "ok"

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert asset.text == "console.log('spa')"
    assert asset.headers["content-type"].startswith("text/javascript")

    missing_asset = client.get("/assets/missing.js")
    assert missing_asset.status_code == 404
