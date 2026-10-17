# Nexa-Trader Website

Professional bilingual landing page, team story, and local trading command center for Nexa-Trader. Turkish is the default language; English is available from the TR/EN switch.

## Run

From the project root:

```bash
.venv/bin/python website/server.py
```

Open <http://127.0.0.1:8787>.

## Data and control behavior

- `GET /api/snapshot` reads the sanitized audit trail from `decisions.log`, `config.json`, and `state.json`.
- `GET /api/live` reads OKX market candles and the configured OKX demo account through the existing CLI integration.
- Scripted scenarios and `SIMULATED` pillar records are excluded.
- The browser refreshes market/audit data every 15 seconds and agent state every 5 seconds.
- `website/assets/snapshot.json` is a static audit fallback generated at server startup.
- Demo-agent start/stop uses a fixed `main.py --loop 30` process; arbitrary commands and live-account mode are not exposed.
- Risk rules are range-validated and atomically persisted only while the agent is stopped.
- Mutating endpoints require the same-origin custom control header and the server defaults to `127.0.0.1`.

## Files

- `index.html` / `index-en.html` — Turkish-default and English landing pages
- `about.html` / `about-en.html` — bilingual team story
- `styles.css` — shared responsive design system
- `app.js` — localized OKX chart, wallet, audit, and control interactions
- `site.js` — lightweight About-page interactions
- `data_snapshot.py` — sanitized audit data model
- `live_data.py` — cached, sanitized OKX market/account model
- `agent_control.py` — demo-only lifecycle and validated rule persistence
- `server.py` — safe local static/API server
- `assets/signal-fusion.html` — standalone Anatomy figure used in the hero

## Static refresh

To rebuild only the fallback snapshot:

```bash
.venv/bin/python website/data_snapshot.py
```
