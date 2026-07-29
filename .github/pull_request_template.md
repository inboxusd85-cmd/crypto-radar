## Verification checklist

- [ ] Backend tests pass with `.venv/bin/pytest -q --strict-config --strict-markers`.
- [ ] Frontend unit tests pass with `npm test -- --run` from `web/`.
- [ ] Production build passes with `npm run build` from `web/`, followed by `npm run verify:assets`; the built HTML/CSS asset namespace has no external resource references.
- [ ] Playwright desktop/mobile E2E passes with `npm run test:e2e` from `web/`.
- [ ] Live/API or integration behavior was checked when the change affects runtime boundaries.
- [ ] No `pageerror`, `console.error`, failed browser requests, or unexpected API responses were introduced.

## Security and data-safety checklist

- [ ] The change preserves read-only and human-in-the-loop behavior.
- [ ] No credentials, tokens, private data, or generated secrets are committed.
- [ ] Dependency changes include the relevant `npm audit --omit=dev` result.
- [ ] Known advisories are documented honestly and are not marked resolved without an upstream fix or verified mitigation.

## Summary

Describe the behavior changed, verification evidence, and any remaining blocker or assumption.
