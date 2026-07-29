# News taxonomy quality metrics

## Scope

The event taxonomy is a collection-level descriptive evidence layer. It is not a validated fundamental signal, does not modify `rules-v1`, and is not included in `composite_market_risk`.

## Separate denominators

Keep these populations separate:

- **collection sample** — persisted RSS/news records grouped by `event_type`;
- **ready outcomes** — records with a materialized forward outcome at a given horizon;
- **directional sample** — ready outcomes with non-zero `production_score` and non-flat forward return.

Never describe a collection count as a validation sample count.

## Horizon quality status

For every event type and horizon (`1h`, `6h`, `1d`, `1w`), expose `ready_count`, `pending_count`, `data_gap_count`, coverage, and `quality_status`:

| Status | Ready outcomes | Meaning |
|---|---:|---|
| `insufficient_sample` | `< 10` | Metrics are withheld; do not infer signal quality. |
| `collecting` | `10–99` | Descriptive monitoring is allowed; evidence is not promotion-ready. |
| `review_candidate` | `>= 100` | Eligible for a separate human/statistical review; not automatic promotion. |

`pending` means the outcome is not mature yet. `data_gap` means the required source/outcome is unavailable. Neither is a zero return or a failed prediction.

## Outcome metrics

For `collecting` and `review_candidate` horizons, the API may expose:

- positive, negative, and flat return rates;
- `directional_accuracy_pct`;
- `directional_sample_count`;
- `directional_accuracy_ci95_pct` using a 95% Wilson interval.

The directional denominator excludes score-zero and flat-return observations. Always display the denominator with accuracy. For `insufficient_sample`, accuracy, denominator, and confidence interval are `null`, and the UI must say `quality metrics withheld`.

## Promotion boundary

These metrics are descriptive forward evidence only. They must not:

- change production weights or thresholds;
- enter the composite feed;
- create labels when labels are undefined;
- start automated trading or execution;
- be called predictive accuracy without an independently defined label, time-based split, sufficient sample, and human review.

Any future promotion requires a separate dataset gate, label specification, time-based evaluation, uncertainty review, and explicit human approval.
