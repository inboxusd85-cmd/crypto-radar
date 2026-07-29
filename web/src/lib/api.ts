export type Severity = "low" | "medium" | "high"
export type SignalClass = "market" | "technical" | "social" | "composite"
export interface EvidenceMetadata { source_count: number; has_sources: boolean; confidence: number; requires_manual_review: boolean }
export interface EvidenceClassSummary { count: number; priority_points: number }

export interface AssetMetric {
  asset: string
  mark_price: number
  mid_price: number | null
  funding_rate: number
  open_interest: number
  day_notional_volume: number
}

export interface Driver {
  priority: number
  role: "ключевой драйвер" | "подтверждающий фактор" | "контекстный фактор"
  signal_type: string
  signal_class: SignalClass
  severity: "low" | "medium" | "high"
  confidence: number
  market_direction: string
  fact: string
  basis: string
  timeframe?: string
  priority_points?: number
}

export interface Signal {
  signal_id: string
  asset: string
  signal_type: string
  signal_class: SignalClass
  fact: string
  basis: string
  source_urls: string[]
  severity: Severity
  confidence: number
  possible_explanations: string[]
  requires_manual_review: boolean
  auto_trade: false
  measurements: Record<string, unknown>
  market_direction: string
  observed_at: string
  evidence_metadata: EvidenceMetadata
}

export interface Overview {
  generated_at: string
  assets: AssetMetric[]
  signals: Signal[]
  meta: {
    requested_assets: string[]
    unavailable_assets: string[]
  }
}

export interface EventPage {
  events: EventRecord[]
  next_before: number | null
  count: number
}

export interface EventRecord {
  asset: string
  signal_type: string
  fact: string
  basis: string
  source_urls: string[]
  severity: Severity
  confidence: number
  possible_explanations: string[]
  requires_manual_review: boolean
  auto_trade: false
  measurements: Record<string, unknown>
  market_direction: string
  observed_at: string
  signal_id: string
  event_id: string
  recorded_at: number
}

export type ReviewStatus = "pending" | "confirmed" | "refuted" | "deferred"
export interface ReviewRecord { event_id: string; status: ReviewStatus; note: string; reviewed_at: number | null }
export interface ForwardOutcome { status: "ready" | "pending" | "data_gap"; close?: number; return_pct?: number; reason?: string }
export interface ReviewItem extends Partial<Signal> { event_id: string; review: ReviewRecord; outcomes?: Record<"1h" | "6h" | "1d" | "1w", ForwardOutcome> }
export interface ReviewQualityBucket { count: number; ready_count_1h: number; average_return_pct_1h: number | null }
export interface ReviewHorizonQuality { ready_count: number; coverage_pct: number | null; average_return_pct: number | null; directional_accuracy_pct: number | null }
export interface ReviewSummary { reviewed_count: number; ready_count_1h: number; coverage_pct_1h: number | null; average_return_pct_1h: number | null; directional_accuracy_pct_1h: number | null; by_severity: Record<string, ReviewQualityBucket>; by_status: Record<string, ReviewQualityBucket>; by_horizon: Record<"1h" | "6h" | "1d" | "1w", ReviewHorizonQuality> }
export interface ValidationHorizon { sample_size: number; pending_count: number; win_count: number; loss_count: number; flat_count: number; win_rate_pct: number | null; average_return_pct: number | null; directional_hit_rate_pct: number | null }
export interface ValidationReport { read_only: true; by_horizon: Record<"1h" | "6h" | "1d" | "1w", ValidationHorizon>; collection: { read_only: true; by_horizon: Record<"1h" | "6h" | "1d" | "1w", ValidationHorizon> } }
export interface ValidationDepthBucket { count: number; ready_count_1h: number; average_return_pct_1h: number | null; directional_accuracy_pct_1h: number | null }
export interface ValidationDepthHorizon { sample_size: number; pending_count: number; data_gap_count?: number; average_return_pct: number | null; directional_error_count: number; conflict_count: number }
export interface ValidationDepthReport { read_only: true; historical_replay: { event_count: number; by_horizon: Record<string, { sample_size: number; pending_count: number; data_gap_count?: number; average_return_pct: number | null }> }; by_dimension: Record<string, Record<string, ValidationDepthBucket>>; by_horizon: Record<"1h" | "6h" | "1d" | "1w", ValidationDepthHorizon> }
export interface ValidationPolicyAction { dimension?: string; bucket?: string; count?: number; ready_count_1h?: number; action: string; reason?: string }
export interface ValidationPolicyReport { read_only: true; status: "collecting" | "insufficient_sample" | "monitor" | "degraded"; recommendation: string; event_count: number; ready_sample_size_1h: number; minimum_sample_size: number; actions: string[]; dimension_actions: ValidationPolicyAction[] }
export interface ArchiveValidationReport { read_only: true; source_db: string; archive_db: string; event_count: number; validation: ValidationReport; time_split: { read_only: true; status: "exploratory"; train_fraction: number; split_at: number; train: { event_count: number; by_horizon: Record<string, { sample_size: number; pending_count: number; coverage_pct: number | null }> }; test: { event_count: number; by_horizon: Record<string, { sample_size: number; pending_count: number; coverage_pct: number | null }> }; dataset_gate: { min_samples: number; min_coverage_pct: number; train_1h: { status: "ready" | "blocked"; sample_size: number; coverage_pct: number | null; reasons: string[] }; test_1h: { status: "ready" | "blocked"; sample_size: number; coverage_pct: number | null; reasons: string[] } } } }
export interface ReviewPage { reviews: ReviewItem[]; count: number }

export interface HistoryPoint {
  observed_at: number
  value: number
}

export type HistoryMetric = "funding_rate" | "mark_mid_spread" | "turnover_ratio" | "mark_price"

export interface AssetHistory {
  asset: string
  metrics: Partial<Record<HistoryMetric, HistoryPoint[]>>
}

export interface AssetDetail {
  generated_at: string
  asset: AssetMetric
  signals: Signal[]
  events: EventRecord[]
}

export interface NewsScore { score: number; label: "позитивно" | "нейтрально" | "негативно"; basis: string }
export interface NewsRankingMetadata { production_model: "rules-v1"; shadow_model: "xgboost-news-v1"; features: number[] }
export interface NewsArticle { source_name: string; source_tier: string; title: string; url: string; published_at: string; summary: string; summary_ru: string; assets: string[]; score: NewsScore; ranking: NewsRankingMetadata }
export interface FundamentalNewsItem { article_id: string; title: string; url: string; published_at: string; source_name: string; source_tier: string; event_type: string; score: NewsScore; provenance: "rss" }
export interface FundamentalGitHubEvent { repo: string; kind: string; external_id: string; occurred_at: string; title: string; url: string; value: Record<string, unknown>; recorded_at: string; provenance: "github_watch" }
export interface FundamentalSynthesis { status: "confirmed" | "emerging" | "conflicting" | "insufficient"; direction: "positive" | "negative" | "mixed"; positive_count: number; negative_count: number; evidence: Array<{ source: "news" | "github"; direction: "positive" | "negative"; title: string; event_type?: string; kind?: string }>; production_impact: "none"; read_only: true; note: string }
export interface FundamentalSnapshot { asset: string; read_only: true; production_impact: "none"; synthesis: FundamentalSynthesis; news: { count: number; items: FundamentalNewsItem[]; status: "ready" | "empty" }; github: { mapped_repos: string[]; events: FundamentalGitHubEvent[]; status: "ready" | "empty" | "unmapped" }; note: string }
export interface AssetNews { asset: string; count: number; news: NewsArticle[] }
export interface NewsDatasetOutcome { status: "pending" | "ready" | "data_gap"; reason?: string; close?: number; return_pct?: number }
export interface NewsDatasetOutcomes { entry: { status: "pending" | "ready"; reason?: string; price?: number; open_time?: number }; outcomes: Record<"1h" | "6h" | "1d" | "1w", NewsDatasetOutcome> }
export interface NewsDatasetRecord { article_id: string; published_at: string; features: number[]; event_type: string; production_model: "rules-v1"; production_score: number; shadow_model: "xgboost-news-v1"; label: null; outcomes: NewsDatasetOutcomes }
export interface NewsDatasetReadiness { ready_count: number; pending_count: number; data_gap_count: number; coverage_pct: number }
export interface NewsTrainingReadiness { min_samples: number; min_coverage_pct: number; horizons: Record<"1h" | "6h" | "1d" | "1w", { status: "ready" | "blocked"; ready_count: number; coverage_pct: number; reasons: string[] }> }
export interface NewsTrainingPreparation { status: "blocked" | "ready"; horizon: "1h" | "6h" | "1d" | "1w"; ready_count: number; coverage_pct: number; reasons: string[]; split?: { train: NewsDatasetRecord[]; validation: NewsDatasetRecord[]; eligible_count: number; excluded_count: number } }
export interface NewsEventTypeBucket { count: number; sample_status: "insufficient_sample" | "collecting" | "sufficient_for_review"; score_distribution: { positive: number; neutral: number; negative: number }; by_horizon: Record<"1h" | "6h" | "1d" | "1w", NewsDatasetReadiness & { average_return_pct: number | null; quality_status: "insufficient_sample" | "collecting" | "review_candidate"; positive_rate_pct: number | null; negative_rate_pct: number | null; flat_rate_pct: number | null; directional_accuracy_pct: number | null; directional_sample_count: number | null; directional_accuracy_ci95_pct: [number, number] | null }> }
export interface NewsDataset { asset: string; count: number; label_status: "unlabeled"; read_only: true; readiness: Record<"1h" | "6h" | "1d" | "1w", NewsDatasetReadiness>; event_type_breakdown: Record<string, NewsEventTypeBucket>; training_readiness: NewsTrainingReadiness; training_preparation: Record<"1h" | "6h" | "1d" | "1w", NewsTrainingPreparation>; records: NewsDatasetRecord[] }
export interface GitHubEvent { repo: string; kind: string; external_id: string; occurred_at: string; title: string; url: string; value: Record<string, unknown>; recorded_at: string; severity?: "low" | "medium" | "high" }
export interface GitHubSummary { total: number; by_kind: Record<string, number>; by_severity: Record<"low" | "medium" | "high", number>; latest: GitHubEvent | null }
export interface GitHubWatch { enabled: boolean; repos: string[]; events: GitHubEvent[]; count: number; summary: GitHubSummary; polling: string; filters: { repo: string | null; kinds: string[]; since: string | null } }

export interface IndicatorSignalResponse {
  asset: string
  generated_at: string
  signals: Signal[]
  aggregate: {
    market_direction: string
    market_regime?: string
    direction_score?: number
    signal_quality?: number
    data_quality?: number
    timeframe_reliability?: Record<string, { freshness: number; completeness: number; score: number }>
    quality_label?: string
    quality_components?: Record<string, number>
    horizons?: Record<"local" | "tactical" | "strategic", { direction: string; timeframes: string[]; status: string }>
    direction_agreement: boolean

    indicator_weights?: Record<string, number>
    indicator_scores?: Record<string, Record<string, number>>
    confirmed_timeframes: string[]
    timeframe_weights?: Record<string, number>
    directional_scores?: Record<string, number>
    basis: string
  }
}

export type CandleTimeframe = "1m" | "10m" | "1h" | "6h" | "1d" | "1w"
export interface CandlePoint { open_time: number; open: number; high: number; low: number; close: number; volume: number; timeframe: CandleTimeframe }
export interface CandleHistory { asset: string; timeframe: CandleTimeframe; candles: CandlePoint[] }
export type LevelPeriod = "month" | "week" | "day"
export type LevelStrength = "strong" | "medium" | "weak"
export interface SupportResistanceLevel { period: LevelPeriod; strength: LevelStrength; support: number; resistance: number; start: string; end: string }
export interface SupportResistanceResponse { asset: string; levels: SupportResistanceLevel[] }
export interface IndicatorObservation {
  asset: string
  timeframe: CandleTimeframe
  period: number
  candle_open_time: number
  closed_candle_count: number
  observed_at: string
  demark: number
  demark_direction: string

  volume_ratio: number
  volume_regime: string
  direction_agreement: boolean
  direction_votes: string[]
  td_sequential: Record<string, unknown>
  market_direction: string
}
export interface IndicatorHistory { asset: string; timeframe: CandleTimeframe; observations: IndicatorObservation[] }

export interface OutcomeWorkerState {
  attempted: number
  ready: number
  pending: number
  errors: number
  status: "ok" | "pending" | "stale" | "error" | "not_started"
  stale?: boolean
  age_seconds?: number
  completed_at: number
}

export interface Health {
  status: string
  api_version: string
  database: { ok: boolean }
  provider: { name: string; last_success_at: string | null; last_indicator_success_at?: string | null }
  social: {
    enabled: boolean
    status: "available_on_demand" | string
    mode: "separate_pipeline" | string
    entrypoint: string
    included_in_market_composite: boolean
    requires_manual_review: boolean
  }
  outcomes: { worker: OutcomeWorkerState | null }
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1"

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
    ...init,
  })
  if (!response.ok) {
    throw new ApiError(response.status, `API request failed (${response.status})`)
  }
  return (await response.json()) as T
}

function requireObject(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ApiError(200, `Invalid ${label} API payload`)
  return value as Record<string, unknown>
}

function validateEventPage(value: unknown): EventPage {
  const payload = requireObject(value, "events")
  if (!Array.isArray(payload.events) || typeof payload.count !== "number") throw new ApiError(200, "Invalid events API payload")
  for (const event of payload.events) {
    const item = requireObject(event, "event")
    for (const key of ["asset", "signal_type", "fact", "basis", "observed_at", "signal_id", "event_id"]) {
      if (typeof item[key] !== "string") throw new ApiError(200, `Invalid event.${key} API payload`)
    }
    if (!Array.isArray(item.source_urls) || typeof item.confidence !== "number" || typeof item.requires_manual_review !== "boolean") throw new ApiError(200, "Invalid event metadata API payload")
  }
  return value as EventPage
}

function validateHealth(value: unknown): Health {
  const payload = requireObject(value, "health")
  const social = requireObject(payload.social, "health.social")
  if (typeof payload.status !== "string" || typeof payload.api_version !== "string" || typeof social.enabled !== "boolean" || typeof social.status !== "string" || typeof social.mode !== "string" || typeof social.entrypoint !== "string" || typeof social.included_in_market_composite !== "boolean" || typeof social.requires_manual_review !== "boolean") throw new ApiError(200, "Invalid health API payload")
  return value as Health
}

function validateNewsDataset(value: unknown): NewsDataset {
  const payload = requireObject(value, "news dataset")
  if (typeof payload.asset !== "string" || typeof payload.count !== "number" || payload.count !== (Array.isArray(payload.records) ? payload.records.length : -1) || payload.label_status !== "unlabeled" || payload.read_only !== true || !Array.isArray(payload.records)) throw new ApiError(200, "Invalid news dataset API payload")
  const training = requireObject(payload.training_readiness, "news training readiness")
  const trainingHorizons = requireObject(training.horizons, "news training readiness horizons")
  if (typeof training.min_samples !== "number" || typeof training.min_coverage_pct !== "number" || ["1h", "6h", "1d", "1w"].some((horizon) => {
    const bucket = requireObject(trainingHorizons[horizon], "news training readiness horizon")
    return (bucket.status !== "ready" && bucket.status !== "blocked") || typeof bucket.ready_count !== "number" || typeof bucket.coverage_pct !== "number" || !Array.isArray(bucket.reasons) || bucket.reasons.some((reason) => typeof reason !== "string")
  })) throw new ApiError(200, "Invalid news dataset API payload")
  const preparation = requireObject(payload.training_preparation, "news training preparation")
  if (["1h", "6h", "1d", "1w"].some((horizon) => {
    const bucket = requireObject(preparation[horizon], "news training preparation horizon")
    return bucket.horizon !== horizon || (bucket.status !== "ready" && bucket.status !== "blocked") || typeof bucket.ready_count !== "number" || typeof bucket.coverage_pct !== "number" || !Array.isArray(bucket.reasons) || bucket.reasons.some((reason) => typeof reason !== "string")
  })) throw new ApiError(200, "Invalid news training preparation API payload")
  const readiness = requireObject(payload.readiness, "news dataset readiness")
  for (const horizon of ["1h", "6h", "1d", "1w"]) {
    const bucket = requireObject(readiness[horizon], "news dataset readiness bucket")
    if (!["ready_count", "pending_count", "data_gap_count", "coverage_pct"].every((key) => typeof bucket[key] === "number")) throw new ApiError(200, "Invalid news dataset API payload")
  }
  for (const record of payload.records) {
    const item = requireObject(record, "news dataset record")
    if (typeof item.article_id !== "string" || typeof item.published_at !== "string" || item.production_model !== "rules-v1" || item.shadow_model !== "xgboost-news-v1" || typeof item.production_score !== "number" || !Number.isInteger(item.production_score) || item.production_score < -10 || item.production_score > 10 || !Array.isArray(item.features) || item.features.some((feature) => typeof feature !== "number") || item.label !== null) throw new ApiError(200, "Invalid news dataset API payload")
    const outcomes = requireObject(item.outcomes, "news dataset outcomes")
    const entry = requireObject(outcomes.entry, "news dataset entry")
    const horizonOutcomes = requireObject(outcomes.outcomes, "news dataset horizon outcomes")
    if ((entry.status !== "pending" && entry.status !== "ready") || ["1h", "6h", "1d", "1w"].some((horizon) => {
      const outcome = requireObject(horizonOutcomes[horizon], "news dataset horizon outcome")
      return outcome.status !== "pending" && outcome.status !== "ready" && outcome.status !== "data_gap"
    })) throw new ApiError(200, "Invalid news dataset API payload")
  }
  return value as NewsDataset
}

function validateFundamentalSnapshot(value: unknown): FundamentalSnapshot {
  const payload = requireObject(value, "fundamental snapshot")
  if (typeof payload.asset !== "string" || payload.read_only !== true || payload.production_impact !== "none") throw new ApiError(200, "Invalid fundamental snapshot API payload")
  const synthesis = requireObject(payload.synthesis, "fundamental synthesis")
  if (!["confirmed", "emerging", "conflicting", "insufficient"].includes(String(synthesis.status)) || !["positive", "negative", "mixed"].includes(String(synthesis.direction)) || synthesis.production_impact !== "none" || synthesis.read_only !== true || !Array.isArray(synthesis.evidence)) throw new ApiError(200, "Invalid fundamental synthesis API payload")
  const news = requireObject(payload.news, "fundamental news")
  const github = requireObject(payload.github, "fundamental github")
  if (typeof news.count !== "number" || !Array.isArray(news.items) || news.count !== news.items.length || !["ready", "empty"].includes(String(news.status))) throw new ApiError(200, "Invalid fundamental snapshot API payload")
  if (!Array.isArray(github.mapped_repos) || !Array.isArray(github.events) || !["ready", "empty", "unmapped"].includes(String(github.status))) throw new ApiError(200, "Invalid fundamental snapshot API payload")
  for (const event of github.events) {
    const item = requireObject(event, "fundamental github event")
    if (typeof item.occurred_at !== "string" || !item.occurred_at || typeof item.title !== "string" || typeof item.repo !== "string" || typeof item.kind !== "string") throw new ApiError(200, "Invalid fundamental github event API payload")
  }
  return value as FundamentalSnapshot
}

function validateAssetNews(value: unknown): AssetNews {
  const payload = requireObject(value, "asset news")
  if (typeof payload.asset !== "string" || typeof payload.count !== "number" || !Number.isInteger(payload.count) || payload.count < 0 || !Array.isArray(payload.news) || payload.count !== payload.news.length) throw new ApiError(200, "Invalid asset news API payload")
  for (const article of payload.news) {
    const item = requireObject(article, "news article")
    for (const key of ["source_name", "source_tier", "title", "url", "published_at", "summary", "summary_ru"]) {
      if (typeof item[key] !== "string") throw new ApiError(200, "Invalid asset news API payload")
    }
    if (!Array.isArray(item.assets)) throw new ApiError(200, "Invalid asset news API payload")
    const score = requireObject(item.score, "news score")
    const ranking = requireObject(item.ranking, "news ranking")
    const scoreIsInteger = typeof score.score === "number" && Number.isInteger(score.score)
    const scoreValue = score.score as number
    const scoreLabelValid = scoreIsInteger && ((scoreValue === 0 && score.label === "нейтрально") || (scoreValue > 0 && score.label === "позитивно") || (scoreValue < 0 && score.label === "негативно"))
    if (!scoreIsInteger || scoreValue < -10 || scoreValue > 10 || typeof score.label !== "string" || !scoreLabelValid || typeof score.basis !== "string" || ranking.production_model !== "rules-v1" || ranking.shadow_model !== "xgboost-news-v1" || !Array.isArray(ranking.features) || ranking.features.some((feature) => typeof feature !== "number")) throw new ApiError(200, "Invalid asset news API payload")
  }
  return value as AssetNews
}
function validateIndicatorHistory(value: unknown): IndicatorHistory {
  const payload = requireObject(value, "indicator history")
  if (typeof payload.asset !== "string" || !Array.isArray(payload.observations)) throw new ApiError(200, "Invalid indicator history API payload")
  for (const observation of payload.observations) {
    const item = requireObject(observation, "indicator observation")
    if (typeof item.timeframe !== "string") throw new ApiError(200, "Invalid indicator observation API payload")
    item.period ??= 0
    item.volume_ratio ??= 0
    item.volume_regime ??= "—"
    item.direction_agreement ??= false
    item.direction_votes ??= []
    item.td_sequential ??= {}
    if (typeof item.period !== "number" || typeof item.volume_ratio !== "number" || typeof item.volume_regime !== "string" || typeof item.direction_agreement !== "boolean" || !Array.isArray(item.direction_votes) || typeof item.td_sequential !== "object") throw new ApiError(200, "Invalid indicator observation API payload")
  }
  return value as IndicatorHistory
}

export function getReviews(status: ReviewStatus = "pending", limit = 100): Promise<ReviewPage> {
  const query = new URLSearchParams({ status, limit: String(limit) })
  return requestJson<ReviewPage>(`/reviews?${query}`)
}

export function getReviewSummary(): Promise<ReviewSummary> {
  return requestJson<ReviewSummary>("/reviews/summary")
}

export function getValidationReport(): Promise<ValidationReport> {
  return requestJson<ValidationReport>("/reviews/validation")
}

export function getValidationDepth(): Promise<ValidationDepthReport> {
  return requestJson<ValidationDepthReport>("/reviews/validation/depth")
}

export function getValidationPolicy(): Promise<ValidationPolicyReport> {
  return requestJson<ValidationPolicyReport>("/reviews/validation/policy")
}

export function getArchiveValidation(limit = 500, trainFraction = 0.8): Promise<ArchiveValidationReport> {
  return requestJson<ArchiveValidationReport>(`/reviews/validation/archive?limit=${limit}&train_fraction=${trainFraction}`)
}

export function updateReview(eventId: string, status: Exclude<ReviewStatus, "pending">, note: string): Promise<ReviewRecord> {
  return requestJson<ReviewRecord>(`/reviews/${encodeURIComponent(eventId)}`, {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ status, note }),
  })
}

export async function getOverview(assets: string[]): Promise<Overview> {
  const query = new URLSearchParams({ assets: assets.join(",") })
  return requestJson<Overview>(`/overview?${query}`)
}

export interface EventQuery {
  asset?: string
  severity?: Severity
  before?: number
  limit?: number
}

export function getEvents(filters: EventQuery = {}): Promise<EventPage> {
  const query = new URLSearchParams()
  if (filters.asset) query.set("asset", filters.asset.toUpperCase())
  if (filters.severity) query.set("severity", filters.severity)
  if (filters.before !== undefined) query.set("before", String(filters.before))
  query.set("limit", String(filters.limit ?? 50))
  return requestJson<unknown>(`/events?${query}`).then(validateEventPage)
}

export function getAsset(asset: string): Promise<AssetDetail> {
  return requestJson<AssetDetail>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}`)
}

export function getHealth(): Promise<Health> {
  return requestJson<unknown>("/health").then(validateHealth)
}

export function getAssetHistory(asset: string, metric?: HistoryMetric, limit = 100): Promise<AssetHistory> {
  const query = new URLSearchParams()
  if (metric) query.set("metric", metric)
  query.set("limit", String(limit))
  return requestJson<AssetHistory>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/history?${query}`)
}

export function getAssetFundamental(asset: string, limit = 20): Promise<FundamentalSnapshot> {
  const boundedLimit = Math.min(100, Math.max(1, Math.trunc(Number.isFinite(limit) ? limit : 20)))
  return requestJson<unknown>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/fundamental?${new URLSearchParams({ limit: String(boundedLimit) })}`).then(validateFundamentalSnapshot)
}
export function getAssetNews(asset: string, limit = 3): Promise<AssetNews> {
  const normalizedLimit = Number.isFinite(limit) ? Math.trunc(limit) : 3
  const boundedLimit = Math.min(3, Math.max(1, normalizedLimit))
  const query = new URLSearchParams({ limit: String(boundedLimit) })
  return requestJson<unknown>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/news?${query}`).then(validateAssetNews)
}

export function getAssetNewsDataset(asset: string, limit = 100): Promise<NewsDataset> {
  const normalizedLimit = Number.isFinite(limit) ? Math.trunc(limit) : 100
  const boundedLimit = Math.min(500, Math.max(1, normalizedLimit))
  return requestJson<unknown>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/news/dataset?${new URLSearchParams({ limit: String(boundedLimit) })}`).then(validateNewsDataset)
}

export function getGitHubWatch(limit = 100): Promise<GitHubWatch> {
  return requestJson<GitHubWatch>(`/github/watch?${new URLSearchParams({ limit: String(limit) })}`)
}

export function pollGitHubWatch(): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/github/watch/poll", { method: "POST" })
}

export function getAssetIndicators(asset: string, timeframes = ["1m", "10m", "1h", "6h", "1d", "1w"]): Promise<IndicatorSignalResponse> {
  const query = new URLSearchParams({ timeframes: timeframes.join(",") })
  return requestJson<IndicatorSignalResponse>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/indicators?${query}`)
}

export function getAssetCandles(asset: string, timeframe: CandleTimeframe, limit = 100): Promise<CandleHistory> {
  const query = new URLSearchParams({ timeframe, limit: String(limit) })
  return requestJson<CandleHistory>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/candles?${query}`)
}

export function getAssetLevels(asset: string): Promise<SupportResistanceResponse> {
  return requestJson<SupportResistanceResponse>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/levels`)
}

export function getAssetIndicatorHistory(asset: string, timeframe: CandleTimeframe, limit = 100): Promise<IndicatorHistory> {
  const query = new URLSearchParams({ timeframe, limit: String(limit) })
  return requestJson<unknown>(`/assets/${encodeURIComponent(asset.trim().toUpperCase())}/indicator-history?${query}`).then(validateIndicatorHistory)
}
