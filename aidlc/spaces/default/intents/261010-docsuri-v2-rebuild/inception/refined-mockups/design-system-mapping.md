# DocSuri v2 — Design System Mapping

Date: 2026-10-11 (Asia/Seoul). Based on the [confirmed direction](refined-mockups-questions.md), [mockups](mockups.md) and bounded current-source inspection. This is a fresh visual system with behavior retained where it satisfies the requirements; it does not choose the implementation stack.

## Foundations

| Foundation | Proposed value / rule |
| --- | --- |
| Brand | DocSuri wordmark; simple typographic mark; no new raster logo or paid asset dependency |
| Voice | Calm, specific and action-oriented; Korean reference interface copy with original-language paper titles; English design documentation |
| Layout | 224px desktop rail, content max 1440px, reading-first hierarchy; assistance about 320px only where it fits |
| Spacing | 4/8/12/16/24/32/48 CSS-pixel scale; use a few consistent gaps rather than per-screen overrides |
| Corners | 8px controls; 16px content panels; no extreme rounding on dense research data |
| Type | System sans for controls/Korean, system serif for editorial paper titles only; 16px base, body line-height about 1.65; 14px supplementary labels and flexible 28–40px page headings |
| Reading | Approximately 65–75 Latin characters per line as a starting point; validate Korean/mixed text, math and tables independently |
| Controls | 44px primary control height as a design preference; WCAG 2.2 AA's 24px target/spacing criterion assessed separately |
| Focus | 3px semantic accent outline and 2px offset; never suppress without equivalent visible replacement |
| Motion | No motion needed to understand progress; reduced-motion removes decorative transitions; no endlessly animated fake progress |
| Layers | Page, bounded popover, modal; avoid overlapping competing panels or fixed bars hiding content/focus |

System fonts keep the design usable without remote font delivery. Font rendering/line breaks vary by platform, so the final browser/language matrix must be exercised rather than inferred from this atlas.

## Semantic colors

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| canvas | #F4F5F0 | #101C1A | Application background |
| surface | #FFFFFF | #182925 | Paper, cards and controls |
| text | #192D2B | #F1F5F1 | Main content |
| muted | #536461 | #AFBDB5 | Secondary text; still readable |
| accent | #126B56 | #8DDFBC | Primary action/link/focus |
| on-accent | #FFFFFF | #101C1A | Text on primary action |
| border | #7D8A85 | #829A90 | Required control boundaries |
| danger | #A12D3C | #FFA7B1 | Error text with explicit label/icon |
| warning | #785700 | #E9CA83 | Partial/stale/limited status with text |

Semantic names carry into any chosen technology. Do not scatter raw colors among components. Decorative separators may use softer colors only when they are not the sole control/focus/status boundary.

Calculated opaque sRGB contrast against the surface (two-decimal rounding; preliminary token check, not rendered conformance):

| Appearance | Foreground role | Foreground | Background | Ratio |
| --- | --- | --- | --- | --- |
| light | text | #192D2B | #FFFFFF | 14.47:1 |
| light | muted | #536461 | #FFFFFF | 6.24:1 |
| light | accent | #126B56 | #FFFFFF | 6.44:1 |
| light | border | #7D8A85 | #FFFFFF | 3.59:1 |
| light | danger | #A12D3C | #FFFFFF | 7.10:1 |
| light | warning | #785700 | #FFFFFF | 6.64:1 |
| light | button | #FFFFFF | #126B56 | 6.44:1 |
| dark | text | #F1F5F1 | #182925 | 13.79:1 |
| dark | muted | #AFBDB5 | #182925 | 7.79:1 |
| dark | accent | #8DDFBC | #182925 | 9.70:1 |
| dark | border | #829A90 | #182925 | 5.04:1 |
| dark | danger | #FFA7B1 | #182925 | 8.25:1 |
| dark | warning | #E9CA83 | #182925 | 9.58:1 |
| dark | button | #101C1A | #8DDFBC | 11.15:1 |

Calculations use WCAG relative luminance and (Llighter + 0.05) / (Ldarker + 0.05). The chosen text tokens exceed 4.5:1 on the stated surface and boundary tokens exceed 3:1. Every actual combination, opacity, image overlay, focus state and disabled-state usage still needs a rendered check. Large text can use the applicable 3:1 threshold; do not apply that threshold to ordinary text.

## Current-to-proposed component mapping

The reference scope consists of nine exact source paths inspected on 2026-10-11. Graph coverage reported no recorded gap and matching metadata at generation 2026-10-11T02:00:14Z; direct source reads informed the observations. This is not an exhaustive component audit. Package metadata is inventory, not a commitment to retain Next/React/Tailwind or any other library.

| Current source | Observed behavior / concern | Proposed disposition |
| --- | --- | --- |
| [globals.css](../../../../../../../frontend/app/globals.css) | Semantic tokens, Korean font fallbacks, system/explicit dark styles and visible outline | Keep semantic-token approach; replace palette/type/spacing with this system; verify every component consumes it |
| [theme.ts](../../../../../../../frontend/lib/theme.ts) | Browser-local choice with system fallback; storage failure tolerated | Preserve Light/Dark/System behavior; label preference state; do not claim account sync that does not exist |
| [ThemeContext.tsx](../../../../../../../frontend/components/theme/ThemeContext.tsx) | Effective OS theme sampled at mount while CSS can respond later | Ensure System label, actual colors and controls respond together to OS changes; check blocked storage without a crash |
| [AppHeader.tsx](../../../../../../../frontend/components/AppHeader.tsx) | Korean destinations, paper/search active mapping, explicit back destination | C01 replaces visual shell; preserve reliable context/back behavior and map every existing destination |
| [BottomNav.tsx](../../../../../../../frontend/components/BottomNav.tsx) | Three compact Korean destinations and active cues | Replace navigation layout for desktop-first emphasis; phone menu retains all web capabilities rather than only three shortcuts |
| [AuthField.tsx](../../../../../../../frontend/components/AuthField.tsx) | Associated labels, validation, autocomplete, password visibility and clear/refocus | Retain successful C08 patterns, expand to provider/MFA/recovery states and both appearances |
| [JobStatus.tsx](../../../../../../../frontend/components/JobStatus.tsx) | Connection/fallback/terminal feedback and event history; fixed color classes and technical state labels | C04 separates connection from job state; semantic colors and understandable copy; verify real transport and ownership |
| [SummaryModal.tsx](../../../../../../../frontend/components/SummaryModal.tsx) | Reads existing results and rereads on retry; source callback, initial focus/Escape/scroll lock; no complete trap/restore evident in inspected component | C03/C04/C07 preserve read-only behavior and source return, add specified focus containment/restoration and explicit expiry |
| [package.json](../../../../../../../frontend/package.json) | Existing frontend/test libraries and historical phone-first description | Inventory only; desktop-first choice supersedes old emphasis; select implementation from later evidence |

## Proposed component inventory and ownership boundaries

| Component family | Responsibility | Keep out of this component |
| --- | --- | --- |
| C01 shell/navigation | Current destination, owner-context display, responsive access | Authorization decisions based only on hidden links |
| C02 query/results | Query/refinement state and result presentation | Search-provider selection or fabricated fallback data |
| C03 paper/reader | Version-bound sections, assets and source navigation | Raw unsafe markup or private/public URL interchange |
| C04 activity/result | State rendering, reconnect view and explicit result read | Implicit resubmission or business dispatch logic |
| C05 durable composer | Input revision, acknowledgement and recovery/conflict UI | Plaintext shared storage shortcuts, automatic restored submission |
| C06 saved work | Committed list/mutation state and scope-specific deletion | Optimistic permanent success without reconciliation |
| C07 dialog/confirmation | Focus, scope/consequence presentation, deliberate action | Hidden external effects on open/close |
| C08 identity/settings form | Labels, validation, permitted input recovery | Client-only authentication/validation |
| C09 evidence/attachments | Claims/source links, coverage, safe artifact views | Treating model/source instructions as authority |
| C10 usage/admin/operation record | Freshness, target, authority and outcome display | Paid fallback or claiming process health equals readiness |
| C11 export preview | Current preview/destination and approval state | Secrets or implicit remote publication |

These are conceptual responsibilities to support repairability; file/package boundaries remain Domain/Contract/Functional Design decisions. Central state/error vocabulary and tested shared behavior reduce per-screen divergence. Every server boundary remains authoritative for owner, resource and operation identity.

## Responsive and language mapping

| Context | Rule |
| --- | --- |
| Desktop ≥1200px | Rail and main context; reading takes priority over secondary assistance; content does not stretch indefinitely |
| Compact 768–1199px | Compact navigation, narrower paired content or assistance below; retain readable form/reader widths |
| Phone <768px | One column, labeled navigation disclosure, stacked actions and full-width panels; no capability removed |
| Reflow/zoom | Normal content works at 320 CSS pixels / equivalent 400% desktop zoom; genuine 2D content scrolls within named regions |
| Korean/mixed text | Korean copy and source-language titles; safe word wrapping for identifiers and URLs; no fixed-height text clipping |
| Appearance | Light/Dark/System available; OS changes update System appearance; all state/focus/feedback tokens tested in both themes |

## Assumptions & Open Questions

Exact supported language choices, per-operation options and current component sub-behaviors still require IB-01/03 reconciliation. Token consistency and conceptual boundaries are proposed, not implemented. Final type sizing, content density and breakpoints require reading/usability checks with actual representative content. Accessibility verification, browser coverage, storage/privacy and $0 capacity remain dependencies in the companion documents.
