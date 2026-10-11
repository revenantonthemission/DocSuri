# DocSuri v2 — Accessibility Checklist

Date: 2026-10-11 (Asia/Seoul). Target: **WCAG 2.2 Level AA**, as confirmed in the [design summary](refined-mockups-questions.md). This is a design checklist and verification plan, not a conformance claim. All applicable Level A and AA criteria need assessment in the implemented release, including criteria not highlighted in this risk-oriented list.

## Sources and interpretation

Use the [normative WCAG 2.2 recommendation](https://www.w3.org/TR/WCAG22/) for conformance decisions. W3C's [2.2 overview](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) and Understanding pages for [target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) and [accessible authentication](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html) were checked on 2026-10-11. Understanding documents explain criteria; they are not a substitute for the normative standard.

Target-size minimum is 24×24 CSS pixels or an applicable spacing/other exception under 2.5.8. The proposed 44px primary-control height is an additional design preference, not an AA requirement. Authentication must avoid unsupported cognitive barriers; permit password managers and paste, and provide a conforming method/assistance as applicable. Draft security must not be weakened to satisfy convenience.

Apple's [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [Color](https://developer.apple.com/design/human-interface-guidelines/color) and [Materials](https://developer.apple.com/design/human-interface-guidelines/materials) guidance inform the revised visual treatment, checked on 2026-10-11. The [HIG-to-web mapping](design-system-mapping.md#apple-hig-to-web-mapping) records the specific adaptations. Native point sizes, Dynamic Type and Apple rendering APIs do not replace CSS sizing, browser zoom or web accessibility criteria. Preserve DocSuri's explicit Light / Dark / System behavior, with System as the default. No HIG conformance claim is made.

## Design checklist and acceptance evidence

Status “Specified” means covered by design, **not passed by implementation**. “Dependency” means content, policy or implementation evidence is needed before acceptance.

| Area / criteria | Design requirement | Verification procedure / evidence | Status |
| --- | --- | --- | --- |
| Text alternatives — 1.1.1 | Informative paper figures/icons have meaningful alternatives; decoration ignored | Inspect representative figure/caption and icon accessible names; identify missing source descriptions and provide a permitted equivalent before claiming usable figure content | Dependency |
| Structure/order — 1.3.1/1.3.2/1.3.3 | Semantic headings, lists, labels, tables and linear reading order | Screen-reader heading/landmark/table traversal on M03/M04/M07/M08/M15; actions understandable without location/shape alone | Specified |
| Orientation/input purpose — 1.3.4/1.3.5 | No unjustified orientation lock; appropriate autocomplete | Landscape phone and keyboard/password-manager flows on M01/M12; field-purpose inspection | Specified |
| Color/contrast — 1.4.1/1.4.3/1.4.11 | Inherited blue/neutral colors with measured text/control variants; no color-only state; normal text ≥4.5:1, applicable large text ≥3:1, applicable non-text components ≥3:1 | Token ratios plus rendered sampling in both themes across normal, error, partial, focus, selected and overlay states; essential control boundaries use strongBorder, not decorativeBorder | Specified |
| Text resize/reflow/spacing — 1.4.4/1.4.10/1.4.12 | 200% text, 320 CSS-pixel reflow/equivalent 400% zoom; no clipped actions with user spacing | Long Korean/Latin titles, URLs, manuscript text, dialogs, account forms and controlled table/figure scrolling; record viewport/browser/zoom and screenshots | Specified |
| Hover/focus content — 1.4.13 | Additional content dismissible, hoverable and persistent as applicable | Keyboard/pointer tooltip/popover test; no essential hover-only explanation | Specified |
| Keyboard/trap — 2.1.1/2.1.2 | All actions keyboard operable; dialog contains focus and closes safely | Complete V01/V04/V07 without pointer; Shift+Tab at dialog boundary; Escape and logical focus return | Specified |
| Timing/movement — 2.2.1/2.2.2; flashes 2.3.1 | Session timing/recovery explained; pause/avoid unnecessary moving content; no dangerous flashes | Session-expiry recovery and timing-policy assessment; reduced-motion test; no animated progress percentage without data | Dependency |
| Bypass/title/order/purpose — 2.4.1–2.4.7 | Skip link, meaningful page title/headings, logical focus order, useful link names and visible focus | Tab through all screen families; verify source-link purpose and title changes; no positive tabindex | Specified |
| Focus not obscured — 2.4.11 | Focused target not entirely hidden by author-created content | Sticky header, modal actions, menus and phone keyboard checks at zoom; focus scroll position evidence | Specified |
| Pointer/label/motion — 2.5.1–2.5.4 | Simple-pointer alternatives; cancellation; visible label included in name; no motion-only control | Graph/list actions; pointer down then cancel; speech-input name match | Specified |
| Dragging — 2.5.7 | No drag-only citation exploration or attachment management | Equivalent buttons/list actions exercised with keyboard and single pointer | Specified |
| Target size — 2.5.8 | Minimum target or documented exception; 44px main controls preferred | Measure target rectangles/spacing in every responsive layout, including icon actions and dialog close | Specified |
| Language/predictability — 3.1.1/3.1.2; 3.2.1–3.2.4 | Korean reference UI with source-language spans; no unexpected submit/navigation on focus/input | Inspect lang attributes and mixed-language reading; form edits do not automatically trigger external effects | Specified |
| Consistent help — 3.2.6 | Repeated help/recovery mechanisms appear consistently where provided | Compare form/job/account help placement without inventing a staffed support commitment | Specified |
| Errors/instructions — 3.3.1–3.3.3 | Linked field errors, usable recovery controls, constraints before entry | Invalid query/email/term/file and save failure; search input/refinements remain reachable during loading/no-match/failure; error summary links focus invalid fields; messages persist | Specified |
| Error prevention — 3.3.4 | Review/confirmation for destructive or applicable consequential submissions | Account/session deletion, history clear, admin grant/revoke and export current-preview confirmation | Specified |
| Redundant entry — 3.3.7 | Previously entered data reused where permitted; do not repeatedly request known input | Registration/verification/provider-return flows and draft recovery; security exceptions documented when applicable | Specified |
| Accessible authentication — 3.3.8 | Managers/paste allowed; no sole memorization/transcription puzzle | Password and MFA paste/autofill, provider alternative and recovery checks with assistive tech | Specified |
| Name/role/value — 4.1.2 | Native controls or complete semantics for custom widgets | Accessibility-tree inspection of menu, theme controls, save state, tabs, dialogs and expanded sections | Specified |
| Status messages — 4.1.3 | Saving/saved/failed/recovered/conflict helper text agrees with the acknowledged revision; job outcomes announced without focus theft | Screen reader hears key status once; repeated events/keystrokes not noisy; error and empty differentiated; failed latest edit never described as recoverable after restart | Specified |

## Component and journey test matrix

| Scope | Representative checks |
| --- | --- |
| C01/C02 navigation/search | Skip link, responsive menu, query label, filters, mode/fallback announcement, results vs no-match vs failure; retained form/refinements and usable edit/clear/retry controls in every search state; return-from-paper context |
| C03 reader/citations | Section/figure/source anchors, version identity, unavailable content, accessible citation list, readable math/figure alternatives |
| C04 job/result | Connection vs job state, terminal announcement once, pending/expired/unauthorized, result read without new work |
| C05 drafts | Long input, matching status/helper for saving/failure/recovery/conflict, known acknowledgement time only, same-owner sign-in, private text removed after access loss, explicit revision choice and discard |
| C06/C07 lists/dialogs | Toggle pending vs committed state, removal focus, trap/Escape/return, history/session/account deletion scope |
| C08 account/settings | Registration/email/reset/provider/MFA, manager/paste, validation summary, consent and glossary conflicts |
| C09 evidence | Source distinctions/quotes/partial or abstained result, attachment validation, artifacts accessible only to owner; M09 visible and accessible “분석 시작” label identifies analysis |
| C10/C11 usage/export | Unknown vs zero, current preview/destination, explicit approval, ambiguous outcome without duplicate publication |
| O01/O02 operational interfaces | Text equivalent of status/authority/freshness; readable existing output; no ANSI-only information or fabricated web parity |

Proposed implementation test matrix: current stable Chromium and Firefox desktop plus Safari/WebKit; keyboard-only; macOS VoiceOver with Safari and Windows NVDA with Firefox/Chromium where an available free test environment permits; iOS VoiceOver and Android TalkBack on available devices. This is a proposed coverage set, not a verified list of owned hardware or a purchase request. Confirm the supported-browser policy and available devices before acceptance; record missing coverage instead of claiming it passed.

Exercise at least 1440×1000, 1024×768, 768×1024, 390×844 and 320×800 CSS-pixel viewports, both appearances, portrait/landscape where applicable, 200% text and 400% zoom, text-spacing overrides and reduced motion. These are verification conditions, not service-quality targets. Automation catches only part of the criteria; manual keyboard, screen-reader and content review remain required.

Also assess increased-contrast/forced-colors settings available in the supported browser and OS matrix. Preserve system-controlled colors where appropriate; no background image, blur or shadow may be the only boundary or state cue. Reading surfaces are opaque in this design; any later translucent functional layer needs a solid reduced-transparency fallback and fresh contrast checks. Verify that zoomed content, disclosure changes and theme changes preserve logical focus and the selected paper/session. These are planned checks until the verification record reports their actual results.

## Evidence status and limitations

- Inherited palette and accessible variant contrast was calculated; see [mapping](design-system-mapping.md). It supports specific opaque color pairs only. Light muted text (4.55:1 on surface) and filled blue button text (4.53:1) need careful rendered checks and must not be faded in enabled states; the blue text variant replaces ordinary accent text on the light surface.
- The [prototype](prototype/index.html) provides inspectable layouts and simulated state selection. The [verification record](design-verification.md) records the actual bounded checks performed.
- No implemented service accessibility audit, screen-reader acceptance, real-user usability validation or certification has occurred in this stage.
- Source figure/math semantics, timing/retention policy, actual provider/MFA behavior, supported-language matrix and every retained option remain downstream dependencies. A screenshot or green automated scan cannot close them.
