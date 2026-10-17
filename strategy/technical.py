"""Deterministic technical indicators; no LLM input is trusted for these values."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class TechnicalSignal:
    trend: str
    volume_confirmed: bool
    bullish_pattern: bool
    last_price: float
    ema_fast: float
    ema_slow: float


def analyze(candles: list[dict]) -> TechnicalSignal:
    if len(candles) < 3:
        raise ValueError("Teknik analiz için en az üç mum gerekir.")
    frame = pd.DataFrame(candles).copy()
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column])
    frame["ema20"] = frame["close"].ewm(span=20, adjust=False).mean()
    frame["ema50"] = frame["close"].ewm(span=50, adjust=False).mean()
    latest, previous = frame.iloc[-1], frame.iloc[-2]
    body_low, body_high = sorted((previous.open, previous.close))
    engulfing = (previous.close < previous.open and latest.close > latest.open
                 and latest.open <= body_low and latest.close >= body_high)
    hammer = ((latest.high - latest.low) > 0 and (min(latest.open, latest.close) - latest.low)
              >= 2 * abs(latest.close - latest.open))
    volume_confirmed = latest.volume >= frame["volume"].tail(min(len(frame), 20)).mean()
    return TechnicalSignal(
        trend="bullish" if latest.ema20 > latest.ema50 else "bearish",
        volume_confirmed=bool(volume_confirmed),
        bullish_pattern=bool(engulfing or hammer),
        last_price=float(latest.close),
        ema_fast=float(latest.ema20),
        ema_slow=float(latest.ema50),
    )
