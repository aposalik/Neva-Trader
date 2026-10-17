import tempfile
import unittest
from pathlib import Path

from execution.executor import Executor
from risk.guardrail import GuardDecision
from risk.position_sizer import size_position


class ExecutorTests(unittest.TestCase):
    def test_execute_is_simulated_by_default_and_audited(self):
        position = size_position(balance_usdt=5000, price=28, risk_pct=.05, max_notional_usd=250,
                                 stop_loss_pct=.012, risk_reward_ratio=2)
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"
            record = Executor(audit_path=audit_path).execute(
                decision=GuardDecision("EXECUTE", ("ok",)), position=position)
            self.assertEqual(record["mode"], "SIMULATED")
            self.assertEqual(record["result"], "SIMULATED_RECEIPT")
            self.assertTrue(record["decision_id"].startswith("nexa_"))
            self.assertTrue(audit_path.exists())

    def test_blocked_order_is_never_submitted(self):
        position = size_position(balance_usdt=5000, price=28, risk_pct=.05, max_notional_usd=250,
                                 stop_loss_pct=.012, risk_reward_ratio=2)
        with tempfile.TemporaryDirectory() as directory:
            record = Executor(audit_path=Path(directory) / "audit.jsonl").execute(
                decision=GuardDecision("BLOCKED", ("macro",)), position=position)
            self.assertEqual(record["result"], "ORDER_NOT_SENT")


if __name__ == "__main__":
    unittest.main()
