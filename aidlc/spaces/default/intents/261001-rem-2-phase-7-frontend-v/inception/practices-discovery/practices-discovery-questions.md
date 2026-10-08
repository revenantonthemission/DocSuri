# Practices Discovery Questions — DocSuri Phase 7

**Gate:** Human Affirmation (required for promotion to memory/team.md and project.md)

---

## Interview Questions

### 1. Way of Working
**Default (from org.md & reverse-engineering):** Trunk-based development, short-lived feature branches (1-2 days), squash-merge to main.

**Question:** Is trunk-based development with short-lived branches and squash-merge the correct way of working for Phase 7?

- A. **Yes, as described** — Trunk-based, short-lived branches, squash-merge
- B. **Different branching strategy** — Specify (e.g., GitFlow, long-lived feature branches)
- C. **Different merge strategy** — Specify (e.g., merge commits, rebase)
- X. Other (please specify)

---

### 2. Walking Skeleton
**Default (from org.md & reverse-engineering):** OFF for feature scope (no skeleton ceremony). Phase 7 is frontend wiring only; backend contract complete.

**Question:** Build a thin end-to-end slice first? A walking skeleton is a minimal version that runs the whole way through, built first to prove the pieces connect before the real features go in.

- A. **No, skip skeleton** — Feature scope, backend already complete, wiring only
- B. **Yes, build skeleton** — Want end-to-end verification before full implementation
- X. Other (please specify)

---

### 3. Testing Posture — Methodology
**Default (from org.md):** test-after (implement, then test).

**Question:** Which testing methodology should we use for Phase 7?

- A. **test-after** — Implement feature, then write tests (team default)
- B. **TDD** — Write failing test first, then implement
- C. **BDD** — Write Gherkin scenarios first, then implement
- D. **ATDD** — Acceptance tests drive development
- E. **Custom** — Mix of approaches (e.g., BDD for user flows, test-after for internals)
- X. Other (please specify)

---

### 4. Testing Posture — Ordering
**Default (from org.md):** Implement each applicable testable layer, then write and run that layer's tests.

**Question:** What test ordering should we follow for Phase 7?

- A. **Layer-then-test** — Implement each layer (BFF routing → JobStatus → AssetViewer → Idempotency), then test that layer
- B. **Test-first per feature** — Write tests for each user story before implementation
- C. **Test-last per component** — Implement component fully, then write its tests
- D. **Mixed** — Test-first for user-facing components, test-after for internals
- X. Other (please specify)

---

### 5. Deployment — Production Approval
**Default (from org.md):** Manual approval (tech lead + product owner) for production deploys.

**Question:** Should production deployments require manual approval, or deploy automatically on merge?

- A. **Manual approval** — Tech lead + product owner sign-off required (current default)
- B. **Automatic on merge** — Continuous deployment to production
- C. **Automatic with canary** — Auto-deploy with canary rollout and manual promotion
- X. Other (please specify)

---

### 6. Code Style — Forbidden Patterns
**Default (from reverse-engineering + ESLint config):** The following are enforced as hard constraints via `no-restricted-imports`:

- NEVER `axios` — use native `fetch` + custom Transport
- NEVER `@tanstack/react-query` — use SWR
- NEVER `lodash` — use native JavaScript
- NEVER `moment.js` — use native `Date`/`Intl`
- NEVER `classnames` — use `clsx`
- NEVER `styled-components` or `@emotion/*` — use CSS Modules + Tailwind

**Question:** Are these forbidden patterns acceptable as hard constraints for Phase 7?

- A. **Yes, all forbidden** — Enforce via ESLint, fail CI on violation
- B. **Allow exceptions** — Specify which patterns to allow and why
- C. **Add more forbidden** — Specify additional patterns to ban
- X. Other (please specify)

---

### 7. Testing — Coverage Floor
**Default (from org.md):** 80% line coverage for `feature` scope.

**Question:** Is 80% line coverage the correct floor for Phase 7 new code?

- A. **Yes, 80%** — Matches org.md feature scope requirement
- B. **Higher (90%)** — Stricter for security-critical wiring
- C. **Lower (70%)** — Pragmatic for wiring work
- X. Other (please specify)

---

### 8. Security Review Timing
**Architect recommendation:** Mid-implementation (Week 2) security review for AssetViewer migration.

**Question:** When should the security review for AssetViewer migration (SEC-8/SEC-9) happen?

- A. **Early (Week 1)** — Design review before implementation
- B. **Mid (Week 2)** — Review implementation after AssetViewer complete (architect recommendation)
- C. **Late (Week 3)** — Final sign-off before merge
- D. **Continuous** — Security reviewer in daily standups
- X. Other (please specify)

---

### 9. Observability
**Current state:** No client-side error tracking (Sentry/DataDog).

**Question:** Should Phase 7 add client-side error tracking?

- A. **Yes, add Sentry** — Full error tracking for Phase 7
- B. **Yes, add DataDog** — Full error tracking with DataDog
- C. **No, defer** — Current console logging sufficient for Phase 7
- D. **Add later** — Post-Phase 7 initiative
- X. Other (please specify)

---

## Confirmation

**Please respond with your choices (A/B/C/D/E/X) for questions 1-9.**

[Answer]:
1. A
2. B
3. A
4. C
5. B
6. A
7. A
8. B
9. A

---

## Consolidated Summary Confirmation

**Summary of your choices:**

1. **Way of Working**: A — Trunk-based, short-lived branches, squash-merge (confirmed)
2. **Walking Skeleton**: B — Yes, build skeleton (end-to-end verification first)
3. **Testing Methodology**: A — test-after (team default)
4. **Testing Ordering**: C — Test-last per component (implement fully, then test)
5. **Deployment — Production Approval**: B — Automatic on merge (continuous deployment)
6. **Code Style — Forbidden Patterns**: A — Yes, all forbidden (enforce via ESLint)
7. **Testing Coverage Floor**: A — 80% (matches org.md feature scope)
8. **Security Review Timing**: B — Mid (Week 2) after AssetViewer complete
9. **Observability**: A — Yes, add Sentry (full error tracking for Phase 7)

**Confirm** — Does this all look correct before I generate the final artifacts?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct