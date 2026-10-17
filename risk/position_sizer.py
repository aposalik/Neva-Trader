"""Deterministik Pozisyon Boyutlandırıcı ve R/R Seviye Hesaplayıcı.

Formüller:
  take_profit_pct = stop_loss_pct * risk_reward_ratio
  notional_target = balance_usdt * (position_size_pct / 100)
  raw_size = notional_target / entry_price
  size = round_step(raw_size, lotSz, mode='down')
  sl_price = round_step(entry_price * (1 - sl_pct), tickSz, mode='down')
  tp_price = round_step(entry_price * (1 + tp_pct), tickSz, mode='up')

Komisyon etkisi (net R/R) jüri şeffaflığı için hesaplanır.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from models import OrderPlan
from utils import round_step, to_float

log = logging.getLogger("nexa.position_sizer")


def calculate_order_plan(
    balance_usdt: float,
    entry_price: float,
    config: dict[str, Any],
    instrument: dict[str, float],
) -> OrderPlan:
    """Parametrelere ve borsa kurallarına göre kesinleşmiş OrderPlan üretir."""
    risk_cfg = config.get("risk", {})
    exec_cfg = config.get("execution", {})

    pos_size_pct = to_float(risk_cfg.get("position_size_pct", 5.0))
    sl_pct = to_float(risk_cfg.get("stop_loss_pct", 1.2))
    rr_ratio = to_float(risk_cfg.get("risk_reward_ratio", 2.0))
    fee_pct = to_float(exec_cfg.get("fee_pct", 0.1))

    # Formül: TP yüzdesi = SL × R/R
    tp_pct = round(sl_pct * rr_ratio, 3)

    # Decimal kullanarak hassas hesaplama (floating point 9.879999999999999 hatasını önler)
    d_bal = Decimal(str(balance_usdt))
    d_price = Decimal(str(entry_price))
    d_pos_pct = Decimal(str(pos_size_pct)) / Decimal("100")
    d_sl_pct = Decimal(str(sl_pct)) / Decimal("100")
    d_tp_pct = Decimal(str(tp_pct)) / Decimal("100")

    d_notional_target = d_bal * d_pos_pct
    d_raw_size = d_notional_target / d_price if d_price > 0 else Decimal("0")

    lot_sz = instrument.get("lotSz", 0.000001)
    tick_sz = instrument.get("tickSz", 0.001)

    size = round_step(float(d_raw_size), lot_sz, mode="down")
    sl_raw = float(d_price * (Decimal("1") - d_sl_pct))
    tp_raw = float(d_price * (Decimal("1") + d_tp_pct))

    sl_price = round_step(sl_raw, tick_sz, mode="down")
    tp_price = round_step(tp_raw, tick_sz, mode="up")

    actual_notional = round(size * entry_price, 2)
    risk_usdt = round(size * (entry_price - sl_price), 2)
    risk_pct_of_balance = round((risk_usdt / (balance_usdt + 1e-9)) * 100.0, 3)

    # Komisyon Sonrası Net R/R Oranı
    net_profit_pct = tp_pct - (2.0 * fee_pct)
    net_loss_pct = sl_pct + (2.0 * fee_pct)
    net_rr = round(net_profit_pct / (net_loss_pct + 1e-9), 2)

    return OrderPlan(
        inst_id=config.get("instrument", "AVAX-USDT"),
        side="buy",
        size=size,
        entry_price=round(entry_price, 4),
        sl_price=round(sl_price, 4),
        tp_price=round(tp_price, 4),
        stop_loss_pct=sl_pct,
        take_profit_pct=tp_pct,
        risk_reward_ratio=rr_ratio,
        notional_usdt=actual_notional,
        risk_usdt=risk_usdt,
        risk_pct_of_balance=risk_pct_of_balance,
        net_rr_after_fees=net_rr,
    )
