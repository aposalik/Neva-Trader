# Nexa-Trader — Agent Instructions

Read `README.md` and `CONTRIBUTING.md` before making a change. This is a four-team hackathon codebase; keep every change scoped to one owner area.

## Mandatory safety constraints

1. Default execution is simulated. Do not enable real trading or alter `LIVE_TRADING_ENABLED=false` unless the human explicitly requests it.
2. Never put API keys, account output, IP allowlists, credentials, or raw balances in source, tests, docs, logs, screenshots, commits, PRs, or chat.
3. An unverified external provider is `FALLBACK: MOCK`, never “live.”
4. Strategy/LLM code may return only a proposal. Position sizing and executor access remain deterministic and must remain behind `risk/guardrail.py`.
5. A `BLOCKED` or `NO_TRADE` decision must never invoke an order command.
6. Do not change ATK execution flags from memory. Verify the installed CLI’s `--help` output and preserve redacted schema evidence.

## Verification before committing

```bash
python -m unittest discover -s tests -v
python main.py --demo-script
```

For new behavior, add a test for both its allowed and blocked/failure path. Keep `main` green; do not directly push to it.

## Ownership

- Core/integration: `risk/`, `execution/`, `main.py`, tests
- ATK/data: `data/okx_client.py`, provider adapters
- Signals: `strategy/`, data fusion
- Product/demo: `README.md`, `docs/`, demo workflow

Cross-owner changes require a focused PR and review from another team.
