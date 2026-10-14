# U2 frontend and browser verification

Observed 2026-10-14 on the owned `docsuri_u2` realm with the actual mounted host, real PostgreSQL stores and the U2 Playwright configuration. These are actual browser journeys against the deployed application composition, not route mocks.

## Frontend unit suites

```sh
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls
```

Result: **92 passed across 4 files** (`accountFlows`, `personalControls`, `libraryControls`, `authorityIsolation`). The files exercise loading, empty, error, conflict/unknown, pending, blocked and completed states, transport authority-generation isolation, late-response discarding, and mutation reconciliation. Existing React `act`/controlled-field warnings remain; they are test-harness noise, not product failures. One rendered field without an `onChange` handler in the integrated shell journey is recorded as a follow-up (not part of an interactive path).

The runner's `frontend` phase executes the same command under the frozen local Playwright/Vitest install and passed with `exitCode 0`.

## Browser journeys

```sh
python3 scripts/verify_docsuri_u2.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json
```

Result: **13 passed** through the runner's supervised host: exit 0, 90.4 s phase, Playwright suite 16–55 s, peak supervised process-tree RSS 910 MB inside the 1 GiB browser budget. A second consecutive run also passed. The phase prepares its own fixtures and corpus, clears the finite entry-admission window, starts the owned host, and stops it afterwards.

Journeys: registration/verification/local MFA enrollment; password reset with fresh authentication and credential replacement; local Google/ORCID fixture link/unlink; profile/interests/appearance persistence across reload; real search → save → revisit → scoped history clear; consent revocation with manual controls preserved and reversible; reset rediscovery after restart (read-only, zero `/settings-reset` writes, saved work kept); administrator MFA assignment grant/revocation for a target account; logout and account switch clear the previous private form and never replay it; withdrawal and reactivation progress through the narrow limited cookie with no ordinary session; and three reflow journeys at 1440×960 light, 820×1180 dark and 390×844 system.

Product fixes were required and completed to make the journeys truthful: a pending protected link survives the bootstrap boundary remount and its completion notice survives the authority refresh; the login helper retries once after the minute boundary when the finite entry-admission bucket is exhausted; TOTP accepts standard ±1 drift with monotonic replay prevention; the identity return vocabulary accepts the installed `account` route; identity-link callbacks no longer conflict on the route allowlist; and reads retry bounded transient dependency/rate pressure while admission refusals surface for explicit manual recovery.

## Appearance, focus and disclosure behavior (verified in source and journeys)

- Appearance changes that fail persistence are marked `화면 모드는 임시 변경이에요. 계정에 저장되지 않았어요`; acknowledged interests/onboarding are never silently discarded.
- Focus/pageshow rechecks run on the mounted app; late responses are discarded by authority generation; private state clears on logout/switch (journey 9).
- Protected material renders locally (canvas QR drawn from the one-time URI); the browser helper scrubs `.protected-material`, password and one-time-code inputs and the URL after each journey.
- Automated keyboard coverage is the reflow journey's explicit Tab-order assertion (display name → affiliation). Zoom/reflow is asserted with a no-horizontal-overflow check at all three viewports.

## Accessibility limitations (honest statement)

Automated keyboard/reflow checks do not establish WCAG conformance. No screen-reader pass was executed and no assistive-technology evidence is claimed; the Korean long-text, focus-order and reflow checks are automated only. Live-region announcements exist for status/alert states (`role=status`/`role=alert`) and were observed in journey snapshots, but a manual screen-reader review remains outstanding and must not be recorded as passed.
