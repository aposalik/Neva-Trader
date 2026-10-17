# Nexa-Trader — Sentinel

> **Agentic Hackathon project** — an explainable, safety-first AVAX/USDT trading agent built around OKX Agent Trade Kit (ATK).

Nexa-Trader observes market and contextual signals, produces a trade proposal, then passes it through deterministic safety controls. The agent can demonstrate a paper workflow today; any OKX **demo** order is a deliberate, separately gated action.

```text
Observe → validate data → propose → deterministic risk gate →
SIMULATED / approved OKX demo order → audit record → demo UI
```

## Why this project

The hackathon’s required deliverable is an autonomous agent using Agent Trade Kit. Trading and Avalanche deployment are optional bonuses. We therefore optimise for a reliable, explainable live demo:

- **The model/signal layer proposes — code enforces.** An LLM or external signal cannot choose an unlimited trade amount or bypass a policy check.
- **No hidden “live” data claims.** Any unavailable integration is visibly marked `FALLBACK: MOCK`.
- **Fail closed.** Negative context, macro blackout, an excessive spread, a pre-existing position, malformed data, or an invalid proposal results in `NO_TRADE`/`BLOCKED`, never an order.
- **Paper by default.** The default executor writes a simulated receipt and JSONL audit line; it does not call OKX.

## Four-team operating model

| Team | Owns | Main paths | First deliverable |
|---|---|---|---|
| **1 — Core & Integration** | policy, sizing, guardrails, executor boundaries, release | `risk/`, `execution/`, `main.py`, `tests/` | One end-to-end simulated decision where a blocked decision cannot execute. |
| **2 — ATK & Market Data** | installed OKX CLI verification, ticker/candle/balance adapter, demo schema evidence | `data/okx_client.py`, `data/` | Redacted proof for CLI version, demo balance, AVAX ticker and candles. |
| **3 — Intelligence & Signals** | technical, news, on-chain, macro adapters and signal fusion | `strategy/`, `data/news.py`, `data/onchain.py`, `data/macro.py` | One provenance-tagged source or an honest degraded fallback. |
| **4 — Product, Demo & Pitch** | demo UX, audit presentation, documentation, Avalanche bonus, jury script | `README.md`, `docs/`, presentation assets | Reproducible green/yellow/red flow on the presentation laptop. |

Read **[CONTRIBUTING.md](CONTRIBUTING.md)** before taking a task. It contains the branch, PR, ownership and security rules.

## Quick start — every teammate

### 1. Clone the repository

```bash
git clone https://github.com/aposalik/Neva-Trader.git
cd Neva-Trader
```

> The GitHub repository is named `Neva-Trader`; the product inside it is **Nexa-Trader**.

### 2. Create an isolated Python environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows Command Prompt**

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install the project-local ATK CLI

Node.js 22+ is recommended. The project pins the CLI under `node_modules`; never rely on a teammate’s unverified global version.

```bash
npm ci
npx --no-install okx --version
```

Expected CLI baseline: `@okx_ai/okx-trade-cli` **1.4.8**.

### 4. Confirm the baseline before changing code

```bash
python -m unittest discover -s tests -v
python main.py --demo-script
```

Expected result: all tests pass and the terminal shows three scenarios:

1. **EXECUTE** — valid aligned signals; records a **simulated** receipt.
2. **NO_TRADE** — negative-news veto; no order route is entered.
3. **BLOCKED** — high-impact macro blackout; no order route is entered.

## Running the agent

```bash
# Run one safe, simulated evaluation
python main.py --once

# Re-evaluate on a cadence (seconds)
python main.py --loop 30

# Demonstrate a high-impact macro-event block
python main.py --simulate-event "US CPI in 10m"

# Run the jury-safe deterministic sequence
python main.py --demo-script
```

### Demo order — deliberately gated

```bash
python main.py --once --execute-demo
```

This is the **only** command that may submit an OKX demo order, and it only does so after every deterministic guardrail passes. It must not be run until Team 2 records the workshop schema verification and the entire team expressly agrees to a sandbox demo. It is not a live-trading command.

## Architecture

| Layer | Responsibility | Rule |
|---|---|---|
| `data/` | OKX read-only wrapper, external-signal adapters, macro blackout lookup | Carry provenance; use transparent fallback rather than inventing data. |
| `strategy/` | EMA trend, volume confirmation, candlestick pattern, signal matrix | Creates only `BUY` or `NO_TRADE` proposals. |
| `risk/` | Position size, SL/TP calculation, macro/spread/position constraints | Final deterministic authority before execution. |
| `execution/` | Simulated receipt or explicitly enabled OKX demo submission | Uses a unique client order id and appends an audit record. |
| `tests/` | Risk, technical and executor contracts | Every behavioral change needs tests. |

### Existing safety gates

- Spot-long only — no leverage, shorts, or margin paths.
- Maximum trade notional and risk percentage are in `config.json`.
- Default settings: 5% risk cap, maximum $250 notional, 1.2% stop, 1:2 risk/reward.
- High-impact event inside the blackout window blocks a trade.
- Wide spreads, an active position, invalid sizes and non-BUY proposals block a trade.
- `LIVE_TRADING_ENABLED=false` remains the default.

## ATK workshop verification — Team 2

Do not implement or modify an executor based on copied screenshots or unverified examples. In the official workshop, run and preserve **redacted** output for:

```bash
npx --no-install okx --version
npx --no-install okx account balance --demo --json
npx --no-install okx market ticker AVAX-USDT --demo --json
npx --no-install okx market candles AVAX-USDT --bar 1H --limit 50 --demo --json
npx --no-install okx spot place --help
```

Record the exact response fields, size/lot requirements, `clOrdId` idempotency behavior, demo flag behavior, TP/SL placement behavior, failure response and cancellation semantics in a PR. Never commit credentials or raw account data.

## Configuration and secrets

- Copy `.env.example` to `.env` only if an optional provider requires it.
- `.env`, credentials and `decisions.log` are ignored by Git.
- Never put keys in an issue, PR, commit, screenshot, terminal recording, test fixture or chat.
- Unavailable providers stay in fixture/degraded mode and must be described that way during the demo.

## Team Git workflow

```bash
# Start every task from latest main
git switch main
git pull --ff-only

# Create a focused branch
git switch -c feat/<team>-<short-description>

# Validate, commit, publish your branch
python -m unittest discover -s tests -v
python main.py --demo-script
git add <files>
git commit -m "feat(signals): add source provenance"
git push -u origin HEAD
```

Then open a Pull Request to `main`, request one reviewer from a different team, and wait for checks. **Do not push directly to `main`.** The Core & Integration owner merges only green, reviewed PRs.

Recommended GitHub repository settings:

1. Add every teammate as a collaborator (Write access is enough).
2. Create a `Teams` project board or labels: `team:core`, `team:atk-data`, `team:signals`, `team:product-demo`.
3. Protect `main`: require a pull request, one approval and passing checks; disable force pushes.
4. Create GitHub Issues for each scoped delivery and link each PR to its issue.

## Demo runbook

1. Start from a fresh terminal, activate `.venv`.
2. Run `python main.py --demo-script`.
3. Explain the three colors: **green = allowed simulated path**, **yellow = needs human caution/block**, **red/no-trade = policy veto**.
4. Show `decisions.log` only if needed; it includes decisions, policy outcome and mode but never secrets.
5. If a live provider is unavailable, show its `FALLBACK: MOCK` label and explain the safe degraded behavior.

## Repository layout

```text
Nexa-Trader/
├── data/          # read-only ATK wrapper and provenance-aware sources
├── strategy/      # deterministic technical and signal logic
├── risk/          # sizing and final guardrails
├── execution/     # simulated-by-default order boundary
├── tests/         # unit/contract checks
├── docs/          # hackathon notes and architecture decisions
├── main.py        # CLI / demo entry point
├── config.json    # non-secret risk configuration
└── CONTRIBUTING.md # four-team collaboration rules
```

## Before declaring work done

- Tests pass.
- `--demo-script` works.
- A blocked/failure path exists and is tested.
- No secrets, private account data or misleading “live” claims were added.
- Documentation matches the behavior.
- The change is merged through a reviewed PR.
