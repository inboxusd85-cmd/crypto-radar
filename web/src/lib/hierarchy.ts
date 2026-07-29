export type HorizonKey = "strategic" | "tactical" | "local"
export type HierarchyDirection = string

export interface HorizonSummary {
  direction: string
  timeframes: string[]
  status: string
}

export interface Reliability {
  freshness: number
  completeness: number
  score: number
}

export interface HierarchyAggregate {
  horizons?: Partial<Record<HorizonKey, HorizonSummary>>
  timeframe_weights?: Record<string, number>
  timeframe_reliability?: Record<string, Reliability>
  directional_scores?: Record<string, number>
  direction_agreement: boolean
  signals?: Array<{ timeframe?: string; market_direction?: string }>
}

export interface HierarchyFrame {
  timeframe: string
  weight: number
  strengthMultiplier: number
  temporalMultiplier: number
  direction: string
  alignment: "подтверждает" | "конфликт" | "нейтрально" | "нет данных"
  reliability: number | null
  freshness: number | null
  completeness: number | null
}

export interface HierarchyGroup {
  key: HorizonKey
  label: string
  description: string
  direction: string
  status: string
  frames: HierarchyFrame[]
  totalWeight: number
  confirmingFrames: number
  conflictingFrames: number
  neutralFrames: number
  confirmingWeight: number
  conflictingWeight: number
  neutralWeight: number
  weightedConfirmationPct: number | null
  weightedNeutralPct: number | null
  totalConfirmationPct: number | null
  totalConflictPct: number | null
  totalNeutralPct: number | null
  weightedAlignment: "перевес подтверждения" | "перевес конфликта" | "равновесие" | "нет направленных данных"
}

const GROUPS: Array<{ key: HorizonKey; label: string; description: string; order: string[] }> = [
  { key: "strategic", label: "Стратегический", description: "Главный режим и наиболее устойчивый контекст", order: ["1w", "1d"] },
  { key: "tactical", label: "Тактический", description: "Рабочее направление на горизонте часов", order: ["6h", "1h"] },
  { key: "local", label: "Локальный", description: "Краткосрочное движение и точка наблюдения", order: ["10m", "1m"] },
]

export function buildSignalHierarchy(aggregate: HierarchyAggregate): HierarchyGroup[] {
  return GROUPS.map((group) => {
    const summary = aggregate.horizons?.[group.key] ?? { direction: "—", timeframes: [], status: "нет данных" }
    const frames = (summary?.timeframes ?? []).map((timeframe) => {
      const weight = aggregate.timeframe_weights?.[timeframe] ?? fallbackWeight(timeframe)
      const reliability = aggregate.timeframe_reliability?.[timeframe]
      const signal = aggregate.signals?.find((item) => item.timeframe === timeframe)
      const direction = signal?.market_direction ?? "нет данных"
      const alignment: HierarchyFrame["alignment"] = direction === "нет данных" ? "нет данных" : direction === "нейтральное" || direction === "—" ? "нейтрально" : direction === summary.direction ? "подтверждает" : "конфликт"
      return {
        timeframe,
        weight,
        strengthMultiplier: Math.max(1, Math.round(weight / 10)),
        temporalMultiplier: timeframeMinutes(timeframe),
        direction,
        alignment,
        reliability: reliability?.score ?? null,
        freshness: reliability?.freshness ?? null,
        completeness: reliability?.completeness ?? null,
      }
    }).sort((left, right) => group.order.indexOf(left.timeframe) - group.order.indexOf(right.timeframe))
    const totalPercentages = normalizeWeightedPercentages([
      frames.filter((frame) => frame.alignment === "подтверждает").reduce((sum, frame) => sum + frame.weight, 0),
      frames.filter((frame) => frame.alignment === "конфликт").reduce((sum, frame) => sum + frame.weight, 0),
      frames.filter((frame) => frame.alignment === "нейтрально").reduce((sum, frame) => sum + frame.weight, 0),
    ])
    return {
      key: group.key,
      label: group.label,
      description: group.description,
      direction: summary?.direction ?? "—",
      status: summary?.status ?? "нет данных",
      frames,
      totalWeight: frames.reduce((sum, frame) => sum + frame.weight, 0),
      confirmingFrames: frames.filter((frame) => frame.alignment === "подтверждает").length,
      conflictingFrames: frames.filter((frame) => frame.alignment === "конфликт").length,
      neutralFrames: frames.filter((frame) => frame.alignment === "нейтрально").length,
      confirmingWeight: frames.filter((frame) => frame.alignment === "подтверждает").reduce((sum, frame) => sum + frame.weight, 0),
      conflictingWeight: frames.filter((frame) => frame.alignment === "конфликт").reduce((sum, frame) => sum + frame.weight, 0),
      neutralWeight: frames.filter((frame) => frame.alignment === "нейтрально").reduce((sum, frame) => sum + frame.weight, 0),
      weightedConfirmationPct: getWeightedConfirmationPct(frames),
      weightedNeutralPct: getWeightedNeutralPct(frames),
      totalConfirmationPct: totalPercentages[0],
      totalConflictPct: totalPercentages[1],
      totalNeutralPct: totalPercentages[2],
      weightedAlignment: getWeightedAlignment(frames),
    }
  })
}

function getWeightedConfirmationPct(frames: HierarchyFrame[]): number | null {
  const directed = frames.filter((frame) => frame.alignment === "подтверждает" || frame.alignment === "конфликт")
  const total = directed.reduce((sum, frame) => sum + frame.weight, 0)
  if (!total) return null
  const confirming = directed.filter((frame) => frame.alignment === "подтверждает").reduce((sum, frame) => sum + frame.weight, 0)
  return Math.round((confirming / total) * 1000) / 10
}

function getWeightedNeutralPct(frames: HierarchyFrame[]): number | null {
  const total = frames.reduce((sum, frame) => sum + frame.weight, 0)
  if (!total) return null
  const neutral = frames.filter((frame) => frame.alignment === "нейтрально").reduce((sum, frame) => sum + frame.weight, 0)
  return Math.round((neutral / total) * 1000) / 10
}

export function normalizeWeightedPercentages(weights: number[]): number[] {
  const total = weights.reduce((sum, weight) => sum + weight, 0)
  if (!total) return weights.map(() => 0)
  const exact = weights.map((weight) => (weight / total) * 100)
  const base = exact.map((value) => Math.floor(value * 10) / 10)
  let remainder = Math.round((100 - base.reduce((sum, value) => sum + value, 0)) * 10)
  const order = exact.map((value, index) => ({ index, fraction: value - base[index] })).sort((left, right) => right.fraction - left.fraction || left.index - right.index)
  for (let cursor = 0; cursor < remainder; cursor += 1) base[order[cursor % order.length].index] += 0.1
  return base.map((value) => Math.round(value * 10) / 10)
}

function getTotalWeightPct(frames: HierarchyFrame[], alignment: HierarchyFrame["alignment"]): number | null {
  const total = frames.reduce((sum, frame) => sum + frame.weight, 0)
  if (!total) return null
  const weight = frames.filter((frame) => frame.alignment === alignment).reduce((sum, frame) => sum + frame.weight, 0)
  return Math.round((weight / total) * 1000) / 10
}

function getWeightedAlignment(frames: HierarchyFrame[]): HierarchyGroup["weightedAlignment"] {
  const confirming = frames.filter((frame) => frame.alignment === "подтверждает").reduce((sum, frame) => sum + frame.weight, 0)
  const conflicting = frames.filter((frame) => frame.alignment === "конфликт").reduce((sum, frame) => sum + frame.weight, 0)
  if (!confirming && !conflicting) return "нет направленных данных"
  if (confirming === conflicting) return "равновесие"
  return confirming > conflicting ? "перевес подтверждения" : "перевес конфликта"
}

function timeframeMinutes(timeframe: string): number {
  return ({ "1m": 1, "10m": 10, "1h": 60, "6h": 360, "1d": 1440, "1w": 10080 } as Record<string, number>)[timeframe] ?? 0
}

function fallbackWeight(timeframe: string): number {
  return ({ "1m": 10, "10m": 20, "1h": 30, "6h": 40, "1d": 50, "1w": 60 } as Record<string, number>)[timeframe] ?? 0
}
