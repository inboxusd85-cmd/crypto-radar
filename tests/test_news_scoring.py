from crypto_radar.news_scoring import score_news


def test_news_score_is_neutral_for_unclassified_article() -> None:
    result = score_news("Weekly ecosystem update", "Protocol metrics remain stable.")

    assert "Итоговая оценка: 0/10" in result["basis"]

def test_news_score_is_capped_and_explains_direction() -> None:
    result = score_news("Hack exploit outage lawsuit", "Bankruptcy risk and attack reported.")

    assert result["score"] < 0
    assert result["score"] >= -10
    assert "негатив" in result["basis"]
    assert "Итоговая оценка:" in result["basis"]


def test_news_score_counts_extended_market_terms_and_numeric_evidence() -> None:
    result = score_news(
        "Bitcoin ETF outflows and whale liquidation risk",
        "Institutional outflow reached $125 million, down 18% week over week; regulatory pressure increased.",
    )

    assert result["score"] <= 3
    assert "маркеров" in result["basis"]
    assert "$125 million" in result["basis"]
    assert "числ" in result["basis"].lower()
    assert "125" in result["basis"]
    assert "18%" in result["basis"]




def test_news_score_ignores_html_dimensions_and_metadata_numbers() -> None:
    result = score_news(
        "Bitcoin update",
        '<p>Outflow reached $125 million, down 18% under BIP 110.</p><img width="1672" height="941"> published 2026',
    )

    assert "$125 million" in result["basis"]
    assert "18%" in result["basis"]
    assert "110" in result["basis"]
    assert "1672" not in result["basis"]
    assert "941" not in result["basis"]
    assert "2026" not in result["basis"]


def test_news_score_ignores_bare_technical_decimals_but_keeps_explicit_facts() -> None:
    result = score_news(
        "Bitcoin market update",
        "Indicator value 0.03; outflow was $125 million, down 18% after BIP 110.",
    )

    assert "0.03" not in result["basis"]
    assert "$125 million" in result["basis"]
    assert "18%" in result["basis"]
    assert "110" in result["basis"]


def test_news_score_positive_markers_move_above_neutral() -> None:
    result = score_news("Partnership adoption growth", "Launch success and record inflows.")

    assert result["score"] > 0
    assert result["score"] <= 10
    assert "позитив" in result["basis"]
    assert "Итоговая оценка:" in result["basis"]


def test_news_score_uses_signed_ten_point_scale() -> None:
    assert score_news("Weekly ecosystem update", "Protocol metrics remain stable.")["score"] == 0
    assert score_news("Partnership adoption growth success record launch approval breakout rally bullish upgrade", "")["score"] == 10
    assert score_news("Hack exploit outage lawsuit bankruptcy risk attack ban fraud scam loss liquidation selloff drawdown bearish downgrade depeg", "")["score"] == -10
