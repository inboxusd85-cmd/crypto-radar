import { describe, expect, it } from "vitest"

import { buildSignalHierarchy, normalizeWeightedPercentages, type HierarchyAggregate } from "./hierarchy"

const aggregate: HierarchyAggregate = {
  horizons: {
    strategic: { direction: "шорт", timeframes: ["1d", "1w"], status: "согласован" },
    tactical: { direction: "лонг", timeframes: ["1h", "6h"], status: "согласован" },
    local: { direction: "лонг", timeframes: ["1m", "10m"], status: "согласован" },
  },
  timeframe_weights: { "1m": 10, "10m": 20, "1h": 30, "6h": 40, "1d": 50, "1w": 60 },
  timeframe_reliability: {
    "1m": { freshness: 100, completeness: 100, score: 100 },
    "10m": { freshness: 100, completeness: 100, score: 100 },
    "1h": { freshness: 90, completeness: 100, score: 90 },
    "6h": { freshness: 80, completeness: 100, score: 80 },
    "1d": { freshness: 70, completeness: 100, score: 70 },
    "1w": { freshness: 60, completeness: 100, score: 60 },
  },
  directional_scores: { лонг: 70, шорт: 110 },
  direction_agreement: false,
  signals: [
    { timeframe: "1w", market_direction: "шорт" },
    { timeframe: "1d", market_direction: "лонг" },
    { timeframe: "1h", market_direction: "лонг" },
    { timeframe: "6h", market_direction: "лонг" },
    { timeframe: "10m", market_direction: "шорт" },
    { timeframe: "1m", market_direction: "шорт" },
  ],
}

describe("signal hierarchy", () => {
  it("normalizes rounded total percentages to exactly 100", () => {
    const percentages = normalizeWeightedPercentages([1, 1, 1])
    expect(percentages).toEqual([33.4, 33.3, 33.3])
    expect(percentages.reduce((sum, value) => sum + value, 0)).toBeCloseTo(100, 10)
  })

  it("groups semantic horizons and orders timeframes from local to strategic", () => {
    const hierarchy = buildSignalHierarchy(aggregate)

    expect(hierarchy.map((group) => group.key)).toEqual(["strategic", "tactical", "local"])
    expect(hierarchy[0].frames.map((frame) => frame.timeframe)).toEqual(["1w", "1d"])
    expect(hierarchy[0].frames[0]).toMatchObject({ weight: 60, strengthMultiplier: 6, temporalMultiplier: 10080, direction: "шорт" })
    expect(hierarchy[2].frames[0]).toMatchObject({ weight: 20, strengthMultiplier: 2, temporalMultiplier: 10, direction: "шорт" })
    expect(hierarchy[0].frames[1]).toMatchObject({ timeframe: "1d", direction: "лонг", alignment: "конфликт" })
    expect(hierarchy[0]).toMatchObject({ confirmingFrames: 1, conflictingFrames: 1, neutralFrames: 0, confirmingWeight: 60, conflictingWeight: 50, weightedConfirmationPct: 54.5, weightedAlignment: "перевес подтверждения", weightedNeutralPct: 0, totalConfirmationPct: 54.5, totalConflictPct: 45.5, totalNeutralPct: 0 })
  })

  it("uses reliability and exposes missing timeframe data explicitly", () => {
    const partial = { ...aggregate, horizons: { ...aggregate.horizons, local: { direction: "—", timeframes: [], status: "нет данных" } } }
    const hierarchy = buildSignalHierarchy(partial)

    expect(hierarchy[2].frames).toHaveLength(0)
    expect(hierarchy[2].status).toBe("нет данных")
    expect(hierarchy[0].frames[0].reliability).toBe(60)
  })

  it("does not infer a frame vote from the horizon when its direction is missing", () => {
    const partial: HierarchyAggregate = {
      ...aggregate,
      horizons: { ...aggregate.horizons, strategic: { direction: "шорт", timeframes: ["1w", "1d"], status: "нет данных" } },
      signals: [{ timeframe: "1w", market_direction: "шорт" }],
    }
    const strategic = buildSignalHierarchy(partial)[0]

    expect(strategic.frames[0]).toMatchObject({ timeframe: "1w", alignment: "подтверждает" })
    expect(strategic.frames[1]).toMatchObject({ timeframe: "1d", direction: "нет данных", alignment: "нет данных" })
    expect(strategic.confirmingWeight).toBe(60)
    expect(strategic.conflictingWeight).toBe(0)
  })
})
