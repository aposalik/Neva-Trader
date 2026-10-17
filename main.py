"""Nexa-Trader (Sentinel) — Ana Çalıştırma ve Otonom Döngü Yöneticisi.

Kullanım:
  python main.py --once                   # Tek seferlik analiz
  python main.py --loop 30                # Her 30 saniyede bir analiz
  python main.py --simulate-event "US CPI in 8m" # Makro blackout simülasyonu
  python main.py --demo-script            # 3 altın senaryoyu sırayla oynatır (Jüri Demosu)
  python main.py --dry-run                # Emri borsaya iletmeden simüle eder

Kullanıcı Risk ve Kural Belirleme (CMD):
  python main.py --capital-pct 10.0 --sl-pct 1.5 --tp-pct 3.0
  python main.py --set-rules              # Terminalden interaktif kural belirleme
"""
from __future__ import annotations

import argparse
import json
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
from strategy.signal_engine import SignalEngine, generate_agentic_reasoning
from strategy.technical import evaluate_technical_strategy
from ui import DashboardRenderer
from utils import append_jsonl, fmt_tr, load_json, now_utc, setup_logging

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
MOCK_DATA_PATH = ROOT / "mock_data.json"
EVENTS_PATH = ROOT / "events.json"
CALENDAR_DATA_PATH = ROOT / "takvim_verileri.json"
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

    # Kullanıcı Kural & Risk Parametreleri (CMD üzerinden doğrudan giriş)
    parser.add_argument("--capital-pct", "--position-size-pct", dest="capital_pct", type=float, default=None,
                        help="İşlem başına kullanılacak bakiye yüzdesi (örn: --capital-pct 5.0).")
    parser.add_argument("--sl-pct", "--stop-loss-pct", dest="sl_pct", type=float, default=None,
                        help="Stop-Loss zarar durdur yüzdesi (örn: --sl-pct 1.0).")
    parser.add_argument("--tp-pct", "--take-profit-pct", dest="tp_pct", type=float, default=None,
                        help="Take-Profit kâr al yüzdesi (örn: --tp-pct 2.0).")
    parser.add_argument("--max-daily-loss-pct", "--kill-switch-pct", dest="max_daily_loss_pct", type=float, default=None,
                        help="Günlük maksimum kümülatif zarar tavanı yüzdesi (örn: --max-daily-loss-pct 3.0).")
    parser.add_argument("--max-daily-trades", dest="max_daily_trades", type=int, default=None,
                        help="Günde açılabilecek maksimum işlem adedi (örn: --max-daily-trades 4).")
    parser.add_argument("--set-rules", "--interactive-rules", action="store_true",
                        help="Ajan başlamadan önce terminalden interaktif kural ve risk parametrelerini sorar.")
    parser.add_argument("--save-rules", action="store_true",
                        help="Girilen kuralları config.json dosyasına kalıcı olarak kaydeder.")
    return parser.parse_args()


def prompt_user_rules(current_risk: dict[str, Any]) -> dict[str, Any]:
    """Terminalden kullanıcıya interaktif olarak risk ve kural parametrelerini sorar."""
    print("\n" + "=" * 65)
    print("[*] NEXA-TRADER: KULLANICI RISK VE ISLEM KURAL AYARLARI")
    print("    [Degeri degistirmeden gecmek icin Enter tusuna basabilirsiniz]")
    print("=" * 65)

    def _ask_float(prompt_text: str, default_val: float) -> float:
        val_str = input(f"-> {prompt_text} [Mevcut: %{default_val:.1f}]: ").strip()
        if not val_str:
            return default_val
        try:
            val = float(val_str)
            if val <= 0:
                print(f"    [!] Deger 0'dan buyuk olmali, varsayilan (%{default_val:.1f}) kullaniliyor.")
                return default_val
            return val
        except ValueError:
            print(f"    [!] Gecersiz sayi, varsayilan (%{default_val:.1f}) kullaniliyor.")
            return default_val

    def _ask_int(prompt_text: str, default_val: int) -> int:
        val_str = input(f"-> {prompt_text} [Mevcut: {default_val}]: ").strip()
        if not val_str:
            return default_val
        try:
            val = int(val_str)
            if val <= 0:
                print(f"    [!] Deger 0'dan buyuk olmali, varsayilan ({default_val}) kullaniliyor.")
                return default_val
            return val
        except ValueError:
            print(f"    [!] Gecersiz tamsayi, varsayilan ({default_val}) kullaniliyor.")
            return default_val

    cur_pos = float(current_risk.get("position_size_pct", 5.0))
    cur_sl = float(current_risk.get("stop_loss_pct", 1.0))
    cur_tp = float(current_risk.get("take_profit_pct", 2.0))
    cur_max_trades = int(current_risk.get("max_daily_trades", 4))
    cur_loss = float(current_risk.get("max_daily_loss_pct", 3.0))

    new_pos = _ask_float("Bakiye Kullanim Yuzdesi (%)", cur_pos)
    new_sl = _ask_float("Stop-Loss (Zarar Durdur) Yuzdesi (%)", cur_sl)
    new_tp = _ask_float("Take-Profit (Kar Al) Yuzdesi (%)", cur_tp)
    new_max_trades = _ask_int("Gunluk Maksimum Islem Sayisi", cur_max_trades)
    new_loss = _ask_float("Gunluk Kill-Switch Zarar Tavani (%)", cur_loss)

    updated = {
        "position_size_pct": new_pos,
        "stop_loss_pct": new_sl,
        "take_profit_pct": new_tp,
        "risk_reward_ratio": round(new_tp / (new_sl + 1e-9), 2),
        "max_daily_trades": new_max_trades,
        "max_daily_loss_pct": new_loss,
    }

    print("-" * 65)
    print(f"[OK] Kural Motoru Guncellendi: Bakiye: %{new_pos:.1f} | SL: -%{new_sl:.1f} | TP: +%{new_tp:.1f} (1:{updated['risk_reward_ratio']:.2f} R/R)")
    print(f"     Gunluk Max Islem: {new_max_trades} | Kill-Switch: %{new_loss:.1f}")
    print("=" * 65 + "\n")
    return updated


class NexaTraderEngine:
    def __init__(
        self,
        is_demo: bool = True,
        dry_run: bool = False,
        config_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.is_demo = is_demo
        self.dry_run = dry_run
        self.config = load_json(CONFIG_PATH)

        if config_overrides:
            for k, v in config_overrides.items():
                if isinstance(v, dict) and k in self.config and isinstance(self.config[k], dict):
                    self.config[k].update(v)
                else:
                    self.config[k] = v

        self.mock_data = load_json(MOCK_DATA_PATH)
        self.inst_id = self.config.get("instrument", "AVAX-USDT")

        self.okx = OKXClient(
            is_demo=self.is_demo,
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
            calendar_path=CALENDAR_DATA_PATH,
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

        agentic_trace = generate_agentic_reasoning(tech_res, onchain_res, news_res, macro_res, action)
        reasons.insert(0, agentic_trace)

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
        mode_str = "CANLI MOD (DIKKAT!)" if not self.is_demo else ("DRY-RUN (SIMULE)" if self.dry_run else "DEMO MODU")
        self.ui.render_cycle(
            decision,
            usdt_bal,
            self.inst_id,
            mode_str,
            risk_rules=self.config.get("risk", {}),
        )

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

    # Demo Script ile Canlı Hesap Çakışma Koruması
    if args.demo_script and args.live:
        print("\n[HATA] --demo-script ve --dry-run modlari gercek fon riski olusmamasi icin")
        print("       --live (Canli Borsa) bayragiyla birlikte CALISTIRILAMAZ!")
        print("       Lutfen guvenli test icin sadece 'python main.py --demo-script' calistirin.\n")
        sys.exit(1)

    is_demo = not args.live
    dry_run = args.dry_run

    base_config = load_json(CONFIG_PATH)
    risk_overrides: dict[str, Any] = {}

    # 1. İnteraktif Kural Belirleme (--set-rules)
    if args.set_rules:
        risk_overrides = prompt_user_rules(base_config.get("risk", {}))

    # 2. Doğrudan CLI Bayrakları
    if args.capital_pct is not None:
        risk_overrides["position_size_pct"] = float(args.capital_pct)
    if args.sl_pct is not None:
        risk_overrides["stop_loss_pct"] = float(args.sl_pct)
    if args.tp_pct is not None:
        risk_overrides["take_profit_pct"] = float(args.tp_pct)
        sl = risk_overrides.get("stop_loss_pct", base_config.get("risk", {}).get("stop_loss_pct", 1.0))
        risk_overrides["risk_reward_ratio"] = round(float(args.tp_pct) / (float(sl) + 1e-9), 2)
    if args.max_daily_loss_pct is not None:
        risk_overrides["max_daily_loss_pct"] = float(args.max_daily_loss_pct)
    if args.max_daily_trades is not None:
        risk_overrides["max_daily_trades"] = int(args.max_daily_trades)

    config_overrides = {"risk": risk_overrides} if risk_overrides else None

    # Kalıcı Kaydetme (--save-rules)
    if args.save_rules and risk_overrides:
        base_config.setdefault("risk", {}).update(risk_overrides)
        CONFIG_PATH.write_text(json.dumps(base_config, indent=2), encoding="utf-8")
        print("[*] Girilen risk kurallari config.json dosyasina kalici olarak kaydedildi.\n")

    engine = NexaTraderEngine(is_demo=is_demo, dry_run=dry_run, config_overrides=config_overrides)

    if risk_overrides and not args.set_rules:
        r = engine.config.get("risk", {})
        sl_val = r.get("stop_loss_pct", 1.0)
        tp_val = r.get("take_profit_pct", sl_val * r.get("risk_reward_ratio", 2.0))
        print(f"[*] Ozel Kullanici Kurallari Devrede: Bakiye: %{r.get('position_size_pct')}% | SL: -%{sl_val}% | TP: +%{tp_val}% (1:{r.get('risk_reward_ratio', 2.0):.2f} R/R)\n")

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
