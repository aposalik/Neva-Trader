"""Paylaşılan veri modelleri (ayak sonuçları, emir planı, karar)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEUTRAL = "NEUTRAL"


class Source(str, Enum):
    LIVE = "LIVE"
    HYBRID = "HYBRID"            # Canlı kaynaktan gelen veri
    MOCK = "MOCK"            # Config gereği bilinçli mock
    FALLBACK = "FALLBACK"    # Canlı kaynak başarısız -> mock'a düşüldü
    SIMULATED = "SIMULATED"  # Demo senaryosu / --simulate-event


@dataclass
class PillarResult:
    """Tek bir sinyal ayağının çıktısı."""

    name: str
    status: Status
    reason: str
    source: Source = Source.LIVE
    metrics: dict[str, Any] = field(default_factory=dict)
    source_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "reason": self.reason,
            "source": self.source.value,
            "source_label": self.source_label,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class OrderPlan:
    """Deterministik olarak hesaplanmış emir planı. frozen: onaydan sonra değiştirilemez."""

    inst_id: str
    side: str
    size: float
    entry_price: float
    sl_price: float
    tp_price: float
    stop_loss_pct: float
    take_profit_pct: float
    risk_reward_ratio: float
    notional_usdt: float
    risk_usdt: float
    risk_pct_of_balance: float
    net_rr_after_fees: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Decision:
    """Bir döngünün nihai kararı (audit trail kaydı)."""

    timestamp: str
    action: str  # BUY | NO_TRADE | BLOCKED
    reasons: list[str]
    pillars: list[PillarResult]
    market: dict[str, Any] = field(default_factory=dict)
    plan: OrderPlan | None = None
    execution: dict[str, Any] | None = None
    scenario: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "scenario": self.scenario,
            "action": self.action,
            "reasons": self.reasons,
            "pillars": [p.to_dict() for p in self.pillars],
            "market": self.market,
            "plan": self.plan.to_dict() if self.plan else None,
            "execution": self.execution,
        }
