import unittest
from risk.guardrail import evaluate
from risk.position_sizer import size_position
from strategy.signal_engine import Proposal


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.position = size_position(balance_usdt=5000, price=25, risk_pct=.05, max_notional_usd=250,
                                      stop_loss_pct=.012, risk_reward_ratio=2)
        self.buy = Proposal("BUY", ("ok",), .8)

    def test_executes_when_everything_is_valid(self):
        outcome = evaluate(proposal=self.buy, position=self.position, spread_pct=.08, max_spread_pct=.35,
                           macro_event=None, open_position=False, single_position_only=True)
        self.assertEqual(outcome.status, "EXECUTE")

    def test_blackout_blocks_order(self):
        outcome = evaluate(proposal=self.buy, position=self.position, spread_pct=.08, max_spread_pct=.35,
                           macro_event={"name": "US CPI", "minutes_until": 8}, open_position=False,
                           single_position_only=True)
        self.assertEqual(outcome.status, "BLOCKED")
        self.assertIn("Macro blackout", outcome.reasons[0])

    def test_no_trade_never_executes(self):
        outcome = evaluate(proposal=Proposal("NO_TRADE", ("veto",), 0), position=self.position,
                           spread_pct=.08, max_spread_pct=.35, macro_event=None, open_position=False,
                           single_position_only=True)
        self.assertEqual(outcome.status, "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
