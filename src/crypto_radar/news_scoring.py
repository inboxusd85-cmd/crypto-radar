from __future__ import annotations

import html
import re

_POSITIVE = (
    "partnership", "adoption", "growth", "success", "record", "inflow",
    "launch", "approval", "approved", "funding", "integration", "surge",
    "breakout", "rally", "bullish", "upgrade", "inflows", "приток",
    "партнер", "рост", "успех", "рекорд", "запуск", "одобр",
    "прорыв", "ралли", "быч", "обновлен",
)
_NEGATIVE = (
    "hack", "exploit", "outage", "lawsuit", "bankruptcy", "risk", "attack",
    "ban", "fraud", "scam", "loss", "inflow out", "outflow", "outflows",
    "liquidation", "liquidations", "whale selling", "regulatory pressure",
    "etf outflow", "selloff", "drawdown", "bearish", "downgrade", "depeg",
    "взлом", "атака", "иск", "банкрот", "риск", "запрет", "мошен", "потер",
    "сбой", "отток", "ликвидац", "распродаж", "снижен", "давлен", "медвеж",
)

_NUMERIC_RE = re.compile(r"(?<![A-Za-zА-Яа-я])(?:[$€£]\s*)?\d+(?:[.,]\d+)?\s*(?:%|[KkMmBb](?:n|illion)?|million|billion|тыс\.?|млн\.?|млрд\.?)?", re.IGNORECASE)


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"<img\b[^>]*>", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\b(?:published|updated|fetched)\s+20\d{2}\b", " ", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def _count(text: str, markers: tuple[str, ...]) -> int:
    lowered = text.casefold()
    return sum(len(re.findall(re.escape(marker), lowered)) for marker in markers)


def _numeric_evidence(text: str) -> list[str]:
    values = [item.strip() for item in _NUMERIC_RE.findall(text) if item.strip()]
    values = [item for item in values if "." not in item and "," not in item or any(symbol in item for symbol in ("$", "€", "£", "%")) or any(unit in item.casefold() for unit in ("million", "billion", "млн", "млрд", "тыс"))]
    return list(dict.fromkeys(values))


def _extract_evidence(title: str, summary: str = "") -> tuple[int, int, list[str]]:
    text = _clean_text(f"{title} {summary}")
    positive = _count(text, _POSITIVE)
    negative = _count(text, _NEGATIVE)
    numbers = _numeric_evidence(text)
    if negative and numbers:
        negative += min(2, len(numbers))
    return positive, negative, numbers


def score_news(title: str, summary: str = "") -> dict[str, object]:
    positive, negative, numbers = _extract_evidence(title, summary)
    score = max(-10, min(10, positive - negative))
    if positive == negative:
        label = "нейтрально"
        basis = "Нет выраженных позитивных или негативных маркеров."
    elif score > 0:
        label = "позитивно"
        basis = f"позитивная оценка: найдено маркеров {positive}; негативных маркеров: {negative}."
    else:
        label = "негативно"
        basis = f"негативная оценка: найдено маркеров {negative}; позитивных маркеров: {positive}."
    basis += f" Итоговая оценка: {score}/10."
    if numbers:
        basis += f" Числовые данные: {', '.join(numbers[:4])}."
    return {"score": score, "label": label, "basis": basis}
