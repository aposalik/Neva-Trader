"""Terminal Görselleştirme ve Rich Dashboard Katmanı.

Jüri demosunda 4 sinyal ayağını, durum rozetlerini (PASS/FAIL/NEUTRAL/FALLBACK)
ve nihai karar/emir detaylarını canlı renkli paneller halinde gösterir.
Windows konsol kod sayfası (cp1254) ve 80 sütun genişlik uyumludur.
"""
from __future__ import annotations

from typing import Any

from models import Decision, OrderPlan, PillarResult, Source, Status

try:
    from rich.box import ROUNDED
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class DashboardRenderer:
    def __init__(self) -> None:
        self.console = Console() if HAS_RICH else None

    def render_cycle(
        self,
        decision: Decision,
        balance_usdt: float,
        pair: str,
        mode_str: str,
    ) -> None:
        """Bir analiz döngüsünün tüm panelini terminale çizer."""
        if not HAS_RICH or self.console is None:
            self._render_plain(decision, balance_usdt, pair, mode_str)
            return

        # 1. Başlık Paneli (ASCII-safe semboller)
        title_text = Text()
        title_text.append("[*] NEXA-TRADER (SENTINEL) ", style="bold cyan")
        title_text.append(f"| {pair} ", style="bold yellow")
        title_text.append(f"| Bakiye: ${balance_usdt:,.2f} USDT ", style="bold green")
        title_text.append(f"| Mod: {mode_str} ", style="magenta")
        title_text.append(f"| {decision.timestamp}", style="dim")

        if decision.scenario:
            title_text.append(f"\n[DEMO SENARYOSU]: {decision.scenario}", style="bold white on blue")

        self.console.print(Panel(title_text, box=ROUNDED, border_style="cyan"))

        # 2. 4 Sinyal Ayağı Tablosu (Dar ekranlar için optimize sütunlar)
        table = Table(box=ROUNDED, expand=True, border_style="dim")
        table.add_column("Sinyal Ayagi", style="bold white", width=18, no_wrap=False)
        table.add_column("Durum", width=11, justify="center")
        table.add_column("Kaynak", width=16, justify="center")
        table.add_column("Gerekce / Detay", style="dim", no_wrap=False)

        for p in decision.pillars:
            st_text = self._status_badge(p.status)
            src_text = self._source_badge(p.source)
            detail = Text(p.reason, overflow="fold")
            table.add_row(p.name, st_text, src_text, detail)

        self.console.print(Panel(table, title="[bold]4 Ayakli Analiz Matrisi[/bold]", border_style="blue", box=ROUNDED))

        # 3. Nihai Karar ve Yürütme Paneli
        if decision.action == "BUY":
            self._render_buy_panel(decision)
        elif decision.action == "BLOCKED":
            self._render_blocked_panel(decision)
        else:
            self._render_no_trade_panel(decision)

        self.console.print()

    def _status_badge(self, status: Status) -> Text:
        if status == Status.PASS:
            return Text("[PASS]", style="bold green")
        elif status == Status.FAIL:
            return Text("[FAIL]", style="bold red")
        return Text("[NEUTRAL]", style="bold yellow")

    def _source_badge(self, source: Source) -> Text:
        if source == Source.LIVE:
            return Text("[CANLI: OKX]", style="bold cyan")
        elif source == Source.FALLBACK:
            return Text("[FALLBACK: MOCK]", style="bold white on dark_red")
        elif source == Source.SIMULATED:
            return Text("[SIMULATED]", style="bold white on purple")
        return Text("[MOCK DATA]", style="yellow")

    def _render_buy_panel(self, decision: Decision) -> None:
        p = decision.plan
        if not p:
            return

        table = Table(box=ROUNDED, expand=True)
        table.add_column("Giris Fiyati", justify="center", style="bold")
        table.add_column("Miktar (AVAX)", justify="center", style="bold green")
        table.add_column("Pozisyon ($)", justify="center")
        table.add_column("Stop-Loss (%1.2)", justify="center", style="bold red")
        table.add_column("Take-Profit (%2.4)", justify="center", style="bold green")
        table.add_column("Maks. Risk ($)", justify="center", style="red")
        table.add_column("Net R/R (Komisyonlu)", justify="center", style="bold cyan")

        table.add_row(
            f"${p.entry_price:.3f}",
            f"{p.size:.2f} AVAX",
            f"${p.notional_usdt:.2f}",
            f"${p.sl_price:.3f} (-%{p.stop_loss_pct:.1f})",
            f"${p.tp_price:.3f} (+%{p.take_profit_pct:.1f})",
            f"${p.risk_usdt:.2f} (%{p.risk_pct_of_balance:.2f})",
            f"1 : {p.net_rr_after_fees:.2f}",
        )

        exec_text = ""
        if decision.execution:
            ex = decision.execution
            if ex.get("success"):
                exec_text = f"\n[bold green][V] EMIR BASARIYLA YURUTULDU:[/] OrdId: {ex.get('ord_id')} | Durum: {ex.get('status')} | Attached TP/SL Kilitlendi."
            else:
                exec_text = f"\n[bold red][X] EMIR BORSA TARAFINDAN REDDEDILDI:[/] {ex.get('error')}"

        panel_content = Text()
        panel_content.append("[BUY] NIHAI KARAR: ALIM EMRI ONAYLANDI\n", style="bold green")
        panel_content.append("Tum 4 ayak onay verdi. Deterministik 1:2 R/R korumasi ile pozisyon aciliyor.\n")

        self.console.print(Panel(
            panel_content,
            title="[bold green]KARAR: BUY[/bold green]",
            border_style="green",
            box=ROUNDED,
        ))
        self.console.print(table)
        if exec_text:
            self.console.print(exec_text)

    def _render_blocked_panel(self, decision: Decision) -> None:
        content = Text()
        content.append("[BLOCKED] NIHAI KARAR: ISLEM GUARDRAIL TARAFINDAN ENGELLENDI\n\n", style="bold red")
        for r in decision.reasons:
            content.append(f"  * {r}\n", style="white")

        self.console.print(Panel(
            content,
            title="[bold red]RISK GUARDRAIL ENGELI[/bold red]",
            border_style="red",
            box=ROUNDED,
        ))

    def _render_no_trade_panel(self, decision: Decision) -> None:
        content = Text()
        content.append("[NO TRADE] NIHAI KARAR: BEKLEMEDE\n\n", style="bold yellow")
        content.append("Giris Kosullari Saglanamadi / Red Sebepleri:\n", style="dim")
        for r in decision.reasons:
            content.append(f"  * {r}\n", style="white")

        self.console.print(Panel(
            content,
            title="[bold yellow]KARAR: BEKLEMEDE (NO TRADE)[/bold yellow]",
            border_style="yellow",
            box=ROUNDED,
        ))

    def _render_plain(self, d: Decision, bal: float, pair: str, mode: str) -> None:
        """Rich yuklu degilse temiz konsol ciktisi."""
        print(f"\n=== NEXA-TRADER | {pair} | Bakiye: ${bal:.2f} | {mode} | {d.timestamp} ===")
        for p in d.pillars:
            print(f"[{p.status.value}] {p.name} ({p.source.value}): {p.reason}")
        print(f"KARAR: {d.action}")
        for r in d.reasons:
            print(f" - {r}")
        if d.plan:
            print(f"PLAN: Giris=${d.plan.entry_price}, Miktar={d.plan.size}, SL=${d.plan.sl_price}, TP=${d.plan.tp_price}")
        if d.execution:
            print(f"YURUTME: {d.execution.get('status')} (ID: {d.execution.get('ord_id')})")
