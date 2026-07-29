import { describe, expect, it, vi } from "vitest"

import { getAsset, getAssetNews, getEvents, getHealth, ApiError } from "./api"

describe("detail API functions", () => {
  it("requests filtered events with cursor parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ events: [], next_before: null, count: 0 }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await getEvents({ asset: "BTC", severity: "high", before: 42, limit: 20 })

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/events?asset=BTC&severity=high&before=42&limit=20", expect.any(Object))
  })

  it("requests normalized asset news with a bounded limit", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", count: 0, news: [] }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    const news = await getAssetNews(" btc ", 3)

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/assets/BTC/news?limit=3", expect.any(Object))
    expect(news).toEqual({ asset: "BTC", count: 0, news: [] })
  })
  it("clamps asset news limit to the backend contract", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ asset: "BTC", count: 0, news: [] }), { status: 200 })))
    vi.stubGlobal("fetch", fetchMock)

    await getAssetNews("BTC", 0)
    await getAssetNews("BTC", 99)

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/assets/BTC/news?limit=1")
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/assets/BTC/news?limit=3")
  })

  it("rejects malformed asset news payloads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", count: 1, news: [{ title: "broken", score: { label: "нейтрально", basis: "missing score" } }] }), { status: 200 })))

    await expect(getAssetNews("BTC", 3)).rejects.toMatchObject({ message: "Invalid asset news API payload" })
  })
  it("rejects a news score whose label disagrees with its signed value", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", count: 1, news: [{ source_name: "Feed", source_tier: "primary", title: "broken", url: "https://example.com/broken", published_at: "2026-07-23T10:00:00Z", summary_ru: "summary", assets: ["BTC"], score: { score: -3, label: "позитивно", basis: "broken" }, ranking: { production_model: "rules-v1", shadow_model: "xgboost-news-v1", features: [] } }] }), { status: 200 })))
    await expect(getAssetNews("BTC", 3)).rejects.toMatchObject({ message: "Invalid asset news API payload" })
  })
  it("clamps non-finite asset news limits to the default bound", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ asset: "BTC", count: 0, news: [] }), { status: 200 })))
    vi.stubGlobal("fetch", fetchMock)

    await getAssetNews("BTC", Number.NaN)
    await getAssetNews("BTC", Number.POSITIVE_INFINITY)

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/assets/BTC/news?limit=3")
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/assets/BTC/news?limit=3")
  })
  it("requests an asset detail and health payload", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ asset: { asset: "BTC" }, signals: [], events: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok", api_version: "0.1.0", database: { ok: true }, provider: { name: "hyperliquid", last_success_at: null }, social: { enabled: false, status: "available_on_demand", mode: "separate_pipeline", entrypoint: "social-run", included_in_market_composite: false, requires_manual_review: true }, outcomes: { worker: null } }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await getAsset("btc")
    await getHealth()

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/assets/BTC")
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/health")
  })

  it("rejects an incomplete health contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })))
    await expect(getHealth()).rejects.toBeInstanceOf(ApiError)
  })

  it("rejects an incomplete event contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ events: [{ asset: "BTC" }], next_before: null, count: 1 }), { status: 200 })))
    await expect(getEvents()).rejects.toBeInstanceOf(ApiError)
  })
})
