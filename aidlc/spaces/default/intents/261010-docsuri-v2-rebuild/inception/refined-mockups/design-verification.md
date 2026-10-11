# DocSuri v2 — Design Verification

Date: 2026-10-11 (Asia/Seoul). Scope: documentation and the local [screen atlas](prototype/index.html). This record does not claim service implementation, user validation, data continuity, durable storage, integration parity or WCAG conformance.

## Artifact identity and environment

- Final atlas SHA-256: `90e22209edae87a7dc33a32f253a5a597b29518ac3cc82a22ca7d0e04244bd22`.
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
| State selector | Nine non-normal examples rendered: loading, empty, failure, partial, interrupted, access-denied, expired, recovered draft and draft conflict |
| Access-denied mock | Sample content region cleared; this is rendering behavior only, not a test of service authorization or actual account isolation |
| Dialog keyboard | Initial focus on safe close/cancel, reverse and forward Tab wrap, Escape close and focus return passed after correcting focus containment |
| Compact navigation | Open menu and Escape returned focus to its trigger |
| System appearance | Emulated OS dark/light changes updated the selected System appearance; assertion waited for the actual media-change event |
| Source navigation | Second fixture opened 2005.11401v4; research source link returned to 1706.03762v7 rather than inheriting unrelated prior paper context |
| Conflict wording | Phone conflict state explicitly says new changes are not saved; no contradictory saved indicator; no horizontal overflow after the wording change |
| Runtime/network | No page-script errors and no HTTP(S) requests observed during the 180-render/state/keyboard run |
| Palette | Opaque semantic pairs calculated: text/secondary/accent/error/warning exceed 4.5:1 on the stated surfaces; control borders exceed 3:1; actual combinations still need implemented verification |
| File checks | Relative documentation links, Unicode replacement characters, stable IDs and final newlines checked; Git whitespace check passed before review |

The 180-render sweep ran before the last small source-language, explicit source-identity and draft-conflict-label edits. Those final edits received targeted navigation, conflict-label and 390px overflow checks; the conflict screenshot was refreshed. The final hash above identifies the resulting atlas. No claim is made that every state of every screen was exercised at every width.

## Visual inspection evidence

The designer inspected desktop search, desktop reader, phone research, dark reader and phone conflict captures for readable hierarchy, wrapping and clipping. Four current illustrative captures are retained:

- [Search — desktop](prototype/previews/search-desktop.png)
- [Reader — dark desktop](prototype/previews/reader-dark-desktop.png)
- [Research — phone](prototype/previews/research-phone.png)
- [Draft conflict — phone](prototype/previews/draft-conflict-phone.png)

The sample screens visibly mark design-only data. Operator records are conceptual representations of existing interfaces, not a shipped web operations console. The prototype navigation is intended for screen review; most product actions open a generic simulation dialog rather than completing a workflow.

## Reproduction outline

1. Open `prototype/index.html` locally in an available browser. No build or server is required.
2. Inspect all 18 Screen choices at the five widths above in Light and Dark appearance. Compare document scroll width with viewport width and inspect content clipping.
3. Select each State example. On M08/M09 compare the draft indicator with the banner; access-denied clears the sample content.
4. In Search, activate Save search; check initial focus, Tab/Shift+Tab containment, Escape and focus return. At phone width repeat menu open/Escape.
5. Select System and change the emulated OS preference; wait for its media-change event and check the rendered theme.
6. Open the second paper from Search and inspect v4 identity; then open the research evidence link and inspect the P1 v7 identity.
7. Treat this as prototype verification only. Run the [accessibility checklist](accessibility-checklist.md) and V01–V09 against the implemented service before any release claim.

## Still required before implementation acceptance

Actual supported-browser/assistive-technology coverage; manual screen-reader and zoom/text-spacing assessment; content figure/math alternatives; source-complete parity vocabulary; draft storage/retention/deletion and shared-device security; real job/owner/transport tests; sustainable public-service/email/provider behavior at $0; and baseline-backed numeric quality goals. No real data migration, account reset, message delivery, Notion export or production operation occurred.
