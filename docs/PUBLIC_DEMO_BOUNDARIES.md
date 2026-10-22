# Public demo boundaries

These rules apply to the repository, portfolio walkthrough, screenshots, recordings and any live demo.

## Allowed

- Fictional customer names, emails, VIN-like strings and service descriptions.
- Test-only API keys used only in isolated local or CI environments.
- Mocked AI calls for deterministic tests.
- Read-only public health/readiness checks.
- Clearly labelled prototype screenshots and controlled synthetic benchmarks.

## Not allowed

- Real customer, legal-client, vehicle-owner or employer data.
- Production API keys, database URLs, passwords, deployment hooks or `.env` files.
- Publishing execution histories containing headers or credentials.
- Claims of vehicle diagnosis, emergency handling or warranty adjudication.
- Unverified claims about users, accuracy, time savings, cost savings or revenue.
- Unbounded public endpoints that can generate paid model usage without authentication and limits.

## Before sharing a live interactive path

- Keep credentials server-side and rotate any value that has appeared in Git history.
- Use synthetic seed data and a separate test environment where practical.
- Set a spending/rate boundary for paid model calls.
- Verify pending and rejected states fail closed.
- Verify logs redact credentials and personal details.
- Provide a visible prototype/limitations notice.
- Retain a way to disable the public interaction without deleting evidence.

Current public health/readiness links are read-only. The portfolio walkthrough is illustrative and separate from the backend. No claim is made that the public deployment is suitable for real service operations.

