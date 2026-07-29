# Security Policy

## Supported scope

Crypto Radar is a read-only, human-in-the-loop market intelligence dashboard. It does not execute trades or expose automated trading credentials.

Security reports should cover the application source, API behavior, frontend, dependency configuration, CI workflows, and deployment scripts in this repository. Reports about third-party services should include the affected integration and reproducible evidence when possible.

## Reporting a vulnerability

Please do not disclose exploitable details in a public issue. Use GitHub's private vulnerability reporting channel for this repository when it is enabled. If private reporting is unavailable, contact the repository maintainers through the repository's configured private communication channel and include:

- a concise description and impact;
- affected path, endpoint, package, or workflow;
- reproducible steps or a minimal proof of concept;
- version/commit and environment details;
- any suggested mitigation.

Do not include real API keys, OAuth tokens, exchange credentials, or private user data in a report.

## Dependency advisories

Dependency updates are monitored by Dependabot through `.github/dependabot.yml`. Every dependency update must pass the backend, frontend, build, and Playwright verification workflow before adoption.

`npm audit --omit=dev` is currently informational in CI because the latest available React Router v7 release has an upstream RSC-mode advisory while this dashboard uses declarative client-side routing only. The audit-suggested downgrade to `react-router-dom@7.11.0` was tested in an isolated copy: unit tests, build, and E2E passed, but the audit still reported `2 high` vulnerabilities, so the production lockfile was intentionally not changed. The advisory remains tracked and must not be represented as resolved until an upstream fix or a verified compatible migration is available. If npm's JSON audit endpoint returns an HTTP/endpoint error, any fallback `0` vulnerability metadata is invalid evidence; use the successful plain `npm audit --omit=dev` report instead.

## Response expectations

Maintainers should acknowledge a valid report, reproduce it in an isolated environment, assess impact, and document the remediation or mitigation. Security fixes should include regression coverage and a fresh verification result.
