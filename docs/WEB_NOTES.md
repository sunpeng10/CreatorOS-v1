# Web delivery notes

## Implementation

- Next.js App Router, TypeScript, React, Tailwind CSS, lucide-react and Recharts. Dependency versions are recorded in the lockfile.
- Public homepage, login and registration; authenticated dashboard, upload/analysis, reports, library, recommendations, accounts, analytics, experiments, settings, orders and tickets; administrator overview, leads, services/quotes, orders, approvals, tickets, finance, agents and audit/data.
- The authenticated shell requests the real session and gates administrator views by role. API authorization remains server-enforced. Every business action uses real same-origin API calls; unavailable services and empty datasets have explicit states.
- `/api/[...path]` is a server route proxy. It reads `API_URL` at runtime (default `http://127.0.0.1:8000`), forwards cookies, preserves private response headers, and returns a structured unavailable-service error. Ports are not baked into the build.
- Next.js dev/build use `--webpack`: Turbopack failed to connect to its CSS worker child process in the Windows sandbox. The supported webpack build compiled and generated all routes successfully.
- All forms explicitly use POST. Authentication submit stays disabled until hydration; SSR regression tests cover both login and registration so passwords cannot be placed in a native GET query string.
- All model and uploaded text is rendered as text. Source links accept only HTTP(S), and external links use noopener/noreferrer. Upload client checks mirror the server default of 100 MB total, 12 files, 10 minute videos and 4K limit.
- AI analysis requires configured status, explicit consent and a budget input. Reports expose source, evidence, observation type, confidence, limitations, task steps, cancellation/retry, editable versions, JSON/Markdown export and printing.
- Admin delivery supports selecting an owned report or entering the linked customer's report ID. Linked customer orders are accepted by the client; unlinked workspace Demo orders can be accepted in the administrator workspace.
- Demo library/financial/metric data is visibly marked; null metrics remain unavailable. Recommendation similarity is independent of relative performance. Analytics imports have column mapping, preview, validation and an explicit import action.
- PUBLISH_CONTENT / REAL_PAYMENT requests create approval records only; the UI states that approved operations still require manual action and do not publish/pay automatically.

## Verification

- `npm run typecheck`: passed.
- `npm run lint`: passed without warnings after cleanup.
- `npm test`: 7 passing assertions across metric/link/upload utilities and pre-hydration authentication SSR behavior.
- `npm run build`: final webpack production rebuild after authentication hardening passed with exit code 0.
- `npm audit --omit=dev`: 0 runtime dependency vulnerabilities. npm reported 8 moderate development-tooling advisories; no force upgrade was performed.
- Source formatted with project-local Prettier. Browser and full end-to-end verification are owned by the root integrator; see the main TEST_REPORT rather than treating frontend checks as browser verification.

Dependency setup was checked against the official [Next.js installation guide](https://nextjs.org/docs/app/getting-started/installation) and [Tailwind PostCSS installation guide](https://tailwindcss.com/docs/installation/using-postcss).
