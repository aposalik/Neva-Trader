from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class PositionPlan:
    notional_usd: float
    size_avax: float
    stop_loss_price: float
    take_profit_price: float


def size_position(*, balance_usdt: float, price: float, risk_pct: float, max_notional_usd: float,
                  stop_loss_pct: float, risk_reward_ratio: float) -> PositionPlan:
    if min(balance_usdt, price, risk_pct, max_notional_usd, stop_loss_pct, risk_reward_ratio) <= 0:
        raise ValueError("Pozisyon boyutlandırma parametreleri pozitif olmalıdır.")
    notional = min(balance_usdt * risk_pct, max_notional_usd)
    size = notional / price
    stop = price * (1 - stop_loss_pct)
    take = price * (1 + stop_loss_pct * risk_reward_ratio)
    return PositionPlan(round(notional, 2), round(size, 6), round(stop, 4), round(take, 4))
