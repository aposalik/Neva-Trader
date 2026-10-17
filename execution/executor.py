"""OKX Spot Emir Yürütme ve TP/SL Doğrulama Katmanı.

Emir gönderme protokolü:
  1. okx spot place --instId AVAX-USDT --side buy --ordType market --sz <size>
     --tdMode cash --tgtCcy base_ccy --tpTriggerPx <tp> --tpOrdPx=-1
     --slTriggerPx <sl> --slOrdPx=-1 --clOrdId <id>
  2. Dönen yanıt ayrıştırılır (sCode, ordId).
  3. Dolum durumu doğrulanır.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from data.okx_client import OKXClient, OKXCLIError
from execution.notary import AvalancheNotary
from models import OrderPlan

log = logging.getLogger("nexa.executor")


class OrderExecutor:
    def __init__(self, okx: OKXClient, config: dict[str, Any]) -> None:
        self.okx = okx
        self.config = config
        self.notary = AvalancheNotary()

    def execute_plan(
        self,
        plan: OrderPlan,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Onaylanmış OrderPlan'ı OKX borsa motoruna iletir ve Avalanche'a mühürler."""
        cl_ord_id = f"NX{int(time.time())}"
        cli_args = self.okx.spot_buy_with_tpsl_args(
            inst_id=plan.inst_id,
            size=plan.size,
            tp_px=plan.tp_price,
            sl_px=plan.sl_price,
            cl_ord_id=cl_ord_id,
        )
        command_preview = self.okx.preview(cli_args)

        # Avalanche Fuji Testnet Noter Mühürü
        notary_proof = self.notary.notarize_decision(
            action="BUY",
            inst_id=plan.inst_id,
            plan=plan,
            reasons=["4 Ayak Oybirliği ile Alım"],
            timestamp_str=str(time.time()),
        )

        if dry_run:
            log.info("[DRY RUN] Emir simüle edildi: %s", command_preview)
            return {
                "success": True,
                "status": "SIMULATED_FILLED",
                "ord_id": f"SIM_ORD_{int(time.time())}",
                "cl_ord_id": cl_ord_id,
                "command": command_preview,
                "fill_px": plan.entry_price,
                "fill_sz": plan.size,
                "attached_tpsl": {"tp": plan.tp_price, "sl": plan.sl_price},
                "notary": notary_proof,
            }

        log.info("OKX Borsasına Emir İletiliyor: %s", command_preview)

        try:
            raw_res = self.okx.submit(cli_args)
            return self._parse_execution_response(raw_res, plan, cl_ord_id, command_preview, notary_proof)
        except OKXCLIError as e:
            log.error("Emir gönderimi başarısız: %s", e)
            return {
                "success": False,
                "status": "CLI_ERROR",
                "error": str(e),
                "command": command_preview,
                "notary": notary_proof,
            }

    def _parse_execution_response(
        self,
        raw_res: Any,
        plan: OrderPlan,
        cl_ord_id: str,
        command_preview: str,
        notary_proof: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Borsa yanıtını inceler."""
        # OKX formatı: [{'clOrdId': '...', 'ordId': '...', 'sCode': '0', 'sMsg': ''}]
        item: dict[str, Any] = {}
        if isinstance(raw_res, list) and raw_res and isinstance(raw_res[0], dict):
            item = raw_res[0]
        elif isinstance(raw_res, dict):
            inner = raw_res.get("data")
            if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                item = inner[0]
            else:
                item = raw_res

        s_code = str(item.get("sCode", item.get("code", "-1")))
        ord_id = str(item.get("ordId", ""))
        s_msg = str(item.get("sMsg", item.get("msg", "")))

        if s_code == "0" and ord_id:
            # 1.5 saniye bekle ve dolumu kontrol et
            time.sleep(1.5)
            fill_info = self._check_fill(plan.inst_id, ord_id)

            return {
                "success": True,
                "status": fill_info.get("state", "PLACED_ATTACHED_TPSL"),
                "ord_id": ord_id,
                "cl_ord_id": cl_ord_id,
                "command": command_preview,
                "fill_px": fill_info.get("fillPx", plan.entry_price),
                "fill_sz": fill_info.get("fillSz", plan.size),
                "attached_tpsl": {"tp": plan.tp_price, "sl": plan.sl_price},
                "raw_response": item,
                "notary": notary_proof,
            }

        return {
            "success": False,
            "status": "REJECTED_BY_EXCHANGE",
            "error": f"sCode={s_code}, sMsg={s_msg}",
            "command": command_preview,
            "raw_response": item,
            "notary": notary_proof,
        }

    def _check_fill(self, inst_id: str, ord_id: str) -> dict[str, Any]:
        """Emrin dolum durumunu ve gerçekleşen ortalama fiyatı sorgular."""
        try:
            details = self.okx.order_details(inst_id, ord_id)
            state = details.get("state", "unknown")
            avg_px = float(details.get("avgPx") or 0.0)
            acc_fill_sz = float(details.get("accFillSz") or 0.0)
            return {
                "state": state,
                "fillPx": avg_px if avg_px > 0 else None,
                "fillSz": acc_fill_sz if acc_fill_sz > 0 else None,
            }
        except Exception as e:
            log.warning("Emir detayları okunamadı: %s", e)
            return {"state": "SUBMITTED_CONFIRMED"}


class OKXExecutor:
    """Demo-only compatibility wrapper for the standalone test_flow script."""

    def __init__(self, is_demo: bool = True) -> None:
        if not is_demo:
            raise ValueError("OKXExecutor yalnızca demo modunda kullanılabilir.")
        self.okx = OKXClient(demo=True)

    def place_spot_buy(
        self,
        inst_id: str,
        size: float,
        tp_trigger: float,
        sl_trigger: float,
    ) -> dict[str, Any]:
        """Place a demo buy where size is the quote-currency amount in USDT."""
        ticker = self.okx.ticker(inst_id)
        entry_price = ticker["last"]
        if size <= 0 or entry_price <= 0 or not sl_trigger < entry_price < tp_trigger:
            raise ValueError("Emir miktarı veya TP/SL fiyatları geçersiz.")

        base_size = size / entry_price
        risk_per_unit = entry_price - sl_trigger
        reward_per_unit = tp_trigger - entry_price
        plan = OrderPlan(
            inst_id=inst_id,
            side="buy",
            size=base_size,
            entry_price=entry_price,
            sl_price=sl_trigger,
            tp_price=tp_trigger,
            stop_loss_pct=risk_per_unit / entry_price * 100,
            take_profit_pct=reward_per_unit / entry_price * 100,
            risk_reward_ratio=reward_per_unit / risk_per_unit,
            notional_usdt=size,
            risk_usdt=base_size * risk_per_unit,
            risk_pct_of_balance=0.0,
            net_rr_after_fees=reward_per_unit / risk_per_unit,
        )
        return OrderExecutor(self.okx, {"instrument": inst_id}).execute_plan(plan)
