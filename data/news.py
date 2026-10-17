"""News signal with explicit provenance and safe fallback."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSignal:
    sentiment: float
    summary: str
    source: str
    is_live: bool
    fallback_reason: str | None = None


def get_news_signal(mock: dict, *, force_negative: bool = False) -> NewsSignal:
    # Gemini/CryptoPanic credentials are optional. Until a verified provider is wired,
    # retain transparent fixture semantics rather than pretending a model call happened.
    if force_negative:
        return NewsSignal(-0.45, "Regulatory-risk scenario", "demo-script", False)
    payload = mock["news"]
    configured = bool(os.getenv("GEMINI_API_KEY"))
    reason = "Gemini/RSS provider henüz doğrulanmadı" if configured else "GEMINI_API_KEY yok"
    return NewsSignal(float(payload["sentiment"]), payload["summary"], payload["source"], False, reason)
