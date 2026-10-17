"""Paper-by-default execution adapter.

A demo order is only submitted after the caller explicitly opts into `execute_demo`.
The module never reads or logs credentials; the OKX CLI owns authentication.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from risk.guardrail import GuardDecision
from risk.position_sizer import PositionPlan


class Executor:
    def __init__(self, *, execute_demo: bool = False, audit_path: Path = Path("decisions.log")):
        self.execute_demo = execute_demo
        self.audit_path = audit_path

    def execute(self, *, decision: GuardDecision, position: PositionPlan, instrument: str = "AVAX-USDT") -> dict:
        decision_id = f"nexa_{uuid.uuid4().hex[:20]}"
        record = {"at": datetime.now(timezone.utc).isoformat(), "decision_id": decision_id, "instrument": instrument,
                  "decision": asdict(decision), "position": asdict(position), "mode": "SIMULATED"}
        if decision.status != "EXECUTE":
            record["result"] = "ORDER_NOT_SENT"
        elif not self.execute_demo:
            record["result"] = "SIMULATED_RECEIPT"
        else:
            local_cli = Path("node_modules/.bin/okx")
            if not shutil.which("okx") and not local_cli.exists():
                raise RuntimeError("OKX CLI bulunamadı; demo emri gönderilmedi.")
            prefix = ["okx"] if shutil.which("okx") else ["npx", "--no-install", "okx"]
            command = [*prefix, "spot", "place", "--instId", instrument, "--side", "buy", "--ordType", "market",
                       "--sz", str(position.size_avax), "--tdMode", "cash", "--clOrdId", decision_id,
                       "--tpTriggerPx", str(position.take_profit_price), "--tpOrdPx", "-1",
                       "--slTriggerPx", str(position.stop_loss_price), "--slOrdPx", "-1", "--demo", "--json"]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
            record["mode"] = "OKX_DEMO"
            record["result"] = "SUBMITTED" if completed.returncode == 0 else "FAILED"
            record["cli_output"] = completed.stdout if completed.returncode == 0 else completed.stderr
        with self.audit_path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
