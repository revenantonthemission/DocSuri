# Design-System Mapping — Phase 7 Frontend Wiring

## Sources and Existing Surface

Grounding: `frontend/app/globals.css`, `frontend/components/SummaryModal.tsx`, `SummaryModal.module.css`, `PaperDetailIsland.tsx`, and `AssetViewer.tsx`. Product sources are `../requirements-analysis/requirements.md`, `../user-stories/stories.md`, `../practices-discovery/team-practices.md`, and confirmed `refined-mockups-questions.md`. `../../ideation/rough-mockups/wireframes.md` and `user-flow.md` supply historical context; their token and behavior proposals are not verified implementation facts.

## Existing Semantic Tokens

These values were read from globals.css. OS dark-mode selection and explicit data-theme light/dark overrides already exist. Reuse both theme paths; do not add a competing status-only theme system.

| Token | Light | Dark | Intended use |
|---|---|---|---|
| --color-bg | #ffffff | #131519 | Page surface |
| --color-surface | #f7f8fa | #1c1f25 | Status/dialog/viewer surface |
| --color-text | #16181d | #f1f3f6 | Main status/caption/control text |
| --color-text-muted | #6b7280 | #9aa3b0 | Secondary timestamps; contrast must be checked per surface |
| --color-border | #d9dde3 | #2c313a | Decorative borders; not sufficient alone for meaningful control boundaries |
| --color-accent | #2f6df6 | #5b8bff | Focus and primary-action emphasis |
| --color-accent-contrast | #ffffff | #0b0c0e | Candidate filled-action text; verify the actual pair |
| --color-danger | #c0362c | #ff7a70 | Error text/icon, always with wording |
| --color-danger-bg | #fdecea | #3a1d1a | Error surface |
| --color-warn-text | #8a5a00 | #ffd98a | Degraded connection emphasis |
| --color-warn-bg | #fff4e0 | #3a2e16 | Degraded connection surface |

No palette-wide contrast pass is claimed. Check rendered text, focus, controls and surfaces in both themes, including overlay compositing. Use --color-text where a muted/accent combination cannot meet the applicable contrast target. A success indicator can use neutral text plus an icon/Completed label; a new success token is optional design implementation work only if justified and contrast-checked.

## Component Mapping

| Design element | Existing starting point | Required integration |
|---|---|---|
| Initial submission surface | Existing summary-level selector and centered dialog styling | Preserve supported initial choices; explicit submit only; pre-job recovery with neutral outcome feedback |
| JobStatus panel | Existing JobStatus and paper-detail action context | Add sticky/in-flow adaptation, actual progress, safe history/recovery and connectivity states |
| Completed result surface | SummaryModal, SummaryView, TranslationView | Read-only submitted-level metadata and exact prepared content; remove mount/selection commands; explicit expiry/unsupported/transient states and read-only retry |
| Asset viewport | AssetViewer | Migrate to paperId/assetId same-origin delivery, actual aspect ratio and controlled load failures |
| Copy feedback | Native button and status text | Exact ID clipboard handling, accessible pending/success/failure states |
| Zoom/pan/reset | Proposed viewer controls | Named native buttons, optional scoped shortcuts, clamped transforms, same-image overview |
| Full-page render fallback | Proposed stable parent presentation and JobStatus boundary | Same-route error display with recovery and safe return; no submit on either action |
| Error/history disclosure | Native details/summary or existing disclosure pattern | Safe content, meaningful labels, keyboard operation |

New component extraction and file organization belong to Domain/Functional Design. Do not create duplicate JobStatus/AssetViewer trees merely because the old mockups listed several alternative paths. CSS Modules plus Tailwind and clsx/tailwind-merge remain the affirmed conventions.

Recovery feedback uses existing semantic text/warning/error tokens with explanatory wording, not a new color implying that every resend starts work. Distinguish actual job state from request-outcome feedback and result availability. Busy action controls retain visible focus while duplicate activation is guarded; removing an action follows the interaction specification's conditional focus rule. No new theme/token namespace is needed for the backend amendment.

## Proposed Local Layout and Motion Parameters

| Parameter | Proposal | Constraint |
|---|---|---|
| Status panel reading width | Fluid, capped at 46rem | Match the existing desktop reading-dialog scale without covering navigation |
| Panel spacing | 1rem padding, 0.5–0.75rem internal gaps | Rem-based sizing; controls wrap |
| Status placement | Bottom of usable viewport above navigation/safe area | Reserve actual panel height in page layout; use in-flow fallback per interaction-spec |
| Existing modal widths | Fluid phone width; 32rem cap from 480px; 46rem from 768px | Source-backed starting point, not a mandate for new global breakpoints |
| Touch/click control target | 44 CSS pixels preferred minimum | Project design target; not misrepresented as a blanket WCAG 2.1 AA threshold |
| Cosmetic transitions | 100–150 ms color/opacity; no delayed status commit | No movement or pulse under reduced motion |
| Viewer transforms | 0.5x–4x relative to fit, fit at 1x | Local interaction proposal; preserve browser zoom and keyboard escape |

Proposals are design handoff parameters, not additional backend/performance SLAs. The selected micro-interactions are hover/press feedback and restrained state transitions, not continuous animations that obscure actual progress.

## Accessibility and Verification Handoff

Reuse the global focus-visible outline as a starting point, but verify contrast against each actual surface; never remove focus indication without replacement. The current modal panel uses outline:none for programmatic panel focus, so provide an appropriate visible focus treatment or focus a visibly identified heading when needed. Maintain WCAG text and non-text thresholds, live messages outside hidden containers, focus restoration, and 320px reflow. See `accessibility-checklist.md` for pending checks and story links. Existing source is not evidence that these integration states already conform.
