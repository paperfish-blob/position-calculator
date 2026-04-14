# Position Sizing Calculator — Spec

A risk-based position sizing tool that computes how many shares to buy (long) or sell short given a defined account risk.

---

## Architecture

| Layer    | Technology                          | Hosting         |
|----------|-------------------------------------|-----------------|
| Frontend | Plain HTML + vanilla JS (no build)  | GitHub Pages    |
| Backend  | Python stdlib `http.server`         | Render / Railway |

---

## State

| Variable       | Type                | Default    | Purpose                                          |
|----------------|---------------------|------------|--------------------------------------------------|
| `direction`    | `'long' \| 'short'` | `'long'`   | Trade direction toggle                           |
| `accountEquity`| `string`            | `'40000'`  | Account size in USD                              |
| `riskPct`      | `string`            | `'0.33'`   | Risk per trade as a % of equity                  |
| `entry`        | `string`            | `''`       | Entry price per share                            |
| `stopLoss`     | `string`            | `''`       | Stop loss price per share                        |
| `ticker`       | `string`            | `''`       | Optional ticker symbol for ADR lookup            |
| `adrData`      | `object \| null`    | `null`     | ADR response from backend (populated on lookup)  |
| `adrLoading`   | `boolean`           | `false`    | Loading state while ADR fetch is in-flight       |
| `useAutoStop`  | `boolean`           | `false`    | When enabled, syncs stop loss to day low/high    |

---

## Computed Result

Recalculated reactively whenever any input changes. Returns `null` if any input is missing/invalid or if `riskPerShare <= 0`.

```
riskDollars  = accountEquity × (riskPct / 100)
riskPerShare = entry − stopLoss        (long)
             = stopLoss − entry        (short)
quantity     = floor(riskDollars / riskPerShare)
totalValue   = quantity × entry
pivotPct     = (stopLoss − entry) / entry × 100
```

---

## ADR API

### Endpoint

```
GET /api/adr/{ticker}
```

### Backend logic (`server.py`)

1. Checks a module-level TTL cache (`CACHE`) keyed by ticker. Returns cached data if not expired (5-min TTL).
2. Calls `yfinance.Ticker(ticker).history(period='1mo')` to fetch ~20+ trading days of OHLCV.
3. Slices the last 20 rows and computes:
   - **ADR $** — `mean(High − Low)` over 20 days
   - **ADR %** — `mean((High − Low) / Close × 100)` over 20 days
   - **day_low** — `Low` of the most recent session
   - **day_high** — `High` of the most recent session
4. Returns HTTP 404 if ticker is not found or data is insufficient.

### Response shape

```json
{
  "ticker": "AAPL",
  "adr": 3.12,
  "adr_pct": 1.85,
  "day_low": 168.40,
  "day_high": 172.80
}
```

### Error responses

| Status | Body                                          | When                              |
|--------|-----------------------------------------------|-----------------------------------|
| 400    | `{"error": "ticker required"}`                | Empty ticker segment in path      |
| 404    | `{"error": "ticker not found or insufficient data"}` | yfinance returns empty DataFrame  |
| 500    | `{"error": "internal server error"}`          | Unexpected exception              |

---

## Auto-Stop Feature

When `useAutoStop` is toggled on and `adrData` is available:
- **Long:** stop loss is automatically set to `adrData.day_low`
- **Short:** stop loss is automatically set to `adrData.day_high`

Implemented by mutating `state.stopLoss` at the top of the `render()` function before computing derived values.

---

## Displayed Outputs

| Field           | Shown when          | Value                                                     |
|-----------------|---------------------|-----------------------------------------------------------|
| Shares to Trade | Result is valid     | `floor(riskDollars / riskPerShare)`                       |
| Risk $          | Result is valid     | Dollar risk amount                                        |
| Total Position  | Result is valid     | Total position value at entry                             |
| Pivot %         | Result is valid     | % distance from entry to stop                            |
| ADR %           | ADR data available  | 20-day average daily range as % of close                  |
| xADR            | Result + ADR valid  | `adr_pct / abs(pivotPct)` — how many ADRs the stop is away|

---

## UI Controls

| Control               | Behavior                                                                 |
|-----------------------|--------------------------------------------------------------------------|
| Long / Short toggle   | Two-button grid; green for long, red for short                           |
| Ticker input          | Debounced 400ms; triggers ADR fetch on change                            |
| Stepper ▲ / ▼         | On Risk %, Entry, Stop Loss; increments by 0.1 (float-safe)             |
| Day Low / High pill   | Toggles `useAutoStop`; label updates with direction; disabled without ADR|
| Reset button          | Restores all fields to defaults                                          |

---

## Deployment

### Backend
1. Push to GitHub
2. Create a new Web Service on [Render](https://render.com) or project on [Railway](https://railway.app)
3. Build command: `pip install -r requirements.txt`
4. Start command: `python server.py` (or via `Procfile`)
5. Note the deployed URL and update `API_BASE` in `index.html`

### Frontend
1. Repo Settings → Pages → Source: `main` branch, root `/`
2. GitHub Pages will serve `index.html` automatically

---

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install yfinance
python server.py
```

Set `API_BASE = 'http://localhost:8080'` in `index.html` for local testing.
