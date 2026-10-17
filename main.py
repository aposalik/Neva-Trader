"""Nexa-Trader (Sentinel) — Ana Çalıştırma ve Otonom Döngü Yöneticisi.

Kullanım:
  python main.py --once                   # Tek seferlik analiz
  python main.py --loop 30                # Her 30 saniyede bir analiz
  python main.py --simulate-event "US CPI in 8m" # Makro blackout simülasyonu
  python main.py --demo-script            # 3 altın senaryoyu sırayla oynatır (Jüri Demosu)
  python main.py --dry-run                # Emri borsaya iletmeden simüle eder
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

# Windows konsol UTF-8 desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

from data.macro import fetch_macro_status
from data.news import fetch_news_sentiment
from data.okx_client import OKXClient, OKXCLIError
from data.onchain import fetch_onchain_metrics
from execution.executor import OrderExecutor
from models import Decision, OrderPlan, Status
from risk.guardrail import GuardrailManager
from risk.position_sizer import calculate_order_plan
from strategy.signal_engine import SignalEngine
from strategy.technical import evaluate_technical_strategy
from ui import DashboardRenderer
from utils import append_jsonl, fmt_tr, load_json, now_utc, setup_logging

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
MOCK_DATA_PATH = ROOT / "mock_data.json"
EVENTS_PATH = ROOT / "events.json"
STATE_PATH = ROOT / "state.json"
AUDIT_LOG_PATH = ROOT / "decisions.log"
REPORTS_DIR = ROOT / "reports"

log = setup_logging()


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nexa-Trader Autonomous Day Trading Agent")
    parser.add_argument("--once", action="store_true", help="Tek bir döngü çalıştırıp çıkar.")
    parser.add_argument("--loop", type=int, default=0, help="Her N saniyede bir döngüyü tekrarlar (örn: --loop 30).")
    parser.add_argument("--demo-script", action="store_true", help="3 altın jüri senaryosunu sırayla otomatik oynatır.")
    parser.add_argument("--simulate-event", type=str, default=None, help="Sanal makro olay enjekte eder (örn: 'US CPI in 8m').")
    parser.add_argument("--dry-run", action="store_true", help="Emirleri borsaya göndermeden simüle eder.")
    parser.add_argument("--live", action="store_true", help="Canlı hesap modu (Varsayılan: --demo simülasyon modu).")
    return parser.parse_args()


class NexaTraderEngine:
    def __init__(self, is_demo: bool = True, dry_run: bool = False) -> None:
        self.is_demo = is_demo
        self.dry_run = dry_run
        self.config = load_json(CONFIG_PATH)
        self.mock_data = load_json(MOCK_DATA_PATH)
        self.inst_id = self.config.get("instrument", "AVAX-USDT")

        self.okx = OKXClient(
            demo=self.is_demo,
            timeout=int(self.config.get("cli", {}).get("timeout_sec", 25)),
            max_retries=int(self.config.get("cli", {}).get("max_retries", 3)),
        )
        self.signal_engine = SignalEngine(self.config)
        self.guardrail = GuardrailManager(self.config, STATE_PATH)
        self.executor = OrderExecutor(self.okx, self.config)
        self.ui = DashboardRenderer()

    def run_single_cycle(
        self,
        simulate_event_str: str | None = None,
        scenario_overrides: dict[str, Any] | None = None,
        scenario_name: str | None = None,
    ) -> Decision:
        """Observe -> Analyze -> Risk Check -> Decide -> Act döngüsünü işletir."""
        now = now_utc()
        timestamp_str = fmt_tr(now)

        # 1. OBSERVE (Bakiye, Ticker, Enstrüman ve Açık Pozisyonlar)
        try:
            balances = self.okx.balances()
            usdt_bal = balances.get("USDT", {}).get("avail", 0.0)
            avax_bal = balances.get("AVAX", {}).get("avail", 0.0)
        except OKXCLIError as e:
            log.warning("Bakiye okunamadı: %s", e)
            usdt_bal, avax_bal = 5000.0, 0.0

        try:
            ticker = self.okx.ticker(self.inst_id)
            current_price = ticker["last"]
        except OKXCLIError as e:
            log.warning("Ticker okunamadı (%s), varsayılan değer kullanılıyor.", e)
            ticker = {"last": 10.0, "bid": 9.995, "ask": 10.005, "ts": int(now.timestamp() * 1000)}
            current_price = 10.0

        try:
            instrument = self.okx.instrument(self.inst_id)
        except OKXCLIError as e:
            instrument = {"lotSz": 0.000001, "tickSz": 0.001, "minSz": 0.1}

        try:
            open_orders = self.okx.open_orders(self.inst_id)
            open_algo_orders = self.okx.open_algo_orders(self.inst_id)
        except Exception:
            open_orders, open_algo_orders = [], []

        # 2. 4 AYAKLI VERİ TOPLAMA
        # 1. Ayak: Teknik
        tech_cfg = self.config.get("technical", {})
        try:
            c_1h = self.okx.candles(self.inst_id, tech_cfg.get("trend_bar", "1H"), limit=int(tech_cfg.get("trend_limit", 100)))
            c_15m = self.okx.candles(self.inst_id, tech_cfg.get("entry_bar", "15m"), limit=int(tech_cfg.get("entry_limit", 50)))
            tech_res = evaluate_technical_strategy(c_1h, c_15m, self.config)
        except Exception as e:
            tech_res = evaluate_technical_strategy([], [], self.config)

        # 2. Ayak: On-Chain
        onchain_res = fetch_onchain_metrics(self.config, self.mock_data)

        # 3. Ayak: Haber
        news_res = fetch_news_sentiment(self.okx, self.config, self.mock_data)

        # 4. Ayak: Makro
        macro_res = fetch_macro_status(
            okx=self.okx,
            config=self.config,
            mock_data=self.mock_data,
            events_path=EVENTS_PATH,
            simulate_event_str=simulate_event_str,
        )

        # 3. ANALYZE & DECIDE (Sinyal Sentezi)
        action, reasons, pillars = self.signal_engine.evaluate(
            technical_res=tech_res,
            onchain_res=onchain_res,
            news_res=news_res,
            macro_res=macro_res,
            scenario_overrides=scenario_overrides,
        )

        plan: OrderPlan | None = None
        execution_res: dict[str, Any] | None = None

        # 4. RISK CHECK & ACT
        if action == "BUY":
            plan = calculate_order_plan(
                balance_usdt=usdt_bal,
                entry_price=current_price,
                config=self.config,
                instrument=instrument,
            )

            # Guardrail Onayı (Executor'dan önce ZORUNLU)
            allowed, block_reason = self.guardrail.validate_execution(
                plan=plan,
                balance_usdt=usdt_bal,
                ticker_data=ticker,
                instrument=instrument,
                open_orders=open_orders,
                open_algo_orders=open_algo_orders,
                base_asset_balance=avax_bal,
                macro_result=macro_res,
            )

            if allowed:
                # ACT (Emir Yürütme)
                execution_res = self.executor.execute_plan(plan, dry_run=self.dry_run)
                if execution_res.get("success"):
                    self.guardrail.record_trade_executed(plan.notional_usdt)
            else:
                action = "BLOCKED"
                reasons = [block_reason]

        # Karar Nesnesini Derle
        decision = Decision(
            timestamp=timestamp_str,
            action=action,
            reasons=reasons,
            pillars=pillars,
            market={"price": current_price, "bid": ticker.get("bid"), "ask": ticker.get("ask")},
            plan=plan,
            execution=execution_res,
            scenario=scenario_name,
        )

        # 5. AUDIT TRAIL & UI RENDER
        append_jsonl(AUDIT_LOG_PATH, decision.to_dict())
        try:
            from export_reports import export_decisions
            export_decisions(AUDIT_LOG_PATH, REPORTS_DIR)
        except Exception:
            pass
        mode_str = "CANLI MOD (DİKKAT!)" if not self.is_demo else ("DRY-RUN (SİMÜLE)" if self.dry_run else "DEMO MODU")
        self.ui.render_cycle(decision, usdt_bal, self.inst_id, mode_str)

        return decision

    def run_demo_script(self) -> None:
        """Jüri önünde 3 altın senaryoyu sırayla otomatik oynatır."""
        scenarios = self.mock_data.get("demo_scenarios", [])
        pause_sec = int(self.config.get("demo_script_pause_sec", 6))

        print("\n" + "="*70)
        print("[*] NEXA-TRADER JURI ALTIN DEMO PROTOKOLU BASLATILIYOR (3 SENARYO)")
        print("="*70 + "\n")

        for idx, sc in enumerate(scenarios, 1):
            name = sc.get("name", f"Senaryo {idx}")
            desc = sc.get("description", "")
            overrides = sc.get("overrides")
            sim_ev = sc.get("simulate_event")

            print(f">>> [SENARYO {idx}/3]: {name}")
            print(f">>> Aciklama: {desc}\n")

            self.run_single_cycle(
                simulate_event_str=sim_ev,
                scenario_overrides=overrides,
                scenario_name=name,
            )

            if idx < len(scenarios):
                print(f"--- Sonraki senaryoya geciliyor ({pause_sec} saniye bekleme)... ---\n")
                time.sleep(pause_sec)

        print("\n" + "="*70)
        print("[V] JURI DEMO SENARYOLARI EKSIKSIZ TAMAMLANDI.")
        print("="*70 + "\n")


def main() -> None:
    load_dotenv()
    args = parse_cli_args()

    is_demo = not args.live
    dry_run = args.dry_run

    engine = NexaTraderEngine(is_demo=is_demo, dry_run=dry_run)

    if args.demo_script:
        engine.run_demo_script()
        return

    if args.once:
        engine.run_single_cycle(simulate_event_str=args.simulate_event)
        return

    # Döngü modu
    loop_interval = max(int(args.loop or engine.config.get("loop_min_interval_sec", 30)), 15)
    print(f"\n[*] Nexa-Trader otonom dongusu baslatildi (Periyot: {loop_interval}s). Cikis: Ctrl+C.\n")

    try:
        while True:
            engine.run_single_cycle(simulate_event_str=args.simulate_event)
            time.sleep(loop_interval)
    except KeyboardInterrupt:
        print("\n\n[CIKIS] Nexa-Trader durduruldu. Guvenli durum kaydedildi.")
        sys.exit(0)


if __name__ == "__main__":
    main()
