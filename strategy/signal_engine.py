"""Four-signal decision matrix. Any failed required signal means no trade."""
from __future__ import annotations
from dataclasses import dataclass
from data.news import NewsSignal
from data.onchain import OnchainSignal
from strategy.technical import TechnicalSignal


@dataclass(frozen=True)
class Proposal:
    action: str
    reasons: tuple[str, ...]
    confidence: float


def propose(technical: TechnicalSignal, news: NewsSignal, onchain: OnchainSignal) -> Proposal:
    checks = {
        "technical": technical.trend == "bullish" and technical.volume_confirmed,
        "news": news.sentiment >= 0,
        "onchain": onchain.score >= 0,
    }
    failed = tuple(name for name, passed in checks.items() if not passed)
    if failed:
        return Proposal("NO_TRADE", (f"Sinyal veto: {', '.join(failed)}",), 0.0)
    confidence = min(0.95, 0.45 + max(news.sentiment, 0) * 0.3 + max(onchain.score, 0) * 0.2
                     + (0.05 if technical.bullish_pattern else 0))
    return Proposal("BUY", ("Trend, hacim, haber ve on-chain sinyalleri uyumlu.",), round(confidence, 2))
