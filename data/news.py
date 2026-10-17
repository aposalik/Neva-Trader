"""Haber Akışı ve Duyarlılık Sağlayıcı (3. Ayak).

1. OKX ATK yerleşik coin-sentiment ve news API'sini sorgular.
2. TradingView'ın ana kripto veri sağlayıcılarından (Cointelegraph RSS) canlı haber başlıklarını çeker.
3. GEMINI_API_KEY mevcutsa haber başlıklarını Google Gemini 3.8 Flash ile derinlemesine puanlar.
4. Google API ücretsiz kotasını (15 RPM) korumak için 3 dakikalık (180s) akıllı önbellek (cache) uygular.
5. Kota dolması (HTTP 429) durumunda sessizce son önbelleği veya OKX ATK sentiment'i devreye alır.
"""
from __future__ import annotations

import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

from data.okx_client import OKXClient, OKXCLIError
from models import PillarResult, Source, Status
from utils import to_float

log = logging.getLogger("nexa.news")

# 3 dakikalık akıllı önbellek (Google API kota koruması için)
_LLM_CACHE: dict[str, Any] = {
    "score": None,
    "reason": None,
    "headlines": [],
    "cached_at": 0.0,
}
CACHE_TTL_SECONDS = 180.0


def fetch_news_sentiment(
    okx: OKXClient,
    config: dict[str, Any],
    mock_data: dict[str, Any],
    force_mock: bool = False,
) -> PillarResult:
    """Haber duyarlılığını puanlar (3. Ayak)."""
    cfg = config.get("pillars", {}).get("news", {})
    coins = cfg.get("coins", ["AVAX", "BTC"])
    min_score = to_float(cfg.get("min_score", 0.0))

    if force_mock or cfg.get("source") == "mock":
        data = mock_data.get("news", {})
        score = to_float(data.get("score", 0.0))
        status = Status.PASS if score >= min_score else Status.FAIL
        return PillarResult(
            name="Haber & Duyarlılık",
            status=status,
            reason=f"Mock haber skoru: {score:+.2f} ({'PASS' if status == Status.PASS else 'FAIL'})",
            source=Source.MOCK,
            metrics={"score": score, "method": "mock_data.json", "headlines": data.get("headlines", [])},
        )

    # 1. AKILLI ÖNBELLEK KONTROLÜ (Son 3 dakika içindeki Gemini analizi hâlâ geçerliyse doğrudan kullan)
    now = time.time()
    if (
        _LLM_CACHE["score"] is not None
        and (now - _LLM_CACHE["cached_at"]) < CACHE_TTL_SECONDS
    ):
        score = _LLM_CACHE["score"]
        reason = _LLM_CACHE["reason"]
        cached_headlines = _LLM_CACHE["headlines"]
        status = Status.PASS if score >= min_score else Status.FAIL
        return PillarResult(
            name="Haber & Duyarlılık (Gemini AI)",
            status=status,
            reason=f"Gemini Skoru: {score:+.2f} | {reason}",
            source=Source.LIVE,
            metrics={"score": score, "method": "gemini_cached", "headlines": cached_headlines[:3]},
        )

    # 2. Canlı başlıkları topla
    headlines: list[str] = []
    try:
        latest_news = okx.news_latest(coins=coins, limit=cfg.get("headline_limit", 5))
        for item in latest_news:
            title = (item.get("title") or item.get("summary") or "").strip()
            if title:
                headlines.append(title)
    except OKXCLIError as e:
        log.warning("OKX haber başlıkları çekilemedi: %s", e)

    # TradingView / Cointelegraph RSS akışından takviye al
    try:
        rss_titles = _fetch_tradingview_partner_rss(limit=5)
        for t in rss_titles:
            if t not in headlines:
                headlines.append(t)
    except Exception as e:
        log.warning("TradingView partner haber akışı okunamadı: %s", e)

    # 3. Gemini API ile başlıkları analiz etmeyi dene
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and headlines and cfg.get("use_llm", True):
        llm_score, llm_reason = _score_with_gemini(
            headlines=headlines,
            api_key=gemini_key,
            model_name=cfg.get("gemini_model", "gemini-3.8-flash"),
        )
        if llm_score is not None:
            # Önbelleğe kaydet
            _LLM_CACHE["score"] = llm_score
            _LLM_CACHE["reason"] = llm_reason
            _LLM_CACHE["headlines"] = headlines
            _LLM_CACHE["cached_at"] = time.time()

            status = Status.PASS if llm_score >= min_score else Status.FAIL
            return PillarResult(
                name="Haber & Duyarlılık (Gemini AI)",
                status=status,
                reason=f"Gemini Skoru: {llm_score:+.2f} | {llm_reason}",
                source=Source.LIVE,
                metrics={"score": llm_score, "method": "gemini_api", "headlines": headlines[:3]},
            )

    # Eğer önceden alınmış bir Gemini önbelleği varsa (kota 429 olsa bile), o geçerli kalsın
    if _LLM_CACHE["score"] is not None:
        score = _LLM_CACHE["score"]
        reason = _LLM_CACHE["reason"]
        status = Status.PASS if score >= min_score else Status.FAIL
        return PillarResult(
            name="Haber & Duyarlılık (Gemini AI)",
            status=status,
            reason=f"Gemini Skoru: {score:+.2f} | {reason}",
            source=Source.LIVE,
            metrics={"score": score, "method": "gemini_preserved", "headlines": _LLM_CACHE["headlines"][:3]},
        )

    # 4. Gemini yoksa OKX ATK coin-sentiment verisini dene
    try:
        sentiment_data = okx.coin_sentiment(coins=coins, period=cfg.get("period", "24h"))
        atk_score, atk_reason = _score_from_atk_sentiment(
            sentiment_data, cfg.get("weights", {"AVAX": 0.6, "BTC": 0.4})
        )
        if atk_score is not None:
            status = Status.PASS if atk_score >= min_score else Status.FAIL
            return PillarResult(
                name="Haber & Duyarlılık (ATK Sentiment)",
                status=status,
                reason=f"ATK Piyasa Duyarlılık Skoru: {atk_score:+.2f} ({atk_reason})",
                source=Source.LIVE,
                metrics={"score": atk_score, "method": "okx_coin_sentiment", "headlines": headlines[:3]},
            )
    except Exception as e:
        log.warning("OKX coin-sentiment okunamadı: %s", e)

    # 5. Canlı veri başarısız -> Güvenli Fallback
    data = mock_data.get("news", {})
    fallback_score = to_float(data.get("score", 0.0))
    status = Status.PASS if fallback_score >= min_score else Status.FAIL
    return PillarResult(
        name="Haber & Duyarlılık",
        status=status,
        reason=f"[FALLBACK: MOCK DATA] Canlı haber servisi yanıt vermedi, mock skor: {fallback_score:+.2f}",
        source=Source.FALLBACK,
        metrics={"score": fallback_score, "method": "fallback_mock", "headlines": headlines or data.get("headlines", [])},
    )


def _fetch_tradingview_partner_rss(limit: int = 5) -> list[str]:
    """TradingView haber akışının ana sağlayıcılarından (Cointelegraph) son başlıkları çeker."""
    url = "https://cointelegraph.com/rss"
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=4)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            titles = []
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    clean = title_elem.text.strip()
                    if clean:
                        titles.append(clean)
                if len(titles) >= limit:
                    break
            return titles
    except Exception as e:
        log.warning("RSS akışı ayrıştırılamadı: %s", e)
    return []


def _score_from_atk_sentiment(
    sentiment_details: list[dict[str, Any]], weights: dict[str, float]
) -> tuple[float | None, str]:
    """OKX coin-sentiment çıktısından ağırlıklı duyarlılık skoru üretir (-1.0 .. +1.0)."""
    if not sentiment_details:
        return None, "veri yok"

    weighted_score = 0.0
    total_weight = 0.0
    notes: list[str] = []

    for item in sentiment_details:
        ccy = item.get("ccy")
        weight = weights.get(ccy, 0.2)
        sent = item.get("sentiment", {})
        bull = to_float(sent.get("bullishRatio", 0.0))
        bear = to_float(sent.get("bearishRatio", 0.0))
        label = sent.get("label", "neutral")

        net_diff = bull - bear
        weighted_score += net_diff * weight
        total_weight += weight
        notes.append(f"{ccy}: {label} (Boğa: %{bull*100:.0f}, Ayı: %{bear*100:.0f})")

    if total_weight == 0:
        return None, "ağırlık sıfır"

    final_score = round(weighted_score / total_weight, 2)
    return final_score, ", ".join(notes)


def _score_with_gemini(headlines: list[str], api_key: str, model_name: str) -> tuple[float | None, str]:
    """Google Gemini REST API'sine istek atarak kurumsal düzeyde derin duyarlılık analizi üretir."""
    if "2.5" in model_name:
        model_name = "gemini-3.8-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    prompt = (
        "Sen Wall Street düzeyinde bir Kripto Portföy Yöneticisi ve Kıdemli Makro Finans Analistisin. "
        "Aşağıdaki AVAX, Bitcoin ve küresel kripto haber başlıklarını derinlemesine incele.\n\n"
        "GÖREVLERİN:\n"
        "1. Kurumsal sermaye akışı (fon/ETF çıkış ve girişleri),\n"
        "2. Büyük balina ve kurucu cüzdan tasfiyeleri (riskten kaçış, geleneksel piyasa korelasyonu),\n"
        "3. Avalanche (AVAX) gibi yüksek betalı Layer-1 altcoinler üzerindeki likidite ve satış baskısı etkisini değerlendir.\n"
        "4. AVAX fiyatı açısından net duyarlılık skorunu -1.0 (aşırı negatif/ayı) ile +1.0 (aşırı pozitif/boğa) arasında belirle.\n\n"
        "Yanıtını SADECE ve KESİNLİKLE şu JSON formatında ver, ek metin veya markdown bloğu yazma:\n"
        '{"score": -0.65, "reason": "Kurumsal sermaye akışı, balina tasfiyeleri ve AVAX likidite etkisini özetleyen 2-3 cümlelik derin teknik gerekçe."}\n\n'
        f"Haber Başlıkları:\n" + "\n".join(f"- {h}" for h in headlines[:5])
    )

    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 429:
            # Sessiz kota koruması: Terminale kırmızı hata basma
            log.info("Gemini API kota sınırı (429), önbellek veya ATK sentiment devrede.")
            return None, "Kota sınırı"

        if res.status_code != 200:
            log.info("Gemini API yanıt kodu: %d", res.status_code)
            return None, "API hatası"

        data = res.json()
        parts = data["candidates"][0]["content"]["parts"]
        raw_text = parts[-1]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json", "").strip()

        parsed = json.loads(raw_text)
        score = float(parsed.get("score", 0.0))
        reason = str(parsed.get("reason", "Gemini analizi tamamlandı."))
        return max(-1.0, min(1.0, score)), reason
    except Exception as e:
        log.info("Gemini analizinde geçici durum: %s", e)
        return None, f"Hata: {e}"
