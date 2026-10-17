"""OKX Agent Trade Kit (okx CLI) için ince Python sarmalayıcı.

Komut, bayrak ve JSON şemaları 17.10.2026'da okx-trade-cli v1.4.8 üzerinde
`--help` çıktıları ve canlı `--json` çağrılarıyla doğrulanmıştır.
DİKKAT: 'news' modülü public veridir ve CLI --demo bayrağıyla çağrıldığında
hata verir; bu nedenle haber/takvim komutlarında --demo/--live kullanılmaz.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import time
from typing import Any

from utils import fmt_num, to_float

log = logging.getLogger("nexa.okx")


class OKXCLIError(RuntimeError):
    """okx CLI çağrısı başarısız (exit code, timeout, bozuk JSON)."""


def _first(data: Any) -> dict[str, Any]:
    """CLI yanıtındaki ilk kaydı döndürür."""
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return inner[0]
        return data
    return {}


class OKXClient:
    def __init__(self, demo: bool = True, timeout: int = 25, max_retries: int = 3) -> None:
        exe = (shutil.which("okx.cmd") if sys.platform == "win32" else None) or shutil.which("okx")
        if exe is None:
            raise OKXCLIError("`okx` CLI bulunamadı. Kurulum: npm install -g @okx_ai/okx-trade-cli")
        self.exe = exe
        self.demo = demo
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.trade_flags = ["--demo" if demo else "--live", "--json"]

    # ------------------------------------------------------------------ çekirdek
    def preview(self, args: list[str]) -> str:
        flags = ["--json"] if args and args[0] == "news" else self.trade_flags
        return "okx " + " ".join(flags + args)

    def _run(self, args: list[str], retry: bool = True) -> Any:
        """CLI'ı çalıştırır, JSON döndürür.

        ÖNEMLİ: 'news' modülü --demo bayrağını kabul etmez, bu nedenle sadece --json ile çağrılır.
        """
        flags = ["--json"] if args and args[0] == "news" else self.trade_flags
        attempts = self.max_retries if retry else 1
        last: Exception | None = None

        for i in range(attempts):
            try:
                proc = subprocess.run(
                    [self.exe, *flags, *args],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=self.timeout,
                )
                if proc.returncode != 0:
                    msg = (proc.stderr or proc.stdout or "").strip()[:400]
                    raise OKXCLIError(f"exit {proc.returncode}: {msg}")
                out = proc.stdout.strip()
                if not out:
                    raise OKXCLIError("boş çıktı")
                return json.loads(out)
            except subprocess.TimeoutExpired:
                last = OKXCLIError(f"timeout ({self.timeout}s)")
            except json.JSONDecodeError as e:
                last = OKXCLIError(f"bozuk JSON: {e}")
            except OKXCLIError as e:
                last = e

            log.warning("okx %s | deneme %d/%d başarısız: %s", " ".join(args[:3]), i + 1, attempts, last)
            if i < attempts - 1:
                time.sleep(2 ** i)

        raise OKXCLIError(f"okx {' '.join(args[:3])}: {last}")

    # ------------------------------------------------------------------ piyasa
    def ticker(self, inst_id: str) -> dict[str, float]:
        row = _first(self._run(["market", "ticker", inst_id]))
        if "last" not in row:
            raise OKXCLIError("ticker şeması beklenmedik")
        return {"last": to_float(row["last"]), "bid": to_float(row.get("bidPx")),
                "ask": to_float(row.get("askPx")), "ts": int(to_float(row.get("ts")))}

    def candles(self, inst_id: str, bar: str, limit: int) -> list[list[str]]:
        data = self._run(["market", "candles", inst_id, "--bar", bar, "--limit", str(limit)])
        if not isinstance(data, list):
            raise OKXCLIError("candles şeması beklenmedik")
        return data

    def instrument(self, inst_id: str) -> dict[str, float]:
        row = _first(self._run(["market", "instruments", "--instType", "SPOT", "--instId", inst_id]))
        if "lotSz" not in row:
            raise OKXCLIError("instrument şeması beklenmedik")
        return {"lotSz": to_float(row["lotSz"]), "tickSz": to_float(row["tickSz"]),
                "minSz": to_float(row["minSz"])}

    # ------------------------------------------------------------------ hesap
    def balances(self) -> dict[str, dict[str, float]]:
        root = _first(self._run(["account", "balance"]))
        out: dict[str, dict[str, float]] = {}
        for d in root.get("details", []) or []:
            ccy = d.get("ccy")
            if ccy:
                out[ccy] = {"avail": to_float(d.get("availBal")),
                            "total": to_float(d.get("cashBal") or d.get("eq"))}
        return out

    # ------------------------------------------------------------------ haber / makro (Public)
    def coin_sentiment(self, coins: list[str], period: str = "24h") -> list[dict[str, Any]]:
        root = _first(self._run(["news", "coin-sentiment", "--coins", ",".join(coins), "--period", period]))
        return root.get("details", []) or []

    def news_latest(self, coins: list[str] | None = None, limit: int = 5) -> list[dict[str, Any]]:
        args = ["news", "latest", "--limit", str(limit)]
        if coins:
            args += ["--coins", ",".join(coins)]
        data = self._run(args)
        return (data.get("details") or []) if isinstance(data, dict) else []

    def economic_calendar(self, region: str | None = None, importance: int | None = None, newer_than_ms: int = 0,
                      older_than_ms: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        cmd = ["news", "economic-calendar", "--limit", str(limit)]
        if region:
            cmd.extend(["--region", str(region)])
        if importance:
            cmd.extend(["--importance", str(importance)])
        data = self._run(cmd)
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------ emir
    @staticmethod
    def spot_buy_with_tpsl_args(inst_id: str, size: float, tp_px: float, sl_px: float, cl_ord_id: str) -> list[str]:
        return ["spot", "place", "--instId", inst_id, "--side", "buy", "--ordType", "market",
                "--tdMode", "cash", "--tgtCcy", "base_ccy", "--sz", fmt_num(size), "--clOrdId", cl_ord_id,
                "--tpTriggerPx", fmt_num(tp_px), "--tpOrdPx=-1",
                "--slTriggerPx", fmt_num(sl_px), "--slOrdPx=-1"]

    @staticmethod
    def spot_oco_sell_args(inst_id: str, size: float, tp_px: float, sl_px: float) -> list[str]:
        return ["spot", "algo", "place", "--instId", inst_id, "--side", "sell", "--sz", fmt_num(size),
                "--ordType", "oco", "--tdMode", "cash",
                "--tpTriggerPx", fmt_num(tp_px), "--tpOrdPx=-1",
                "--slTriggerPx", fmt_num(sl_px), "--slOrdPx=-1"]

    @staticmethod
    def spot_market_sell_args(inst_id: str, size: float) -> list[str]:
        return ["spot", "place", "--instId", inst_id, "--side", "sell", "--ordType", "market",
                "--tdMode", "cash", "--tgtCcy", "base_ccy", "--sz", fmt_num(size)]

    def submit(self, args: list[str]) -> Any:
        return self._run(args, retry=False)

    def order_details(self, inst_id: str, ord_id: str) -> dict[str, Any]:
        return _first(self._run(["spot", "get", "--instId", inst_id, "--ordId", ord_id]))

    def open_orders(self, inst_id: str) -> list[dict[str, Any]]:
        data = self._run(["spot", "orders", "--instId", inst_id])
        return data if isinstance(data, list) else []

    def open_algo_orders(self, inst_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for ord_type in ("oco", "conditional"):
            data = self._run(["spot", "algo", "orders", "--instId", inst_id, "--ordType", ord_type])
            if isinstance(data, list):
                out.extend(d for d in data if isinstance(d, dict))
        return out
