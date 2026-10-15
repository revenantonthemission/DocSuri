# U3 paper and corpus capabilities — frontend components

The U3 contributions extend the existing Korean responsive workspace (shared shell, inherited blue/neutral colors, Apple HIG web adaptations, Light/Dark/System, WCAG 2.2 AA target) rather than introducing new visual languages. This file defines the public-paper component hierarchy, props/state behaviour, interaction flows, validation and API integration points; the [interaction specification](../../../inception/refined-mockups/interaction-spec.md) components C02–C04 remain the UX reference. Behaviour is defined by [functional-spec.md](functional-spec.md) and [rules.md](rules.md).

## Component hierarchy

```text
WebWorkspace (existing shell)
  +-- QueryWorkspace
  |     +-- QueryBar (input, mode selector, submit, rerun)
  |     +-- FilterPanel (filters, ordering, active-filter summary)
  |     +-- ResultList
  |     |     +-- ResultRow (metadata, availability badge, open action)
  |     |     +-- SnapshotNotice (freshness/degradation/expired boundary)
  |     +-- SearchStatusLine (distinct loading/empty/error/partial states)
  +-- PaperWorkspace
  |     +-- PaperIdentityHeader (title, authors, venue, version label, source links)
  |     +-- ReadingSurface
  |     |     +-- SectionNavigator (anchors)
  |     |     +-- SectionView (text)
  |     |     +-- FigureView (opaque asset handle -> authorized delivery)
  |     |     +-- ContentStatePanel (absent/building/unsupported/failed/withdrawn/restricted)
  |     +-- CitationExplorer (cited/citing lists, depth control, freshness/coverage labels, save)
  |     +-- AssistancePanel
  |     |     +-- OptionPicker (action, language, presentation level)
  |     |     +-- AcceptAction
  |     |     +-- ActivityCard (ordered progress, reconnect/poll fallback)
  |     |     +-- PreparedResultPanel (content, coverage, provenance, expired state)
  |     +-- GlossaryEditor (terms, validation, conflict resolution)
```

## Shared state contracts

- **Authority generation.** Every U3 view keys cached and in-flight data to the transport's authority generation; account switch, logout and expiry clear private state and late responses for a previous generation are discarded (not rendered).
- **Job identity.** One accepted assistance job per panel instance; the ActivityCard and PreparedResultPanel read the same job identity; navigation away never starts or restarts work.
- **Context preservation.** Query text, filters, ordering, the open paper/version and the last acknowledged result survive errors, reconnect and sign-in changes; a safe return restores the view without queuing mutations.
- **Announcements.** Each state change is announced through one ARIA live region per surface; focus moves to the state panel heading on error and back to the invoking control on recovery.

## QueryWorkspace

- **Purpose.** FR1 search/refinement surface over the published generation.
- **Props/state.** `queryText`, `mode` (`lexical|semantic|auto`), `filters`, `ordering`, `activeFilters`, `resultsPage`, `snapshotId`, `degradation` (`none|semantic-unavailable|partial|provider-limited`), `state` (`idle|loading|results|empty|error|invalid`), `rerunContext`.
- **Interactions.** Submit runs W4; refinement preserves the query and updates the snapshot; pagination requests the next page for the same snapshot; rerun re-executes the recorded context; opening a row routes to PaperWorkspace with stable paper/version identity.
- **Validation.** Client mirrors server bounds (empty/whitespace/oversized) but the server outcome is authoritative; invalid input renders inline guidance without clearing prior results.
- **API integration.** C05 `search`; guest requests carry no owner identity and show no history affordances; authenticated requests may record history facts through the service, never from the client.
- **States.** Loading skeleton with progress affordance; empty result distinct from error; degradation notice names the fallback; expired snapshot offers explicit rerun; `data-testid` hooks for E2E (`search-query`, `search-mode`, `search-submit`, `search-results`, `snapshot-notice`, `search-status`).

## ResultList / ResultRow

- **Purpose.** Stable, snapshot-bound result presentation.
- **Props/state.** `page`, `snapshotId`, `items[]{paperId, paperVersionId, title, authors, venue, year, availabilityDisposition}`, `focusIndex`.
- **Interactions.** Keyboard traversal; open resolves the exact version via C04 `resolvePaper`; availability badge explains source-only/restricted entries before opening.
- **Validation.** No synthetic rows; absent metadata fields render as absent, never placeholder text.
- **States.** `data-testid` `result-row`, `result-availability`.

## PaperWorkspace

- **PaperIdentityHeader.** `props: {paper, version, sourceLinks}`; shows version label exactly as recorded; source-only badge when no readable content exists; anchor links open in the shell's safe external-link pattern.
- **ReadingSurface.** Reads C04 `readContent` for the exact version; renders sections with anchors, figures via C04 `readAsset` handles only (no raw URLs); navigation preserves scroll/focus per section; back-navigation re-resolves the same version.
- **ContentStatePanel.** Renders each disposition with distinct copy and recovery: absent (offer search again), building (progress + retry affordance, no infinite spinner), unsupported/failed (bounded error with request ID), withdrawn/restricted (authorized metadata/source links only). Never invents text.
- **testids.** `paper-identity`, `reading-surface`, `section-anchor`, `figure-view`, `content-state`.

## CitationExplorer

- **Purpose.** FR9 cited/citing exploration.
- **Props/state.** `rootVersion`, `direction (cited|citing)`, `depth`, `nodes`, `edges`, `freshness`, `coverage`, `state (loading|ready|partial|unavailable|error)`.
- **Interactions.** Expand/collapse within resolved bounds; depth control bounded by policy; save action calls the Library operation for eligible nodes (never through Discovery); ineligible nodes show the limitation.
- **States.** Fresh/stale/unknown and complete/partial/unavailable labels on the result; provider failure keeps previously explored nodes and any saved references.
- **testids.** `citation-explorer`, `citation-node`, `citation-save`, `citation-freshness`.

## AssistancePanel

- **OptionPicker.** Reads C06 `readAssistanceOptions`; renders only reconciled options with vocabulary revision; unavailable options are absent or explicitly marked (no parity implication from an empty list).
- **AcceptAction.** Submits C06 `acceptAssistance` with the exact paper/version, content hash, option ids and glossary revision; generates a client operation key once per intended submission (retry after loss reuses it); disabled states carry the reason (ineligible source, unresolved policy, capacity).
- **ActivityCard.** Reads C06 `readAssistanceJob` plus ordered progress through the browser transport (C13/C14 contract); renders ordered steps from owner-assigned sequence; reconnect uses the last known event id and falls back to polling with the same snapshot; stale/out-of-order events never regress the display; terminal failure shows the safe error and retry affordance.
- **PreparedResultPanel.** Reads C06 `readPreparedAssistance`; renders content, coverage and provenance; partial coverage is disclosed; expired results show the expired state and explain that requesting again is an explicit new action; refresh/revisit returns the same retained result.
- **States.** `data-testid` `assistance-options`, `start-summary`, `start-translation`, `activity-card`, `job-progress`, `prepared-result`, `result-expired`, `assistance-unavailable`.

## GlossaryEditor

- **Purpose.** FR4 owner terminology.
- **Props/state.** `terms[]`, `revision`, `state (idle|loading|ready|saving|conflict|invalid|error)`, `constraintViolations`.
- **Interactions.** Add/edit/remove terms; save sends expected revision (absent glossary uses the virtual initial revision token); on conflict, both versions are shown and the owner chooses how to converge; failed writes keep the previous committed terms visible.
- **Validation.** Inline per-term feedback for empty/duplicate/oversized input; Unicode handled per normalization rules; server outcome authoritative.
- **API integration.** C06 `readGlossary`, `replaceGlossary`.
- **testids.** `glossary-editor`, `glossary-term`, `glossary-save`, `glossary-conflict`.

## Cross-cutting accessibility and Korean copy

- All interactive elements carry `data-testid` attributes for automation plus meaningful Korean labels; icon-only controls have accessible names.
- Status, progress and conflict updates use polite/assertive live regions per tone; focus order follows the visual reading order; compact/reflow layouts preserve the approved responsive breakpoints.
- Reduced-motion preference suppresses non-essential transitions; long Korean text wraps without clipping in result rows and section views.
- Error copy carries the request id where available and never exposes internal identifiers or secrets.
