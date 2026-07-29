import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import App, { factorSummary, forwardValidationStatusLabel, reviewPriority, reviewQueueSummary } from "./App"

const reviews = { reviews: [{ event_id: "event-1", asset: "BTC", signal_type: "composite_market_risk", severity: "medium", market_direction: "шорт", confidence: 0.7, fact: "Проверить снижение", review: { event_id: "event-1", status: "pending", note: "", reviewed_at: null }, outcomes: { "1h": { status: "ready", return_pct: 1.25 }, "6h": { status: "data_gap", reason: "missing_entry_price" }, "1d": { status: "pending" }, "1w": { status: "pending" } } }], count: 1 }

function renderReviews() {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes("/summary")) return Promise.resolve(new Response(JSON.stringify({ reviewed_count: 1, ready_count_1h: 1, coverage_pct_1h: 100, average_return_pct_1h: 1.25, directional_accuracy_pct_1h: 100, by_severity: {}, by_status: {}, by_horizon: { "1h": { ready_count: 1, coverage_pct: 100, average_return_pct: 1.25, directional_accuracy_pct: 100 }, "6h": { ready_count: 0, coverage_pct: 0, average_return_pct: null, directional_accuracy_pct: null }, "1d": { ready_count: 0, coverage_pct: 0, average_return_pct: null, directional_accuracy_pct: null }, "1w": { ready_count: 0, coverage_pct: 0, average_return_pct: null, directional_accuracy_pct: null } } }), { status: 200 }))
    if (url.includes("validation/depth")) return Promise.resolve(new Response(JSON.stringify({ historical_replay: { event_count: 7, by_horizon: { "1h": { sample_size: 7, pending_count: 0, data_gap_count: 0, average_return_pct: -0.73 }, "6h": { sample_size: 7, pending_count: 1, data_gap_count: 6, average_return_pct: -0.61 }, "1d": { sample_size: 7, pending_count: 0, data_gap_count: 0, average_return_pct: -1.72 }, "1w": { sample_size: 0, pending_count: 7, data_gap_count: 0, average_return_pct: null } } }, by_horizon: { "1h": { sample_size: 7, pending_count: 0, data_gap_count: 0, average_return_pct: -0.73, directional_error_count: 2, conflict_count: 0 }, "6h": { sample_size: 7, pending_count: 1, data_gap_count: 6, average_return_pct: -0.61, directional_error_count: 1, conflict_count: 0 }, "1d": { sample_size: 7, pending_count: 0, data_gap_count: 0, average_return_pct: -1.72, directional_error_count: 2, conflict_count: 0 }, "1w": { sample_size: 0, pending_count: 7, data_gap_count: 0, average_return_pct: null, directional_error_count: 0, conflict_count: 0 } }, by_dimension: { signal_quality: { unknown: { count: 7, ready_count_1h: 7, average_return_pct_1h: -0.73, directional_accuracy_pct_1h: 0 } }, confidence: { high: { count: 3, ready_count_1h: 3, average_return_pct_1h: -0.88, directional_accuracy_pct_1h: null } } } }), { status: 200 }))
    if (url.endsWith("/reviews/validation")) return Promise.resolve(new Response(JSON.stringify({ read_only: true, by_horizon: { "1h": { sample_size: 1, pending_count: 0, win_count: 1, loss_count: 0, flat_count: 0, win_rate_pct: 100, average_return_pct: 1.25, directional_hit_rate_pct: 100 }, "6h": { sample_size: 0, pending_count: 1, win_count: 0, loss_count: 0, flat_count: 0, win_rate_pct: null, average_return_pct: null, directional_hit_rate_pct: null }, "1d": { sample_size: 0, pending_count: 1, win_count: 0, loss_count: 0, flat_count: 0, win_rate_pct: null, average_return_pct: null, directional_hit_rate_pct: null }, "1w": { sample_size: 0, pending_count: 1, win_count: 0, loss_count: 0, flat_count: 0, win_rate_pct: null, average_return_pct: null, directional_hit_rate_pct: null } }, collection: { read_only: true, by_horizon: { "1h": { sample_size: 28, pending_count: 31 }, "6h": { sample_size: 22, pending_count: 37 }, "1d": { sample_size: 7, pending_count: 52 }, "1w": { sample_size: 0, pending_count: 59 } } } }), { status: 200 }))
    if (url.includes("validation/policy")) return Promise.resolve(new Response(JSON.stringify({ status: "collecting", recommendation: "Накопить outcomes", ready_sample_size_1h: 1, minimum_sample_size: 5, actions: [], dimension_actions: [{ dimension: "signal_quality", bucket: "unknown", action: "Недостаточно данных dimension", reason: "metadata отсутствует" }] }), { status: 200 }))
    if (url.includes("/reviews") && init?.method === "PUT") return Promise.resolve(new Response(JSON.stringify({ event_id: "event-1", status: "confirmed", note: "ok", reviewed_at: 1 }), { status: 200 }))
    if (url.includes("/reviews")) return Promise.resolve(new Response(JSON.stringify(reviews), { status: 200 }))
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<MemoryRouter initialEntries={["/reviews"]}><QueryClientProvider client={client}><App /></QueryClientProvider></MemoryRouter>)
}

describe("validation workspace", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })
  it("shows policy, outcome semantics and human review controls", async () => {
    renderReviews()
    expect(await screen.findByRole("heading", { name: "Validation" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Historical replay" })).toBeVisible()
    expect(screen.getByText("28 ready 1h · 31 pending · reviewed subset remains separate")).toBeVisible()
    expect(screen.getByText("7 events · 7 ready 1h · 14 pending/data gaps")).toBeVisible()
    expect(screen.getByText("6h: 1 pending · 6 data gaps")).toBeVisible()
    expect(screen.getByText("1w: 7 pending")).toBeVisible()
    expect(screen.getByRole("heading", { name: "Forward validation" })).toBeVisible()
    expect(screen.getByText("-0.73%")).toBeVisible()
    expect(screen.getAllByText("7 samples · 0 pending").length).toBe(2)
    expect(screen.getAllByText("ожидание forward data").length).toBe(3)
    const sixHour = [...document.querySelectorAll(".validation-horizon-card")].find((card) => card.textContent?.includes("6h"))
    expect(sixHour).toHaveTextContent("нет данных")
    expect(sixHour).toHaveTextContent("1 pending")
    const dimensions = screen.getByText("Dimension breakdown")

    expect(dimensions).toBeVisible()
    expect(dimensions.closest("details")).not.toHaveAttribute("open")
    fireEvent.click(dimensions)
    expect(screen.getAllByText("metadata отсутствует").length).toBe(2)
    expect(screen.getByText((content) => content.includes("Недостаточно данных dimension"))).toBeVisible()
    expect(screen.getByRole("tab", { name: "Ожидают" })).toHaveAttribute("aria-selected", "true")
  })

  it("labels outcome availability without implying policy readiness", () => {
    expect(forwardValidationStatusLabel("ready")).toBe("результат доступен")
    expect(forwardValidationStatusLabel("pending")).toBe("ожидание forward data")
    expect(forwardValidationStatusLabel("data_gap")).toBe("data gap")
  })

  it("summarizes queue urgency and keeps factor detail compact", () => {
    expect(reviewQueueSummary([
      { severity: "high", outcomes: { "1h": { status: "ready", return_pct: 1 } } },
      { severity: "low", outcomes: { "1h": { status: "pending" } } },
    ])).toEqual({ total: 2, high: 1, ready: 1, dataGap: 0 })
    expect(factorSummary("Для BTC оценены 5 рыночных факторов: funding_rate=high, mark_mid_spread=low, open_interest_turnover=low, mark_price_change=low, multi_timeframe_consensus=low.")).toBe("5 факторов · 1 повышенный риск")
  })

})
