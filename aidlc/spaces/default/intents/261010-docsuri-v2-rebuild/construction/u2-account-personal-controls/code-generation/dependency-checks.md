# U2 dependency observations

Observed 2026-10-14 KST during implementation. This is an intermediate dependency check, not a final frozen-source verification or a clean security assessment.

## Frontend production advisory comparison

The current frontend uses pinned `qrcode` 1.5.4 for transient local MFA QR rendering and development types 1.5.5. Its browser renderer does not require an external QR service. The package declares MIT licensing; the final distribution still needs the complete dependency/license inventory.

The implementation worker ran `corepack pnpm@9.15.9 --dir frontend audit --prod --json`. The parent extracted `frontend/package.json` and `frontend/pnpm-lock.yaml` from the exact develop base `295a3d19997b17661504d9163bd822cd50333fba` into an isolated temporary directory and ran the same production audit there. Neither audit passed: both returned the same five advisory IDs, with two High and three Moderate findings. No new advisory ID appeared in this comparison; this does not establish that the added package or application is vulnerability-free.

| Package and installed version | Advisory | Severity | Present in base and current lock |
|---|---|---|---|
| brace-expansion 5.0.11 | GHSA-q2hr-2g5m-vwhr | Moderate | Yes |
| source-map-js 1.2.1 | GHSA-68fv-2mgg-jv7q | High | Yes |
| sharp 0.35.4 | GHSA-wq5f-xc86-pv6w | High | Yes |
| next 15.5.26 | GHSA-4jqv-mc3x-m676 | Moderate | Yes |
| next 15.5.26 | GHSA-mcj8-r9mp-w47p | Moderate | Yes |

Raw temporary outputs: `/tmp/docsuri-u2-frontend-audit.json` and `/tmp/docsuri-u2-base-dependency-audit/result.json`. These are regenerable observations, not durable release artifacts. Advisory data is time-sensitive; recheck frozen inputs during the final validation. The interim Git policy permits documenting inherited failures, but does not convert these findings into passing results.

## Current build observation

`corepack pnpm@9.15.9 --dir frontend exec vite build` passed against the working implementation: 88 modules transformed, CSS 6.94 kB, JavaScript 279.00 kB (reported gzip 88.67 kB). The build took 534 ms on this host. This single build is not a performance target, browser acceptance result or immutable release identity.

## 2026-10-14 later — frozen-input recheck and added-dependency licensing

Added dependencies relative to base `295a3d19`: `qrcode` 1.5.4 (runtime, MIT — transient local MFA QR rendering, no external QR service) and `@types/qrcode` 1.5.5 (development, MIT). No Python dependency changed; `backend/uv.lock` and `shared/python/uv.lock` remain the frozen inputs recorded in the run manifest.

```sh
corepack pnpm@9.15.9 --dir frontend audit --prod --json
```

Re-run against the current lock: exit 1 with **2 high + 3 moderate**, exactly the five inherited advisories — `brace-expansion >=4.0.0 <5.0.12` (moderate), `source-map-js >=1.0.0 <1.2.2` (high), `sharp <0.35.5` (high), and `next >=15.0.0 <15.5.27` twice (moderate). No advisory appears from the added packages, and the interim Git policy's inherited-failure documentation still applies: these are not converted into passing results, and advisory data remains time-sensitive.

Current build after the workspace changes: 88 modules, CSS 6.94 kB, JavaScript 283.58 kB (reported gzip 89.94 kB), built in ~460 ms. The workspace typecheck (`tsc --noEmit`) and the U2 frontend unit configuration passed. The scoped CI workflow (`.github/workflows/u2-account-controls.yml`) pins actions by commit SHA, runs read-only with frozen lockfiles, executes the cumulative U1+U2 frontend configuration with coverage, and never uploads private logs, keys, proofs or backups. Its first actual execution happens when the working branch opens its PR; no CI pass is claimed here.
