# Team Formation Questions — Phase 7 Frontend Wiring

**Gate:** Delivery Lead Review (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/org.md#Way of Working`: "We use **trunk-based development**. All work merges to `main` via short-lived feature branches (typically resolved within 1-2 days)."
- [memory:M2] `aidlc/spaces/default/memory/org.md#Testing Posture`: "`feature` scope adds an 80% line-coverage floor and CI execution before merge."

---

## Questions for Team Formation

### 1. Team Composition
**Question:** Does the proposed team composition match available resources?

- A. **Yes, as proposed** — 2 Frontend, 1 Backend (PT), 1 QA (PT), 1 Security
- B. **Add 1 more Frontend** — Workload too high for 2 engineers
- C. **Reduce Backend/QA allocation** — Less part-time involvement needed
- D. **Use contractor for AssetViewer** — Specialized security migration
- X. Other (please specify)

### 2. Pairing Strategy
**Question:** Is targeted pairing (U2, U5) the right approach, or full mob?

- A. **Targeted pairing** — Pair only on high-risk units (U2 SSE, U5 idempotency)
- B. **Full mob** — All 2 frontend engineers mob on everything
- C. **No pairing** — Individual ownership with code review only
- D. **Pair on all U1-U6** — Pair for all core capabilities
- X. Other (please specify)

### 3. Security Review Timing
**Question:** When should Security Reviewer be engaged for AssetViewer migration (SEC-8/SEC-9)?

- A. **Early (Week 1)** — Review design before implementation starts
- B. **Mid (Week 2)** — Review implementation after U4 complete
- C. **Late (Week 3)** — Final sign-off before merge
- D. **Continuous** — Reviewer in Slack channel, async feedback
- X. Other (please specify)

### 4. Cross-Training Priority
**Question:** Which cross-training should happen first?

- A. **SSE deep dive** — Frontend Lead teaches Eng 2 EventSource patterns
- B. **BFF proxy internals** — Backend teaches both frontend engineers
- C. **Security compliance** — Security reviewer briefs both on SEC-8/SEC-9
- D. **Playwright E2E** — QA teaches SSE testing patterns
- X. Other (please specify)

### 5. Timeline Confidence
**Question:** Is the 6.5-day estimate realistic for this team?

- A. **Yes, confident** — Team velocity supports this
- B. **Add 1-2 days buffer** — SSE integration may have surprises
- C. **Reduce scope** — Drop Should/Could items if needed
- D. **Parallel tracks needed** — Both engineers full parallel from Day 1
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | 2 frontend engineers available at 50-100% | Org capacity |
| 2 | Backend engineer available 20% for contract clarification | Scope Definition |
| 3 | QA engineer available 40% for test review | Org capacity |
| 4 | Security reviewer available on-demand for sign-off | Scope Definition |
| 5 | Pair programming tools available (VS Code Live Share) | Standard tooling |
| 6 | Trunk-based workflow with 1-2 day branches | Org Way of Working |
| 7 | 80% coverage floor for new code | Org Testing Posture |

---

## Open Questions

1. **Remote pairing tool preference**: VS Code Live Share, Tuple, or screen share?
2. **Daily standup time**: 9:30 AM or async written updates?
3. **PR review SLA**: 4 hours, 8 hours, or next business day?

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-5.**

[Answer]:
1. A
2. A
3. B
4. D
5. A

---

## Consolidated Summary Confirmation

**Summary of your choices:**

1. **Team Composition**: A — Yes, as proposed (2 Frontend, 1 Backend PT, 1 QA PT, 1 Security)
2. **Pairing Strategy**: A — Targeted pairing on high-risk units (U2 SSE, U5 idempotency)
3. **Security Review Timing**: B — Mid (Week 2), review implementation after U4 complete
4. **Cross-Training Priority**: D — Playwright E2E first (QA teaches SSE testing patterns)
5. **Timeline Confidence**: A — Yes, confident (team velocity supports 6.5 days)

**Open Questions for Later:**
- Remote pairing tool: VS Code Live Share / Tuple / screen share (decide Week 1)
- Standup time: 9:30 AM or async (decide Week 1)
- PR review SLA: 4h / 8h / next business day (decide Week 1)

**Confirm** — Does this all look correct before I generate the artifact?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct