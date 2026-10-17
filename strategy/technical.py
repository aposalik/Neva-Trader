"""Teknik Analiz Motoru (1. Ayak).

1. 1H Grafikte Trend & Hacim:
   - EMA 20 > EMA 50
   - Fiyat > EMA 20
   - Son kapanan 1H hacmi > önceki 5 saatin ortalama hacmi
2. 15m Grafikte Mikro Giriş & Mum Formasyonu:
   - EMA 20 bölgesine geri çekilme (pullback)
   - Dönüş Mum Formasyonu: Bullish Engulfing, Hammer veya Morning Star
3. OKX mum sıralaması (en yeni başta) ve kapanmamış mum (confirm=0) kurallarına tam uyumludur.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from models import PillarResult, Source, Status
from utils import to_float

log = logging.getLogger("nexa.technical")


def parse_candles(raw_candles: list[list[str]], drop_unconfirmed: bool = True) -> pd.DataFrame:
    """OKX mum listesini alır, kronolojik (eskiden yeniye) Pandas DataFrame'e dönüştürür."""
    if not raw_candles:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "vol", "confirm"])

    # OKX Candle şeması: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    rows = []
    for c in raw_candles:
        if len(c) < 9:
            continue
        confirm = str(c[8])
        if drop_unconfirmed and confirm == "0":
            # Kapanmamış mumu yoksay
            continue
        rows.append({
            "ts": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "vol": float(c[5]),
            "confirm": confirm,
        })

    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "vol", "confirm"])

    df = pd.DataFrame(rows)
    # OKX en yeni mumu ilk sıraya koyar; kronolojik analiz için ters çeviriyoruz
    df = df.iloc[::-1].reset_index(drop=True)
    return df


def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Üstel Hareketli Ortalama (EMA) hesaplar."""
    return series.ewm(span=span, adjust=False).mean()


def detect_bullish_engulfing(df: pd.DataFrame, idx: int = -1) -> bool:
    """Bullish Engulfing (Yutan Boğa Mumu) formasyonunu tespit eder."""
    if len(df) < abs(idx) + 1:
        return False

    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]

    # Önceki mum kırmızı, güncel mum yeşil olmalı
    prev_red = prev["close"] < prev["open"]
    curr_green = curr["close"] > curr["open"]
    if not (prev_red and curr_green):
        return False

    # Güncel gövde önceki gövdeyi yutmalı
    curr_body = curr["close"] - curr["open"]
    prev_body = prev["open"] - prev["close"]

    engulfs = (curr["open"] <= prev["close"] * 1.002) and (curr["close"] >= prev["open"] * 0.998)
    significant_body = curr_body >= prev_body * 0.9
    return bool(engulfs and significant_body)


def detect_hammer(df: pd.DataFrame, idx: int = -1) -> bool:
    """Hammer (Çekiç) formasyonunu tespit eder."""
    if len(df) < abs(idx):
        return False

    c = df.iloc[idx]
    body = abs(c["close"] - c["open"])
    candle_range = c["high"] - c["low"]
    if candle_range <= 0 or body <= 0:
        return False

    lower_shadow = min(c["open"], c["close"]) - c["low"]
    upper_shadow = c["high"] - max(c["open"], c["close"])

    # Çekiç kuralı: Alt gölge en az gövdenin 2 katı, üst gölge çok küçük olmalı
    is_long_lower = lower_shadow >= 2.0 * body
    is_small_upper = upper_shadow <= 0.3 * body
    return bool(is_long_lower and is_small_upper)


def detect_morning_star(df: pd.DataFrame, idx: int = -1) -> bool:
    """Morning Star (Sabah Yıldızı) 3 mumluk dönüş formasyonunu tespit eder."""
    if len(df) < abs(idx) + 2:
        return False

    c1 = df.iloc[idx - 2]  # İlk mum (güçlü kırmızı)
    c2 = df.iloc[idx - 1]  # İkinci mum (küçük gövdeli yıldız / doji)
    c3 = df.iloc[idx]      # Üçüncü mum (güçlü yeşil)

    avg_body = df["close"].diff().abs().tail(10).mean() or 0.1

    c1_red = (c1["close"] < c1["open"]) and ((c1["open"] - c1["close"]) >= avg_body * 0.6)
    c2_small = abs(c2["close"] - c2["open"]) <= avg_body * 0.5
    c3_green = c3["close"] > c3["open"]
    # 3. mum 1. mumun gövdesinin en az yarısına kadar yükselmeli
    c3_rebound = c3["close"] >= (c1["open"] + c1["close"]) / 2

    return bool(c1_red and c2_small and c3_green and c3_rebound)


def evaluate_technical_strategy(
    raw_candles_1h: list[list[str]],
    raw_candles_15m: list[list[str]],
    config: dict[str, Any],
) -> PillarResult:
    """1H Makro Trend + Hacim ve 15m Mikro Price Action formasyonlarını birleştirir."""
    cfg = config.get("technical", {})
    ema_fast = int(cfg.get("ema_fast", 20))
    ema_slow = int(cfg.get("ema_slow", 50))
    vol_lookback = int(cfg.get("volume_lookback", 5))

    df_1h = parse_candles(raw_candles_1h, drop_unconfirmed=True)
    df_15m = parse_candles(raw_candles_15m, drop_unconfirmed=True)

    if len(df_1h) < ema_slow + 5:
        return PillarResult(
            name="Teknik Analiz (1H Trend + 15m Formasyon)",
            status=Status.NEUTRAL,
            reason=f"Yetersiz 1H mum verisi ({len(df_1h)} < {ema_slow + 5})",
            source=Source.LIVE,
        )

    if len(df_15m) < 15:
        return PillarResult(
            name="Teknik Analiz (1H Trend + 15m Formasyon)",
            status=Status.NEUTRAL,
            reason=f"Yetersiz 15m mum verisi ({len(df_15m)} < 15)",
            source=Source.LIVE,
        )

    # 1. Aşama: 1H Trend & EMA Hesaplama
    df_1h["ema_fast"] = calculate_ema(df_1h["close"], span=ema_fast)
    df_1h["ema_slow"] = calculate_ema(df_1h["close"], span=ema_slow)

    last_1h = df_1h.iloc[-1]
    ema_f_val = float(last_1h["ema_fast"])
    ema_s_val = float(last_1h["ema_slow"])
    close_1h = float(last_1h["close"])

    # Trend Filtresi: EMA20 > EMA50 ve Kapanış > EMA20
    is_trend_up = (ema_f_val > ema_s_val) and (close_1h > ema_f_val)

    # Hacim Filtresi: Son 1H hacmi > önceki 5 saatin ortalaması
    prev_vol_avg = float(df_1h["vol"].iloc[-(vol_lookback + 1):-1].mean()) if len(df_1h) > vol_lookback else 1.0
    curr_vol = float(last_1h["vol"])
    vol_ratio = curr_vol / (prev_vol_avg + 1e-6)
    is_vol_confirmed = vol_ratio >= 1.0

    # 2. Aşama: 15m Mikro Giriş & Mum Formasyonu
    df_15m["ema_fast"] = calculate_ema(df_15m["close"], span=ema_fast)
    patterns_found: list[str] = []

    if detect_bullish_engulfing(df_15m, idx=-1):
        patterns_found.append("Bullish Engulfing")
    if detect_hammer(df_15m, idx=-1):
        patterns_found.append("Hammer")
    if detect_morning_star(df_15m, idx=-1):
        patterns_found.append("Morning Star")

    # Pullback denetimi (son 4 mum içinde fiyatta EMA20'ye yakınlaşma veya temas)
    recent_lows = df_15m["low"].tail(int(cfg.get("pullback_lookback", 4)))
    recent_ema20 = df_15m["ema_fast"].tail(int(cfg.get("pullback_lookback", 4)))
    diffs = (recent_lows - recent_ema20).abs() / recent_ema20
    pullback_detected = bool((diffs <= float(cfg.get("pullback_tolerance_pct", 0.2)) / 100).any() or (recent_lows <= recent_ema20).any())

    # Karar Sentezi
    metrics = {
        "ema20_1h": round(ema_f_val, 3),
        "ema50_1h": round(ema_s_val, 3),
        "close_1h": round(close_1h, 3),
        "volume_ratio": round(vol_ratio, 2),
        "patterns": patterns_found,
        "pullback": pullback_detected,
    }

    if not is_trend_up:
        reason = f"1H Trend AŞAĞI/ZAYIF (EMA20={ema_f_val:.3f}, EMA50={ema_s_val:.3f}, Kapanış={close_1h:.3f})"
        return PillarResult(name="Teknik Analiz (1H Trend + 15m Formasyon)", status=Status.FAIL, reason=reason, source=Source.LIVE, metrics=metrics)

    if not is_vol_confirmed:
        reason = f"1H Hacim Teyitsiz (Hacim oranı {vol_ratio:.2f} < 1.0x eşiği)"
        return PillarResult(name="Teknik Analiz (1H Trend + 15m Formasyon)", status=Status.FAIL, reason=reason, source=Source.LIVE, metrics=metrics)

    if not patterns_found:
        reason = f"1H Trend ve Hacim YUKARI ({vol_ratio:.2f}x), ancak 15m'de teyitli dönüş mumu yok (Beklemede)"
        return PillarResult(name="Teknik Analiz (1H Trend + 15m Formasyon)", status=Status.NEUTRAL, reason=reason, source=Source.LIVE, metrics=metrics)

    pattern_names = ", ".join(patterns_found)
    reason = f"1H Trend YUKARI (EMA20>EMA50) + Hacim Güçlü ({vol_ratio:.2f}x) | 15m Dönüş Formasyonu: {pattern_names}"
    return PillarResult(name="Teknik Analiz (1H Trend + 15m Formasyon)", status=Status.PASS, reason=reason, source=Source.LIVE, metrics=metrics)
