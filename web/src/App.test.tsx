import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import App, { CandleFreshness, candleClosedAgeLabel, candleFreshnessStatus, forwardValidationStatus, forwardValidationStatusLabel, indicatorSnapshotAgeLabel, indicatorSnapshotStatus, scoreDistribution } from "./App"

const overview = {
  generated_at: "2026-07-21T12:00:00Z",
  assets: [{ asset: "BTC", mark_price: 65000, mid_price: 64990, funding_rate: 0.00001, open_interest: 40000, day_notional_volume: 2000000000 }],
  signals: [{ signal_id: "signal-1", asset: "BTC", signal_type: "composite_market_risk", signal_class: "composite", fact: "Давление финансирования повышено.", basis: "Funding elevated", source_urls: ["https://example.com/source"], severity: "high", confidence: 0.8, possible_explanations: [], requires_manual_review: true, auto_trade: false, measurements: { drivers: [{ fact: "Funding elevated" }] }, market_direction: "снижение", observed_at: "2026-07-21T12:00:00Z", evidence_metadata: { source_count: 1, has_sources: true, confidence: 0.8, requires_manual_review: true } }], meta: { requested_assets: ["BTC"], unavailable_assets: [] },
}

function renderApp(entry = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={client}><App /></QueryClientProvider></MemoryRouter>)
}

function mockOverview() {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((input: RequestInfo | URL) => {
    if (String(input).includes("/overview")) return Promise.resolve(new Response(JSON.stringify(overview), { status: 200 }))
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  }))
}

function mockAssetWorkspace() {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes("/assets/BTC/indicators")) return Promise.resolve(new Response(JSON.stringify({ asset: "BTC", generated_at: "2026-07-21T12:00:00Z", signals: [{ signal_id: "indicator-1", asset: "BTC", signal_type: "multi_timeframe_indicators", signal_class: "technical", fact: "Индикаторы BTC на 1h", basis: "DeMark and TD", source_urls: ["https://example.com/candles"], severity: "medium", confidence: 0.72, possible_explanations: [], requires_manual_review: true, auto_trade: false, measurements: { timeframe: "1h", demark: 0.131, demark_direction: "лонг", demark_zone: "oversold", volume_ratio: 3.29, volume_regime: "повышенный", rei: -23.7, rei_regime: "neutral", demark_exhaustion: "none", td_structure: { td_demand_line: 63802, td_supply_line: 63952, demand_breakout: "false", supply_breakout: "false" }, td_retracement: { retracement_zone: "below_618", retracement_382: 63928.69, retracement_618: 63880.31 }, td_scenario: { scenario: "none", reason: "conditions_not_confirmed" }, direction_agreement: true, closed_candle_count: 80, candle_open_time: 1721642400000, td_sequential: { signal_state: "completed", buy_setup_count: 8, sell_setup_count: 0, buy_countdown: 13, sell_countdown: 0, buy_entry_at_countdown_close: 64980, buy_entry_price: 65025 } }, market_direction: "лонг", observed_at: "2026-07-21T12:00:00Z", evidence_metadata: { source_count: 1, has_sources: true, confidence: 0.72, requires_manual_review: true } }], aggregate: { market_direction: "лонг", direction_score: 42, data_quality: 88, quality_label: "высокое", direction_agreement: false, confirmed_timeframes: [], basis: "Weighted agreement", horizons: { local: { direction: "лонг", timeframes: ["1m", "10m"], status: "согласован" }, tactical: { direction: "шорт", timeframes: ["1h", "6h"], status: "конфликт" }, strategic: { direction: "нейтральное", timeframes: ["1d", "1w"], status: "частично" } } } }), { status: 200 }))
    if (url.includes("/assets/BTC/levels")) return Promise.resolve(new Response(JSON.stringify({ asset: "BTC", levels: [{ period: "day", strength: "strong", support: 64000, resistance: 67000, start: "2026-07-20", end: "2026-07-21" }] }), { status: 200 }))
    if (url.includes("/assets/BTC/history")) return Promise.resolve(new Response(JSON.stringify({ asset: "BTC", metrics: { mark_price: [{ observed_at: 1, value: 64000 }, { observed_at: 2, value: 65000 }] } }), { status: 200 }))
    if (url.includes("/assets/BTC") && !url.includes("dataset")) return Promise.resolve(new Response(JSON.stringify({ generated_at: "2026-07-21T12:00:00Z", asset: overview.assets[0], signals: overview.signals, events: [] }), { status: 200 }))
    if (url.includes("/dataset")) return Promise.resolve(new Response(JSON.stringify({ asset: "BTC", count: 0, label_status: "unlabeled", read_only: true, readiness: { "1h": { ready_count: 0, pending_count: 0, data_gap_count: 1, coverage_pct: 0 }, "6h": { ready_count: 0, pending_count: 1, data_gap_count: 0, coverage_pct: 0 }, "1d": { ready_count: 0, pending_count: 0, data_gap_count: 0, coverage_pct: 0 }, "1w": { ready_count: 0, pending_count: 0, data_gap_count: 0, coverage_pct: 0 } }, training_readiness: { min_samples: 10, min_coverage_pct: 80, horizons: { "1h": { status: "blocked", ready_count: 0, coverage_pct: 0, reasons: ["data_gap"] }, "6h": { status: "blocked", ready_count: 0, coverage_pct: 0, reasons: ["pending_outcomes"] }, "1d": { status: "blocked", ready_count: 0, coverage_pct: 0, reasons: [] }, "1w": { status: "ready", ready_count: 10, coverage_pct: 100, reasons: [] } } }, training_preparation: { "1h": { status: "blocked", horizon: "1h", ready_count: 0, coverage_pct: 0, reasons: ["data_gap"] }, "6h": { status: "blocked", horizon: "6h", ready_count: 0, coverage_pct: 0, reasons: ["pending_outcomes"] }, "1d": { status: "blocked", horizon: "1d", ready_count: 0, coverage_pct: 0, reasons: [] }, "1w": { status: "ready", horizon: "1w", ready_count: 10, coverage_pct: 100, reasons: [] } }, event_type_breakdown: { general: { count: 4, sample_status: "insufficient_sample", score_distribution: { positive: 1, neutral: 2, negative: 1 }, by_horizon: Object.fromEntries(["1h", "6h", "1d", "1w"].map(horizon => [horizon, { ready_count: horizon === "1h" ? 3 : 1, pending_count: horizon === "1h" ? 1 : 3, data_gap_count: 0, coverage_pct: horizon === "1h" ? 75 : 25, average_return_pct: horizon === "1h" ? 0.4 : null, quality_status: "insufficient_sample", positive_rate_pct: null, negative_rate_pct: null, flat_rate_pct: null, directional_accuracy_pct: null, directional_sample_count: null, directional_accuracy_ci95_pct: null }])) } }, records: [] }), { status: 200 }))
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  }))
}

describe("new Signal Room UI", () => {
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
  it("renders decision-first overview with safety and evidence paths", async () => {
    mockOverview(); renderApp()
    expect(await screen.findByRole("heading", { name: "Обзор рынка" })).toBeVisible()
    expect(screen.getByText("READ")).toBeVisible()
    expect(screen.getAllByText("Давление финансирования повышено.")[0]).toBeVisible()
    expect(screen.getByText("manual review required")).toBeVisible()
    expect(screen.getByRole("link", { name: "Открыть evidence →" })).toHaveAttribute("href", "/asset/BTC?from=overview&asset=BTC")
    expect(screen.getByRole("link", { name: "Analyze ↗" })).toHaveAttribute("href", "/asset/BTC?from=overview&asset=BTC")
    expect(screen.getByRole("heading", { name: "Market universe" })).toBeVisible()
  })

  it("keeps evidence collapsed until analyst opens it", async () => {
    mockOverview(); renderApp("/signals")
    expect(await screen.findByRole("heading", { name: "Сигналы" })).toBeVisible()
    const summary = screen.getAllByText("Показать основание и источники")[0]
    expect(summary.closest("details")).not.toHaveAttribute("open")
    fireEvent.click(summary)
    expect(screen.getAllByText("Funding elevated")[1]).toBeVisible()
    expect(screen.getByText("example.com")).toBeVisible()
  })

  it("refreshes indicator candles every minute while the asset workspace is open", async () => {
    vi.useFakeTimers()
    mockAssetWorkspace(); renderApp("/asset/BTC")
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByRole("heading", { name: "BTC" })).toBeVisible()
    const fetchMock = vi.mocked(fetch)
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/assets/BTC/indicators"))).toHaveLength(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/assets/BTC/indicators"))).toHaveLength(2)
    vi.useRealTimers()
  })

  it("renders the asset evidence workspace with consensus, levels and history", async () => {
    mockAssetWorkspace(); renderApp("/asset/BTC?from=signals&asset=BTC&timeframe=1h")
    expect(await screen.findByRole("heading", { name: "BTC" })).toBeVisible()
    expect(screen.getByText("Signal context · 1h")).toBeVisible()
    expect(screen.getByRole("link", { name: "← Вернуться к сигналам" })).toHaveAttribute("href", "/signals?asset=BTC&timeframe=1h")
    expect(screen.getByRole("link", { name: "Analyze ↗" })).toHaveAttribute("href", "/asset/BTC?from=signals&asset=BTC&timeframe=1h")
    expect(screen.getByText("focused · 1h")).toBeVisible()
    expect(screen.getByText("SELECTED FROM SIGNALS")).toBeVisible()
    expect(screen.getByRole("heading", { name: "Multi-timeframe consensus" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Основные индикаторы" })).toBeVisible()
    expect(screen.getByLabelText("Последнее обновление индикаторов")).toHaveTextContent(/21 июл\. 2026 г\./)
    expect(screen.getByText("0.131")).toBeVisible()
    expect(screen.getByText("Buy 8/9 · Buy 13/13")).toBeVisible()
    expect(screen.getByText("3.29×")).toBeVisible()
    const details = screen.getByText("Показать TD / REI evidence")
    expect(details.closest("details")).not.toHaveAttribute("open")
    fireEvent.click(details)
    expect(screen.getByText(/demand/)).toBeVisible()
    expect(screen.getByText(/below_618/)).toBeVisible()
    expect(screen.getByText("-23.7")).toBeVisible()
    expect(screen.getByLabelText("Фактический вход")).toHaveTextContent(/65\s*025/)
    expect(screen.getByLabelText("Источник баров")).toHaveTextContent(/80 закрытых OHLCV-свечей/)
    expect(screen.getByLabelText("Последний закрытый бар")).toHaveTextContent(/22 июл\. 2024 г\./)
    expect(screen.getByLabelText("Закрытие последнего бара")).toHaveTextContent(/22 июл\. 2024 г\./)
    expect(screen.getByLabelText("Следующее ожидаемое закрытие")).toHaveTextContent(/22 июл\. 2024 г\./)
    expect(screen.getByText("weighted direction: лонг")).toBeVisible()
    expect(screen.getByText("Weighted agreement")).toBeVisible()
    expect(screen.getByText("нет данных")).toBeVisible()
    expect(screen.getByText("ожидается")).toBeVisible()
    expect(screen.getByText("training blocked · data_gap")).toBeVisible()
    expect(screen.getByText(/1h: 3 ready · 1 pending · 0 gap · insufficient sample/)).toBeVisible()
    expect(screen.getByText(/6h: 1 ready · 3 pending · 0 gap · insufficient sample/)).toBeVisible()
    expect(screen.getByText(/1d: 1 ready · 3 pending · 0 gap · insufficient sample/)).toBeVisible()
    expect(screen.getByText(/1w: 1 ready · 3 pending · 0 gap · insufficient sample/)).toBeVisible()
    expect(screen.getByRole("generic", { name: "1h taxonomy readiness" })).toHaveAttribute("data-quality-status", "insufficient_sample")
    expect(screen.getByRole("generic", { name: "6h taxonomy readiness" })).toHaveAttribute("data-quality-status", "insufficient_sample")
    expect(screen.getByRole("generic", { name: "1d taxonomy readiness" })).toHaveAttribute("data-quality-status", "insufficient_sample")
    expect(screen.getByRole("generic", { name: "1w taxonomy readiness" })).toHaveAttribute("data-quality-status", "insufficient_sample")
    expect(screen.getByRole("heading", { name: "Support / resistance" })).toBeVisible()
    expect(screen.getByText(/64\s*000/)).toBeVisible()
    expect(screen.getByRole("heading", { name: "Price history" })).toBeVisible()
  })
})

describe("semantic state helpers", () => {
  it("keeps data gaps distinct from pending outcomes", () => {
    expect(forwardValidationStatus(["ready", "pending", "data_gap"])).toBe("data_gap")
    expect(forwardValidationStatusLabel("data_gap")).toBe("data gap")
    expect(forwardValidationStatusLabel("pending")).toBe("ожидание forward data")
  })

  it("classifies indicator snapshot age", () => {
    expect(indicatorSnapshotAgeLabel(1_000, 60_999)).toBe("0м")
    expect(indicatorSnapshotAgeLabel(1_000, 181_001)).toBe("3м")
    expect(indicatorSnapshotStatus(1_000, 181_001)).toBe("stale")
    expect(indicatorSnapshotStatus(1_000, 181_000)).toBe("fresh")
  })

  it("formats elapsed time since the last closed candle", () => {
    expect(candleClosedAgeLabel(1_000, "1m", 121_001)).toBe("1м")
    expect(candleClosedAgeLabel(1_000, "1h", 10_801_000)).toBe("2ч")
  })

  it("refreshes candle freshness without reloading evidence", () => {
    vi.useFakeTimers()
    vi.setSystemTime(120_000)
    render(<CandleFreshness candleOpenTime={1_000} timeframe="1m" />)
    expect(screen.getByText("ожидается закрытие текущего бара")).toBeVisible()
    vi.setSystemTime(121_001)
    act(() => vi.advanceTimersByTime(60_000))
    expect(screen.getByText("данные устарели")).toBeVisible()
    vi.useRealTimers()
  })

  it("marks an overdue next close as stale data", () => {
    expect(candleFreshnessStatus(1_000, "1m", 121_001)).toBe("stale")
    expect(candleFreshnessStatus(1_000, "1m", 120_000)).toBe("awaiting_close")
  })

  it("counts zero as neutral, not missing", () => {
    expect(scoreDistribution([-7, 0, 6])).toEqual({ negative: 1, neutral: 1, positive: 1 })
  })
})
