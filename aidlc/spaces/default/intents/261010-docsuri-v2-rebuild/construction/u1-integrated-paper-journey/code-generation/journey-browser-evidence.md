# Canonical journey browser surface and mounted boundary evidence

Date: 2026-10-13 (KST). Code Generation Steps 9–12 complete and ticked;
assistance normal-output readiness remains false and is not claimed here.

## Implemented boundary

- `backend/local_browser.py` now owns the shared canonical browser boundary:
  exact Host/scheme/origin/cookie bounds, bounded JSON bodies, server-derived
  principal (session or bound anonymous entry flow), canonical safe error
  mapping and private cookies. Owner-declared conflicts (40001 revision,
  23505 changed intent, P0001 guard decision) map to `409 CONFLICT` and check
  violations to `422 INVALID_ARGUMENT`; a serialization failure is no longer
  misreported as a dependency outage. `accounts/local_http.py` was refactored
  onto it with unchanged 403 dispositions for denied identities and its full
  mounted suite stayed green.
- `backend/local_host.py` assembles the journey realm: account, host, corpus,
  discovery, library, settings, usage and assistance routers, a public
  `/api/v2/capabilities` catalogue with the real local vocabulary, and truthful
  readiness. C01 `host-resolve-navigation` returns the finite installed route
  manifest for the current principal: pending capabilities stay visible but
  unavailable, owner-bound destinations are unavailable to an anonymous caller,
  a changed authority revision clears prior private rendering state, return
  context is schema-validated and echoed, navigation creates no work and an
  unknown route id is refused before any effect.
- `backend/local_observation.py` is the bounded owner-store observation
  boundary. Each installed owner provides one read of its own key relation and
  guard function through its own pool; results are recorded through the
  operations owner and `/health/ready` derives from fresh observations,
  re-probing within the same bounded call when evidence is missing or stale.
  A missing store, schema, relation or privilege never passes as ready, and
  observation evidence carries counts only — no content, identifiers or
  credentials.
- New owner adapters: corpus (`resolve-paper`, `read-content`, the canonical
  asset route with bounded unavailability), discovery (`c05/search` with owner
  or bound-anonymous CSRF, snapshot-expiry disposition, semantic mode requiring
  a real embedder), library (save/list/read/remove paper and saved query,
  history list/read/clear with the server-captured checkpoint), personalization
  (`settings-read`, `settings-update`, `settings-update-onboarding` over the
  retained manual vocabulary), usage (`usage-inspect` over the finite no-reset
  wallet bound to the environment retention window), and assistance
  (`read-assistance-options`, `accept-assistance`, `read-assistance-job`,
  `read-prepared-assistance`, `read-assistance-history`, `read-glossary`,
  `/api/v2/jobs/*` and the ordered `Last-Event-ID` progress stream).
- `summarization/local_catalog.py` is the finite, documented source-selection
  policy over the two approved fixtures; `summarization/local_result.py` is the
  private canonical result document codec. The mounted options catalogue
  truthfully exposes no runnable option and `accept-assistance` refuses with
  `503 NOT_READY` while the reviewed-readiness marker is absent.
- Owner-side participant initialization: Library `ensure_boundary` and Usage
  `ensure_entitlement` create the owner rows a freshly registered account needs
  before its first effect.
- Append-only amendments applied through the owned bootstrap to both realms:
  `corpus.reference_metadata` (metadata-only saved-reference identity),
  `library.history.sequence` (completion ordering), `usage.entitlement.created_at`
  (no-reset period), `assistance.result.revision` (canonical ResultRef).
- Fixed a real adapter defect: a fresh `library.history_boundary` stores
  `eligible_after = '-infinity'`, which psycopg cannot load into a Python
  datetime; the repository now selects only the generation/revision tokens it
  owns. Corpus `reader_view` no longer calls the library/assistance-only
  availability function; corpus-owned row state decides the disposition.

## Route scope decisions (U1 boundary, not silent gaps)

The canonical contract lists every unit's operations. The authoritative
functional design assigns the following to later units, so this unit does not
mount them and never fabricates their behavior:

- `settings-list-suggestions`, `settings-list-recent-papers`, `settings-reset`,
  usage records/plan/assignment and administrator grant/revoke: WF8.5 declares
  "full preference variants, recent-paper behavior, consent/reset controls …
  and remaining administrative quotas are U2 parity work". `settings-update-onboarding`
  is a U1 binding (component hierarchy, entry/default state) and is mounted.
- `accept-corpus-run` / `read-corpus-run` / `retry-corpus-run`: ingestion
  execution is U2; U1 publishes eligible versioned fixtures and withdrawal
  through its owned bootstrap and repository.
- `replace-glossary`: the functional specification assigns glossary to U3;
  U1 reads the owner-bound empty-glossary token and captures it at acceptance.
- C11 `read-dashboard` / `list-incidents` / `request-recovery`: "full operator
  protocols are not added to U1"; the local operator surface is the supervisor
  and verification tooling (Steps 13–14), not a browser administrator.
- C05 `read-citations`, C07–C14 operations: U8/U4/U5/U6/U7.

## Korean workspace and mounted browser scenarios (Steps 11–12)

The Vite static workspace (`frontend/index.html`, `frontend/src/`) replaces the
placeholder with the approved Korean journey: session bootstrap and account
entry (register/verify/login), C01 navigation, search with visible query/order
controls and bounded author/year filters, exact paper/version reading with
anchor targets, save/remove with truthful pending/unknown/conflict/committed
states, library (saved papers, saved queries with an explicit 다시 검색,
history with a scoped clear confirmation), assistance options/history/result
reads, appearance (light/dark/system, storage-failure tolerant), finite usage
and the shared skip link/main-region focus path. The account subtree remounts
on an account change, so a late A response cannot populate B, and the
bootstrapping state is rendered before any private surface. Two races found
during the browser pass were fixed in the app: the transport now bootstraps
lazily when a reload submits before the first session read, and the shell no
longer presents the entry form while authority is unknown.

Executed evidence (all with the real mounted backend, persistent store and
static build; nothing mocked):

| Command (wrapper phase) | Result |
|---|---|
| `--phase frontend` | **11 passed**, zero failures (`frontend-outcomes.json`) |
| `--phase browser` | **6 passed**, zero skipped/unexpected, axe scan clean of serious/critical violations |

The six mounted scenarios cover: (1) P1 find → read (`softmax` literal) → save →
fresh authenticated return through owned lists; (2) P2 guest search, the
truthful sign-in requirement for private reading, then the authenticated exact
`2005.11401v4` read; (3) assistance truthfully refuses new work while the model
readiness marker is absent (no option, no start control, no fabricated job);
(4) cross-account denial with an authorized positive control (A's saved marker
query is visible to A through the UI and the direct API, invisible to B through
both); (5) reload interruption recovers the same authoritative truth with no
locally asserted outcome, job or result identity; (6) 320px reflow, skip-link →
main keyboard focus, light/dark appearance persistence, 200% text reflow and a
rendered axe scan (automated evidence only; manual confirmation still required).

Truthful adaptations (readiness gap, not manufactured passes): the planned
"supported translation" and "interrupted accepted-work recovery" scenarios
cannot exercise accepted assistance while P1/P2 model evidence is unresolved, so
scenario 3/5 assert the refusal and the read-only reload recovery instead. A
stream break/sleep/restart is exercised at the component boundary (a closed
stream marks only the connection stale; bounded polling recovers the
authoritative snapshot). The accessibility scan is automated evidence; rendered
manual confirmation remains outstanding.

The 200% text check found and fixed a real reflow defect (bounded inputs/selects
now shrink instead of overflowing at 320px), and the axe scan found and fixed a
real contrast defect (link/nav text now uses the accessible accent variant).

The browser phase additionally required two bounded runner capabilities, now in
`scripts/verify_docsuri_u1.py`: it re-mints the owned journey TLS material when
the environment retention was explicitly renewed (the certificate is bound to
that window), and it performs the finite fixture transition for the browser run
(two registered owners; the established demo account is deactivated for the run
and reactivated afterwards, with the test-owned attempt ledger reset). Neither
step deletes user data or touches another realm.

## Executed checks and outcomes (Steps 9–10 backend suites)

```text
python3 scripts/verify_docsuri_u1.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

| Phase | Result |
|---|---|
| database | **47 passed**, zero skips/failures |
| component | **198 passed**, zero skips/failures |
| repository | **84 passed**, zero skips/failures |
| integration | **23 passed**, zero skips/failures |

The integration suite runs the actual journey database and published P1/P2
corpus: real registration/verification/login through the mounted HTTPS-scheme
ASGI boundary, lexical search finding both approved papers, canonical content
reading (literal `softmax`/LaTeX text preserved), acknowledged save re-discovery
after a fresh authenticated return, recorded search history and clear with a
server-captured checkpoint, settings CAS plus onboarding transitions with an
unsupported-interest refusal and stale-revision conflict, finite usage, truthful
assistance refusal, figure-caption reading with bounded asset unavailability and
anonymous denial, mounted read-glossary token/isolation, library receipt replay
after a later removal with a changed-intent conflict, C01 navigation permissions
and return context, observation-derived readiness including stale-evidence
re-probe, and an owner-bound assistance job created through the real repository
path whose snapshot, prepared result, ordered SSE replay, expired-result
disposition and reconnect resume are read by owner A while owner B receives
identical 404/empty dispositions. The four carried legacy paper-job defects
(Q-01 ordering/recovery, Q-02 result semantics, Q-03 non-no-op dispatch, Q-04
frame framing/reconnect) have regressions through the actual U1 bindings.
Reads created no new job and no debit.

Scoped Ruff lint and format passed on every changed file; `git diff --check`
passed. A stale `__pycache__` entry that had compiled a helper as a generator
was cleared after diagnosis; the cause (same-second edit with unchanged size)
is a test-harness issue, not product behavior.

## Remaining obligations (not claimed)

- Assistance normal-output readiness (P1/P2 grounding and priority) remains
  false with all failed model attempts retained; the mounted options/accept
  paths truthfully refuse new work until reviewed evidence exists.
- No corpus figure bytes exist in this realm; the reader exposes captions and
  the asset route returns a bounded unavailability instead of fabricated
  content.
- Progress frames come from the authoritative job sequence, including stored
  trigger-appended events; dedicated progress publication remains worker work.
- Cumulative 80% per-module coverage measurement, the Korean web experience
  (Steps 11–12), browser journeys, operations supervision (Steps 13–14) and the
  completion record (Step 15) remain. The semantic search mode requires the
  pinned local embedder; the mounted assembly currently admits lexical mode
  only.
