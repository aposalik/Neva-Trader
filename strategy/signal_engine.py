"""4 Ayaklı Karar ve Sinyal Birleştirme Motoru.

4 sinyal ayağını (Teknik, On-Chain, Haber, Makro) toplar ve oybirliği kuralını işletir.
Demo senaryoları aktif olduğunda overrides parametrelerini uygular.
"""
from __future__ import annotations

import logging
from typing import Any

from models import PillarResult, Source, Status

log = logging.getLogger("nexa.signals")


class SignalEngine:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def evaluate(
        self,
        technical_res: PillarResult,
        onchain_res: PillarResult,
        news_res: PillarResult,
        macro_res: PillarResult,
        scenario_overrides: dict[str, Any] | None = None,
    ) -> tuple[str, list[str], list[PillarResult]]:
        """4 ayağı değerlendirir.

        Döndürür:
            action: 'BUY' veya 'NO_TRADE'
            reasons: Red veya onay gerekçeleri listesi
            pillars: Son 4 ayak sonucu (override edilmiş haliyle)
        """
        pillars = [technical_res, onchain_res, news_res, macro_res]

        # Demo senaryo overrides varsa uygula
        if scenario_overrides:
            pillars = self._apply_overrides(pillars, scenario_overrides)

        reasons: list[str] = []
        all_passed = True

        for p in pillars:
            if p.status != Status.PASS:
                all_passed = False
                reasons.append(f"[{p.name} - {p.status.value}] {p.reason}")

        if all_passed:
            action = "BUY"
            reasons.append("Tüm 4 sinyal ayağı ONAY (PASS) verdi. Giriş koşulları sağlandı.")
        else:
            action = "NO_TRADE"

        return action, reasons, pillars

    def _apply_overrides(
        self,
        pillars: list[PillarResult],
        overrides: dict[str, Any],
    ) -> list[PillarResult]:
        """Demo senaryolarında belirli ayakları simüle edilmiş sonuçlarla günceller."""
        updated: list[PillarResult] = []
        mapping = {
            "Teknik Analiz": "technical",
            "On-Chain": "onchain",
            "Haber": "news",
            "Makro": "macro",
        }

        for p in pillars:
            key = None
            for prefix, k in mapping.items():
                if prefix.lower() in p.name.lower():
                    key = k
                    break

            if key and key in overrides:
                ov = overrides[key]
                st = Status(ov.get("status", "PASS"))
                updated.append(PillarResult(
                    name=p.name + " (SIMULATED)",
                    status=st,
                    reason=ov.get("reason", p.reason),
                    source=Source.SIMULATED,
                    metrics=ov.get("metrics", p.metrics),
                ))
            else:
                updated.append(p)

        return updated
