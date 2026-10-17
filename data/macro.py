"""Economic-event blackout logic; event data is stored in Europe/Istanbul timestamps."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json


def blackout_event(events_path: Path, now: datetime, window_minutes: int) -> dict | None:
    for event in json.loads(events_path.read_text()):
        if int(event.get("impact", 0)) < 3:
            continue
        event_time = datetime.fromisoformat(event["at"])
        delta_minutes = (event_time - now).total_seconds() / 60
        if abs(delta_minutes) <= window_minutes:
            return {**event, "minutes_until": round(delta_minutes, 1)}
    return None
