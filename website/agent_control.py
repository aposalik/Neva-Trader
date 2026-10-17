"""Demo-only agent lifecycle and validated risk-rule persistence for the local UI."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from data_snapshot import CONFIG_PATH, PROJECT_ROOT, _load_json

RUNTIME_DIR = PROJECT_ROOT / "website" / ".runtime"
PID_PATH = RUNTIME_DIR / "agent.pid"
LOG_PATH = RUNTIME_DIR / "agent.log"
_lock = threading.RLock()
_process: subprocess.Popen[str] | None = None


class ControlError(RuntimeError):
    pass


def _pid_command(pid: int) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _is_agent_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    command = _pid_command(pid)
    return "main.py" in command and str(PROJECT_ROOT) in command


def _managed_pid() -> int | None:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if _is_agent_pid(pid):
        return pid
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def _external_agent_pid() -> int | None:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    own_pid = os.getpid()
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[1]
        if pid != own_pid and "main.py" in command and str(PROJECT_ROOT) in command:
            return pid
    return None


def agent_status() -> dict[str, Any]:
    with _lock:
        pid = _managed_pid()
        external_pid = None if pid else _external_agent_pid()
        running = pid is not None or external_pid is not None
        managed = pid is not None
        config = _load_json(CONFIG_PATH, {})
        is_demo = bool((config.get("execution") or {}).get("is_demo", True))
        log_tail: list[str] = []
        if LOG_PATH.exists():
            try:
                log_tail = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
            except OSError:
                pass
        return {
            "running": running,
            "managed": managed,
            "external": external_pid is not None,
            "mode": "DEMO" if is_demo else "LIVE",
            "loopSeconds": 30,
            "canStart": is_demo and not running,
            "canStop": managed,
            "logTail": log_tail,
        }


def start_agent() -> dict[str, Any]:
    global _process
    with _lock:
        status = agent_status()
        if status["running"]:
            raise ControlError("Nexa-Trader ajanı zaten çalışıyor.")
        if status["mode"] != "DEMO":
            raise ControlError("Web kontrolü yalnızca OKX demo hesabında kullanılabilir.")

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        log_handle = LOG_PATH.open("a", encoding="utf-8")
        log_handle.write(f"\n[{datetime.now().astimezone().isoformat(timespec='seconds')}] Web arayüzünden demo ajan başlatılıyor.\n")
        log_handle.flush()
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            _process = subprocess.Popen(
                [sys.executable, str(PROJECT_ROOT / "main.py"), "--loop", "30"],
                cwd=str(PROJECT_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                start_new_session=True,
            )
        finally:
            log_handle.close()
        time.sleep(0.4)
        if _process.poll() is not None:
            raise ControlError("Ajan başlatılamadı; çalışma günlüğünü kontrol edin.")
        PID_PATH.write_text(str(_process.pid), encoding="utf-8")
        return agent_status()


def stop_agent() -> dict[str, Any]:
    global _process
    with _lock:
        pid = _managed_pid()
        if pid is None:
            if _external_agent_pid() is not None:
                raise ControlError("Ajan harici bir terminalde çalışıyor; güvenlik için buradan durdurulamaz.")
            return agent_status()
        try:
            os.killpg(pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline and _is_agent_pid(pid):
            time.sleep(0.1)
        if _is_agent_pid(pid):
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        PID_PATH.unlink(missing_ok=True)
        _process = None
        return agent_status()


def current_rules() -> dict[str, Any]:
    risk = (_load_json(CONFIG_PATH, {}).get("risk") or {}).copy()
    return {
        "positionSizePct": float(risk.get("position_size_pct", 5.0)),
        "stopLossPct": float(risk.get("stop_loss_pct", 1.0)),
        "takeProfitPct": float(risk.get("take_profit_pct", 2.0)),
        "riskRewardRatio": float(risk.get("risk_reward_ratio", 2.0)),
        "maxDailyTrades": int(risk.get("max_daily_trades", 4)),
        "maxDailyLossPct": float(risk.get("max_daily_loss_pct", 3.0)),
        "maxSpreadPct": float(risk.get("max_spread_pct", 0.15)),
    }


def _number(payload: dict[str, Any], key: str, minimum: float, maximum: float) -> float:
    try:
        value = float(payload[key])
    except (KeyError, TypeError, ValueError):
        raise ControlError(f"Geçersiz veya eksik kural: {key}") from None
    if not minimum <= value <= maximum:
        raise ControlError(f"{key} değeri {minimum}–{maximum} aralığında olmalı.")
    return value


def save_rules(payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        if agent_status()["running"]:
            raise ControlError("Kuralları değiştirmeden önce ajanı durdurun.")
        position = _number(payload, "positionSizePct", 0.1, 20.0)
        stop_loss = _number(payload, "stopLossPct", 0.1, 10.0)
        take_profit = _number(payload, "takeProfitPct", 0.1, 30.0)
        max_loss = _number(payload, "maxDailyLossPct", 0.1, 20.0)
        max_trades = _number(payload, "maxDailyTrades", 1, 20)
        if not float(max_trades).is_integer():
            raise ControlError("maxDailyTrades tam sayı olmalı.")

        config = _load_json(CONFIG_PATH, {})
        if not isinstance(config, dict):
            raise ControlError("config.json okunamadı.")
        risk = config.setdefault("risk", {})
        risk.update({
            "position_size_pct": round(position, 4),
            "stop_loss_pct": round(stop_loss, 4),
            "take_profit_pct": round(take_profit, 4),
            "risk_reward_ratio": round(take_profit / stop_loss, 2),
            "max_daily_trades": int(max_trades),
            "max_daily_loss_pct": round(max_loss, 4),
        })
        temporary = CONFIG_PATH.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(CONFIG_PATH)
        except OSError as error:
            raise ControlError(f"Kurallar kaydedilemedi: {error}") from error
        return current_rules()
