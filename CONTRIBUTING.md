# Nexa-Trader — Team Contribution Guide

This repository is operated by four delivery teams. We optimise for a **working, explainable and safe demo**, not for maximum scope or live trading.

## The single product path

```text
Observe → validate data → create proposal → deterministic risk gate →
SIMULATED / approved OKX demo order → immutable audit record → dashboard
```

The model and signal layer may **propose**. Only deterministic code may calculate the order amount, enforce policy, and invoke the executor.

## Team ownership

| Team | Owner area | Primary paths | Definition of done |
|---|---|---|---|
| 1 — Core & Integration | contracts, risk policy, orchestration, release | `risk/`, `execution/`, `main.py`, `tests/` | Tests pass; a blocked decision cannot reach an order command. |
| 2 — ATK & Market Data | official ATK CLI discovery, ticker/candles/balance adapters | `data/okx_client.py`, `data/` | Commands, schemas and demo behavior are recorded with redacted evidence. |
| 3 — Intelligence & Signals | technical analysis, news/on-chain/macro adapters and signal fusion | `strategy/`, `data/news.py`, `data/onchain.py`, `data/macro.py` | Every external signal has source, timestamp and explicit degraded fallback. |
| 4 — Product, Demo & Pitch | terminal/UI experience, audit presentation, documentation, Avalanche bonus, pitch | `README.md`, `docs/`, demo assets | Three repeatable scenarios work on the presentation machine. |

One owner owns each file. For a cross-team file, open an issue and pair for the small shared change rather than editing concurrently.

## Git workflow

1. Update local `main`: `git switch main && git pull --ff-only`.
2. Create a short-lived branch:
   ```bash
   git switch -c feat/<team>-<short-description>
   # Example: git switch -c feat/signals-rss-provenance
   ```
3. Make one focused change. Never commit `.env`, credentials, local logs or `decisions.log`.
4. Run the project verification:
   ```bash
   python -m unittest discover -s tests -v
   python main.py --demo-script
   ```
5. Push and open a Pull Request (PR) into `main`.
6. Assign one reviewer from another team. The Core & Integration owner merges only after checks are green.

### Branch naming

- `feat/core-*`, `feat/atk-*`, `feat/signals-*`, `feat/product-*`
- `fix/*` for defects
- `docs/*` for documentation only

No direct pushes to `main`. Enable GitHub branch protection when the team is created: require a pull request, one approval, and passing checks.

## Integration rhythm

- **Every 60–90 min, 5 minutes:** what merged, next small delivery, blocker, demo status.
- **First checkpoint:** a complete simulated flow works from a fresh clone.
- **Feature freeze:** two hours before the presentation. Only fixes, rehearsal and offline fallback after that.
- `main` must stay runnable. If it becomes red, stop feature work and fix it first.

## Security / trading rules

- `LIVE_TRADING_ENABLED=false` is the default and must remain so for hackathon work.
- `--execute-demo` is an intentional sandbox/demo action; never run it without the team’s explicit agreement.
- Never copy an API key, secret or passphrase into GitHub issues, PRs, logs, chat, screenshots or `.env.example`.
- A provider without verified coverage or credentials must be marked `FALLBACK: MOCK`; it is never described as live.
- ATK order syntax must be verified using the installed CLI’s `--help` output before any executor change.

## PR checklist

- [ ] I ran the tests and demo script.
- [ ] Happy path and a failure/blocked path were considered.
- [ ] No credentials or personal data were added.
- [ ] Data provenance and fallback behavior are clear.
- [ ] I updated README/docs if installation, behavior or safety changed.
- [ ] I kept the PR scoped to one delivery.
