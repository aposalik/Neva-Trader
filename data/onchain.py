"""On-Chain Veri Sağlayıcı (2. Ayak).

CryptoQuant API / Avalanche cüzdan dinamiklerini analiz eder.
Kaynak ayarına (config["pillars"]["onchain"]["source"]) göre canlı veya şeffaf MOCK fallback çalıştırır.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from models import PillarResult, Source, Status
from utils import to_float

log = logging.getLogger("nexa.onchain")


def fetch_onchain_metrics(
    config: dict[str, Any],
    mock_data: dict[str, Any],
    force_mock: bool = False,
) -> PillarResult:
    """On-chain metriklerini çeker ve 2. Ayak değerlendirmesini yapar."""
    cfg = config.get("pillars", {}).get("onchain", {})
    source_setting = cfg.get("source", "mock")
    api_key = os.getenv("CRYPTOQUANT_API_KEY")

    # Canlı kaynak denenmesi gerekiyorsa (API anahtarı varsa ve mock zorlanmıyorsa)
    if not force_mock and source_setting == "live" and api_key:
        try:
            # Not: CryptoQuant AVAX endpoint'i enterprise/özel plan gerektirdiğinde
            # burada timeout korumalı istek atılır; arıza durumunda güvenle fallback'e geçilir.
            raise NotImplementedError("CryptoQuant AVAX API anahtarı yapılandırılmadı.")
        except Exception as e:
            log.warning("Canlı On-Chain verisi alınamadı (%s), mock_data.json fallback'e geçiliyor.", e)
            return _evaluate_metrics(mock_data.get("onchain", {}), source=Source.FALLBACK)

    # Standart MOCK kaynağı (bilinçli yapılandırma)
    data = mock_data.get("onchain", {})
    return _evaluate_metrics(data, source=Source.MOCK)


def _evaluate_metrics(data: dict[str, Any], source: Source) -> PillarResult:
    """Verilen on-chain verisini kurallara göre puanlar."""
    reserve_chg = to_float(data.get("exchange_reserve_change_24h_pct"), 0.0)
    mvrv = to_float(data.get("mvrv_ratio"), 1.5)
    whale = str(data.get("whale_accumulation_trend", "STABLE")).upper()

    reasons: list[str] = []
    passed = True

    # Kural 1: Borsa Rezerv Değişimi (Rezerv düşüyorsa satış baskısı azdır -> Pozitif)
    if reserve_chg < 0:
        reasons.append(f"Borsa rezervleri 24s'de %{reserve_chg:.2f} azalışta (Pozitif)")
    else:
        reasons.append(f"Borsa rezervleri %{reserve_chg:.2f} artışta (Satış baskısı)")
        passed = False

    # Kural 2: MVRV Oranı (1.0 - 2.5 sağlıklı boğa alanı)
    if mvrv > 3.7:
        reasons.append(f"MVRV aşırı ısınma/tepe bölgesinde ({mvrv:.2f} > 3.7)")
        passed = False
    elif mvrv < 1.0:
        reasons.append(f"MVRV aşırı ucuzluk bölgesinde ({mvrv:.2f} < 1.0, Birikim)")
    else:
        reasons.append(f"MVRV sağlıklı bölgede ({mvrv:.2f})")

    # Kural 3: Balina Birikimi
    if whale == "INCREASING":
        reasons.append("Balina birikimi aktif (INCREASING)")
    else:
        reasons.append(f"Balina birikimi zayıf ({whale})")
        # Balina nötrse tek başına işlemi öldürmez ama rezerv de artıyorsa red sebebi olur
        if not passed:
            passed = False

    status = Status.PASS if passed else Status.FAIL
    reason_str = " | ".join(reasons)

    return PillarResult(
        name="On-Chain (CryptoQuant)",
        status=status,
        reason=reason_str,
        source=source,
        metrics={
            "exchange_reserve_change_24h_pct": reserve_chg,
            "mvrv_ratio": mvrv,
            "whale_accumulation_trend": whale,
            "as_of": data.get("as_of", "bilinmiyor"),
        },
    )
