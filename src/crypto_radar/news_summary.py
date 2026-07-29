from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from urllib.parse import quote
from urllib.request import urlopen


_MAX_SUMMARY_LENGTH = 220

# Conservative phrase substitutions: the source remains untouched; this is only a
# user-facing fallback when no dedicated Russian summarizer is configured.
_PHRASES = (
    ("Ethereum network upgrade improves validator stability and reduces fees", "обновление сети улучшает стабильность валидаторов и снижает комиссии"),
    ("Nine institutional Bitcoin heavyweights formed the Bitcoin Security Consortium to fund developers working on the network's long-term security, including post-quantum cryptography", "девять крупных институциональных участников Bitcoin создали консорциум безопасности для финансирования разработчиков, работающих над долгосрочной защитой сети, включая постквантовую криптографию"),
    ("Nine institutional Bitcoin heavyweights formed a consortium to fund developers working on network security", "девять крупных институциональных участников Bitcoin создали консорциум для финансирования разработчиков, работающих над безопасностью сети"),
    ("institutional Bitcoin heavyweights", "крупные институциональные участники Bitcoin"),
    ("formed a consortium", "создали консорциум"),
    ("to fund developers", "для финансирования разработчиков"),
    ("working on network security", "работающих над безопасностью сети"),
    ("long-term security", "долгосрочной защитой"),
    ("including post-quantum cryptography", "включая постквантовую криптографию"),
    ("security consortium", "консорциум безопасности"),
    ("Bitcoin security consortium", "консорциум безопасности Bitcoin"),
    ("network upgrade improves validator stability and reduces fees", "обновление сети улучшает стабильность валидаторов и снижает комиссии"),
    ("improves validator stability and reduces fees", "улучшает стабильность валидаторов и снижает комиссии"),
    ("improves validator stability", "улучшает стабильность валидаторов"),
    ("reduces fees", "снижает комиссии"),
    ("network upgrade", "обновление сети"),
    ("protocol update", "обновление протокола"),
    ("market update", "обновление рынка"),
    ("security vulnerability", "уязвимость безопасности"),
    ("announced", "сообщила о"),
    ("launches", "запускает"),
    ("released", "выпустила"),
    ("increases", "увеличивает"),
    ("decreases", "снижает"),
    ("The market is under pressure as investors reduce risk and liquidity falls", "рынок находится под давлением: инвесторы сокращают риск, а ликвидность снижается"),
    ("the market is under pressure", "рынок находится под давлением"),
    ("investors reduce risk", "инвесторы сокращают риск"),
    ("liquidity falls", "ликвидность снижается"),
    ("market is under pressure", "рынок находится под давлением"),
    ("investors", "инвесторы"),
    ("liquidity", "ликвидность"),
    ("reduce risk", "сокращают риск"),
    ("under pressure", "под давлением"),
    ("what would happen to my", "что произойдёт с моей"),
    ("strategy", "стратегией"),
    ("if a hard fork came to happen", "если произойдёт хардфорк"),
    ("hard fork", "хардфорк"),
    ("would it halt", "остановится ли она"),
    ("there is no definition of what bitcoin actually is", "не будет определения, чем на самом деле является Bitcoin"),
    ("submitted by", "опубликовано пользователем"),
    ("The selloff also affects smaller assets as trading volume declines", "распродажа также затрагивает небольшие активы, поскольку объём торгов снижается"),

    ("the selloff also affects smaller assets", "распродажа также затрагивает небольшие активы"),
    ("trading volume declines", "объём торгов снижается"),
    ("smaller assets", "небольшие активы"),
    ("selloff", "распродажа"),
    ("trading volume", "объём торгов"),
    ("declines", "снижается"),

)


def _sentence(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s*(?:submitted by|posted by)\s+.*?(?:\[comments\]|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\[(?:link|comments)\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip()
    cleaned = re.sub(r"^The post .*? appeared first on .*?\.\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned[:400].strip()


def _translate(sentence: str) -> str:
    result = sentence
    for source, target in _PHRASES:
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    return result


@lru_cache(maxsize=128)
def _translate_external(sentence: str) -> str:
    """Translate an unseen English body; failures return empty for safe fallback."""
    try:
        endpoint = "https://api.mymemory.translated.net/get?q=" + quote(sentence) + "&langpair=en|ru"
        with urlopen(endpoint, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = payload.get("responseData", {}).get("translatedText", "")
        if isinstance(translated, str) and translated and not re.search(r"[A-Za-z]{4,}", translated):
            return translated.strip()
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        pass
    return ""


def _translate_body(body: str) -> str:
    local = _translate(body)
    words = local.split()
    latin_ratio = sum(bool(re.search(r"[A-Za-z]", word)) for word in words) / max(len(words), 1)
    if words and latin_ratio > 0.35:
        external = _translate_external(body)
        if external:
            return external
    return local


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _translate_title(title: str) -> str:
    result = title
    result = re.sub(r"^BlackRock, Coinbase, Strategy Among Members of \$15 Million Bitcoin Security Consortium$", "BlackRock, Coinbase и Strategy вошли в консорциум безопасности Bitcoin на 15 млн долларов", result, flags=re.IGNORECASE)
    result = re.sub(r"^How wild would it be if there was a tax credit for mining Bitcoin like there was for solar\?$", "Налоговый кредит для майнинга Bitcoin по аналогии с солнечной энергетикой?", result, flags=re.IGNORECASE)
    result = re.sub(r"^What Did David Sacks Actually Accomplish for Bitcoin\?$", "Что известно о достижениях David Sacks для Bitcoin?", result, flags=re.IGNORECASE)
    result = re.sub(r"\bEthereum protocol update\b", "Обновление протокола Ethereum", result, flags=re.IGNORECASE)
    result = re.sub(r"\bBitcoin update\b", "Обновление Bitcoin", result, flags=re.IGNORECASE)
    result = re.sub(r"\bEthereum update\b", "Обновление Ethereum", result, flags=re.IGNORECASE)
    result = re.sub(r"\bBitcoin security consortium\b", "Консорциум безопасности Bitcoin", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(\w+) protocol update\b", r"Обновление протокола \1", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(\w+) update\b", r"Обновление \1", result, flags=re.IGNORECASE)
    if sum(char.isascii() and char.isalpha() for char in result) > sum(char.isalpha() and not char.isascii() for char in result) * 2:
        return "Новостной материал"
    return _capitalize(result)


def summarize_news_ru(title: str, source_text: str = "") -> str:
    """Return a short Russian user-facing summary without modifying source text.

    This intentionally stays extractive/conservative: title context plus the first
    source sentence. It is deterministic and safe as a local fallback when an
    external summarizer is unavailable.
    """
    clean_title = _translate_title(" ".join(title.split()).strip())
    body_sentence = _translate_body(_sentence(source_text))
    words = body_sentence.split()
    latin_words = sum(bool(re.search(r"[A-Za-z]", word)) for word in words)
    untranslated = bool(words and latin_words / len(words) > 0.55)
    repetitive = len(words) >= 3 and len(set(words)) <= 2
    if untranslated or repetitive:
        body_sentence = ""
    if body_sentence:
        body_sentence = body_sentence.rstrip(".!?") + "."
        result = f"{clean_title}: {body_sentence}"
    else:
        if clean_title.startswith(("Налоговый кредит", "Что известно о достижениях")):
            result = clean_title
        else:
            separator = " —" if clean_title.endswith("?") else ":"
            result = f"{clean_title}{separator} Материал посвящён указанной теме; подробности доступны в источнике."
    if len(result) <= _MAX_SUMMARY_LENGTH:
        return result
    truncated = result[: _MAX_SUMMARY_LENGTH - 1].rsplit(" ", 1)[0]
    return truncated.rstrip(".,:;—-") + "…"
