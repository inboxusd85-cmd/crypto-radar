import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import App from "./App"

function renderRoute(entry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  vi.stubGlobal("fetch", vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes("/overview")) return Promise.resolve(new Response(JSON.stringify({ generated_at: "2026-07-21T12:00:00Z", assets: [{ asset: "BTC", mark_price: 65000, mid_price: 64990, funding_rate: 0.00001, open_interest: 40000, day_notional_volume: 2000000000 }], signals: [{ signal_id: "composite-1", asset: "BTC", signal_type: "composite_market_risk", signal_class: "composite", fact: "Composite", basis: "basis", source_urls: [], severity: "medium", confidence: 0.7, possible_explanations: [], requires_manual_review: true, auto_trade: false, measurements: {}, market_direction: "лонг", observed_at: "2026-07-21T12:00:00Z", evidence_metadata: { source_count: 0, has_sources: false, confidence: 0.7, requires_manual_review: true } }], meta: { requested_assets: ["BTC"], unavailable_assets: [] } }), { status: 200 }))
    if (url.includes("/assets/BTC/indicators")) {
      const response = new Response(JSON.stringify({ asset: "BTC", generated_at: "2026-07-21T12:00:00Z", signals: [{ signal_id: "technical-1", asset: "BTC", signal_type: "multi_timeframe_indicators", signal_class: "technical", fact: "DeMark technical", basis: "technical basis", source_urls: [], severity: "medium", confidence: 0.72, possible_explanations: [], requires_manual_review: true, auto_trade: false, measurements: { timeframe: "1h", demark: 0.131, demark_direction: "лонг", volume_ratio: 1.2, volume_regime: "обычный", direction_agreement: true, td_sequential: { signal_state: "setup", buy_setup_count: 8, sell_setup_count: 0, buy_countdown: 0, sell_countdown: 0 } }, market_direction: "лонг", observed_at: "2026-07-21T12:00:00Z", evidence_metadata: { source_count: 0, has_sources: false, confidence: 0.72, requires_manual_review: true } }], aggregate: { market_direction: "лонг", direction_agreement: true, confirmed_timeframes: [], basis: "technical" } }), { status: 200 })
      return Promise.resolve(response)
    }
    return Promise.resolve(new Response(JSON.stringify({ events: [], count: 0, next_before: null }), { status: 200 }))
  }))
  return render(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={client}><App /></QueryClientProvider></MemoryRouter>)
}

describe("Signal Room navigation", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })
  it("renders the immutable event observatory", async () => {
    renderRoute("/events")
    expect(await screen.findByRole("heading", { name: "Журнал событий" })).toBeVisible()
    expect(screen.getByText(/Immutable observation log/)).toBeVisible()
    expect(screen.getAllByRole("link", { name: /Журнал/ }).find((link) => link.getAttribute("aria-current") === "page")).toBeTruthy()
  })

  it("shows DeMark and TD as a separate technical layer", async () => {
    renderRoute("/signals?asset=BTC&timeframe=1h")
    expect(await screen.findByRole("heading", { name: "Сигналы" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Composite signal feed" })).toBeVisible()
    expect(screen.getByRole("link", { name: "Analyze ↗" })).toHaveAttribute("href", "/asset/BTC?from=signals&asset=BTC")
    expect(screen.getByRole("heading", { name: "DeMark / TD Sequential" })).toBeVisible()
    expect(screen.getByText("0.131")).toBeVisible()
    expect(screen.getByText("Buy 8/9 · нет countdown")).toBeVisible()
    expect(screen.getByText("1 / 1 technical observations")).toBeVisible()
    const evidence = screen.getByRole("link", { name: "evidence ↗" })
    expect(evidence).toHaveAttribute("href", "/asset/BTC?from=signals&asset=BTC&timeframe=1h")
    fireEvent.click(screen.getAllByRole("button", { name: "Все" })[0])
    expect(screen.getByText("1 / 1 technical observations")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "1h" }))
    expect(screen.getByText("1 / 1 technical observations")).toBeVisible()
  })
  it("preserves overview context when opening an asset", async () => {
    renderRoute("/")
    expect(await screen.findByRole("heading", { name: "Обзор рынка" })).toBeVisible()
    expect(screen.getByRole("link", { name: "Открыть evidence →" })).toHaveAttribute("href", "/asset/BTC?from=overview&asset=BTC")
    expect(screen.getByRole("link", { name: /BTC/ })).toHaveAttribute("href", "/asset/BTC?from=overview&asset=BTC")
  })


  it("keeps every primary route reachable from the mobile menu", () => {
    renderRoute("/events")
    fireEvent.click(screen.getByRole("button", { name: "Меню" }))
    const nav = screen.getByRole("navigation", { name: "Мобильная навигация" })
    for (const label of ["Обзор", "Сигналы", "Validation", "Журнал", "Система", "GitHub Watch"]) expect(nav).toHaveTextContent(label)
  })

  it("marks the active primary route and keeps app navigation out of static assets", () => {
    const routes = [
      ["/", "/"],
      ["/signals", "/signals"],
      ["/reviews", "/reviews"],
      ["/events", "/events"],
      ["/health", "/health"],
      ["/github", "/github"],
    ] as const

    for (const [entry, href] of routes) {
      cleanup()
      renderRoute(entry)
      const nav = screen.getByRole("navigation", { name: "Основная навигация" })
      expect(within(nav).getByRole("link", { current: "page" })).toHaveAttribute("href", href)
      expect([...nav.querySelectorAll("a")].map((link) => link.getAttribute("href")).filter((link) => link?.startsWith("/assets/"))).toEqual([])
    }
  })
})
