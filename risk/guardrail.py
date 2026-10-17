"""Final deterministic gate before execution."""
from __future__ import annotations
from dataclasses import dataclass
from strategy.signal_engine import Proposal
from risk.position_sizer import PositionPlan


@dataclass(frozen=True)
class GuardDecision:
    status: str  # EXECUTE / BLOCKED / NO_TRADE
    reasons: tuple[str, ...]


def evaluate(*, proposal: Proposal, position: PositionPlan, spread_pct: float, max_spread_pct: float,
             macro_event: dict | None, open_position: bool, single_position_only: bool) -> GuardDecision:
    reasons: list[str] = []
    if proposal.action != "BUY":
        reasons.append("Strategy did not issue BUY.")
    if macro_event:
        reasons.append(f"Macro blackout: {macro_event['name']} in {macro_event['minutes_until']}m")
    if spread_pct > max_spread_pct:
        reasons.append(f"Spread too high: {spread_pct:.2f}% > {max_spread_pct:.2f}%")
    if single_position_only and open_position:
        reasons.append("Single-position lock active.")
    if position.notional_usd <= 0:
        reasons.append("Invalid approved notional.")
    return GuardDecision("EXECUTE" if not reasons else ("NO_TRADE" if proposal.action != "BUY" else "BLOCKED"), tuple(reasons or ["All deterministic checks passed."]))
