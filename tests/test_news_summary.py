from crypto_radar.news_summary import summarize_news_ru


def test_summarize_news_ru_returns_compact_russian_summary() -> None:
    result = summarize_news_ru(
        "Ethereum protocol update",
        "Ethereum network upgrade improves validator stability and reduces fees.",
    )

    assert result == "Обновление протокола Ethereum: обновление сети улучшает стабильность валидаторов и снижает комиссии."


def test_summarize_news_ru_does_not_echo_long_source_body() -> None:
    result = summarize_news_ru("Bitcoin update", " ".join(["Bitcoin"] * 100))

    assert len(result) < 240
    assert result.startswith("Обновление Bitcoin:")


def test_summarize_news_ru_strips_rss_html_and_extracts_content() -> None:
    result = summarize_news_ru(
        "Bitcoin security consortium",
        '<p><img src="https://example.test/image.png" /> Nine institutional Bitcoin heavyweights formed a consortium to fund developers working on network security.</p>',
    )

    assert "Nine institutional" not in result
    assert "консорциум" in result or "подробности доступны" not in result


def test_summarize_news_ru_translates_real_unchained_title() -> None:
    result = summarize_news_ru(
        "BlackRock, Coinbase, Strategy Among Members of $15 Million Bitcoin Security Consortium",
        "Nine institutional Bitcoin heavyweights formed the Bitcoin Security Consortium to fund developers working on the network's long-term security, including post-quantum cryptography.",
    )

    assert result.startswith("BlackRock, Coinbase и Strategy вошли в консорциум безопасности Bitcoin")
    assert "девять крупных институциональных участников" in result


def test_summarize_news_ru_translates_unknown_article_body_instead_of_using_title_only() -> None:
    result = summarize_news_ru(
        "Bitcoin market update",
        "The market is under pressure as investors reduce risk and liquidity falls. The selloff also affects smaller assets as trading volume declines by 18% after $125 million leaves the market.",
    )

    assert "The market is under pressure" not in result
    assert "рынок" in result.lower()
    assert "инвестор" in result.lower()
    assert "ликвидност" in result.lower()
    assert "125" in result
    assert "18%" in result
    assert "распродаж" in result.lower() or "объём" in result.lower()


def test_summarize_news_ru_does_not_expose_unknown_english_title() -> None:
    result = summarize_news_ru(
        "What Did David Sacks Actually Accomplish for Bitcoin?",
        "I am trying to separate the hype from the facts.",
    )

    assert "What Did David Sacks" not in result
    assert "Что известно о достижениях David Sacks" in result
    assert "Материал посвящён указанной теме" not in result


def test_summarize_news_ru_keeps_meaning_for_known_reddit_titles() -> None:
    tax_credit = summarize_news_ru(
        "How wild would it be if there was a tax credit for mining Bitcoin like there was for solar?",
        "",
    )
    sacks = summarize_news_ru(
        "What Did David Sacks Actually Accomplish for Bitcoin?",
        "",
    )

    assert "налоговый кредит" in tax_credit.lower()
    assert "достижениях David Sacks" in sacks
    assert "Материал посвящён указанной теме" not in tax_credit
    assert "Материал посвящён указанной теме" not in sacks
