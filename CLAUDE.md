# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development

### Run the backend locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install yfinance
python server.py
# Listens on http://localhost:8080
```

### Test the ADR endpoint
```bash
curl http://localhost:8080/api/adr/AAPL
```

### Deploy
- **Frontend:** GitHub Pages serves `index.html` from the root of `main` branch at `https://paperfish-blob.github.io/position-calculator`
- **Backend:** Render/Railway picks up `Procfile` (`web: python server.py`) and `requirements.txt` automatically on push
- After deploying the backend, update `API_BASE` in `index.html` to the live URL before pushing

---

## Architecture

Three files do all the work:

### `server.py`
Pure Python stdlib HTTP server (`socketserver.ThreadingMixIn` + `TCPServer`). Single route: `GET /api/adr/{ticker}`. Uses `yfinance` to fetch 1 month of OHLCV, slices the last 20 rows, and returns ADR $, ADR %, `day_low`, and `day_high`. Results are cached in a module-level dict (`CACHE`) with a 5-minute TTL. Binds to `0.0.0.0:$PORT` so Render/Railway can inject the port via env.

### `index.html`
Self-contained — all CSS and JS are inline, no build step, no external dependencies. State is a plain JS object (`state`). Every user interaction calls `setState(patch)` which merges the patch and calls `render()`. `render()` is a single function that rewrites all DOM nodes from scratch on every call. Computed values (shares, risk $, pivot %, xADR) are derived inside `render()` and never stored. The auto-stop effect (syncing `stopLoss` to `day_low`/`day_high`) is applied by mutating `state.stopLoss` directly at the top of `render()` before computing derived values — this avoids re-entrant `setState` calls.

**`API_BASE` constant** (top of the `<script>` block) must point to the deployed backend URL. Change it to `http://localhost:8080` for local development.

### `docs/spec.md`
Canonical reference for state variables, computed formulas, ADR API contract, and UI control behaviour.
