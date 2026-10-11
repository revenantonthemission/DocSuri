# DocSuri v2 — Design System Mapping

Date: 2026-10-11 (Asia/Seoul). Based on the [confirmed direction](refined-mockups-questions.md), [mockups](mockups.md) and bounded current-source inspection. This revision inherits DocSuri's current blue/neutral colors and applies Apple HIG principles through explicit web adaptations. It preserves required behavior and does not choose the implementation stack.

## Foundations

| Foundation | Proposed value / rule |
| --- | --- |
| Brand | DocSuri wordmark; simple typographic mark; no new raster logo or paid asset dependency |
| Voice | Calm, specific and action-oriented; Korean reference interface copy with original-language paper titles; English design documentation |
| Layout | 224px desktop rail, content max 1440px, reading-first hierarchy; assistance about 320px only where it fits |
| Spacing | 4/8/12/16/24/32/48 CSS-pixel scale; use a few consistent gaps rather than per-screen overrides |
| Corners | 8px controls; 16px content panels; no extreme rounding on dense research data |
| Type | One Korean-capable system sans stack for shell and paper text; weight, size and spacing express hierarchy. 16px base, body line-height about 1.65; 14px supplementary labels and flexible 28–40px page headings |
| Reading | Approximately 65–75 Latin characters per line as a starting point; validate Korean/mixed text, math and tables independently |
| Controls | 44px primary control height as a design preference; WCAG 2.2 AA's 24px target/spacing criterion assessed separately |
| Focus | 3px semantic accent outline and 2px offset; never suppress without equivalent visible replacement |
| Motion | No motion needed to understand progress; reduced-motion removes decorative transitions; no endlessly animated fake progress |
| Layers | Opaque reading surfaces, grouped controls, bounded popover and modal; restrained depth for functional overlays; no competing panels or fixed bars hiding content/focus |

System fonts keep the design usable without remote font delivery. Font rendering/line breaks vary by platform, so the final browser/language matrix must be exercised rather than inferred from this atlas.

## Semantic colors

Inherited values come from [current global styles](../../../../../../../frontend/app/globals.css), directly checked on 2026-10-11. These are DocSuri colors, not copied Apple system-color constants. Preserve their semantic roles in any selected implementation. The proposed additions are `accentText` in light appearance and `strongBorder` in both appearances.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| canvas | #ffffff | #131519 | Inherited application background |
| surface | #f7f8fa | #1c1f25 | Inherited neutral content/control surface |
| text | #16181d | #f1f3f6 | Inherited main content |
| muted | #6b7280 | #9aa3b0 | Inherited secondary text; fully opaque on canvas/surface |
| accent | #2f6df6 | #5b8bff | Inherited primary-action fill and focus cue |
| onAccent | #ffffff | #0b0c0e | Inherited text on primary-action fill |
| accentSoft | #eaf1ff | #1b2742 | Inherited selected/context background |
| accentText | #2963df | #5b8bff | Accessible blue links/selected labels on canvas, surface and accentSoft |
| decorativeBorder | #d9dde3 | #2c313a | Inherited nonessential separators; never sole control boundary |
| strongBorder | #818997 | #728094 | Added required control boundary, including adjacent status/selection backgrounds |
| danger | #c0362c | #ff7a70 | Inherited error text with explicit label/icon |
| dangerBg | #fdecea | #3a1d1a | Inherited error background |
| warning | #8a5a00 | #ffd98a | Inherited partial/stale/limited status text |
| warningBg | #fff4e0 | #3a2e16 | Inherited warning background |

Blue carries interactivity and selection consistently; normal prose uses `text`. A filled primary button uses `accent`/`onAccent`, while a blue text link uses `accentText`. Selected state also has a label/shape/semantic state; status is never conveyed by color alone. Avoid repeated saturated backgrounds across every control. Shadows and soft separators can organize content, but the required control boundary uses `strongBorder`.

The original light accent has 4.53:1 contrast on white but 4.26:1 on the inherited light surface, so it is not the normal-size text color on that surface. The darker blue text variant preserves the hue family. The original decorative borders provide only 1.28:1 (light) and 1.26:1 (dark) against their surfaces, so they cannot stand alone as required control boundaries. Neither case justifies changing the whole brand palette.

Calculated opaque sRGB pairs (two-decimal rounding; preliminary token check, not rendered conformance):

| Appearance | Foreground role / background role | Foreground | Background | Ratio |
| --- | --- | --- | --- | --- |
| light | text on surface | #16181d | #f7f8fa | 16.71:1 |
| light | muted on surface | #6b7280 | #f7f8fa | 4.55:1 |
| light | accentText on surface | #2963df | #f7f8fa | 5.01:1 |
| light | accentText on accentSoft | #2963df | #eaf1ff | 4.70:1 |
| light | strongBorder on surface | #818997 | #f7f8fa | 3.32:1 |
| light | strongBorder on accentSoft | #818997 | #eaf1ff | 3.11:1 |
| light | strongBorder on dangerBg | #818997 | #fdecea | 3.08:1 |
| light | strongBorder on warningBg | #818997 | #fff4e0 | 3.23:1 |
| light | danger on dangerBg | #c0362c | #fdecea | 4.83:1 |
| light | warning on warningBg | #8a5a00 | #fff4e0 | 5.44:1 |
| light | onAccent on accent | #ffffff | #2f6df6 | 4.53:1 |
| dark | text on surface | #f1f3f6 | #1c1f25 | 14.85:1 |
| dark | muted on surface | #9aa3b0 | #1c1f25 | 6.48:1 |
| dark | accentText on surface | #5b8bff | #1c1f25 | 5.17:1 |
| dark | accentText on accentSoft | #5b8bff | #1b2742 | 4.65:1 |
| dark | strongBorder on surface | #728094 | #1c1f25 | 4.11:1 |
| dark | strongBorder on accentSoft | #728094 | #1b2742 | 3.70:1 |
| dark | strongBorder on dangerBg | #728094 | #3a1d1a | 3.82:1 |
| dark | strongBorder on warningBg | #728094 | #3a2e16 | 3.31:1 |
| dark | danger on dangerBg | #ff7a70 | #3a1d1a | 6.03:1 |
| dark | warning on warningBg | #ffd98a | #3a2e16 | 9.82:1 |
| dark | onAccent on accent | #0b0c0e | #5b8bff | 6.13:1 |

Calculations use WCAG relative luminance and (Llighter + 0.05) / (Ldarker + 0.05). All listed text pairs exceed 4.5:1 and the strong boundaries exceed 3:1. The light muted pair (4.55:1) and filled blue button (4.53:1) have little margin: do not reduce enabled text opacity or move these colors onto another background without recalculating. Use `text` for secondary copy on accentSoft unless that exact pair is independently verified. Keep focus outlines separate from the control by their 2px offset and test the adjacent background; selected and hovered surfaces need their own rendered checks. Large-text thresholds do not apply to ordinary text. Inactive controls still require clear textual explanations when their unavailability affects a task.

## Apple HIG-to-web mapping

Primary Apple guidance was checked on 2026-10-11. The following applications are DocSuri design judgments for a browser-based research service; they are not a certification, an exhaustive HIG audit or a selection of native Apple technologies.

| HIG reference / principle | DocSuri application and web adaptation | Where / verification |
| --- | --- | --- |
| [Layout](https://developer.apple.com/design/human-interface-guidelines/layout): hierarchy, alignment and related groups | Stable navigation rail and context header; readable paper column; assistance is secondary; responsive panels retain the active object and reading order | C01/C03; inspect desktop/phone reflow and return-to-paper context |
| [Typography](https://developer.apple.com/design/human-interface-guidelines/typography): clear text hierarchy and legibility | Korean-capable system sans stack; restrained weights/sizes; wrapping, browser zoom and user text spacing. Native point sizes and Dynamic Type APIs are not CSS requirements | M03/M04/M08; long mixed-language text, 200% text and 320px reflow |
| [Color](https://developer.apple.com/design/human-interface-guidelines/color): consistent meaning and appearance-aware colors | Retain DocSuri blue/neutral identity, use semantic light/dark pairs, give text and essential borders measured variants; labels and shapes supplement color | Palette above; rendered state/focus sampling in both appearances |
| [Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons): selective emphasis, clear action and press feedback | One principal action per task group, consistent button sizing and precise effect labels; secondary actions have lower visual emphasis. Native buttons with focus/pressed/busy feedback; destructive confirmation initially favors Cancel | C02/C05/C07/C11; Send question, Start analysis and Approve and export remain different actions |
| [Progress indicators](https://developer.apple.com/design/human-interface-guidelines/progress-indicators): accurate feedback in a consistent place | Keep status beside the affected task; distinguish saving from saved and connection from job state. Show percentages only when supported by meaningful data; reduced motion preserves a text explanation | C04/C05; no artificial advancement or endless success-looking indicator |
| [Materials](https://developer.apple.com/design/human-interface-guidelines/materials): distinguish functional layers from content | Opaque paper/content surfaces; separation through spacing, tone and restrained overlay depth. No Liquid Glass dependency or decorative glass behind reading text; any later transparency needs a solid fallback | C01/C03/C07; legibility, focused-content visibility and reduced-transparency checks |
| [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility): perception and operability beyond visual styling | Semantic HTML, visible focus, keyboard operation, status announcements and measured contrast under the web WCAG target; CSS target sizes are independent design choices, not native-point conversions | [Accessibility checklist](accessibility-checklist.md); manual assistive-technology and rendered checks |
| [Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode): appearance adaptation | System is the default; preserve explicit Light / Dark / System controls for approved capability parity. This deliberately differs from native guidance discouraging app-specific appearance settings | C08/M11; change OS appearance dynamically, then verify explicit override and blocked preference storage |

No Apple font, icon or design-asset bundle is required: use available system fonts and existing or independently suitable web assets. Browser Back, links, text selection and keyboard conventions remain browser behaviors. Native gestures, chrome and rendering APIs are not introduced by this reference.

## Current-to-proposed component mapping

The reference scope consists of nine exact source paths inspected on 2026-10-11. Graph coverage reported no recorded gap and matching metadata at generation 2026-10-11T02:00:14Z; direct source reads informed the observations. This is not an exhaustive component audit. Package metadata is inventory, not a commitment to retain Next/React/Tailwind or any other library.

| Current source | Observed behavior / concern | Proposed disposition |
| --- | --- | --- |
| [globals.css](../../../../../../../frontend/app/globals.css) | Semantic tokens, Korean font fallbacks, system/explicit dark styles and visible outline | Inherit blue/neutral and warning/danger families; retain semantic tokens; add verified text/boundary variants and consistent type/spacing; verify every component consumes it |
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
