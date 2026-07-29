from __future__ import annotations

from .models import Signal


def render_markdown(signal: Signal) -> str:
    explanations = "\n".join(f"- {item}" for item in signal.possible_explanations) or "- Нет дополнительных гипотез"
    sources = "\n".join(f"- {url}" for url in signal.source_urls) or "- Источник не указан"
    return f"""## {signal.asset} — {signal.severity.upper()}\n\n**Факт:** {signal.fact}\n\n**Направление рынка:** {signal.market_direction}\n\n**Основание:** {signal.basis}\n\n**Уверенность:** {signal.confidence:.0%}\n\n**Возможные объяснения:**\n{explanations}\n\n**Источники:**\n{sources}\n\nРучная проверка: {'да' if signal.requires_manual_review else 'нет'}\nАвтоторговля: {'да' if signal.auto_trade else 'нет'}\n"""
