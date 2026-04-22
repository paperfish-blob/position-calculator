# Position Sizing Calculator — Spec

**Live app:** https://paperfish-blob.github.io/position-calculator/

A risk-based position sizing tool that computes how many shares to buy (long) or sell short given a defined account risk.

---

## Architecture

| Layer    | Technology                          | Hosting         |
|----------|-------------------------------------|-----------------|
| Frontend | Plain HTML + vanilla JS (no build)  | GitHub Pages    |
| Backend  | Python stdlib `http.server`         | Render / Railway |

---

## State

| Variable       | Type                | Default    | Purpose                                             |
|----------------|---------------------|------------|-----------------------------------------------------|
| `direction`    | `'long' \| 'short'` | `'long'`   | Trade direction toggle                              |
| `accountEquity`| `string`            | `'40000'`  | Account size in USD                                 |
| `riskPct`      | `string`            | `'0.33'`   | Risk per trade as a % of equity                     |
| `entry`        | `string`            | `''`       | Entry price per share                               |
| `stopLoss`     | `string`            | `''`       | Stop loss price per share                           |
| `ticker`       | `string`            | `''`       | Optional ticker symbol for ADR lookup               |
| `adrData`      | `object \| null`    | `null`     | ADR response from backend (populated on lookup)     |
| `adrLoading`   | `boolean`           | `false`    | Loading state while ADR fetch is in-flight          |
| `adrError`     | `boolean`           | `false`    | True when last ADR fetch returned an error / 404    |
| `useAutoStop`  | `boolean`           | `false`    | When enabled, syncs stop loss to day low/high       |
| `useAutoEntry` | `boolean`           | `false`    | When enabled, syncs entry price to last close price |
| `useAutoHigh`  | `boolean`           | `false`    | When enabled, syncs entry price to day_high         |

---

## Computed Result

Recalculated reactively whenever any input changes. Returns `null` if any input is missing/invalid or if `riskPerShare <= 0`.

```
riskDollars  = accountEquity × (riskPct / 100)
riskPerShare = entry − stopLoss        (long)
             = stopLoss − entry        (short)
quantity     = floor(riskDollars / riskPerShare)
totalValue   = quantity × entry
capitalPct   = (totalValue / accountEquity) × 100
pivotPct     = (stopLoss − entry) / entry × 100
thirdStop    = entry − riskPerShare / 3   (long)
             = entry + riskPerShare / 3   (short)
earlyStop    = entry − riskPerShare / 2       (long)
             = entry + riskPerShare / 2       (short)
twoThirdStop = entry − riskPerShare × 2 / 3  (long)
             = entry + riskPerShare × 2 / 3  (short)
adrTarget    = entry × (1 + adr_pct / 100)         (requires adrData)
adrTarget15  = entry × (1 + adr_pct × 1.5 / 100)  (requires adrData)
adrTarget2   = entry × (1 + adr_pct × 2   / 100)  (requires adrData)
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
  "day_high": 172.80,
  "current_price": 171.25
}
```

### Error responses

| Status | Body                                          | When                              |
|--------|-----------------------------------------------|-----------------------------------|
| 400    | `{"error": "ticker required"}`                | Empty ticker segment in path      |
| 404    | `{"error": "ticker not found or insufficient data"}` | yfinance returns empty DataFrame  |
| 500    | `{"error": "internal server error"}`          | Unexpected exception              |

---

## Auto-Stop / Auto-Entry Features

Both are applied by mutating state directly at the top of `render()` before computing derived values, avoiding re-entrant `setState` calls.

### Auto-Stop (`useAutoStop`)

When toggled on and `adrData` is available:
- **Long:** `stopLoss` → `adrData.day_low`
- **Short:** `stopLoss` → `adrData.day_high`

Toggling direction resets `useAutoStop` to `false`.

### Auto-Entry (`useAutoEntry`)

When toggled on and `adrData` is available:
- **Both directions:** `entry` → `adrData.current_price` (last close)

Toggling direction or activating Auto-High resets `useAutoEntry` to `false`.

### Auto-High (`useAutoHigh`)

When toggled on and `adrData` is available:
- **Both directions:** `entry` → `adrData.day_high`

Toggling direction or activating Auto-Entry resets `useAutoHigh` to `false`.

---

## Displayed Outputs

| Field           | Shown when          | Value                                                      |
|-----------------|---------------------|------------------------------------------------------------|
| Shares to Trade | Result is valid     | `floor(riskDollars / riskPerShare)`                        |
| Risk $          | Result is valid     | Dollar risk amount                                         |
| % of Capital    | Result is valid     | `(totalValue / accountEquity) × 100`                       |
| Total Position  | Result is valid     | Total position value at entry                              |
| Pivot %         | Result is valid     | % distance from entry to stop (red if negative)            |
| ADR %           | ADR data available  | 20-day average daily range as % of close                   |
| xADR            | Result + ADR valid  | `adr_pct / abs(pivotPct)` — how many ADRs the stop is away |
| ⅓ Risk Stop     | Result is valid     | Price at which one-third of the risk is realised (`thirdStop`) |
| ½ Risk Stop     | Result is valid     | Price at which half the risk is realised (`earlyStop`)             |
| ⅔ Risk Stop     | Result is valid     | Price at which two-thirds of the risk is realised (`twoThirdStop`)  |
| Entry + ADR     | Result + ADR valid  | Upside target: entry + 1× ADR (`adrTarget`)                        |
| Entry + ADR×1.5 | Result + ADR valid  | Upside target: entry + 1.5× ADR (`adrTarget15`)                    |
| Entry + ADR×2   | Result + ADR valid  | Upside target: entry + 2× ADR (`adrTarget2`)                       |

---

## UI Controls

| Control               | Behavior                                                                               |
|-----------------------|----------------------------------------------------------------------------------------|
| Long / Short toggle   | Two-button grid; green for long, red for short; resets both auto pills on change       |
| Ticker input          | Debounced 400ms; triggers ADR fetch on change; clears adrData/adrError while typing    |
| Load timer            | Shows elapsed seconds next to the spinner while an ADR fetch is in-flight              |
| Stepper ▲ / ▼         | On Risk %, Entry, Stop Loss; increments by 0.1 (float-safe)                           |
| Day Low / High pill   | Toggles `useAutoStop`; label is "Day Low" (long) / "Day High" (short); disabled without ADR |
| Last pill             | Toggles `useAutoEntry`; sets entry to `current_price`; disabled without ADR; mutually exclusive with High pill |
| High pill             | Toggles `useAutoHigh`; sets entry to `day_high`; disabled without ADR; mutually exclusive with Last pill      |
| Reset (✕) button      | Clears the ticker field and restores all state to defaults                             |

---

## Deployment

### Backend — Render

1. Go to [render.com](https://render.com) and sign up / log in with GitHub
2. Click **New** → **Web Service**
3. Connect the `paperfish-blob/position-calculator` repo
4. Configure:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python server.py` (or leave blank — `Procfile` handles it)
   - **Instance type:** Free
5. Click **Create Web Service** and wait ~2 min for the first deploy
6. Copy the deployed URL (e.g. `https://position-calculator-api.onrender.com`)
7. Update `API_BASE` in `index.html` to that URL, then commit and push

> **Note:** The free Render tier spins down after 15 min of inactivity. The first ADR lookup after idle takes ~30 seconds to wake up.

### Frontend — GitHub Pages

1. Push the repo to GitHub
2. Go to repo **Settings** → **Pages** (left sidebar)
3. Under *Branch*, select `main` / `/ (root)` → **Save**
4. Wait ~60 seconds — the app is live at:
   **https://paperfish-blob.github.io/position-calculator/**

> Subsequent pushes to `main` redeploy GitHub Pages automatically.

---

## Known Limitations

### Manual Redeploy on Render
If the live API is not reflecting recent `server.py` changes, trigger a manual redeploy:
1. Go to [render.com](https://render.com) → your `position-calculator-api` service
2. Click **Manual Deploy** → **Deploy latest commit**
3. Wait ~2 min for the build to finish

---

### Render Free Tier — Cold Start
The backend is hosted on Render's free tier, which spins the server down after 15 minutes of inactivity. The first request after idle takes ~20–30 seconds to wake up. To mitigate this, `index.html` fires a silent warm-up ping to `/api/adr/SPY` on every page load so the server starts waking before the user types a ticker.

#### Keep-Alive via UptimeRobot (recommended)

UptimeRobot is a free external monitoring service that pings on a real clock — unlike GitHub Actions cron, which can be delayed by 15–30 minutes and is unreliable for sub-15-minute keep-alives.

**Setup (one-time):**

1. Sign up at [uptimerobot.com](https://uptimerobot.com) (free tier supports up to 50 monitors at 5-min intervals)
2. Click **Add New Monitor** with these settings:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `Render Backend - Position Calculator`
   - **URL:** `https://position-calculator-api.onrender.com/api/adr/SPY`
   - **Monitoring Interval:** `5 minutes`
3. Save — UptimeRobot will show a green "Up" status within the first ping cycle (~5 min)

**Verification:**
- Wait 5–10 minutes after setup and confirm green status on the UptimeRobot dashboard
- Response time should appear in the dashboard (expected: <3s on a warm instance)
- Open the live app and fetch a ticker — response should be ~200–500ms instead of the 30–60s cold-start delay

> The GitHub Actions workflow (`.github/workflows/keep-alive.yml`) is kept for manual testing but its cron schedule is disabled — UptimeRobot fully replaces it.

If cold starts are still unacceptable, upgrade to Render's paid tier ($7/mo) which has no spin-down.

#### Keep-Alive Cron Job
A GitHub Actions workflow (`.github/workflows/keep-alive.yml`) pings the backend every 8 minutes to prevent spin-down:

```
GET https://position-calculator-api.onrender.com/api/adr/SPY
```

The schedule (`*/8 * * * *`) keeps well under Render's 15-minute threshold, accounting for occasional GitHub Actions scheduling delays. Because the repo is public, this uses zero paid Actions minutes.

To test it manually: go to repo → **Actions** → "Keep Render Backend Alive" → **Run workflow**.

#### Verifying the schedule
Scheduled runs appear in the **Actions** tab with timestamps — you should see entries ~8 minutes apart. Note that GitHub Actions cron schedules are often delayed on newly pushed workflows, sometimes up to 15–30 minutes before the first scheduled run fires. After that initial delay, it settles into the 8-minute cadence.

- GitHub doesn't guarantee exact cron timing — it queues jobs when runners are available
- For low-traffic or new repos, the first few scheduled runs can be slow to appear
- If no scheduled runs appear after ~1 hour, that would indicate a problem

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install yfinance
python server.py
```

Set `API_BASE = 'http://localhost:8080'` in `index.html` for local testing.
