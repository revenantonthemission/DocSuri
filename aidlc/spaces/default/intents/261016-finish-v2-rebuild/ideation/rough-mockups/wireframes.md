# Wireframes — Finish the DocSuri v2 rebuild (new screens only)

Date: 2026-10-16 (Asia/Seoul)
Isolated run. Sources: [rough-mockups-questions.md](rough-mockups-questions.md), [scope document](../scope-definition/scope-document.md), [intent backlog](../scope-definition/intent-backlog.md).
Scope: only the screens the remaining units add; all existing screens continue their built design. Low fidelity — structure and hierarchy, not visuals.

## W1 — Topics & digests management (U5)

```
+----------------------------------------------+
| DocSuri        [search] [library] [topics]   |
+----------------------------------------------+
| topics                                        |
|  followed topics                              |
|  +------------------------------------------+|
|  | topic row: name, last digest date,       ||
|  |   [digest settings] [unsubscribe]        ||
|  | topic row: ...                           ||
|  +------------------------------------------+|
|  [ follow new topic ]                         |
|  empty state: no topics yet -> follow prompt  |
+----------------------------------------------+
```

<!-- Text fallback: top navigation bar; main region lists followed topics, each row offering digest settings and unsubscribe; a follow-new-topic action below; an empty state explains and prompts the first follow. -->

Accessibility: content in an `h2` under the page `h1`; `main` landmark holds the list; each row action keyboard-reachable with visible focus; digest status changes announced via a polite live region.

## W2 — Digest settings (U5, per topic)

```
+----------------------------------------------+
| topic: <name>                                 |
|  delivery cadence   [ select: daily / weekly ]|
|  delivery time      [ time in my timezone ]   |
|  content window     [ select: 7 / 30 days ]   |
|  language / level   [ inherited preference ]  |
|  [ save ]  [ unsubscribe topic ]              |
+----------------------------------------------+
```

<!-- Text fallback: a small settings form bound to one topic: cadence, delivery time, content window, language/level inherited from preferences; save and unsubscribe actions. -->

Accessibility: labelled fields (`label` bound to each input), inline validation on blur, destructive unsubscribe confirmed with a dialog that names the affected topic; focus returns to the trigger on close.

## W3 — Export preview & approval (U6)

```
+----------------------------------------------+
| export                                        |
|  prepared artifact                            |
|  +------------------------------------------+|
|  | artifact: <title>, revision, evidence    ||
|  +------------------------------------------+|
|  destination   [ notion workspace / page ]    |
|  preview       [ read-only rendered preview ] |
|  [ approve and export ]                       |
|  status: preparing / sent / unknown - settle  |
+----------------------------------------------+
```

<!-- Text fallback: the exact prepared artifact with its revision, a destination picker bound to the owner's Notion configuration, a read-only preview, one approve-and-export action, and an outcome status line that distinguishes sent from unknown-until-reconciled. -->

Accessibility: `h2` sections (artifact, destination, preview, action); the approval button is the only trigger of an export — reading and previewing never export; status announced via a polite live region; approval requires explicit activation (no auto-submission).

## W4 — Assembled navigation (U8)

```
+----------------------------------------------+
| DocSuri   [search] [library] [topics]         |
|           [research] [export] [settings]      |
+----------------------------------------------+
| one workspace: every view reachable,          |
| consistent placement, current view highlighted|
+----------------------------------------------+
```

<!-- Text fallback: the shared navigation gains topics and export entries alongside the built sections, with consistent placement, highlight of the current view, and responsive collapse at smaller widths. -->

Accessibility: persistent `nav` landmark, current view indicated with an accessible state (not color alone), keyboard entry from the first skip-to-content link.

## Screen states

Each new screen carries the built application's five-state discipline: empty (guidance + first action), loading (in-context skeleton), populated, error (plain-language, actionable, never color-only), partial (long topic lists paginate; a topic with no eligible content says so). [Q3] [Q4] [Q5]
