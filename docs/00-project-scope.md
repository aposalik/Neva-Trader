# Nexa-Trader — Scope

## Hackathon goal

Build an autonomous AI agent using Agent Trade Kit (ATK). Trading and Avalanche deployment are optional bonus work.

## MVP demonstration

```text
Observe market → form proposal → enforce policy → simulate/paper result → audit record
```

## Non-negotiable safety constraints

- LLM proposes; deterministic code validates policy and order bounds.
- Live trading remains disabled unless the team explicitly approves it later.
- ATK command names, demo behavior, and order schemas are verified from official workshop output before implementation.
- Credentials remain local and are never logged, prompted, or committed.

## Initial backlog

1. Capture ATK CLI version and demo balance/ticker responses (redacted).
2. Create a small `MarketState` adapter for AVAX-USDT.
3. Define `TradeProposal` and a fail-closed `RiskDecision`.
4. Add simulated executor and audit record.
5. Demo execute / pending approval / rejected cases.
