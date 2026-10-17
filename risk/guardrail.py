"""Deterministik Risk Koruma Katmanı (Guardrail).

Executor'dan önce MUTLAKA çağrılır; atlanması kodla imkansızdır.
Şu kontrolleri doğrular:
  1. Config geçerliliği
  2. Bakiye yeterliliği
  3. Minimum emir büyüklüğü (minSz)
  4. Alış-Satış makası (Spread kontrolü)
  5. Açık pozisyon veya bekleyen emir varlığı
  6. Günlük işlem adedi sınırı (max_daily_trades)
  7. Günlük kümülatif zarar kilidi (Kill-switch)
  8. Makro blackout durumu
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import OrderPlan, PillarResult, Status
from utils import load_json, to_float

log = logging.getLogger("nexa.guardrail")


class GuardrailManager:
    def __init__(self, config: dict[str, Any], state_file: Path) -> None:
        self.config = config
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Günlük işlem durumunu (trades, loss) yükler; yeni günde otomatik sıfırlar."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        default_state = {
            "date": today_str,
            "trades_count": 0,
            "daily_loss_usdt": 0.0,
            "daily_loss_pct": 0.0,
        }
        if not self.state_file.exists():
            return default_state

        try:
            data = load_json(self.state_file)
            if data.get("date") != today_str:
                # Yeni gün başlangıcı
                return default_state
            return data
        except Exception:
            return default_state

    def _save_state(self) -> None:
        try:
            self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("state.json kaydedilemedi: %s", e)

    def record_trade_executed(self, notional_usdt: float) -> None:
        """Yeni bir işlem açıldığında istatistiği günceller."""
        self.state["trades_count"] = int(self.state.get("trades_count", 0)) + 1
        self._save_state()

    def record_trade_closed(self, pnl_usdt: float, balance_usdt: float) -> None:
        """Kapanan işlemin kâr/zararını işler."""
        if pnl_usdt < 0:
            loss = abs(pnl_usdt)
            curr_loss = float(self.state.get("daily_loss_usdt", 0.0)) + loss
            self.state["daily_loss_usdt"] = curr_loss
            if balance_usdt > 0:
                self.state["daily_loss_pct"] = round((curr_loss / balance_usdt) * 100.0, 2)
            self._save_state()

    def validate_execution(
        self,
        plan: OrderPlan,
        balance_usdt: float,
        ticker_data: dict[str, float],
        instrument: dict[str, float],
        open_orders: list[dict[str, Any]],
        open_algo_orders: list[dict[str, Any]],
        base_asset_balance: float,
        macro_result: PillarResult,
    ) -> tuple[bool, str]:
        """Tüm deterministik kuralları sırayla doğrular.

        Döndürür:
            (True, "ONAY") veya (False, "[BLOCKED: Gerekçe]")
        """
        risk_cfg = self.config.get("risk", {})

        # 1. Config Doğrulaması
        if plan.size <= 0 or plan.sl_price <= 0 or plan.tp_price <= 0:
            return False, "[BLOCKED: Geçersiz emir planı (Sıfır veya negatif parametre)]"

        if plan.sl_price >= plan.entry_price or plan.tp_price <= plan.entry_price:
            return False, f"[BLOCKED: Mantıksız TP/SL seviyeleri (Giriş={plan.entry_price}, SL={plan.sl_price}, TP={plan.tp_price})]"

        # 2. Bakiye Kontrolü
        min_pos_usdt = to_float(risk_cfg.get("min_position_usdt", 5.0))
        if balance_usdt < min_pos_usdt:
            return False, f"[BLOCKED: Yetersiz USDT bakiyesi ({balance_usdt:.2f} < {min_pos_usdt:.2f} USDT)]"

        # 3. Minimum İşlem Adımı (minSz)
        min_sz = instrument.get("minSz", 0.1)
        if plan.size < min_sz:
            return False, f"[BLOCKED: Hesaplanan emir büyüklüğü ({plan.size}) borsa minimumunun ({min_sz} AVAX) altında]"

        # 4. Spread / Likidite Kontrolü
        max_spread_pct = to_float(risk_cfg.get("max_spread_pct", 0.15))
        bid = ticker_data.get("bid", 0.0)
        ask = ticker_data.get("ask", 0.0)
        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / bid) * 100.0
            if spread_pct > max_spread_pct:
                return False, f"[BLOCKED: Alış-Satış makası aşırı geniş (%{spread_pct:.3f} > %{max_spread_pct:.3f} eşiği)]"

        # 5. Açık Pozisyon ve Bekleyen Emir Kilidi
        if open_orders:
            return False, f"[BLOCKED: Halihazırda {len(open_orders)} adet bekleyen spot emir mevcut]"

        if open_algo_orders:
            return False, f"[BLOCKED: Halihazırda {len(open_algo_orders)} adet bekleyen algo/TP-SL emir mevcut]"

        # AVAX varlığı varsa (değeri min_pos_usdt üzerindeyse)
        current_price = ticker_data.get("last", plan.entry_price)
        base_val_usdt = base_asset_balance * current_price
        if base_val_usdt >= min_pos_usdt:
            return False, f"[BLOCKED: Halihazırda aktif {base_asset_balance:.3f} AVAX pozisyonu ({base_val_usdt:.2f} USDT) mevcut]"

        # 6. Günlük Maksimum İşlem Limiti
        max_daily_trades = int(risk_cfg.get("max_daily_trades", 4))
        trades_today = int(self.state.get("trades_count", 0))
        if trades_today >= max_daily_trades:
            return False, f"[BLOCKED: Günlük maksimum işlem adedine ({trades_today}/{max_daily_trades}) ulaşıldı]"

        # 7. Günlük Kümülatif Zarar Kilidi (Kill-Switch)
        max_daily_loss_pct = to_float(risk_cfg.get("max_daily_loss_pct", 3.0))
        curr_loss_pct = float(self.state.get("daily_loss_pct", 0.0))
        if curr_loss_pct >= max_daily_loss_pct:
            return False, f"[BLOCKED: Günlük kümülatif zarar limiti (%{curr_loss_pct:.2f} >= %{max_daily_loss_pct:.2f}) aşıldı! Kill-Switch devrede.]"

        # 8. Makro Blackout Kontrolü
        if macro_result.status != Status.PASS:
            return False, f"[BLOCKED: {macro_result.reason}]"

        return True, "ONAY (Tüm risk ve guardrail kontrolleri başarıyla geçildi)"
