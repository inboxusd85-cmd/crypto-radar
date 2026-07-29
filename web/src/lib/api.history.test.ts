import { describe, expect, it, vi } from "vitest"

import { getAssetCandles, getAssetHistory, getAssetIndicatorHistory, getAssetIndicators } from "./api"

describe("asset history API", () => {
  it("requests a bounded Hyperliquid metric series", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", metrics: { mark_price: [{ observed_at: 1, value: 100 }] } }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await getAssetHistory("btc", "mark_price", 24)

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/assets/BTC/history?metric=mark_price&limit=24", expect.any(Object))
  })

  it("requests all signal metrics when no metric is selected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", metrics: {} }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)

    await getAssetHistory("BTC", undefined, 48)

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/assets/BTC/history?limit=48", expect.any(Object))
  })

  it("requests indicator signals for selected timeframes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", generated_at: "now", signals: [] }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    await getAssetIndicators("btc", ["1m", "1h"])
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/assets/BTC/indicators?timeframes=1m%2C1h", expect.any(Object))
  })

  it("requests persisted candle and indicator series for a timeframe", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ asset: "BTC", candles: [], observations: [] }), { status: 200 })))
    vi.stubGlobal("fetch", fetchMock)

    await getAssetCandles("btc", "1w", 52)
    await getAssetIndicatorHistory("btc", "1w", 52)

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/assets/BTC/candles?timeframe=1w&limit=52", expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/assets/BTC/indicator-history?timeframe=1w&limit=52", expect.any(Object))
  })

  it("rejects an incomplete indicator observation contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", timeframe: "1h", observations: [{ period: 1 }] }), { status: 200 })))
    await expect(getAssetIndicatorHistory("btc", "1h", 1)).rejects.toThrow("Invalid indicator observation API payload")
  })

  it("accepts legacy observations with fields added later", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ asset: "BTC", timeframe: "1h", observations: [{ timeframe: "1h", demark: 0.5, demark_direction: "нейтральное" }] }), { status: 200 })))
    const result = await getAssetIndicatorHistory("btc", "1h", 1)
    expect(result.observations[0]).toMatchObject({ period: 0, volume_ratio: 0, volume_regime: "—", direction_agreement: false, direction_votes: [], td_sequential: {} })
  })
})
