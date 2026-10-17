from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from data.macro import blackout_event
from data.news import get_news_signal
from data.onchain import get_onchain_signal
from execution.executor import Executor
from risk.guardrail import evaluate
from risk.position_sizer import size_position
from strategy.signal_engine import propose
from strategy.technical import analyze

ROOT = Path(__file__).parent
console = Console()


def load_json(name: str):
    return json.loads((ROOT / name).read_text())


def run_cycle(*, scenario: str = "normal", execute_demo: bool = False) -> dict:
    config, mock = load_json("config.json"), deepcopy(load_json("mock_data.json"))
    technical = analyze(mock["candles"])
    negative_news = scenario == "negative-news"
    news, onchain = get_news_signal(mock, force_negative=negative_news), get_onchain_signal(mock)
    proposal = propose(technical, news, onchain)

    macro_event = None
    if scenario == "macro-blackout":
        macro_event = {"name": "US CPI", "minutes_until": 8.0, "source": "demo-script"}
    else:
        macro_event = blackout_event(ROOT / "events.json", datetime.now().astimezone(), config["macro_blackout_minutes"])

    position = size_position(balance_usdt=mock["market"]["balance_usdt"], price=technical.last_price,
                             risk_pct=config["risk_per_trade_pct"], max_notional_usd=config["max_notional_usd"],
                             stop_loss_pct=config["stop_loss_pct"], risk_reward_ratio=config["risk_reward_ratio"])
    decision = evaluate(proposal=proposal, position=position, spread_pct=mock["market"]["spread_pct"],
                        max_spread_pct=config["max_spread_pct"], macro_event=macro_event, open_position=False,
                        single_position_only=config["single_position_only"])
    receipt = Executor(execute_demo=execute_demo, audit_path=ROOT / "decisions.log").execute(
        decision=decision, position=position, instrument=config["instrument"])
    result = {"technical": technical, "news": news, "onchain": onchain, "proposal": proposal,
              "macro_event": macro_event, "position": position, "decision": decision, "receipt": receipt}
    render(result)
    return result


def render(result: dict) -> None:
    technical, news, onchain = result["technical"], result["news"], result["onchain"]
    table = Table(title="NEXA-TRADER / SENTINEL", expand=True)
    table.add_column("Signal")
    table.add_column("Status")
    table.add_row("Technical", f"{technical.trend} | volume={'PASS' if technical.volume_confirmed else 'FAIL'} | ${technical.last_price:.2f}")
    table.add_row("News", f"{news.sentiment:+.2f} | {news.source} | {'LIVE' if news.is_live else 'FALLBACK: MOCK'}")
    table.add_row("On-chain", f"{onchain.signal} ({onchain.score:+.2f}) | {'LIVE' if onchain.is_live else 'FALLBACK: MOCK'}")
    macro = result["macro_event"]
    table.add_row("Macro", "CLEAR" if not macro else f"BLACKOUT: {macro['name']} in {macro['minutes_until']}m")
    console.print(table)
    decision, plan = result["decision"], result["position"]
    body = f"[bold]{decision.status}[/bold]\n" + "\n".join(decision.reasons)
    body += f"\n\nnotional=${plan.notional_usd:.2f} | AVAX={plan.size_avax} | SL={plan.stop_loss_price} | TP={plan.take_profit_price}"
    console.print(Panel(body, title="Deterministic Guardrail", border_style="green" if decision.status == "EXECUTE" else "yellow"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexa-Trader Sentinel")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", type=int, metavar="SECONDS")
    mode.add_argument("--simulate-event", metavar="TEXT")
    mode.add_argument("--demo-script", action="store_true")
    parser.add_argument("--execute-demo", action="store_true", help="Explicitly submit an OKX DEMO order if guardrails pass.")
    args = parser.parse_args()

    if args.demo_script:
        for label, scenario in (("1. Perfect BUY", "normal"), ("2. News veto", "negative-news"), ("3. Macro blackout", "macro-blackout")):
            console.rule(label)
            run_cycle(scenario=scenario, execute_demo=args.execute_demo and scenario == "normal")
        return
    if args.simulate_event:
        console.print(f"[yellow]Simulated event:[/] {args.simulate_event}")
        run_cycle(scenario="macro-blackout" if "CPI" in args.simulate_event.upper() else "normal", execute_demo=args.execute_demo)
        return
    if args.once:
        run_cycle(execute_demo=args.execute_demo)
        return
    while True:
        run_cycle(execute_demo=args.execute_demo)
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
