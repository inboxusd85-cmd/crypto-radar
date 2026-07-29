import { describe, expect, it, vi } from "vitest"

import { getArchiveValidation, getAssetNewsDataset, getOverview, getValidationDepth } from "./api"

describe("getOverview", () => {
  it("requests the read-only overview endpoint with selected assets", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      generated_at: "2026-07-21T12:00:00Z",
      assets: [],
      signals: [],
      meta: { requested_assets: ["BTC", "ETH"], unavailable_assets: [] },
    }), { status: 200, headers: { "Content-Type": "application/json" } }))
    vi.stubGlobal("fetch", fetchMock)
    const overview = await getOverview(["BTC", "ETH"])
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/overview?assets=BTC%2CETH", expect.any(Object))
    expect(overview.meta.requested_assets).toEqual(["BTC", "ETH"])
  })
})

describe("getAssetNewsDataset", () => {
  it("requests and validates the unlabeled read-only dataset", async () => {
    const emptyHorizon = { ready_count: 0, pending_count: 1, data_gap_count: 0, coverage_pct: 0 }
    const blocked = { status: "blocked", ready_count: 0, coverage_pct: 0, reasons: ["insufficient_samples", "insufficient_coverage"] }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      asset: "BTC", count: 0, label_status: "unlabeled", read_only: true,
      readiness: { "1h": emptyHorizon, "6h": emptyHorizon, "1d": emptyHorizon, "1w": emptyHorizon },
      training_readiness: { min_samples: 100, min_coverage_pct: 80, horizons: { "1h": blocked, "6h": blocked, "1d": blocked, "1w": blocked } },
      training_preparation: { "1h": { status: "blocked", horizon: "1h", ready_count: 0, coverage_pct: 0, reasons: ["insufficient_samples"] }, "6h": { status: "blocked", horizon: "6h", ready_count: 0, coverage_pct: 0, reasons: ["insufficient_samples"] }, "1d": { status: "blocked", horizon: "1d", ready_count: 0, coverage_pct: 0, reasons: ["insufficient_samples"] }, "1w": { status: "blocked", horizon: "1w", ready_count: 0, coverage_pct: 0, reasons: ["insufficient_samples"] } }, event_type_breakdown: {}, records: [],
    }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    const dataset = await getAssetNewsDataset("btc", 501)
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/assets/BTC/news/dataset?limit=500", expect.any(Object))
    expect(dataset.read_only).toBe(true)
    expect(dataset.label_status).toBe("unlabeled")
  })
})

describe("getValidationDepth", () => {
  it("requests the read-only depth validation endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ read_only: true, historical_replay: { event_count: 0, by_horizon: {} }, by_dimension: {}, by_horizon: {} }), { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    await getValidationDepth()
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/reviews/validation/depth", expect.any(Object))
  })
})

describe("getArchiveValidation", () => {
  it("requests the isolated read-only archive validation endpoint", async () => {
    const payload = {
      read_only: true,
      source_db: "data/crypto_radar.sqlite3",
      archive_db: "data/crypto_radar_backfill.sqlite3",
      event_count: 0,
      validation: { read_only: true, by_horizon: {} },
      time_split: { read_only: true, status: "exploratory", train_fraction: 0.8, split_at: 0, train: { event_count: 0, by_horizon: {} }, test: { event_count: 0, by_horizon: {} }, dataset_gate: {} },
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }))
    vi.stubGlobal("fetch", fetchMock)
    const report = await getArchiveValidation(100, 0.75)
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/reviews/validation/archive?limit=100&train_fraction=0.75", expect.any(Object))
    expect(report.read_only).toBe(true)
  })
})
