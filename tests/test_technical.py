"""Teknik analiz göstergeleri ve mum formasyonları birim testleri."""
from __future__ import annotations

import pandas as pd
import pytest

from strategy.technical import (
    calculate_ema,
    detect_bullish_engulfing,
    detect_hammer,
    detect_morning_star,
    parse_candles,
)


def test_calculate_ema():
    prices = pd.Series([10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8])
    ema = calculate_ema(prices, span=3)
    assert len(ema) == len(prices)
    assert ema.iloc[-1] > ema.iloc[0]
    assert 11.5 < ema.iloc[-1] < 11.8


def test_detect_bullish_engulfing_positive():
    df = pd.DataFrame([
        {"open": 10.5, "high": 10.6, "low": 9.9, "close": 10.0},  # Kırmızı mum
        {"open": 9.95, "high": 10.8, "low": 9.9, "close": 10.6},  # Yutan yeşil mum
    ])
    assert detect_bullish_engulfing(df, idx=-1) is True


def test_detect_bullish_engulfing_negative():
    # İkisi de yeşil mum -> Engulfing olamaz
    df = pd.DataFrame([
        {"open": 10.0, "high": 10.5, "low": 9.9, "close": 10.4},
        {"open": 10.4, "high": 10.8, "low": 10.3, "close": 10.7},
    ])
    assert detect_bullish_engulfing(df, idx=-1) is False


def test_detect_hammer_positive():
    # Küçük gövde üstte (10.4-10.5 = 0.1), uzun alt gölge (10.4 - 10.0 = 0.4), neredeyse sıfır üst gölge
    df = pd.DataFrame([
        {"open": 10.4, "high": 10.52, "low": 10.0, "close": 10.5},
    ])
    assert detect_hammer(df, idx=-1) is True


def test_detect_hammer_negative():
    # Doji veya simetrik gölgeler -> Çekiç değil
    df = pd.DataFrame([
        {"open": 10.0, "high": 10.8, "low": 9.2, "close": 10.05},
    ])
    assert detect_hammer(df, idx=-1) is False


def test_detect_morning_star_positive():
    df = pd.DataFrame([
        {"open": 10.8, "high": 10.9, "low": 10.1, "close": 10.2},  # 1: Güçlü kırmızı
        {"open": 10.15, "high": 10.2, "low": 10.05, "close": 10.12}, # 2: Küçük gövdeli yıldız
        {"open": 10.15, "high": 10.7, "low": 10.1, "close": 10.65}, # 3: 1'in gövdesinin üst yarısına çıkan yeşil
    ])
    assert detect_morning_star(df, idx=-1) is True


def test_parse_candles_order_inversion():
    # OKX en yeni mumu başta döndürür: t2, sonra t1
    raw = [
        ["1700000002000", "10.5", "10.6", "10.4", "10.55", "100", "1000", "1000", "1"], # Yeni
        ["1700000001000", "10.0", "10.5", "9.9", "10.4", "80", "800", "800", "1"],     # Eski
    ]
    df = parse_candles(raw, drop_unconfirmed=True)
    # DataFrame kronolojik olmalı: t1 başta, t2 sonda
    assert df.iloc[0]["ts"] == 1700000001000
    assert df.iloc[1]["ts"] == 1700000002000
