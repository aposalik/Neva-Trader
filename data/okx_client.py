"""Read-only OKX Agent Trade Kit CLI adapter.

No order-placement capability lives in this module. The accepted CLI syntax is kept
in one place so workshop validation can update it without touching strategy code.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OkxCliError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketSnapshot:
    instrument: str
    price: float
    balance_usdt: float | None
    source: str
    is_live: bool


class OkxClient:
    def __init__(self, binary: str = "okx", demo: bool = True, timeout_seconds: int = 12):
        self.binary = binary
        self.demo = demo
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return shutil.which(self.binary) is not None or (Path("node_modules/.bin") / self.binary).exists()

    @property
    def command_prefix(self) -> list[str]:
        if shutil.which(self.binary):
            return [self.binary]
        if (Path("node_modules/.bin") / self.binary).exists():
            return ["npx", "--no-install", self.binary]
        raise OkxCliError("OKX CLI bulunamadı.")

    def _run_json(self, *args: str) -> Any:
        command = [*self.command_prefix, *args, "--json"]
        if self.demo:
            command.append("--demo")
        result = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds)
        if result.returncode != 0:
            raise OkxCliError(result.stderr.strip() or "OKX CLI komutu başarısız.")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise OkxCliError("OKX CLI JSON çıktısı beklenen formatta değil.") from error

    def ticker(self, instrument: str = "AVAX-USDT") -> Any:
        # Workshop field guide: okx market ticker AVAX-USDT --demo --json
        return self._run_json("market", "ticker", instrument)

    def candles(self, instrument: str = "AVAX-USDT", bar: str = "1H", limit: int = 50) -> Any:
        return self._run_json("market", "candles", instrument, "--bar", bar, "--limit", str(limit))

    def balance(self) -> Any:
        return self._run_json("account", "balance")
