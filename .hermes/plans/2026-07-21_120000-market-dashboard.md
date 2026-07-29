# Crypto Radar Market Dashboard Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a responsive, read-only web dashboard for the existing market-only Crypto Radar: live market snapshots, explainable anomaly signals, event history, and system health — with social/X functionality deliberately excluded from v1.

**Architecture:** Add a small FastAPI application that wraps existing domain objects instead of duplicating signal logic. The API is strictly read-only: it can request a fresh public Hyperliquid snapshot and read the existing SQLite event journal; it has no order, wallet, signing, or mutation endpoints. Build an independent React + TypeScript SPA that consumes that API, uses typed DTOs, and presents a calm, dense dashboard optimized for manual analysis.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, Pydantic v2, pytest; React 18+, TypeScript, Vite, TanStack Query, React Router, Recharts, CSS modules or vanilla CSS with design tokens, Vitest + React Testing Library, Playwright for one browser smoke test.

**Scope boundary (v1):** Include only Hyperliquid market data, market signals, historical event journal, and health. Do not expose X/social posts, source reputation, OAuth state, order endpoints, wallet information, or automatic trading controls.

---

## Current Context

- The project is a Python CLI package; there is no web server or browser client yet.
- `src/crypto_radar/cli.py` currently orchestrates the market snapshot pipeline.
- `src/crypto_radar/providers/hyperliquid.py` supplies public market snapshots.
- `src/crypto_radar/events.py:AlertEventJournal` reads event payloads from SQLite.
- `src/crypto_radar/models.py:Signal` and `src/crypto_radar/serialization.py:signal_to_dict` are the canonical signal contract.
- `pyproject.toml` contains no runtime dependencies.
- Existing automated suite is green (`103 passed` at planning time).

## Product Shape

### Primary user questions

1. **What requires attention now?** — ranked active/current signals.
2. **Why did it trigger?** — factor evidence, basis, confidence and alternate explanations.
3. **What is the latest market state?** — price, funding, OI, volume, and timestamp per tracked asset.
4. **What changed over time?** — event-history filters and detail view.
5. **Is the radar healthy?** — local DB/schema status and last data refresh.

### Routes

| Route | Purpose |
|---|---|
| `/` | Market overview: KPI strip, current signals, asset grid, freshness |
| `/signals` | Filterable current signal list with detail side panel/drawer |
| `/events` | Historical event journal with asset/severity/date filters |
| `/assets/:asset` | Single-asset view: latest metrics, current signals, event timeline |
| `/health` | API, database/schema, provider freshness, app version |

### Interaction and visual rules

- Calm dark-first analyst interface; support light theme only if inexpensive after v1 baseline.
- Severity is semantic and redundant: color + label + icon/text, never color alone.
- High severity is prominent but not alarming; manual review remains visible on every signal.
- Use system typography, tight display-heading tracking, readable tabular figures.
- Use responsive grid: desktop sidebar/filters, mobile bottom sheet or drawer for filters and signal detail.
- Respect `prefers-reduced-motion`; transitions use opacity/short transforms, no decorative chart motion.
- Never render a “Buy”, “Sell”, “Execute”, or wallet-related interaction.

---

## API Contract

Prefix every endpoint with `/api/v1`. Return ISO-8601 UTC strings and explicit `generated_at`/`observed_at` fields. All endpoints are `GET` and JSON-only.

### `GET /api/v1/overview`

Runs a fresh read-only market snapshot through the existing domain pipeline without writing SQLite state by default. Response:

```json
{
  "generated_at": "2026-07-21T10:15:00Z",
  "assets": [
    {
      "asset": "BTC",
      "mark_price": 66340.0,
      "mid_price": 66345.5,
      "funding_rate": 0.0000078277,
      "open_interest": 36691.33892,
      "day_notional_volume": 2614205842.59256
    }
  ],
  "signals": [
    {
      "signal_id": "...",
      "asset": "BTC",
      "signal_type": "composite_market_risk",
      "severity": "medium",
      "fact": "...",
      "basis": "...",
      "confidence": 0.72,
      "possible_explanations": [],
      "source_urls": ["..."],
      "measurements": {},
      "observed_at": "2026-07-21T10:15:00Z",
      "requires_manual_review": true,
      "auto_trade": false
    }
  ],
  "meta": {
    "requested_assets": ["BTC", "ETH", "SOL", "HYPE", "ZEC"],
    "unavailable_assets": []
  }
}
```

### `GET /api/v1/events`

Query params: `asset?: string`, `severity?: low|medium|high`, `limit?: int=50`, `before?: ISO timestamp`.

Response envelope:

```json
{
  "events": [],
  "next_before": null,
  "count": 0
}
```

Filtering happens in an API repository/query helper, not in React.

### `GET /api/v1/assets/{asset}`

Returns the latest live asset metrics, current signals for that asset, and recent events. Unknown/unavailable symbols return a typed 404.

### `GET /api/v1/health`

Returns:

```json
{
  "status": "ok",
  "api_version": "0.1.0",
  "database": { "ok": true },
  "provider": { "name": "hyperliquid", "last_success_at": null },
  "social": { "enabled": false }
}
```

Do not include `xurl`, OAuth status, social tables, or credentials in this frontend-facing endpoint.

---

## Implementation Plan

### Task 1: Add backend web dependencies and application layout

**Objective:** Introduce a minimal HTTP application without changing CLI behavior.

**Files:**
- Modify: `pyproject.toml`
- Create: `src/crypto_radar/web/__init__.py`
- Create: `src/crypto_radar/web/app.py`
- Create: `tests/test_web_app.py`

**Step 1: Write failing test**

```python
from fastapi.testclient import TestClient
from crypto_radar.web.app import create_app


def test_app_exposes_read_only_api_docs():
    response = TestClient(create_app()).get("/api/v1/health")
    assert response.status_code == 200
```

**Step 2: Run RED**

```bash
python3 -m pytest tests/test_web_app.py -q
```

Expected: import failure because the web app does not exist.

**Step 3: Implement minimal app factory**

- Add runtime dependencies: `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `pydantic>=2`.
- Use an explicit `create_app(history_path: Path | None = None) -> FastAPI` factory.
- Store `history_path` in `app.state`; default it from `CRYPTO_RADAR_HISTORY` or `data/crypto_radar.sqlite3`.
- Add only the health router skeleton; do not serve static frontend files yet.

**Step 4: Run GREEN**

```bash
python3 -m pytest tests/test_web_app.py -q
```

**Step 5: Commit**

```bash
git add pyproject.toml src/crypto_radar/web tests/test_web_app.py
git commit -m "feat: add read-only web app factory"
```

---

### Task 2: Extract a reusable market snapshot service from CLI orchestration

**Objective:** Make the existing market-signal pipeline callable from both CLI and API without copy/paste.

**Files:**
- Create: `src/crypto_radar/market_snapshot_service.py`
- Modify: `src/crypto_radar/cli.py`
- Test: `tests/test_market_snapshot_service.py`

**Step 1: Write failing service test**

Use fixture `MarketSnapshot` objects and a fake provider. Assert the service returns:

- normalized asset rows;
- generated composite signals;
- requested/unavailable asset metadata;
- deterministic `observed_at` when passed;
- no database write when `persist=False`.

**Step 2: Run RED**

```bash
python3 -m pytest tests/test_market_snapshot_service.py -q
```

**Step 3: Implement the smallest reusable service**

Create a `MarketSnapshotService` with injected provider and optional history path. Move the logic currently in `cli.main()` that:

- fetches assets;
- collects historical metric values;
- computes spread/turnover;
- generates funding/basis/price components;
- aggregates components;
- applies severity filter;
- appends metric history only when explicitly requested.

Keep alert deduplication and event persistence as CLI-specific behavior initially. The API overview call must use `persist=False`.

**Step 4: Refactor CLI to call service**

Preserve current CLI output and all existing behavior. Do not change signal IDs or market event semantics.

**Step 5: Run tests**

```bash
python3 -m pytest tests/test_market_snapshot_service.py tests/test_cli.py tests/test_market_signals.py -q
python3 -m pytest -q
```

**Step 6: Commit**

```bash
git add src/crypto_radar/market_snapshot_service.py src/crypto_radar/cli.py tests/test_market_snapshot_service.py
git commit -m "refactor: extract reusable market snapshot service"
```

---

### Task 3: Define explicit API DTOs and overview endpoint

**Objective:** Publish a stable, typed, read-only overview response.

**Files:**
- Create: `src/crypto_radar/web/schemas.py`
- Create: `src/crypto_radar/web/routers/overview.py`
- Modify: `src/crypto_radar/web/app.py`
- Test: `tests/test_web_overview.py`

**Step 1: Write failing endpoint test**

Inject a fixture provider/service through `app.dependency_overrides` and assert:

```python
def test_overview_returns_assets_signals_and_utc_generation_time(client):
    response = client.get("/api/v1/overview?assets=BTC,ETH")
    assert response.status_code == 200
    body = response.json()
    assert [item["asset"] for item in body["assets"]] == ["BTC", "ETH"]
    assert body["signals"][0]["auto_trade"] is False
    assert body["signals"][0]["requires_manual_review"] is True
    assert body["generated_at"].endswith("Z")
```

**Step 2: Run RED**

```bash
python3 -m pytest tests/test_web_overview.py -q
```

**Step 3: Implement DTOs and route**

- Define Pydantic models for asset metric, signal, overview meta, and overview response.
- Reuse `signal_to_dict` for signal conversion, then validate with the DTO.
- Validate `assets` input: uppercase, comma-separated, non-empty, max 20.
- Map provider failure to HTTP 503 with a non-sensitive JSON error.
- Set `Cache-Control: no-store` on live overview.

**Step 4: Run GREEN and regression suite**

```bash
python3 -m pytest tests/test_web_overview.py -q
python3 -m pytest -q
```

**Step 5: Commit**

```bash
git add src/crypto_radar/web tests/test_web_overview.py
git commit -m "feat: expose market overview API"
```

---

### Task 4: Add event-history repository filters and API endpoint

**Objective:** Give the frontend paginated, server-filtered market event history.

**Files:**
- Modify: `src/crypto_radar/events.py`
- Create: `src/crypto_radar/web/routers/events.py`
- Modify: `src/crypto_radar/web/schemas.py`
- Test: `tests/test_web_events.py`
- Test: `tests/test_event_journal.py`

**Step 1: Write failing repository tests**

Test combinations of:

- asset filter;
- severity filter;
- `before` cursor;
- invalid cursor;
- limit caps;
- descending `recorded_at` order.

**Step 2: Run RED**

```bash
python3 -m pytest tests/test_event_journal.py tests/test_web_events.py -q
```

**Step 3: Extend `AlertEventJournal` minimally**

Add `list_events_page(asset=None, severity=None, before=None, limit=50)`. Query indexed columns first; filter severity in SQL using the stored `severity` column. Return decoded payload and a `next_before` cursor based on the final record.

**Step 4: Implement `GET /api/v1/events`**

- Parse query params through Pydantic/FastAPI validation.
- Enforce `1 <= limit <= 100`.
- Return event payloads with `event_id`, `recorded_at`, and standard signal fields.
- Return 422 for invalid filter values.

**Step 5: Run GREEN/full suite**

```bash
python3 -m pytest tests/test_event_journal.py tests/test_web_events.py -q
python3 -m pytest -q
```

**Step 6: Commit**

```bash
git add src/crypto_radar/events.py src/crypto_radar/web tests/test_event_journal.py tests/test_web_events.py
git commit -m "feat: add filtered market event API"
```

---

### Task 5: Add asset-detail and health endpoints

**Objective:** Support a useful asset route and operational UI without exposing social/OAuth internals.

**Files:**
- Create: `src/crypto_radar/web/routers/assets.py`
- Create: `src/crypto_radar/web/routers/health.py`
- Modify: `src/crypto_radar/web/app.py`
- Modify: `src/crypto_radar/web/schemas.py`
- Test: `tests/test_web_assets.py`
- Test: `tests/test_web_health.py`

**Step 1: Write failing tests**

- `GET /api/v1/assets/BTC` returns current metrics, only BTC signals, and recent BTC events.
- Unknown asset returns 404 `{ "detail": "Asset not found" }`.
- Health response has `status`, `database.ok`, provider name, and `social.enabled=false`.

**Step 2: Run RED**

```bash
python3 -m pytest tests/test_web_assets.py tests/test_web_health.py -q
```

**Step 3: Implement endpoints**

- Reuse overview service data; do not create an alternate signal-calculation path.
- Health checks SQLite connectivity and required market tables only.
- Do not invoke `xurl` or `doctor_report()` from the public web health endpoint.

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_web_assets.py tests/test_web_health.py -q
python3 -m pytest -q
```

**Step 5: Commit**

```bash
git add src/crypto_radar/web tests/test_web_assets.py tests/test_web_health.py
git commit -m "feat: add asset detail and market health APIs"
```

---

### Task 6: Scaffold the React application and typed API client

**Objective:** Create a strict TypeScript frontend that can develop against a local API.

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/lib/api.ts`
- Create: `web/src/lib/types.ts`
- Create: `web/src/test/setup.ts`
- Create: `web/src/lib/api.test.ts`
- Create: `web/.env.example`

**Step 1: Bootstrap**

Use Vite React TypeScript template in a temporary directory, then copy only needed files. Do not commit `node_modules`.

Dependencies:

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5",
    "react": "^18 || ^19",
    "react-dom": "^18 || ^19",
    "react-router-dom": "^6 || ^7",
    "recharts": "^2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6",
    "@testing-library/react": "^16",
    "@types/react": "^18 || ^19",
    "@types/react-dom": "^18 || ^19",
    "typescript": "^5",
    "vite": "^6",
    "vitest": "^3"
  }
}
```

**Step 2: Write failing API-client tests**

Mock `fetch` and assert `getOverview()`:

- requests `/api/v1/overview`;
- passes selected assets;
- throws a typed `ApiError` on non-2xx;
- parses the canonical Signal fields.

**Step 3: Run RED**

```bash
cd web && npm test -- --run src/lib/api.test.ts
```

**Step 4: Implement typed client**

- API base defaults to same-origin `/api/v1`; env override is `VITE_API_BASE_URL`.
- Keep frontend types structurally aligned with backend DTOs.
- Never derive severity or calculate confidence in the browser.

**Step 5: Run tests/build**

```bash
cd web && npm test -- --run
cd web && npm run build
```

**Step 6: Commit**

```bash
git add web
git commit -m "feat: scaffold typed market dashboard client"
```

---

### Task 7: Establish dashboard tokens, shell, and accessible shared primitives

**Objective:** Build the visual system before feature pages.

**Files:**
- Create: `web/src/styles/tokens.css`
- Create: `web/src/styles/global.css`
- Create: `web/src/components/AppShell.tsx`
- Create: `web/src/components/SeverityBadge.tsx`
- Create: `web/src/components/MetricValue.tsx`
- Create: `web/src/components/LoadingState.tsx`
- Create: `web/src/components/ErrorState.tsx`
- Create: `web/src/components/EmptyState.tsx`
- Test: `web/src/components/SeverityBadge.test.tsx`

**Step 1: Write failing primitive tests**

Assert that severity is visible as text and not color-only:

```tsx
render(<SeverityBadge severity="high" />)
expect(screen.getByText("High")).toBeVisible()
expect(screen.getByLabelText("Severity: high")).toBeVisible()
```

**Step 2: Implement design tokens**

- Neutral charcoal/slate background, elevated surface, high-contrast text.
- Severity tokens: low/medium/high with WCAG-compliant text colors.
- 4/8/12/16/24/32 spacing scale.
- System font stack and tabular figures (`font-variant-numeric: tabular-nums`).
- `prefers-reduced-motion` removes transform animation.
- No glass/translucent surface stacked on another translucent surface.

**Step 3: Implement application shell**

- Desktop: persistent left navigation and top status bar.
- Mobile: compact header, navigation sheet or bottom navigation.
- Current page title and refreshed time always visible.

**Step 4: Run tests/build**

```bash
cd web && npm test -- --run
cd web && npm run build
```

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add dashboard visual system and shell"
```

---

### Task 8: Build the overview dashboard

**Objective:** Answer “what matters now?” in one screen.

**Files:**
- Create: `web/src/pages/OverviewPage.tsx`
- Create: `web/src/components/OverviewKpis.tsx`
- Create: `web/src/components/SignalTable.tsx`
- Create: `web/src/components/AssetMetricGrid.tsx`
- Create: `web/src/components/SignalDetailDrawer.tsx`
- Create: `web/src/hooks/useOverview.ts`
- Test: `web/src/pages/OverviewPage.test.tsx`

**Step 1: Write failing page tests**

Mock overview response and assert:

- generated timestamp appears;
- high-severity signal is first;
- click/tap signal opens detail drawer;
- drawer shows `fact`, `basis`, confidence, source links, possible explanations, and manual-review notice;
- `auto_trade` is never rendered as a control.

**Step 2: Implement data query**

- `useQuery` with `refetchInterval: 60_000`.
- Preserve old data during refetch.
- Add manual “Refresh” button with disabled/loading state.
- Show API failure in an error state without erasing last successful data.

**Step 3: Implement layout**

1. Header: title, selected asset chips, refresh time/button.
2. KPI row: signals by severity, assets tracked, market refresh freshness.
3. Primary table: asset, severity, confidence, signal type, observed time, concise basis preview.
4. Asset metric grid: price, funding, OI, 24h volume.
5. Detail drawer: full evidence and measured inputs.

**Step 4: Run tests/build**

```bash
cd web && npm test -- --run src/pages/OverviewPage.test.tsx
cd web && npm run build
```

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add market overview dashboard"
```

---

### Task 9: Build signal explorer and event history pages

**Objective:** Make historical review and drill-down fast without loading all events at once.

**Files:**
- Create: `web/src/pages/SignalsPage.tsx`
- Create: `web/src/pages/EventsPage.tsx`
- Create: `web/src/components/SignalFilters.tsx`
- Create: `web/src/components/EventTimeline.tsx`
- Create: `web/src/hooks/useEvents.ts`
- Test: `web/src/pages/EventsPage.test.tsx`

**Step 1: Write failing tests**

- Asset and severity filters alter API query parameters.
- “Load more” appends a second page using `next_before`.
- Empty result has a clear no-events state.
- Selecting an event opens the same evidence/detail presentation used by overview (reuse component).

**Step 2: Implement filters and query state**

- Persist filters in URL query parameters: `?asset=BTC&severity=high`.
- Use TanStack Query `useInfiniteQuery` for cursored events.
- Do not fetch all history on initial page load.

**Step 3: Implement pages**

- `/signals`: current overview results with full filters and table/card responsive mode.
- `/events`: timeline/table showing observed vs recorded time, severity, asset, and signal ID.

**Step 4: Run tests/build**

```bash
cd web && npm test -- --run src/pages/EventsPage.test.tsx
cd web && npm run build
```

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add signal explorer and event history"
```

---

### Task 10: Build asset detail and health pages

**Objective:** Provide focused asset research and transparent system state.

**Files:**
- Create: `web/src/pages/AssetPage.tsx`
- Create: `web/src/pages/HealthPage.tsx`
- Create: `web/src/components/MetricChart.tsx`
- Create: `web/src/hooks/useAsset.ts`
- Create: `web/src/hooks/useHealth.ts`
- Test: `web/src/pages/AssetPage.test.tsx`
- Test: `web/src/pages/HealthPage.test.tsx`

**Step 1: Write failing tests**

- Asset page shows 404 state for unavailable asset.
- Asset page shows metrics and filtered recent events.
- Health page shows database/provider status but no X/social/OAuth controls or text.

**Step 2: Implement asset page**

- Route param is uppercased and validated.
- Show current metrics and latest signals.
- Add a small Recharts visualization only for data already supplied by API; do not fabricate a time series.
- If no historical series endpoint exists yet, show event timeline rather than fake price chart.

**Step 3: Implement health page**

- Display API version, database status, provider status, and refresh timestamp.
- Explain errors in plain language.

**Step 4: Run tests/build**

```bash
cd web && npm test -- --run src/pages/AssetPage.test.tsx src/pages/HealthPage.test.tsx
cd web && npm run build
```

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add asset research and health pages"
```

---

### Task 11: Add production serving, developer workflow, and end-to-end smoke test

**Objective:** Make frontend/API runnable together and verify the critical user journey in a browser.

**Files:**
- Modify: `src/crypto_radar/web/app.py`
- Create: `web/playwright.config.ts`
- Create: `web/e2e/overview.spec.ts`
- Create: `scripts/run_dashboard.sh`
- Modify: `README.md`
- Modify: `.gitignore`

**Step 1: Decide serving model**

For v1 production, FastAPI serves the built Vite `web/dist` directory and falls back to `index.html` for client routes. In development, Vite proxies `/api` to Uvicorn.

**Step 2: Write failing Playwright smoke test**

```ts
test("analyst can inspect a current signal", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: /market overview/i })).toBeVisible()
  await page.getByRole("row").filter({ hasText: /BTC|ETH|SOL|HYPE|ZEC/ }).first().click()
  await expect(page.getByText(/manual review/i)).toBeVisible()
})
```

Mock API data in the browser test or use a fixture-injected backend; do not depend on a live market call for CI.

**Step 3: Implement static serving and scripts**

`scripts/run_dashboard.sh` should:

1. run `npm run build` in `web/` when `web/dist` is missing or `BUILD_FRONTEND=1`;
2. export `PYTHONPATH=src`;
3. start `uvicorn crypto_radar.web.app:create_app --factory --host 127.0.0.1 --port 8000`.

Avoid shell backgrounding in the script; it is a foreground process suitable for Hermes process tracking.

**Step 4: Update README**

Document:

```bash
# terminal 1
PYTHONPATH=src uvicorn crypto_radar.web.app:create_app --factory --reload

# terminal 2
cd web && npm install && npm run dev
```

And production-like run:

```bash
./scripts/run_dashboard.sh
```

**Step 5: Verify**

```bash
python3 -m pytest -q
cd web && npm test -- --run
cd web && npm run build
cd web && npx playwright test
```

Then start the API and use a browser smoke check against `http://127.0.0.1:8000`.

**Step 6: Commit**

```bash
git add src/crypto_radar/web web scripts README.md .gitignore
git commit -m "feat: ship market dashboard"
```

---

## Acceptance Criteria

### Functional

- [ ] Dashboard is usable at one URL after a documented local start command.
- [ ] Overview displays fresh public Hyperliquid metrics for selected assets.
- [ ] Current market signals are visible, severity-ranked, and drillable.
- [ ] Every signal detail shows `fact`, `basis`, confidence, source URLs, possible explanations, observed time, and manual-review state.
- [ ] Events page supports asset/severity filters and cursor pagination.
- [ ] Asset detail route works and invalid assets return a clear empty/404 state.
- [ ] Health page displays database and provider status.
- [ ] No API or UI path can place trades, sign transactions, access wallet keys, or show social/OAuth credentials.

### Quality

- [ ] Python full suite remains green.
- [ ] API endpoint tests cover happy path, input validation, provider failure, and SQLite event filtering.
- [ ] Frontend unit tests cover severity accessibility, overview rendering, signal detail, filters, and error/empty states.
- [ ] One Playwright critical-path test passes with deterministic fixture data.
- [ ] `npm run build` completes with strict TypeScript checking.
- [ ] Mobile viewport (360px), tablet, and desktop layouts are manually inspected.
- [ ] Keyboard focus is visible; drawer can close with Escape; severity never relies on color alone.

---

## Risks and Decisions

1. **Fresh snapshot writes vs read-only UI:** The API overview must not mutate history by default. A future scheduled collector should write history/events; the dashboard reads its output.
2. **SQLite concurrency:** SQLite is appropriate for the current single-node MVP. Enable WAL mode only after adding a focused test and observing concurrent API/collector access; do not add it preemptively.
3. **Live API availability:** Hyperliquid failures should render a stale-data/error state, never crash the SPA. CI must use fixture providers.
4. **Chart scope:** Do not show price charts until a dedicated historical-price API exists. Event timelines are truthful and useful with current data.
5. **Auth:** v1 assumes localhost/private network access. Add authentication before exposing the dashboard publicly; do not mix auth work into the initial dashboard slice.
6. **Social:** Keep `social.enabled=false` and leave social routes/UI absent. This preserves a clean extension point without exposing unfinished X/OAuth functionality.

## Phase 2 (not part of this implementation)

- Scheduled market collector process and last-success tracking.
- Historical metric endpoints and asset price/funding/OI charts.
- WebSocket or server-sent refresh notifications.
- Alert delivery integrations (Telegram/email) with user-configured thresholds.
- Login/RBAC, multi-user watchlists, and public deployment hardening.
- Reintroduction of social signals as a separately permissioned tab only after X OAuth and live smoke are complete.
