"""On-chain signal abstraction; AVAX-specific sources must be verified before live use."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class OnchainSignal:
    signal: str
    score: float
    source: str
    is_live: bool
    fallback_reason: str | None = None


def get_onchain_signal(mock: dict) -> OnchainSignal:
    payload = mock["onchain"]
    return OnchainSignal(payload["signal"], float(payload["score"]), payload["source"], False,
                         "AVAX kapsamlı on-chain provider doğrulanmadı")
