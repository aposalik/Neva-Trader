"""Ortak yardımcılar: zaman, yuvarlama, logging, JSON."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
# Türkiye 2016'dan beri yaz saati uygulamıyor -> sabit UTC+3 (Windows'ta tzdata bağımlılığı gerekmez)
TR_TZ = timezone(timedelta(hours=3), name="TRT")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ms_to_dt(ms: Any) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fmt_tr(dt: datetime) -> str:
    return dt.astimezone(TR_TZ).strftime("%d.%m.%Y %H:%M TRT")


def round_step(value: float, step: float, mode: str = "down") -> float:
    """Değeri borsa adımına (lotSz/tickSz) yuvarlar. Float hatası olmaması için Decimal kullanır."""
    if step <= 0:
        raise ValueError("step > 0 olmalı")
    v, s = Decimal(str(value)), Decimal(str(step))
    rounding = ROUND_DOWN if mode == "down" else ROUND_HALF_UP
    return float((v / s).to_integral_value(rounding=rounding) * s)


def fmt_num(x: float) -> str:
    """CLI'a gönderilecek sayıyı bilimsel gösterim olmadan yazar (1e-06 -> 0.000001)."""
    return format(Decimal(str(x)).normalize(), "f")


def to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def setup_logging() -> logging.Logger:
    """Dosyaya (DEBUG) + terminale (WARNING, renkli) log."""
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("nexa")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_DIR / "nexa.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    logger.addHandler(fh)
    try:
        from rich.logging import RichHandler

        ch: logging.Handler = RichHandler(show_path=False, markup=False, rich_tracebacks=False)
    except ImportError:
        ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    logger.addHandler(ch)
    return logger
