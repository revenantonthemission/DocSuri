# DocSuri v2 — Design Verification

Date: 2026-10-11 (Asia/Seoul). Scope: documentation and the local [screen atlas](prototype/index.html). This record does not claim service implementation, user validation, data continuity, durable storage, integration parity or WCAG conformance.

## Artifact identity and environment

- Final atlas SHA-256: `68a3f2018e5961429c5f3d2295616eff60182d432b0efc1319c84f4729bb4f1e`.
- Local installed Google Chrome `154.0.8037.98`, launched headless by the repository's Playwright test package `1.55.1` in a temporary isolated browser profile.
- File URL opened directly; no DocSuri service, database, worker, real accounts or provider credentials used.
- The bundled Playwright browser binary was absent. The installed Chrome fallback required execution outside the filesystem sandbox. No browser download or package change was made.
- Atlas state controls and action dialogs are simulations. They do not perform the persisted or external actions whose UI they illustrate.

## Performed checks

| Check | Observed result / limits |
| --- | --- |
| Requirements map | All 50 stable FR subrequirement IDs appear in the 20-row capability map; 18 screen/record compositions and 11 component specifications counted |
| Responsive normal layouts | 18 compositions × 5 widths (1440, 1024, 768, 390, 320 CSS pixels) × 2 themes = 180 renders; no whole-page horizontal overflow detected |
| Basic visible-control naming | No visible button/input/select/textarea without text, associated label or aria-label detected in those 180 renders; this heuristic is not a full accessible-name audit |
| Search recovery | Loading, empty and failure × five widths × two themes = 30 renders; query and selected search mode remain visible and unchanged, with an editable results-region recovery panel; edit action focuses the query |
| Draft states | M08/M09 × saving/loading, failure, interruption, conflict and recovery = 10 checks at 390px; helper names the last acknowledged example time and excludes newer unsaved edits; typing in normal state marks the text unsaved |
| Access-denied mock | Sample content region cleared; this is rendering behavior only, not a test of service authorization or actual account isolation |
| Dialog keyboard | Initial focus on safe close/cancel, reverse and forward Tab wrap, Escape close and focus return passed after correcting focus containment |
| Compact navigation | Open menu and Escape returned focus to its trigger |
| System appearance | Emulated OS dark/light changes updated the selected System appearance; assertion waited for the actual media-change event |
| Source navigation | Second fixture opened 2005.11401v4; returning to search preserved the entered query; research source link returned to 1706.03762v7 rather than inheriting unrelated prior paper context |
| Novelty action | M09 visible primary label and simulated action both say Start analysis (`분석 시작`); research question submission retains its distinct label |
| Runtime/network | No page-script errors and no HTTP(S) requests observed during the complete revised-atlas run |
| Palette | 26 opaque token pairs read from the rendered stylesheet passed their checks: selected text pairs ≥4.5:1 and control boundaries ≥3:1, including soft, error and warning backgrounds. This is not an exhaustive pixel-level contrast audit |
| File checks | Relative documentation links, Unicode replacement characters, stable IDs and final newlines checked; Git whitespace check passed before review |

The final run exercised the atlas identified by the hash above after the palette and interaction changes. Its repeatable [verification script](prototype/verify.cjs) records the browser, counts, contrast ratios and content hash. Initial candidate control borders failed adjacent soft/error or dark warning backgrounds; the final light `#818997` and dark `#728094` variants pass all sampled boundary pairs. No claim is made that every state of every screen was exercised at every width. Draft copying, persistent storage, Browser Back integration and service actions remain outside this simulation's implemented behavior.

## Visual inspection evidence

The designer inspected desktop search/recovery, dark reader, phone research and phone conflict captures for readable hierarchy, wrapping and clipping. Five current illustrative captures are retained:

- [Search — desktop](prototype/previews/search-desktop.png)
- [Search recovery — desktop](prototype/previews/search-recovery-desktop.png)
- [Reader — dark desktop](prototype/previews/reader-dark-desktop.png)
- [Research — phone](prototype/previews/research-phone.png)
- [Draft conflict — phone](prototype/previews/draft-conflict-phone.png)

The sample screens visibly mark design-only data. Operator records are conceptual representations of existing interfaces, not a shipped web operations console. The prototype navigation is intended for screen review; most product actions open a generic simulation dialog rather than completing a workflow.

## Reproduction outline

1. Open `prototype/index.html` locally in an available browser. No build or server is required. From the repository root, `node aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/refined-mockups/prototype/verify.cjs` repeats the automated checks and refreshes captures. It uses the installed Chrome path by default; set `DOCSURI_CHROME` to another compatible executable if needed. It requires the existing frontend Playwright dependency and does not install anything.
2. Inspect all 18 Screen choices at the five widths above in Light and Dark appearance. Compare document scroll width with viewport width and inspect content clipping.
3. On M03 select loading, empty and failure: query, filters and ordering remain visible; the results region changes. On M08/M09 compare both draft-status lines for saving, failure, interruption, conflict and recovery; access-denied clears the sample content. The remaining generic state examples are available for inspection but not exhaustively tested.
4. In Search, activate Save search; check initial focus, Tab/Shift+Tab containment, Escape and focus return. At phone width repeat menu open/Escape.
5. Select System and change the emulated OS preference; wait for its media-change event and check the rendered theme.
6. Open the second paper from Search and inspect v4 identity; then open the research evidence link and inspect the P1 v7 identity.
7. Treat this as prototype verification only. Run the [accessibility checklist](accessibility-checklist.md) and V01–V09 against the implemented service before any release claim.

## Still required before implementation acceptance

Actual supported-browser/assistive-technology coverage; manual screen-reader and zoom/text-spacing assessment; content figure/math alternatives; source-complete parity vocabulary; draft storage/retention/deletion and shared-device security; real job/owner/transport tests; sustainable public-service/email/provider behavior at $0; and baseline-backed numeric quality goals. No real data migration, account reset, message delivery, Notion export or production operation occurred.
